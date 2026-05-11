"""
Менеджер меток для генератора кода (Sprint 6).

Отвечает за создание уникальных меток для всех управляющих конструкций:
ветвлений (if/else), циклов (while/for) и выражений с коротким замыканием (&&, ||).
"""
from __future__ import annotations


class LabelManager:
    """
    Генератор уникальных меток ассемблера.

    Каждый вызов new_label() возвращает метку с уникальным
    числовым суффиксом, гарантируя отсутствие конфликтов
    при генерации вложенных управляющих конструкций.
    """

    def __init__(self) -> None:
        self._counter: int = 0

    def new_label(self, prefix: str = "L") -> str:
        """Создать уникальную метку с заданным префиксом."""
        self._counter += 1
        return f"{prefix}_{self._counter}"

    # ---- Удобные методы для типичных управляющих конструкций ----

    def new_if_labels(self) -> tuple[str, str, str]:
        """Вернуть тройку меток: (then, else, endif)."""
        then_label  = self.new_label("L_then")
        else_label  = self.new_label("L_else")
        endif_label = self.new_label("L_endif")
        return then_label, else_label, endif_label

    def new_while_labels(self) -> tuple[str, str, str]:
        """Вернуть тройку меток: (cond, body, end)."""
        cond_label = self.new_label("L_while_cond")
        body_label = self.new_label("L_while_body")
        end_label  = self.new_label("L_while_end")
        return cond_label, body_label, end_label

    def new_for_labels(self) -> tuple[str, str, str]:
        """Вернуть тройку меток: (cond, body, end)."""
        cond_label = self.new_label("L_for_cond")
        body_label = self.new_label("L_for_body")
        end_label  = self.new_label("L_for_end")
        return cond_label, body_label, end_label

    def new_sc_and_labels(self) -> tuple[str, str]:
        """Метки для короткого замыкания &&: (false_label, end_label)."""
        false_label = self.new_label("L_sc_false")
        end_label   = self.new_label("L_sc_end")
        return false_label, end_label

    def new_sc_or_labels(self) -> tuple[str, str]:
        """Метки для короткого замыкания ||: (true_label, end_label)."""
        true_label = self.new_label("L_sc_true")
        end_label  = self.new_label("L_sc_end")
        return true_label, end_label

    @property
    def counter(self) -> int:
        """Текущее значение счётчика меток (для отладки)."""
        return self._counter
