"""
Генератор x86-64 ассемблера для MiniCompiler (Sprint 6).

Транслирует IR-программу в ассемблерный код формата NASM,
следуя соглашению о вызовах System V AMD64 ABI.

Архитектура:
  - X86Generator.generate(ir_program) → строка NASM-кода
  - Для каждой функции: RegisterAllocator строит StackFrame,
    затем _gen_function обходит блоки и инструкции.
  - Все временные и переменные хранятся на стеке.
  - Scratch-регистры rax/rcx/rdx используются для вычислений.
  - Аргументы передаются в rdi, rsi, rdx, rcx, r8, r9 (System V ABI).
  - Возврат значения — в rax.

Новое в Sprint 6:
  - Используются миксины ControlFlowGeneratorMixin и ExpressionGeneratorMixin.
  - LabelManager отвечает за генерацию уникальных меток.
  - Управляющие конструкции (if/else, while, for) корректно транслируются
    в условные переходы x86-64 (jnz, jz, jmp + метки).
  - Короткое замыкание && и || реализовано на уровне IR (ir_generator.py).
"""

from __future__ import annotations

from typing import List, Dict, Optional

from src.ir.control_flow import IRProgram, IRFunction
from src.ir.basic_block import BasicBlock
from src.ir.ir_instructions import (
    IRInstruction, IROpcode, IROperand,
    TempOperand, VarOperand, LiteralOperand, LabelOperand,
)
from .stack_frame import StackFrame
from .register_allocator import RegisterAllocator
from .label_manager import LabelManager
from .control_flow_generator import ControlFlowGeneratorMixin
from .expression_generator import ExpressionGeneratorMixin
from . import abi


class X86Generator(ControlFlowGeneratorMixin, ExpressionGeneratorMixin):
    """
    Генератор x86-64 ассемблера (NASM синтаксис).

    Принцип работы:
      1. Для каждой функции RegisterAllocator строит StackFrame.
      2. Генерируется пролог: push rbp / mov rbp, rsp / sub rsp, N.
      3. Параметры сохраняются из регистров ABI в стековые слоты.
      4. Обходятся базовые блоки; каждая IR-инструкция → NASM-инструкции.
      5. RETURN генерирует эпилог: mov rsp, rbp / pop rbp / ret.
    """

    def __init__(self) -> None:
        self._lines: List[str] = []
        self._frame: Optional[StackFrame] = None
        self._func: Optional[IRFunction] = None
        # Строковые литералы: значение → метка в .rodata
        self._string_literals: Dict[str, str] = {}
        self._str_counter: int = 0
        # Менеджер меток (Sprint 6): уникальные имена для управляющих конструкций
        self._labels: LabelManager = LabelManager()

    # ----------------------------------------------------------------
    # Публичный интерфейс
    # ----------------------------------------------------------------

    def generate(self, ir_program: IRProgram) -> str:
        """
        Сгенерировать полный NASM-файл для IR-программы.

        :param ir_program: IR всей программы
        :return: строка с ассемблерным кодом
        """
        self._lines = []
        self._string_literals = {}
        self._str_counter = 0

        self._emit("; Сгенерировано MiniCompiler (Sprint 6)")
        self._emit("; Цель: x86-64 Linux, синтаксис: NASM")
        self._emit("; Соглашение: System V AMD64 ABI")
        self._emit("")
        self._emit("section .text")
        self._emit("")

        # Объявляем все функции как глобальные символы
        for func in ir_program.functions:
            self._emit(f"global {func.name}")
        self._emit("")

        # Генерируем код для каждой функции
        for func in ir_program.functions:
            self._gen_function(func)

        # Строковые литералы в секции .rodata
        if self._string_literals:
            self._emit("")
            self._emit("section .rodata")
            for value, label in self._string_literals.items():
                encoded = self._encode_string(value)
                self._emit(f"{label}: db {encoded}, 0")

        return "\n".join(self._lines)

    # ----------------------------------------------------------------
    # Генерация функции
    # ----------------------------------------------------------------

    def _gen_function(self, func: IRFunction) -> None:
        self._func = func

        # Распределяем стековые слоты
        allocator = RegisterAllocator()
        self._frame = allocator.allocate(func)
        stack_size = self._frame.aligned_size

        # Пролог функции
        self._emit(f"; === Функция: {func.name} -> {func.return_type} ===")
        self._emit(f"{func.name}:")
        self._emit(f"    push rbp")
        self._emit(f"    mov rbp, rsp")
        if stack_size > 0:
            self._emit(
                f"    sub rsp, {stack_size}"
                f"          ; стековый фрейм: {self._frame.total_slots} слотов"
            )

        # Сохраняем параметры из регистров ABI в стек
        self._gen_param_stores(func)

        # Генерируем тело функции (блок за блоком)
        for block in func.cfg.blocks:
            self._gen_block(block)

        self._emit("")

    def _gen_param_stores(self, func: IRFunction) -> None:
        """Сохранить аргументы функции из регистров ABI в стековые слоты."""
        for i, (param_name, param_type) in enumerate(func.params):
            if i >= abi.MAX_INT_ARGS_IN_REGS:
                # Аргументы, переданные на стеке, не реализованы в этом спринте
                self._emit(
                    f"    ; TODO: параметр '{param_name}' передан на стеке "
                    f"(индекс {i} >= {abi.MAX_INT_ARGS_IN_REGS})"
                )
                continue
            reg = abi.INT_ARG_REGS[i]
            key = f"{param_name}_0"
            offset = self._frame.get_offset(key)
            if offset is not None:
                self._emit(
                    f"    mov qword [rbp{offset:+d}], {reg}"
                    f"     ; параметр {param_type} {param_name}"
                )

    # ----------------------------------------------------------------
    # Генерация базового блока
    # ----------------------------------------------------------------

    def _gen_block(self, block: BasicBlock) -> None:
        # entry-блок не получает отдельной метки — он идёт сразу после имени функции
        if block.label != "entry":
            self._emit(f".{block.label}:")

        for instr in block.instructions:
            self._gen_instr(instr)

    # ----------------------------------------------------------------
    # Диспетчер инструкций
    # ----------------------------------------------------------------

    def _gen_instr(self, instr: IRInstruction) -> None:
        # Комментарий: IR-инструкция для читаемости
        self._emit(f"    ; {instr.format().strip()}")

        op = instr.opcode

        if op == IROpcode.ALLOCA:
            pass  # слот выделен в pre-pass, код не нужен

        elif op == IROpcode.PARAM:
            pass  # обрабатывается в _gen_param_stores / _gen_call

        elif op == IROpcode.MOVE:
            self._gen_move(instr)

        elif op == IROpcode.LOAD:
            self._gen_load(instr)

        elif op == IROpcode.STORE:
            self._gen_store(instr)

        elif op == IROpcode.ADD:
            self._gen_binary(instr, "add")

        elif op == IROpcode.SUB:
            self._gen_binary(instr, "sub")

        elif op == IROpcode.MUL:
            self._gen_mul(instr)

        elif op == IROpcode.DIV:
            self._gen_divmod(instr, remainder=False)

        elif op == IROpcode.MOD:
            self._gen_divmod(instr, remainder=True)

        elif op == IROpcode.NEG:
            self._gen_neg(instr)

        elif op == IROpcode.NOT:
            self._gen_not(instr)

        elif op == IROpcode.AND:
            self._gen_logical_and(instr)

        elif op == IROpcode.OR:
            self._gen_logical_or(instr)

        elif op == IROpcode.XOR:
            self._gen_xor(instr)

        elif op in (
            IROpcode.CMP_EQ, IROpcode.CMP_NE,
            IROpcode.CMP_LT, IROpcode.CMP_LE,
            IROpcode.CMP_GT, IROpcode.CMP_GE,
        ):
            self._gen_cmp(instr)

        elif op == IROpcode.JUMP:
            self._gen_jump(instr)

        elif op == IROpcode.JUMP_IF:
            self._gen_jump_cond(instr, negate=False)

        elif op == IROpcode.JUMP_IF_NOT:
            self._gen_jump_cond(instr, negate=True)

        elif op == IROpcode.CALL:
            self._gen_call(instr)

        elif op == IROpcode.RETURN:
            self._gen_return(instr)

        else:
            self._emit(f"    ; [не реализовано: {op.value}]")

    # ----------------------------------------------------------------
    # Конкретные генераторы для каждой IR-инструкции
    # ----------------------------------------------------------------

    def _gen_move(self, instr: IRInstruction) -> None:
        """MOVE dest, src — копирование значения."""
        self._load_to_reg(instr.src1, "rax")
        self._store_from_reg("rax", instr.dest)

    def _gen_load(self, instr: IRInstruction) -> None:
        """LOAD dest, [var] — загрузить значение переменной в временную."""
        self._load_to_reg(instr.src1, "rax")
        self._store_from_reg("rax", instr.dest)

    def _gen_store(self, instr: IRInstruction) -> None:
        """STORE [var], src — сохранить значение в переменную."""
        self._load_to_reg(instr.src1, "rax")
        self._store_from_reg("rax", instr.dest)

    def _gen_binary(self, instr: IRInstruction, mnemonic: str) -> None:
        """ADD / SUB: dest = src1 OP src2. Делегирует к ExpressionGeneratorMixin."""
        self._gen_binary_expr(instr, mnemonic)

    def _gen_mul(self, instr: IRInstruction) -> None:
        """MUL: знаковое умножение. Делегирует к ExpressionGeneratorMixin."""
        self._gen_mul_expr(instr)

    def _gen_divmod(self, instr: IRInstruction, remainder: bool) -> None:
        """DIV / MOD через idiv. Делегирует к ExpressionGeneratorMixin."""
        self._gen_divmod_expr(instr, remainder)

    def _gen_neg(self, instr: IRInstruction) -> None:
        """NEG: арифметическое отрицание. Делегирует к ExpressionGeneratorMixin."""
        self._gen_neg_expr(instr)

    def _gen_not(self, instr: IRInstruction) -> None:
        """NOT: логическое отрицание. Делегирует к ExpressionGeneratorMixin."""
        self._gen_not_expr(instr)

    def _gen_logical_and(self, instr: IRInstruction) -> None:
        """AND: побитовое И для булевых (без КЗ). Делегирует к ExpressionGeneratorMixin."""
        self._gen_and_expr(instr)

    def _gen_logical_or(self, instr: IRInstruction) -> None:
        """OR: побитовое ИЛИ для булевых (без КЗ). Делегирует к ExpressionGeneratorMixin."""
        self._gen_or_expr(instr)

    def _gen_xor(self, instr: IRInstruction) -> None:
        """XOR: побитовое исключающее ИЛИ. Делегирует к ExpressionGeneratorMixin."""
        self._gen_xor_expr(instr)

    def _gen_cmp(self, instr: IRInstruction) -> None:
        """CMP_*: сравнение → 0 или 1. Делегирует к ExpressionGeneratorMixin."""
        self._gen_cmp_expr(instr)

    def _gen_call(self, instr: IRInstruction) -> None:
        """CALL dest, func, args — вызов функции по ABI."""
        # Загрузить аргументы в регистры ABI (rdi, rsi, rdx, rcx, r8, r9)
        for i, arg in enumerate(instr.args):
            if i < abi.MAX_INT_ARGS_IN_REGS:
                reg = abi.INT_ARG_REGS[i]
                self._load_to_reg(arg, reg)
            else:
                # TODO: аргументы на стеке (Sprint 6+)
                self._emit(f"    ; TODO: аргумент {i} → стек")

        func_name = str(instr.src1)
        self._emit(f"    call {func_name}")

        # Результат в rax → сохранить в dest
        if instr.dest is not None:
            self._store_from_reg("rax", instr.dest)

    def _gen_return(self, instr: IRInstruction) -> None:
        """RETURN [value] — возврат из функции с эпилогом."""
        if instr.src1 is not None:
            self._load_to_reg(instr.src1, "rax")
        else:
            # void return: rax = 0
            self._emit("    xor eax, eax")

        # Эпилог: восстановить стек и вернуться
        self._emit("    mov rsp, rbp")
        self._emit("    pop rbp")
        self._emit("    ret")

    # ----------------------------------------------------------------
    # Вспомогательные методы
    # ----------------------------------------------------------------

    def _load_to_reg(self, op: IROperand, reg: str) -> None:
        """Загрузить операнд в указанный регистр."""
        if isinstance(op, LiteralOperand):
            self._emit_load_literal(op, reg)
        elif isinstance(op, (VarOperand, TempOperand)):
            key = self._operand_key(op)
            offset = self._frame.get_offset(key)
            if offset is not None:
                self._emit(f"    mov {reg}, qword [rbp{offset:+d}]")
            else:
                # Операнд не выделен: обнуляем и предупреждаем
                self._emit(f"    xor {reg}, {reg}  ; предупреждение: слот не найден для {op}")
        elif isinstance(op, LabelOperand):
            # Метки не загружаются в регистры — ошибка использования
            self._emit(f"    ; предупреждение: попытка загрузить метку {op} в регистр")
        else:
            self._emit(f"    xor {reg}, {reg}  ; неизвестный тип операнда")

    def _emit_load_literal(self, op: LiteralOperand, reg: str) -> None:
        """Загрузить литерал в регистр."""
        value = op.value
        if isinstance(value, bool):
            # bool проверяем до int (bool — подкласс int в Python)
            self._emit(f"    mov {reg}, {1 if value else 0}")
        elif isinstance(value, int):
            self._emit(f"    mov {reg}, {value}")
        elif isinstance(value, float):
            # Упрощённо: floor до int; полная поддержка float — в будущих спринтах
            self._emit(f"    mov {reg}, {int(value)}  ; float→int (упрощённо)")
        elif isinstance(value, str):
            label = self._get_string_label(value)
            self._emit(f"    lea {reg}, [rel {label}]")
        else:
            self._emit(f"    mov {reg}, 0  ; неизвестный литерал: {value!r}")

    def _store_from_reg(self, reg: str, dest: Optional[IROperand]) -> None:
        """Сохранить значение из регистра в стековый слот операнда-приёмника."""
        if dest is None:
            return
        key = self._operand_key(dest)
        offset = self._frame.get_offset(key)
        if offset is not None:
            self._emit(f"    mov qword [rbp{offset:+d}], {reg}")

    def _operand_key(self, op: IROperand) -> str:
        """Уникальный строковый ключ для поиска операнда в StackFrame."""
        if isinstance(op, TempOperand):
            return f"__t{op.number}"
        if isinstance(op, VarOperand):
            return f"{op.name}_{op.version}"
        return str(op)

    def _label_ref(self, label: str) -> str:
        """Форматировать ссылку на метку для NASM (локальные метки с '.')."""
        if label.startswith("."):
            return label
        return f".{label}"

    def _get_string_label(self, value: str) -> str:
        """Получить или создать метку .rodata для строкового литерала."""
        if value not in self._string_literals:
            self._str_counter += 1
            self._string_literals[value] = f".L.str{self._str_counter}"
        return self._string_literals[value]

    def _encode_string(self, value: str) -> str:
        """
        Кодировать строку Python в NASM-директиву db.

        Например: 'hello\\nworld' → '"hello", 10, "world"'
        """
        escape_map = {"\\n": 10, "\\t": 9, "\\r": 13, "\\\\": ord("\\")}
        parts: List[str] = []
        current = ""
        i = 0
        while i < len(value):
            matched = False
            for seq, code in escape_map.items():
                if value[i:i + len(seq)] == seq:
                    if current:
                        parts.append(f'"{current}"')
                        current = ""
                    parts.append(str(code))
                    i += len(seq)
                    matched = True
                    break
            if not matched:
                current += value[i]
                i += 1
        if current:
            parts.append(f'"{current}"')
        return ", ".join(parts) if parts else '""'

    def _emit(self, line: str) -> None:
        self._lines.append(line)
