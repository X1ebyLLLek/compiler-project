"""
Система типов MiniCompiler.

Базовые типы (int, float, bool, void, string),
структурные и функциональные типы,
правила совместимости и приведения.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# --- Представление типов ---

@dataclass(frozen=True)
class Type:
    """Базовый класс для всех типов."""
    name: str

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other):
        if not isinstance(other, Type):
            return NotImplemented
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)


@dataclass(frozen=True)
class StructType(Type):
    """Тип структуры с именованными полями."""
    fields: tuple = ()  # кортеж пар (имя, тип)

    def __str__(self) -> str:
        return f"struct {self.name}"

    def get_field_type(self, field_name: str) -> Optional[Type]:
        for fname, ftype in self.fields:
            if fname == field_name:
                return ftype
        return None

    def has_field(self, field_name: str) -> bool:
        return any(fname == field_name for fname, _ in self.fields)


@dataclass(frozen=True)
class FunctionType(Type):
    """Тип функции: параметры → возвращаемый тип."""
    param_types: tuple = ()     # кортеж Type
    return_type: Type = None

    def __str__(self) -> str:
        params = ", ".join(str(p) for p in self.param_types)
        ret = str(self.return_type) if self.return_type else "void"
        return f"({params}) -> {ret}"


# --- Базовые типы (синглтоны) ---

INT_TYPE = Type("int")
FLOAT_TYPE = Type("float")
BOOL_TYPE = Type("bool")
VOID_TYPE = Type("void")
STRING_TYPE = Type("string")
ERROR_TYPE = Type("<error>")  # тип-заглушка при ошибках

# маппинг строкового имени -> объект типа
BUILTIN_TYPES: Dict[str, Type] = {
    "int": INT_TYPE,
    "float": FLOAT_TYPE,
    "bool": BOOL_TYPE,
    "void": VOID_TYPE,
    "string": STRING_TYPE,
}


def resolve_type_name(name: str, struct_types: Optional[Dict[str, StructType]] = None) -> Optional[Type]:
    """Преобразовать строковое имя типа в объект Type."""
    if name in BUILTIN_TYPES:
        return BUILTIN_TYPES[name]
    if struct_types and name in struct_types:
        return struct_types[name]
    return None


# --- Правила совместимости ---

def is_assignable(target: Type, value: Type) -> bool:
    """
    Можно ли присвоить значение типа value переменной типа target?

    Правила:
    - Одинаковые типы — всегда можно
    - int → float (widening) — разрешено
    - float → int (narrowing) — запрещено
    - ERROR_TYPE совместим с чем угодно (подавляем каскадные ошибки)
    """
    if target == ERROR_TYPE or value == ERROR_TYPE:
        return True
    if target == value:
        return True
    # Неявное расширение: int -> float
    if target == FLOAT_TYPE and value == INT_TYPE:
        return True
    return False


def common_numeric_type(left: Type, right: Type) -> Optional[Type]:
    """
    Определить результирующий тип арифметической операции.

    int ∧ int → int
    float ∧ float → float
    int ∧ float → float  (widening)
    float ∧ int → float
    """
    if left == ERROR_TYPE or right == ERROR_TYPE:
        return ERROR_TYPE
    if left == INT_TYPE and right == INT_TYPE:
        return INT_TYPE
    if left == FLOAT_TYPE and right == FLOAT_TYPE:
        return FLOAT_TYPE
    if (left == INT_TYPE and right == FLOAT_TYPE) or \
       (left == FLOAT_TYPE and right == INT_TYPE):
        return FLOAT_TYPE
    return None


def is_numeric(t: Type) -> bool:
    """Является ли тип числовым (int или float)."""
    return t in (INT_TYPE, FLOAT_TYPE) or t == ERROR_TYPE


def is_boolean(t: Type) -> bool:
    """Является ли тип логическим."""
    return t == BOOL_TYPE or t == ERROR_TYPE


# --- Правила операторов ---

def binary_result_type(operator: str, left: Type, right: Type) -> Optional[Type]:
    """Тип результата бинарной операции, None если типы несовместимы."""
    if left == ERROR_TYPE or right == ERROR_TYPE:
        return ERROR_TYPE

    # Арифметические операторы
    if operator in ("+", "-", "*", "/", "%"):
        return common_numeric_type(left, right)

    # Операторы сравнения
    if operator in ("<", "<=", ">", ">="):
        if is_numeric(left) and is_numeric(right):
            return BOOL_TYPE
        return None

    # Операторы равенства (работают для числовых, bool, string)
    if operator in ("==", "!="):
        if is_numeric(left) and is_numeric(right):
            return BOOL_TYPE
        if left == right and left in (BOOL_TYPE, STRING_TYPE):
            return BOOL_TYPE
        return None

    # Логические операторы
    if operator in ("&&", "||"):
        if is_boolean(left) and is_boolean(right):
            return BOOL_TYPE
        return None

    return None


def unary_result_type(operator: str, operand: Type) -> Optional[Type]:
    """
    Определить тип результата унарной операции.

    -int → int, -float → float
    !bool → bool
    """
    if operand == ERROR_TYPE:
        return ERROR_TYPE

    if operator == "-":
        if operand == INT_TYPE:
            return INT_TYPE
        if operand == FLOAT_TYPE:
            return FLOAT_TYPE
        return None

    if operator == "!":
        if operand == BOOL_TYPE:
            return BOOL_TYPE
        return None

    return None
