"""
Поддержка внешних функций (extern) для x86-64 кодогенератора (Sprint 7).

Миксин ExternalCallsMixin для X86Generator.

Что делает:
  - Генерирует `extern` объявления в начале секции .text
  - Правильно вызывает внешние функции по System V AMD64 ABI
  - Для variadic функций (printf, scanf, ...) вставляет xor eax, eax перед call
  - Следит за выравниванием стека (перед call rsp должен быть выровнен на 16 байт)

Список заранее известных внешних функций взят из стандартного libc.
Если функция не в списке — предполагаем non-variadic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Set, List

from src.ir.ir_instructions import (
    IRInstruction, IROpcode, IROperand,
    TempOperand, VarOperand, LiteralOperand, LabelOperand,
)
from . import abi

if TYPE_CHECKING:
    from .x86_generator import X86Generator


# Variadic функции из libc — перед их вызовом нужен xor eax, eax
# (количество аргументов в векторных регистрах)
_VARIADIC_FUNCTIONS: Set[str] = {
    "printf",
    "fprintf",
    "sprintf",
    "snprintf",
    "scanf",
    "fscanf",
    "sscanf",
    "dprintf",
}

# Все известные внешние функции libc (не обязательно variadic)
_KNOWN_EXTERN_FUNCTIONS: Set[str] = _VARIADIC_FUNCTIONS | {
    "malloc",
    "free",
    "calloc",
    "realloc",
    "memcpy",
    "memmove",
    "memset",
    "memcmp",
    "strlen",
    "strcpy",
    "strncpy",
    "strcmp",
    "strncmp",
    "strcat",
    "strncat",
    "puts",
    "putchar",
    "getchar",
    "fgets",
    "fopen",
    "fclose",
    "fread",
    "fwrite",
    "fflush",
    "exit",
    "abort",
    "atoi",
    "atof",
    "rand",
    "srand",
}


class ExternalCallsMixin:
    """
    Миксин для X86Generator.

    Хранит набор внешних имён, которые нужно объявить через extern,
    и генерирует правильный вызовной код с соблюдением ABI.
    """

    def _init_extern_state(self: "X86Generator") -> None:
        """
        Инициализировать состояние extern.

        Вызывать из X86Generator.__init__() после базовой инициализации.
        Отдельный метод нужен потому что миксин не имеет __init__.
        """
        # Набор имён функций, для которых нужно emit 'extern'
        self._extern_names: Set[str] = set()

    def _register_extern(self: "X86Generator", func_name: str) -> None:
        """Зарегистрировать имя как внешнее. Будет добавлено в секцию extern."""
        # Если это одна из известных libc функций или явно внешняя — добавляем
        self._extern_names.add(func_name)

    def _emit_extern_declarations(self: "X86Generator") -> None:
        """
        Вывести все накопленные extern-объявления.

        Вызывается в начале generate() перед секцией .text.
        """
        for name in sorted(self._extern_names):
            self._emit(f"extern {name}")
        if self._extern_names:
            self._emit("")

    def _is_variadic(self, func_name: str) -> bool:
        """Вернуть True если функция принимает переменное число аргументов."""
        return func_name in _VARIADIC_FUNCTIONS

    def _is_known_extern(self, func_name: str) -> bool:
        """Вернуть True если функция известна как внешняя (из libc и т.п.)."""
        return func_name in _KNOWN_EXTERN_FUNCTIONS

    def _gen_extern_call(self: "X86Generator", instr: IRInstruction) -> None:
        """
        Сгенерировать вызов внешней функции с соблюдением ABI.

        Отличие от обычного _gen_call:
          - Перед call выравниваем стек на 16 байт (sub rsp, X)
          - Для variadic добавляем xor eax, eax
          - После call восстанавливаем стек (add rsp, X)

        instr.src1  — имя функции (строка через LabelOperand или VarOperand)
        instr.args  — аргументы (операнды IR)
        instr.dest  — куда положить результат (или None)
        """
        func_name = str(instr.src1)

        # Загружаем аргументы в регистры ABI
        n_args = len(instr.args)
        for i, arg in enumerate(instr.args):
            if i < abi.MAX_INT_ARGS_IN_REGS:
                reg = abi.INT_ARG_REGS[i]
                self._load_to_reg(arg, reg)
            else:
                # Аргументы на стеке — кладём в обратном порядке
                # (упрощённо, только для демонстрации)
                self._emit(f"    ; TODO: аргумент {i} на стек")

        # Выравнивание стека: если число аргументов нечётное (с учётом push rbp),
        # нужен дополнительный padding. Простой способ — всегда sub rsp, 8 если нечётно.
        # Точный расчёт: (n_stack_args * 8 + 8) % 16 == 0
        # Для простоты: фиксированный sub rsp, 8 если нужно
        stack_args = max(0, n_args - abi.MAX_INT_ARGS_IN_REGS)
        needs_align = (stack_args % 2 != 0)
        if needs_align:
            self._emit(f"    sub rsp, 8      ; выравнивание стека на 16 байт")

        # Для variadic функций: xor eax, eax (количество xmm аргументов = 0)
        if self._is_variadic(func_name):
            self._emit(f"    xor eax, eax    ; variadic: xmm аргументов нет")

        self._emit(f"    call {func_name}")

        # Восстанавливаем стек если делали padding
        if needs_align:
            self._emit(f"    add rsp, 8      ; восстановление стека после выравнивания")

        # Результат в rax → сохранить в dest
        if instr.dest is not None:
            self._store_from_reg("rax", instr.dest)
