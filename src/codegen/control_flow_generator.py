"""
Генератор управляющих конструкций x86-64 (Sprint 6).

Миксин для X86Generator: предоставляет методы генерации ассемблера
для ветвлений (if/else) и циклов (while/for) по инструкциям IR.

Принцип работы:
  - Методы этого класса вызываются из X86Generator._gen_instr
    при встрече инструкций условного/безусловного перехода.
  - Генерирует сравнения (cmp + set*/j*) и метки блоков.
  - Поддерживает вложенные конструкции благодаря LabelManager.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.ir.ir_instructions import IRInstruction, IROpcode, IROperand

if TYPE_CHECKING:
    # Импорт для аннотаций, чтобы избежать циклической зависимости
    from .x86_generator import X86Generator


# Таблица: IR-опкод сравнения → инструкция условного перехода (прямой/инвертированный)
_CMP_TO_JCC = {
    IROpcode.CMP_EQ: ("je",  "jne"),
    IROpcode.CMP_NE: ("jne", "je"),
    IROpcode.CMP_LT: ("jl",  "jge"),
    IROpcode.CMP_LE: ("jle", "jg"),
    IROpcode.CMP_GT: ("jg",  "jle"),
    IROpcode.CMP_GE: ("jge", "jl"),
}


class ControlFlowGeneratorMixin:
    """
    Миксин для X86Generator.

    Методы работают через self._emit, self._load_to_reg,
    self._label_ref — все предоставляются X86Generator.
    """

    def _gen_jump(self: "X86Generator", instr: IRInstruction) -> None:
        """JUMP label — безусловный переход."""
        label = self._label_ref(str(instr.src1))
        self._emit(f"    jmp {label}")

    def _gen_jump_cond(self: "X86Generator", instr: IRInstruction, negate: bool) -> None:
        """
        JUMP_IF cond, label   — переход если cond != 0.
        JUMP_IF_NOT cond, label — переход если cond == 0.
        """
        self._load_to_reg(instr.src1, "rax")
        self._emit("    test rax, rax")
        label = self._label_ref(str(instr.src2))
        # JUMP_IF → jnz; JUMP_IF_NOT → jz
        mnemonic = "jz" if negate else "jnz"
        self._emit(f"    {mnemonic} {label}")

    def _gen_cmp_jump(
        self: "X86Generator",
        cmp_instr: IRInstruction,
        target_label: str,
        negate: bool = False,
    ) -> None:
        """
        Генерирует оптимальный условный переход для сравнения.

        Используется когда CMP_* непосредственно управляет ветвлением
        (без промежуточного сохранения в 0/1). Генерирует:
            cmp rax, rcx
            j<cc> target

        Параметр negate инвертирует условие (для JUMP_IF_NOT).
        """
        if cmp_instr.opcode not in _CMP_TO_JCC:
            return

        self._load_to_reg(cmp_instr.src1, "rax")
        self._load_to_reg(cmp_instr.src2, "rcx")
        self._emit("    cmp rax, rcx")

        jcc_true, jcc_false = _CMP_TO_JCC[cmp_instr.opcode]
        chosen = jcc_false if negate else jcc_true
        label_ref = self._label_ref(target_label)
        self._emit(f"    {chosen} {label_ref}")

    def _emit_block_label(self: "X86Generator", label: str) -> None:
        """Вывести метку базового блока (с точкой для локальной области)."""
        if label != "entry":
            self._emit(f".{label}:")
