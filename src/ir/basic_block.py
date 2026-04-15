"""
Базовые блоки кода (Basic Blocks) для IR MiniCompiler.

Базовый блок — линейная последовательность инструкций без ветвлений
внутри блока. Блок заканчивается инструкцией передачи управления
(JUMP, JUMP_IF, JUMP_IF_NOT, RETURN) или является последним.

Sprint 4: IR Generation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Set

from .ir_instructions import IRInstruction, IROpcode, IROperand


@dataclass
class BasicBlock:
    """
    Базовый блок — линейная последовательность IR-инструкций.

    Каждый блок имеет:
    - уникальную метку (label)
    - список инструкций (instructions)
    - список блоков-преемников (successors)
    - список блоков-предшественников (predecessors)
    """
    label: str                                         # Метка блока: "entry", "L_then", ...
    instructions: List[IRInstruction] = field(default_factory=list)
    successors: List["BasicBlock"] = field(default_factory=list)
    predecessors: List["BasicBlock"] = field(default_factory=list)

    def add_instruction(self, instr: IRInstruction) -> None:
        """Добавить инструкцию в блок."""
        self.instructions.append(instr)

    def add_successor(self, block: "BasicBlock") -> None:
        """
        Добавить преемника. Одновременно регистрирует себя
        как предшественника у целевого блока.
        """
        if block not in self.successors:
            self.successors.append(block)
        if self not in block.predecessors:
            block.predecessors.append(self)

    def is_terminated(self) -> bool:
        """
        Проверить, завершён ли блок инструкцией управления потоком.

        Блок считается завершённым, если последняя инструкция —
        JUMP, JUMP_IF, JUMP_IF_NOT или RETURN.
        """
        if not self.instructions:
            return False
        last = self.instructions[-1]
        return last.opcode in (
            IROpcode.JUMP,
            IROpcode.JUMP_IF,
            IROpcode.JUMP_IF_NOT,
            IROpcode.RETURN,
        )

    def get_terminator(self) -> Optional[IRInstruction]:
        """Вернуть завершающую инструкцию блока (или None)."""
        if self.is_terminated():
            return self.instructions[-1]
        return None

    def instruction_count(self) -> int:
        """Количество инструкций в блоке (не считая LABEL-псевдоинструкций)."""
        return sum(
            1 for i in self.instructions
            if i.opcode != IROpcode.LABEL
        )

    def dump(self) -> str:
        """Текстовый дамп блока в человекочитаемом виде."""
        lines = [f"  # Базовый блок: {self.label}"]
        lines.append(f"  {self.label}:")
        for instr in self.instructions:
            lines.append(instr.format())
        if self.successors:
            succ_names = ", ".join(b.label for b in self.successors)
            lines.append(f"    # -> преемники: [{succ_names}]")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"BasicBlock({self.label!r}, {len(self.instructions)} instr)"

    def __str__(self) -> str:
        return self.label

    def __eq__(self, other) -> bool:
        return isinstance(other, BasicBlock) and self.label == other.label

    def __hash__(self) -> int:
        return hash(self.label)
