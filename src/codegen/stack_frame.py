"""
Управление стековым фреймом функции (Sprint 5).

Отслеживает распределение стекового пространства для
локальных переменных и временных значений IR.

Схема фрейма (System V AMD64 ABI):
  [rbp+8]  — адрес возврата (сохранён CALL)
  [rbp]    — сохранённый rbp вызывающей стороны
  [rbp-8]  — первая локальная переменная
  [rbp-16] — вторая локальная переменная
  ...
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class StackSlot:
    """Один выделенный слот в стековом фрейме."""
    name: str     # ключ операнда (например "x_0" или "__t3")
    offset: int   # смещение от rbp (отрицательное)
    size: int = 8 # размер в байтах


class StackFrame:
    """
    Стековый фрейм функции.

    Назначает отрицательные смещения от rbp для каждого
    именованного операнда. Итоговый размер выравнивается на 16 байт.
    """

    def __init__(self) -> None:
        self._slots: Dict[str, StackSlot] = {}
        self._used: int = 0  # текущий размер (байт, до выравнивания)

    def allocate(self, name: str, size: int = 8) -> int:
        """
        Выделить слот для операнда.

        Если слот уже существует — вернуть его смещение без повторного выделения.
        """
        if name in self._slots:
            return self._slots[name].offset
        self._used += size
        offset = -self._used
        self._slots[name] = StackSlot(name=name, offset=offset, size=size)
        return offset

    def get_offset(self, name: str) -> Optional[int]:
        """Вернуть смещение для имени или None, если не выделено."""
        slot = self._slots.get(name)
        return slot.offset if slot else None

    def has(self, name: str) -> bool:
        """Проверить, выделен ли слот для данного имени."""
        return name in self._slots

    @property
    def aligned_size(self) -> int:
        """Размер фрейма, выровненный на 16 байт (для соблюдения ABI)."""
        if self._used == 0:
            return 0
        return (self._used + 15) & ~15

    @property
    def total_slots(self) -> int:
        """Общее число выделенных слотов."""
        return len(self._slots)

    def dump(self) -> str:
        """Текстовый дамп содержимого фрейма (для отладки)."""
        lines = [f"StackFrame (размер {self.aligned_size} байт):"]
        for name, slot in self._slots.items():
            lines.append(f"  [rbp{slot.offset:+d}]  {name} ({slot.size}B)")
        return "\n".join(lines)
