"""
Пакет ir — модули для генерации трёхадресного промежуточного представления (IR).

Sprint 4: IR Generation.
"""

from .ir_instructions import (
    IRInstruction, IROpcode,
    IROperand, TempOperand, VarOperand, LiteralOperand, LabelOperand,
)
from .basic_block import BasicBlock
from .control_flow import ControlFlowGraph, IRFunction, IRProgram
from .ir_generator import IRGenerator

__all__ = [
    "IRInstruction", "IROpcode",
    "IROperand", "TempOperand", "VarOperand", "LiteralOperand", "LabelOperand",
    "BasicBlock",
    "ControlFlowGraph", "IRFunction", "IRProgram",
    "IRGenerator",
]
