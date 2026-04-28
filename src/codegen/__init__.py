"""
Модуль генерации x86-64 кода для MiniCompiler.

Sprint 5: генерация ассемблерного кода в синтаксисе NASM,
соглашение о вызовах System V AMD64 ABI.
"""

from .x86_generator import X86Generator

__all__ = ["X86Generator"]
