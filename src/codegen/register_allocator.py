"""
Распределитель регистров для MiniCompiler (Sprint 5).

Стратегия: stack-based allocation — все операнды (переменные и временные)
хранятся на стеке. Scratch-регистры (rax, rcx, rdx) используются только
для вычислений внутри одной инструкции и не сохраняют значение между ними.

В будущем этот модуль может быть заменён на линейное сканирование
(linear scan) или раскраску графа (graph coloring).
"""

from __future__ import annotations

from src.ir.control_flow import IRFunction
from src.ir.ir_instructions import (
    IROpcode, IROperand, TempOperand, VarOperand, LiteralOperand,
)
from .stack_frame import StackFrame


class RegisterAllocator:
    """
    Простейший распределитель регистров (stack-based).

    Обходит все инструкции функции и назначает стековые слоты
    каждому уникальному операнду-приёмнику (dest).

    Порядок обхода:
      1. ALLOCA-инструкции обрабатываются первыми (переменные исходника).
      2. Все прочие dest (временные) добавляются по мере встречи.
    """

    def allocate(self, func: IRFunction) -> StackFrame:
        """
        Построить StackFrame для функции.

        :param func: IR-функция с CFG
        :return: StackFrame со слотами для всех операндов
        """
        frame = StackFrame()

        # Два прохода:
        # 1. Сначала ALLOCA и ARRAY_ALLOC (переменные исходника идут в начало фрейма)
        for block in func.cfg.blocks:
            for instr in block.instructions:
                if instr.opcode == IROpcode.ALLOCA and instr.dest:
                    key = self._operand_key(instr.dest)
                    frame.allocate(key)
                elif instr.opcode == IROpcode.ARRAY_ALLOC and instr.dest:
                    # Массив: выделяем count * 8 байт подряд
                    count = 1
                    if hasattr(instr.src1, 'value') and instr.src1 is not None:
                        count = int(instr.src1.value)
                    elem_size = 8
                    if hasattr(instr.src2, 'value') and instr.src2 is not None:
                        elem_size = int(instr.src2.value)
                    key = self._operand_key(instr.dest)
                    frame.allocate(key, size=count * elem_size)

        # 2. Затем все остальные dest (временные)
        for block in func.cfg.blocks:
            for instr in block.instructions:
                if instr.dest is not None:
                    key = self._operand_key(instr.dest)
                    if not frame.has(key):
                        frame.allocate(key)

        return frame

    @staticmethod
    def _operand_key(op: IROperand) -> str:
        """Уникальный строковый ключ для операнда."""
        if isinstance(op, TempOperand):
            return f"__t{op.number}"
        if isinstance(op, VarOperand):
            return f"{op.name}_{op.version}"
        return str(op)
