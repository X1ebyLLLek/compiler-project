"""
Оптимизационные проходы на уровне ассемблера (Sprint 7).

Применяются после генерации NASM-кода, до вывода.
Это post-IR оптимизации над строками ассемблера.

Реализовано:
  1. Peephole: убрать бесполезные пары mov (mov rax, X / mov X, rax)
  2. Peephole: убрать jmp к следующей инструкции (jmp .Lnext / .Lnext:)
  3. Peephole: xor eax, eax вместо mov eax, 0

Эти оптимизации не затрагивают корректность — только убирают избыточный код,
который типично генерирует stack-based кодоген.

Класс AsmOptimizer — отдельный, не миксин.
"""

from __future__ import annotations

import re
from typing import List, Tuple


class AsmOptimizer:
    """
    Пост-генерационный оптимизатор ассемблерного кода.

    Принимает список строк NASM-кода, возвращает оптимизированный список.
    Работает как серия peephole-проходов (окно из 2-3 строк).
    """

    def __init__(self) -> None:
        # Статистика
        self._removed_mov_pairs = 0
        self._removed_dead_jumps = 0
        self._replaced_mov_zero = 0

    def optimize(self, lines: List[str]) -> List[str]:
        """
        Запустить все оптимизационные проходы.

        :param lines: строки NASM-кода
        :return: оптимизированный список строк
        """
        self._removed_mov_pairs = 0
        self._removed_dead_jumps = 0
        self._replaced_mov_zero = 0

        result = list(lines)
        result = self._pass_replace_mov_zero(result)
        result = self._pass_remove_redundant_mov_pairs(result)
        result = self._pass_remove_dead_jumps(result)
        return result

    def get_stats(self) -> dict:
        """Статистика последнего запуска."""
        return {
            "removed_mov_pairs": self._removed_mov_pairs,
            "removed_dead_jumps": self._removed_dead_jumps,
            "replaced_mov_zero": self._replaced_mov_zero,
            "total": (
                self._removed_mov_pairs
                + self._removed_dead_jumps
                + self._replaced_mov_zero
            ),
        }

    # ----------------------------------------------------------------
    # Проход 1: mov reg, 0 → xor reg, reg (короче и быстрее)
    # ----------------------------------------------------------------

    # Регистры, для которых безопасно делать xor r32, r32 вместо mov r64, 0
    _ZERO_REGS = {"rax", "rbx", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"}

    def _pass_replace_mov_zero(self, lines: List[str]) -> List[str]:
        """Заменить 'mov rax, 0' на 'xor eax, eax' (обнуляет весь rax)."""
        result = []
        # mov <reg64>, 0 → xor <reg32>, <reg32>
        pat = re.compile(r'^(\s+)mov\s+(r\w+),\s+0\s*$')
        reg64_to_32 = {
            "rax": "eax", "rbx": "ebx", "rcx": "ecx", "rdx": "edx",
            "rsi": "esi", "rdi": "edi",
            "r8": "r8d", "r9": "r9d", "r10": "r10d", "r11": "r11d",
        }
        for line in lines:
            m = pat.match(line)
            if m:
                indent = m.group(1)
                reg = m.group(2)
                if reg in reg64_to_32:
                    r32 = reg64_to_32[reg]
                    result.append(f"{indent}xor {r32}, {r32}")
                    self._replaced_mov_zero += 1
                    continue
            result.append(line)
        return result

    # ----------------------------------------------------------------
    # Проход 2: убрать избыточные пары mov
    # ----------------------------------------------------------------

    def _pass_remove_redundant_mov_pairs(self, lines: List[str]) -> List[str]:
        """
        Убрать пары вида:
            mov qword [rbp-X], rax
            mov rax, qword [rbp-X]

        где второй mov немедленно загружает то, что только что сохранили.
        Это типичный артефакт stack-based кодогена при MOVE-инструкциях.
        """
        result = []
        i = 0
        # Паттерн: mov qword [rbp±N], REG и потом mov REG, qword [rbp±N]
        store_pat = re.compile(r'\s+mov\s+qword\s+\[rbp([+-]\d+)\],\s+(\w+)')
        load_pat = re.compile(r'\s+mov\s+(\w+),\s+qword\s+\[rbp([+-]\d+)\]')

        while i < len(lines):
            if i + 1 < len(lines):
                sm = store_pat.match(lines[i])
                lm = load_pat.match(lines[i + 1])
                if sm and lm:
                    store_offset = sm.group(1)
                    store_reg = sm.group(2)
                    load_reg = lm.group(1)
                    load_offset = lm.group(2)
                    # Если сохраняем в [rbp±X] а потом загружаем из [rbp±X] в тот же reg
                    if store_offset == load_offset and store_reg == load_reg:
                        # Оставляем только store, пропускаем load
                        result.append(lines[i])
                        i += 2
                        self._removed_mov_pairs += 1
                        continue
            result.append(lines[i])
            i += 1
        return result

    # ----------------------------------------------------------------
    # Проход 3: убрать jmp к следующей метке
    # ----------------------------------------------------------------

    def _pass_remove_dead_jumps(self, lines: List[str]) -> List[str]:
        """
        Убрать безусловный прыжок если следующая непустая строка — его цель.

        Пример:
            jmp .Lend_1
        .Lend_1:          ← следующая метка

        Такой jmp ничего не делает.
        """
        result = []
        jmp_pat = re.compile(r'\s+jmp\s+(\S+)')
        label_pat = re.compile(r'^(\S+):')

        i = 0
        while i < len(lines):
            m = jmp_pat.match(lines[i])
            if m:
                target = m.group(1)
                # Найдём следующую непустую/некомментарную строку
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    lm = label_pat.match(lines[j])
                    if lm and lm.group(1) == target:
                        # Прыжок к следующей метке — убираем jmp
                        i += 1
                        self._removed_dead_jumps += 1
                        continue
            result.append(lines[i])
            i += 1
        return result
