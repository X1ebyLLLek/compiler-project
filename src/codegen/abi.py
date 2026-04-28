"""
Константы System V AMD64 ABI для MiniCompiler (Sprint 5).

Описывает соглашение о вызовах для x86-64 Linux:
  - порядок регистров для аргументов
  - caller-saved / callee-saved регистры
  - регистры возврата значений
"""

# Регистры для передачи целочисленных аргументов (по порядку)
INT_ARG_REGS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]

# Регистры для передачи аргументов с плавающей точкой (XMM)
FLOAT_ARG_REGS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]

# Регистр возврата целого значения
RETURN_REG_INT = "rax"

# Регистр возврата значения с плавающей точкой
RETURN_REG_FLOAT = "xmm0"

# Caller-saved регистры (можно использовать свободно, вызываемый не обязан сохранять)
CALLER_SAVED = ["rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"]

# Callee-saved регистры (вызываемый обязан сохранять и восстанавливать)
CALLEE_SAVED = ["rbx", "r12", "r13", "r14", "r15"]

# Scratch-регистры для промежуточных вычислений (caller-saved)
SCRATCH_1 = "rax"
SCRATCH_2 = "rcx"
SCRATCH_3 = "rdx"

# Максимальное число аргументов в регистрах
MAX_INT_ARGS_IN_REGS = 6
MAX_FLOAT_ARGS_IN_REGS = 8

# Размер слова (байт)
WORD_SIZE = 8
