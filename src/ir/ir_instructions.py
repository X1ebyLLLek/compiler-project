"""
Инструкции промежуточного представления (IR) для MiniCompiler.

Реализует трёхадресный код (three-address code, TAC):
  result = operand1 OP operand2

Каждая инструкция состоит из:
  - опкода (IROpcode)
  - операндов (IROperand)

Sprint 4: IR Generation.
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Any


# ============================================================
# Опкоды инструкций
# ============================================================

class IROpcode(Enum):
    """Коды операций промежуточного представления."""

    # -- Арифметические операции --
    ADD = "ADD"     # dest = src1 + src2
    SUB = "SUB"     # dest = src1 - src2
    MUL = "MUL"     # dest = src1 * src2
    DIV = "DIV"     # dest = src1 / src2
    MOD = "MOD"     # dest = src1 % src2
    NEG = "NEG"     # dest = -src1

    # -- Логические операции --
    AND = "AND"     # dest = src1 && src2
    OR  = "OR"      # dest = src1 || src2
    NOT = "NOT"     # dest = !src1
    XOR = "XOR"     # dest = src1 ^ src2

    # -- Операции сравнения --
    CMP_EQ = "CMP_EQ"   # dest = (src1 == src2)
    CMP_NE = "CMP_NE"   # dest = (src1 != src2)
    CMP_LT = "CMP_LT"   # dest = (src1 < src2)
    CMP_LE = "CMP_LE"   # dest = (src1 <= src2)
    CMP_GT = "CMP_GT"   # dest = (src1 > src2)
    CMP_GE = "CMP_GE"   # dest = (src1 >= src2)

    # -- Операции с памятью --
    LOAD  = "LOAD"   # dest = *addr
    STORE = "STORE"  # *addr = src
    ALLOCA = "ALLOCA"  # dest = выделить память (размер)
    MOVE  = "MOVE"   # dest = src (копирование)

    # -- Управление потоком --
    JUMP         = "JUMP"          # безусловный переход к метке
    JUMP_IF      = "JUMP_IF"       # переход если src != 0
    JUMP_IF_NOT  = "JUMP_IF_NOT"   # переход если src == 0
    LABEL        = "LABEL"         # метка (псевдоинструкция)

    # -- Функциональные операции --
    CALL   = "CALL"    # dest = func(args...)
    RETURN = "RETURN"  # return [value]
    PARAM  = "PARAM"   # передача аргумента (номер, значение)

    # -- PHI-узел (для SSA, если потребуется) --
    PHI = "PHI"  # dest = phi((val1, block1), (val2, block2), ...)

    # -- Операции с массивами (Sprint 7) --
    ARRAY_ALLOC = "ARRAY_ALLOC"  # выделить место под массив на стеке
    ARRAY_LOAD  = "ARRAY_LOAD"   # dest = base[index]
    ARRAY_STORE = "ARRAY_STORE"  # base[index] = src
    GET_ADDR    = "GET_ADDR"     # dest = &var (адрес переменной/массива)


# ============================================================
# Операнды инструкций
# ============================================================

@dataclass
class IROperand:
    """Базовый класс операнда IR."""

    def __str__(self) -> str:
        raise NotImplementedError


@dataclass
class TempOperand(IROperand):
    """Временная переменная: t1, t2, ..."""
    number: int
    type_name: str = ""  # тип для аннотации (необязательно)

    def __str__(self) -> str:
        return f"t{self.number}"

    def __repr__(self) -> str:
        return f"TempOperand({self.number})"

    def __eq__(self, other) -> bool:
        return isinstance(other, TempOperand) and self.number == other.number

    def __hash__(self) -> int:
        return hash(("TempOperand", self.number))


@dataclass
class VarOperand(IROperand):
    """Переменная из исходного кода: x_0, y_0, ..."""
    name: str          # оригинальное имя в исходнике
    version: int = 0   # версия (для отслеживания переименований)

    def __str__(self) -> str:
        return f"{self.name}_{self.version}"

    def __repr__(self) -> str:
        return f"VarOperand({self.name!r}, {self.version})"

    def __eq__(self, other) -> bool:
        return (isinstance(other, VarOperand)
                and self.name == other.name
                and self.version == other.version)

    def __hash__(self) -> int:
        return hash(("VarOperand", self.name, self.version))


@dataclass
class LiteralOperand(IROperand):
    """Константа (литерал): 42, 3.14, true."""
    value: Any
    type_name: str = ""

    def __str__(self) -> str:
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return str(self.value)

    def __repr__(self) -> str:
        return f"LiteralOperand({self.value!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, LiteralOperand) and self.value == other.value

    def __hash__(self) -> int:
        return hash(("LiteralOperand", self.value))


@dataclass
class LabelOperand(IROperand):
    """Метка базового блока: L_then, L_while_cond, ..."""
    name: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"LabelOperand({self.name!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, LabelOperand) and self.name == other.name

    def __hash__(self) -> int:
        return hash(("LabelOperand", self.name))


# ============================================================
# Инструкция IR
# ============================================================

@dataclass
class IRInstruction:
    """
    Одна инструкция промежуточного представления.

    Формат:
        dest = opcode src1, src2   (для двухоперандных)
        dest = opcode src1         (для одноoperandных)
        opcode label               (управление потоком)
        dest opcode src1, args...  (вызов функции)

    Поля:
        opcode  — код операции
        dest    — операнд-приёмник (может быть None)
        src1    — первый операнд-источник (может быть None)
        src2    — второй операнд-источник (может быть None)
        args    — список дополнительных аргументов (для CALL, PHI)
        comment — комментарий (для читаемого дампа)
        source_line — строка исходника, которой соответствует инструкция
    """
    opcode: IROpcode
    dest: Optional[IROperand] = None
    src1: Optional[IROperand] = None
    src2: Optional[IROperand] = None
    args: List[IROperand] = field(default_factory=list)
    comment: str = ""
    source_line: int = 0

    def format(self) -> str:
        """Форматировать инструкцию в читаемом виде."""
        op = self.opcode.value
        parts = []

        if self.opcode == IROpcode.LABEL:
            # Метка — ставим в начало строки без отступа
            return f"{self.src1}:"

        if self.opcode == IROpcode.JUMP:
            parts.append(f"JUMP {self.src1}")

        elif self.opcode in (IROpcode.JUMP_IF, IROpcode.JUMP_IF_NOT):
            parts.append(f"{op} {self.src1}, {self.src2}")

        elif self.opcode == IROpcode.RETURN:
            if self.src1 is not None:
                parts.append(f"RETURN {self.src1}")
            else:
                parts.append("RETURN")

        elif self.opcode == IROpcode.CALL:
            arg_str = ", ".join(str(a) for a in self.args)
            call_str = f"CALL {self.src1}" + (f", {arg_str}" if self.args else "")
            if self.dest is not None:
                parts.append(f"{self.dest} = {call_str}")
            else:
                parts.append(call_str)

        elif self.opcode == IROpcode.PARAM:
            # PARAM индекс, значение
            parts.append(f"PARAM {self.src1}, {self.src2}")

        elif self.opcode == IROpcode.STORE:
            # STORE [addr], src
            parts.append(f"STORE [{self.dest}], {self.src1}")

        elif self.opcode == IROpcode.LOAD:
            parts.append(f"{self.dest} = LOAD [{self.src1}]")

        elif self.opcode == IROpcode.ALLOCA:
            parts.append(f"{self.dest} = ALLOCA")

        elif self.opcode == IROpcode.ARRAY_ALLOC:
            count = self.src1 if self.src1 is not None else "?"
            parts.append(f"{self.dest} = ARRAY_ALLOC {count}")

        elif self.opcode == IROpcode.ARRAY_LOAD:
            parts.append(f"{self.dest} = ARRAY_LOAD [{self.src1}][{self.src2}]")

        elif self.opcode == IROpcode.ARRAY_STORE:
            parts.append(f"ARRAY_STORE [{self.dest}][{self.src1}], {self.src2}")

        elif self.opcode == IROpcode.GET_ADDR:
            parts.append(f"{self.dest} = GET_ADDR {self.src1}")

        elif self.opcode == IROpcode.MOVE:
            parts.append(f"{self.dest} = MOVE {self.src1}")

        elif self.opcode == IROpcode.NEG:
            parts.append(f"{self.dest} = NEG {self.src1}")

        elif self.opcode == IROpcode.NOT:
            parts.append(f"{self.dest} = NOT {self.src1}")

        elif self.opcode == IROpcode.PHI:
            # PHI dest, (val1, block1), (val2, block2)
            phi_args = ", ".join(
                f"({a}, {b})" for a, b in zip(self.args[::2], self.args[1::2])
            )
            parts.append(f"{self.dest} = PHI {phi_args}")

        else:
            # Бинарные операции: dest = SRC1 OP SRC2
            if self.dest is not None and self.src1 is not None and self.src2 is not None:
                parts.append(f"{self.dest} = {op} {self.src1}, {self.src2}")
            elif self.dest is not None and self.src1 is not None:
                parts.append(f"{self.dest} = {op} {self.src1}")
            else:
                parts.append(f"{op}")

        result = "    " + "".join(parts)
        if self.comment:
            result = f"{result:<40}# {self.comment}"
        return result

    def __str__(self) -> str:
        return self.format()


# ============================================================
# Маппинг операторов языка -> опкоды IR
# ============================================================

# Бинарные операторы исходного языка -> IR-опкод
BINARY_OP_TO_OPCODE = {
    "+":  IROpcode.ADD,
    "-":  IROpcode.SUB,
    "*":  IROpcode.MUL,
    "/":  IROpcode.DIV,
    "%":  IROpcode.MOD,
    "&&": IROpcode.AND,
    "||": IROpcode.OR,
    "==": IROpcode.CMP_EQ,
    "!=": IROpcode.CMP_NE,
    "<":  IROpcode.CMP_LT,
    "<=": IROpcode.CMP_LE,
    ">":  IROpcode.CMP_GT,
    ">=": IROpcode.CMP_GE,
}
