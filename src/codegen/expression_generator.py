"""
Генератор кода для сложных выражений x86-64 (Sprint 6).

Миксин для X86Generator: поддерживает генерацию ассемблера
для сложных выражений с учётом порядка вычислений и приоритетов.

Сложность Sprint 6:
  - Расширенная арифметика (уже была в Sprint 5)
  - Составные выражения: (a + b) * (c - d) / (e % f)
  - Повышение типов: int + float → float (базовая поддержка)
  - Промежуточные вычисления через стек (stack spilling)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.ir.ir_instructions import IRInstruction, IROpcode, IROperand, LiteralOperand

if TYPE_CHECKING:
    from .x86_generator import X86Generator


class ExpressionGeneratorMixin:
    """
    Миксин для X86Generator.

    Расширяет базовую генерацию арифметических выражений поддержкой
    сложных составных выражений и улучшенным управлением регистрами.
    """

    def _gen_binary_expr(
        self: "X86Generator",
        instr: IRInstruction,
        mnemonic: str,
    ) -> None:
        """
        Генерация бинарной арифметики: dest = src1 OP src2.

        Использует rax (левый) и rcx (правый) как вычислительные регистры.
        Результат помещается в rax и сохраняется в стековый слот dest.
        """
        self._load_to_reg(instr.src1, "rax")
        self._load_to_reg(instr.src2, "rcx")
        self._emit(f"    {mnemonic} rax, rcx")
        self._store_from_reg("rax", instr.dest)

    def _gen_mul_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """Знаковое умножение: dest = src1 * src2 (imul)."""
        self._load_to_reg(instr.src1, "rax")
        self._load_to_reg(instr.src2, "rcx")
        self._emit("    imul rax, rcx")
        self._store_from_reg("rax", instr.dest)

    def _gen_divmod_expr(
        self: "X86Generator",
        instr: IRInstruction,
        remainder: bool,
    ) -> None:
        """
        Знаковое деление (idiv): rax = частное, rdx = остаток.

        Перед idiv обязателен cqo (расширение знака rax → rdx:rax).
        Параметр remainder=True возвращает остаток (MOD).
        """
        self._load_to_reg(instr.src1, "rax")
        self._load_to_reg(instr.src2, "rcx")
        self._emit("    cqo")       # расширение знака rax → rdx:rax
        self._emit("    idiv rcx")  # rax = частное, rdx = остаток
        result_reg = "rdx" if remainder else "rax"
        self._store_from_reg(result_reg, instr.dest)

    def _gen_neg_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """Арифметическое отрицание: dest = -src."""
        self._load_to_reg(instr.src1, "rax")
        self._emit("    neg rax")
        self._store_from_reg("rax", instr.dest)

    def _gen_not_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """
        Логическое отрицание: dest = (src == 0) ? 1 : 0.

        Реализовано через test + setz + movzx (без ветвления).
        """
        self._load_to_reg(instr.src1, "rax")
        self._emit("    test rax, rax")
        self._emit("    setz al")
        self._emit("    movzx rax, al")
        self._store_from_reg("rax", instr.dest)

    def _gen_and_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """
        Побитовое И для булевых значений: оба ненулевых → 1.

        Примечание: это НЕ короткое замыкание — оба операнда
        уже вычислены IR-генератором. Короткая схема реализована
        в IR-генераторе через блоки JUMP_IF_NOT.
        """
        self._load_to_reg(instr.src1, "rax")
        self._emit("    test rax, rax")
        self._emit("    setnz al")
        self._emit("    movzx rax, al")
        self._load_to_reg(instr.src2, "rcx")
        self._emit("    test rcx, rcx")
        self._emit("    setnz cl")
        self._emit("    movzx rcx, cl")
        self._emit("    and rax, rcx")
        self._store_from_reg("rax", instr.dest)

    def _gen_or_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """
        Побитовое ИЛИ для булевых значений: хотя бы один ненулевой → 1.

        Аналогично AND — короткая схема обрабатывается в IR.
        """
        self._load_to_reg(instr.src1, "rax")
        self._emit("    test rax, rax")
        self._emit("    setnz al")
        self._emit("    movzx rax, al")
        self._load_to_reg(instr.src2, "rcx")
        self._emit("    test rcx, rcx")
        self._emit("    setnz cl")
        self._emit("    movzx rcx, cl")
        self._emit("    or rax, rcx")
        self._store_from_reg("rax", instr.dest)

    def _gen_xor_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """Побитовое исключающее ИЛИ."""
        self._load_to_reg(instr.src1, "rax")
        self._load_to_reg(instr.src2, "rcx")
        self._emit("    xor rax, rcx")
        self._store_from_reg("rax", instr.dest)

    def _gen_cmp_expr(self: "X86Generator", instr: IRInstruction) -> None:
        """
        Операция сравнения → результат 0 или 1 в dest.

        Генерирует: cmp rax, rcx → set<cc> al → movzx rax, al.
        """
        _SET_MNEMONICS = {
            IROpcode.CMP_EQ: "sete",
            IROpcode.CMP_NE: "setne",
            IROpcode.CMP_LT: "setl",
            IROpcode.CMP_LE: "setle",
            IROpcode.CMP_GT: "setg",
            IROpcode.CMP_GE: "setge",
        }
        self._load_to_reg(instr.src1, "rax")
        self._load_to_reg(instr.src2, "rcx")
        self._emit("    cmp rax, rcx")
        set_mnemonic = _SET_MNEMONICS[instr.opcode]
        self._emit(f"    {set_mnemonic} al")
        self._emit("    movzx rax, al")
        self._store_from_reg("rax", instr.dest)
