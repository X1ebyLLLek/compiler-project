"""
Модуль ошибок семантического анализа.

Каждая ошибка хранит категорию, позицию (строка, столбец),
контекст и подсказку для исправления.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


class SemanticErrorKind:
    """Категории семантических ошибок."""
    UNDECLARED_VARIABLE = "undeclared_variable"
    DUPLICATE_DECLARATION = "duplicate_declaration"
    TYPE_MISMATCH = "type_mismatch"
    ARGUMENT_COUNT_MISMATCH = "argument_count_mismatch"
    ARGUMENT_TYPE_MISMATCH = "argument_type_mismatch"
    INVALID_RETURN_TYPE = "invalid_return_type"
    INVALID_CONDITION_TYPE = "invalid_condition_type"
    USE_BEFORE_DECLARATION = "use_before_declaration"
    INVALID_ASSIGNMENT_TARGET = "invalid_assignment_target"
    UNDECLARED_FUNCTION = "undeclared_function"
    NOT_A_FUNCTION = "not_a_function"
    INVALID_OPERATOR = "invalid_operator"
    VOID_VARIABLE = "void_variable"


@dataclass
class SemanticError:
    """
    Представление одной ошибки семантического анализа.

    Хранит категорию, текст ошибки, позицию (строка/столбец),
    контекст (имя функции и т.п.), ожидаемый/фактический типы
    и подсказку для исправления.
    """
    kind: str
    message: str
    line: int = 0
    column: int = 0
    context: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    suggestion: Optional[str] = None

    def format(self, source_lines: Optional[List[str]] = None) -> str:
        """Форматировать ошибку с указанием позиции и фрагмента кода."""
        parts = [f"semantic error: {self.message}"]
        parts.append(f"  --> строка {self.line}:{self.column}")

        if source_lines and 0 < self.line <= len(source_lines):
            src_line = source_lines[self.line - 1].rstrip()
            parts.append("   |")
            parts.append(f"   | {src_line}")
            # Подчёркивание позиции ошибки
            pointer = " " * (self.column - 1) + "^"
            parts.append(f"   | {pointer}")
            parts.append("   |")

        if self.expected and self.actual:
            parts.append(f"   = ожидалось: {self.expected}")
            parts.append(f"   = получено:  {self.actual}")

        if self.context:
            parts.append(f"   = контекст: {self.context}")

        if self.suggestion:
            parts.append(f"   = подсказка: {self.suggestion}")

        return "\n".join(parts)

    def __str__(self) -> str:
        return self.format()


class SemanticErrorCollector:
    """Собирает ошибки по ходу анализа (error recovery)."""

    def __init__(self):
        self._errors: List[SemanticError] = []

    def add(self, error: SemanticError):
        self._errors.append(error)

    def add_error(
        self,
        kind: str,
        message: str,
        line: int = 0,
        column: int = 0,
        context: Optional[str] = None,
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        self._errors.append(SemanticError(
            kind=kind,
            message=message,
            line=line,
            column=column,
            context=context,
            expected=expected,
            actual=actual,
            suggestion=suggestion,
        ))

    @property
    def errors(self) -> List[SemanticError]:
        return list(self._errors)

    @property
    def has_errors(self) -> bool:
        return len(self._errors) > 0

    @property
    def count(self) -> int:
        return len(self._errors)

    def format_all(self, source_lines: Optional[List[str]] = None) -> str:
        """Форматировать все ошибки одним блоком."""
        if not self._errors:
            return "Семантических ошибок не обнаружено."
        parts = []
        for i, err in enumerate(self._errors, 1):
            parts.append(f"[{i}/{len(self._errors)}] {err.format(source_lines)}")
        parts.append(f"\nВсего ошибок: {len(self._errors)}")
        return "\n\n".join(parts)
