"""
Генерация кода для массивов x86-64 (Sprint 7).

Миксин ArrayGeneratorMixin для X86Generator.
Умеет:
  - выделять место под локальные массивы на стеке (ARRAY_ALLOC)
  - генерировать адресный расчёт элемента: base + index * element_size
  - загружать/сохранять элементы массива (ARRAY_LOAD, ARRAY_STORE)
  - брать адрес переменной (GET_ADDR) — нужно для передачи массива в функцию

Все локальные массивы живут на стеке. Глобальные — в .data / .bss
(объявляются в generate() через _emit_global_arrays()).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from src.ir.ir_instructions import (
    IRInstruction, IROpcode,
    TempOperand, VarOperand, LiteralOperand, LabelOperand,
)

if TYPE_CHECKING:
    from .x86_generator import X86Generator

# Размер одного элемента в байтах (пока поддерживаем только int/bool = 8 байт)
ELEMENT_SIZE = 8


class ArrayGeneratorMixin:
    """
    Миксин для X86Generator.

    Добавляет поддержку IR-инструкций:
      ARRAY_ALLOC  — выделить стековое место под массив
      ARRAY_LOAD   — загрузить элемент массива в temp
      ARRAY_STORE  — сохранить значение в элемент массива
      GET_ADDR     — положить адрес переменной/массива в temp
    """

    def _gen_array_alloc(self: "X86Generator", instr: IRInstruction) -> None:
        """
        ARRAY_ALLOC dest, size_literal

        Выделяет size * ELEMENT_SIZE байт на стеке.
        Реально место уже выделено через RegisterAllocator (ALLOCA pre-pass),
        поэтому здесь просто обнуляем блок памяти (нулевая инициализация).

        instr.dest  — VarOperand массива (base адрес)
        instr.src1  — LiteralOperand(количество элементов)
        instr.src2  — LiteralOperand(размер элемента, опционально; по умолчанию 8)
        """
        if instr.dest is None or instr.src1 is None:
            self._emit("    ; ARRAY_ALLOC: некорректная инструкция (нет dest или размера)")
            return

        count = instr.src1.value if isinstance(instr.src1, LiteralOperand) else 1
        elem_size = (
            instr.src2.value if isinstance(instr.src2, LiteralOperand) else ELEMENT_SIZE
        )
        total_bytes = int(count) * int(elem_size)

        dest_key = self._operand_key(instr.dest)
        base_offset = self._frame.get_offset(dest_key)

        if base_offset is None:
            self._emit(f"    ; ARRAY_ALLOC: слот для {instr.dest} не найден")
            return

        # Нулевая инициализация блока через rep stosq
        # rdi = &array[0], rcx = count, rax = 0
        self._emit(f"    ; инициализация массива {instr.dest} ({count} × {elem_size}B)")
        self._emit(f"    lea rdi, [rbp{base_offset:+d}]")
        self._emit(f"    mov rcx, {count}")
        self._emit(f"    xor rax, rax")
        self._emit(f"    rep stosq")

    def _gen_array_load(self: "X86Generator", instr: IRInstruction) -> None:
        """
        ARRAY_LOAD dest, base, index

        Загружает элемент массива: dest = base[index]
        Адресный расчёт: [rbp + base_offset + index * ELEMENT_SIZE]

        instr.dest  — TempOperand (куда загрузить)
        instr.src1  — VarOperand (имя массива / базовый адрес)
        instr.src2  — операнд с индексом (TempOperand или LiteralOperand)
        """
        if instr.dest is None or instr.src1 is None:
            self._emit("    ; ARRAY_LOAD: некорректная инструкция")
            return

        base_key = self._operand_key(instr.src1)
        base_offset = self._frame.get_offset(base_key)

        if base_offset is None:
            self._emit(f"    ; ARRAY_LOAD: базовый адрес {instr.src1} не найден")
            return

        # Если индекс — константа, используем прямой расчёт
        if isinstance(instr.src2, LiteralOperand):
            idx = int(instr.src2.value)
            element_offset = base_offset + idx * ELEMENT_SIZE
            self._emit(f"    mov rax, qword [rbp{element_offset:+d}]")
        else:
            # Индекс — переменная: загружаем в rcx, считаем адрес через shl+add
            self._load_to_reg(instr.src2, "rcx")
            self._emit(f"    lea rax, [rbp{base_offset:+d}]")
            self._emit(f"    shl rcx, 3")           # rcx * 8 (log2(ELEMENT_SIZE) = 3)
            self._emit(f"    add rax, rcx")          # rax = base + index*8
            self._emit(f"    mov rax, qword [rax]")  # разыменование

        self._store_from_reg("rax", instr.dest)

    def _gen_array_store(self: "X86Generator", instr: IRInstruction) -> None:
        """
        ARRAY_STORE base, index, value

        Сохраняет значение в элемент массива: base[index] = value

        instr.dest  — VarOperand (имя массива)
        instr.src1  — операнд с индексом
        instr.src2  — операнд со значением
        """
        if instr.dest is None or instr.src1 is None or instr.src2 is None:
            self._emit("    ; ARRAY_STORE: некорректная инструкция")
            return

        base_key = self._operand_key(instr.dest)
        base_offset = self._frame.get_offset(base_key)

        if base_offset is None:
            self._emit(f"    ; ARRAY_STORE: базовый адрес {instr.dest} не найден")
            return

        # Загружаем значение в rdx
        self._load_to_reg(instr.src2, "rdx")

        if isinstance(instr.src1, LiteralOperand):
            # Постоянный индекс — прямой адрес
            idx = int(instr.src1.value)
            element_offset = base_offset + idx * ELEMENT_SIZE
            self._emit(f"    mov qword [rbp{element_offset:+d}], rdx")
        else:
            # Динамический индекс
            self._load_to_reg(instr.src1, "rcx")
            self._emit(f"    lea rax, [rbp{base_offset:+d}]")
            self._emit(f"    shl rcx, 3")             # rcx * 8
            self._emit(f"    add rax, rcx")            # rax = &base[index]
            self._emit(f"    mov qword [rax], rdx")    # *rax = value

    def _gen_get_addr(self: "X86Generator", instr: IRInstruction) -> None:
        """
        GET_ADDR dest, var

        Кладёт адрес переменной/массива в dest.
        Нужно для передачи массива в функцию как указатель.

        instr.dest  — TempOperand (куда записать адрес)
        instr.src1  — VarOperand (переменная, адрес которой нужен)
        """
        if instr.dest is None or instr.src1 is None:
            self._emit("    ; GET_ADDR: некорректная инструкция")
            return

        src_key = self._operand_key(instr.src1)
        offset = self._frame.get_offset(src_key)

        if offset is None:
            self._emit(f"    ; GET_ADDR: переменная {instr.src1} не найдена")
            return

        self._emit(f"    lea rax, [rbp{offset:+d}]")
        self._store_from_reg("rax", instr.dest)
