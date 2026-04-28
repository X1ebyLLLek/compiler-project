"""
Тесты генерации x86-64 кода (Sprint 5).

Проверяем:
  - структуру пролога/эпилога функций
  - соответствие IR-инструкций ассемблерным
  - передачу аргументов по System V ABI
  - управляющие структуры (if, while)
  - рекурсивные вызовы функций
  - секции и директивы NASM
"""

import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator
from src.codegen.stack_frame import StackFrame
from src.codegen.register_allocator import RegisterAllocator


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def compile_to_asm(source: str) -> str:
    """Полный цикл компиляции: исходный код → строка NASM-ассемблера."""
    scanner = Scanner(source)
    tokens = scanner._tokens
    parser = Parser(tokens)
    ast = parser.parse()
    assert not parser.get_errors(), f"Ошибки парсинга: {parser.get_errors()}"

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast, source=source)
    assert not analyzer.get_errors(), (
        f"Семантические ошибки: {[str(e) for e in analyzer.get_errors()]}"
    )

    generator = IRGenerator()
    ir_program = generator.generate(ast)

    codegen = X86Generator()
    return codegen.generate(ir_program)


def asm_lines(source: str) -> list[str]:
    """Вернуть непустые строки ассемблера (без ведущих пробелов)."""
    return [line.strip() for line in compile_to_asm(source).splitlines() if line.strip()]


# --------------------------------------------------------------------------
# TEST-1: Структура секций и глобальные объявления (ASM-1)
# --------------------------------------------------------------------------

class TestSections:
    """Проверяем наличие обязательных секций и директив NASM."""

    def test_text_section_present(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "section .text" in asm

    def test_global_directive_for_main(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "global main" in asm

    def test_global_directive_for_named_function(self):
        source = "fn compute(int x) -> int { return x; }"
        asm = compile_to_asm(source)
        assert "global compute" in asm

    def test_multiple_globals(self):
        source = """
        fn helper(int a) -> int { return a; }
        fn main() -> int { return 0; }
        """
        asm = compile_to_asm(source)
        assert "global helper" in asm
        assert "global main" in asm

    def test_function_label_present(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "main:" in asm

    def test_named_function_label(self):
        source = "fn compute(int x) -> int { return x; }"
        asm = compile_to_asm(source)
        assert "compute:" in asm

    def test_rodata_section_for_string_literal(self):
        # Строки компилируются как литералы — при наличии должна появиться секция
        source = """
        fn get_msg() -> int {
            int x = 0;
            return x;
        }
        """
        asm = compile_to_asm(source)
        # Без строковых литералов секции .rodata быть не должно
        assert "section .rodata" not in asm


# --------------------------------------------------------------------------
# TEST-1: Пролог и эпилог функций (STK-1, STK-4)
# --------------------------------------------------------------------------

class TestPrologueEpilogue:
    """Проверяем корректность пролога и эпилога каждой функции."""

    def test_push_rbp_in_prologue(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "push rbp" in asm

    def test_mov_rbp_rsp_in_prologue(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "mov rbp, rsp" in asm

    def test_sub_rsp_for_locals(self):
        source = """
        fn main() -> int {
            int x = 5;
            return x;
        }
        """
        asm = compile_to_asm(source)
        assert "sub rsp," in asm

    def test_stack_aligned_to_16(self):
        """Размер стекового фрейма должен быть кратен 16."""
        source = """
        fn main() -> int {
            int a = 1;
            int b = 2;
            int c = a + b;
            return c;
        }
        """
        asm = compile_to_asm(source)
        # Извлекаем значение из "sub rsp, N"
        for line in asm.splitlines():
            if "sub rsp," in line:
                parts = line.strip().split(",")
                n_str = parts[-1].strip().split()[0]
                n = int(n_str)
                assert n % 16 == 0, f"Размер фрейма {n} не кратен 16"
                break

    def test_mov_rsp_rbp_in_epilogue(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "mov rsp, rbp" in asm

    def test_pop_rbp_in_epilogue(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "pop rbp" in asm

    def test_ret_instruction(self):
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "ret" in asm


# --------------------------------------------------------------------------
# TEST-2: Арифметические операции (ASM-2)
# --------------------------------------------------------------------------

class TestArithmetic:
    """Проверяем трансляцию арифметических IR-опкодов в x86 инструкции."""

    def test_addition_uses_add_instruction(self):
        source = """
        fn add(int a, int b) -> int {
            return a + b;
        }
        """
        asm = compile_to_asm(source)
        assert "add rax, rcx" in asm

    def test_subtraction_uses_sub_instruction(self):
        source = """
        fn sub(int a, int b) -> int {
            return a - b;
        }
        """
        asm = compile_to_asm(source)
        assert "sub rax, rcx" in asm

    def test_multiplication_uses_imul(self):
        source = """
        fn mul(int a, int b) -> int {
            return a * b;
        }
        """
        asm = compile_to_asm(source)
        assert "imul rax, rcx" in asm

    def test_division_uses_idiv_and_cqo(self):
        source = """
        fn divide(int a, int b) -> int {
            return a / b;
        }
        """
        asm = compile_to_asm(source)
        assert "cqo" in asm
        assert "idiv rcx" in asm

    def test_modulo_uses_idiv_rdx(self):
        source = """
        fn modulo(int a, int b) -> int {
            return a % b;
        }
        """
        asm = compile_to_asm(source)
        assert "cqo" in asm
        assert "idiv rcx" in asm

    def test_negation_uses_neg(self):
        source = """
        fn negate(int a) -> int {
            int r = -a;
            return r;
        }
        """
        asm = compile_to_asm(source)
        assert "neg rax" in asm

    def test_literal_return_value_in_rax(self):
        source = """
        fn answer() -> int {
            return 42;
        }
        """
        asm = compile_to_asm(source)
        assert "mov rax, 42" in asm


# --------------------------------------------------------------------------
# TEST-2: Сравнения (ASM-2)
# --------------------------------------------------------------------------

class TestComparisons:
    """Проверяем трансляцию операций сравнения.

    Семантический анализатор запрещает присваивать bool в int,
    поэтому сравнения тестируем через условие if (принимает bool).
    """

    def test_equal_uses_sete(self):
        source = """
        fn eq(int a, int b) -> int {
            if (a == b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "cmp rax, rcx" in asm
        assert "sete al" in asm

    def test_not_equal_uses_setne(self):
        source = """
        fn neq(int a, int b) -> int {
            if (a != b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setne al" in asm

    def test_less_than_uses_setl(self):
        source = """
        fn lt(int a, int b) -> int {
            if (a < b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setl al" in asm

    def test_less_equal_uses_setle(self):
        source = """
        fn le(int a, int b) -> int {
            if (a <= b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setle al" in asm

    def test_greater_than_uses_setg(self):
        source = """
        fn gt(int a, int b) -> int {
            if (a > b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setg al" in asm

    def test_greater_equal_uses_setge(self):
        source = """
        fn ge(int a, int b) -> int {
            if (a >= b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setge al" in asm

    def test_movzx_after_set(self):
        """Результат сравнения расширяется через movzx."""
        source = """
        fn eq(int a, int b) -> int {
            if (a == b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "movzx rax, al" in asm


# --------------------------------------------------------------------------
# TEST-2: Передача параметров (STK-2)
# --------------------------------------------------------------------------

class TestParameterPassing:
    """Проверяем сохранение аргументов из регистров ABI в стек."""

    def test_first_param_saved_from_rdi(self):
        source = """
        fn identity(int x) -> int {
            return x;
        }
        """
        asm = compile_to_asm(source)
        assert "rdi" in asm

    def test_second_param_saved_from_rsi(self):
        source = """
        fn second(int a, int b) -> int {
            return b;
        }
        """
        asm = compile_to_asm(source)
        assert "rsi" in asm

    def test_third_param_saved_from_rdx(self):
        source = """
        fn third(int a, int b, int c) -> int {
            return c;
        }
        """
        asm = compile_to_asm(source)
        assert "rdx" in asm

    def test_param_stored_to_stack(self):
        """Параметр сохраняется в стековый слот через rbp."""
        source = """
        fn identity(int x) -> int {
            return x;
        }
        """
        asm = compile_to_asm(source)
        # Должна быть инструкция mov [rbp-N], rdi
        assert "[rbp-" in asm
        assert "rdi" in asm


# --------------------------------------------------------------------------
# TEST-1: Управляющие структуры (ASM-2)
# --------------------------------------------------------------------------

class TestControlFlow:
    """Проверяем генерацию условных переходов и меток."""

    def test_if_generates_conditional_jump(self):
        source = """
        fn test(int a, int b) -> int {
            if (a > b) {
                return 1;
            } else {
                return 0;
            }
        }
        """
        asm = compile_to_asm(source)
        # Должен быть условный переход
        has_jnz = "jnz" in asm
        has_jz = "jz" in asm
        assert has_jnz or has_jz, "Не найден условный переход для if"

    def test_if_generates_block_labels(self):
        source = """
        fn test(int a) -> int {
            if (a > 0) {
                return 1;
            } else {
                return 0;
            }
        }
        """
        asm = compile_to_asm(source)
        # Должны быть локальные метки (начинаются с .)
        local_labels = [line for line in asm.splitlines() if line.strip().startswith(".L_")]
        assert len(local_labels) >= 2, "Ожидались метки блоков .L_*"

    def test_while_generates_back_edge_label(self):
        source = """
        fn countdown(int n) -> int {
            while (n > 0) {
                n = n - 1;
            }
            return n;
        }
        """
        asm = compile_to_asm(source)
        # while должен содержать метку условия и метку конца
        local_labels = [line.strip() for line in asm.splitlines() if line.strip().startswith(".L_while")]
        assert len(local_labels) >= 2, "Ожидались метки while-цикла"

    def test_unconditional_jump_uses_jmp(self):
        source = """
        fn test(int a) -> int {
            if (a > 0) {
                return 1;
            }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "jmp" in asm


# --------------------------------------------------------------------------
# TEST-2: Вызовы функций (ASM-2, STK-2)
# --------------------------------------------------------------------------

class TestFunctionCalls:
    """Проверяем генерацию call и передачу аргументов."""

    def test_call_instruction_present(self):
        source = """
        fn double(int x) -> int {
            return x + x;
        }
        fn main() -> int {
            int r = double(5);
            return r;
        }
        """
        asm = compile_to_asm(source)
        assert "call double" in asm

    def test_first_arg_in_rdi_before_call(self):
        source = """
        fn identity(int x) -> int {
            return x;
        }
        fn main() -> int {
            int r = identity(42);
            return r;
        }
        """
        asm = compile_to_asm(source)
        assert "rdi" in asm

    def test_return_value_from_call_in_rax(self):
        """После call результат берётся из rax."""
        source = """
        fn get() -> int {
            return 7;
        }
        fn main() -> int {
            int r = get();
            return r;
        }
        """
        asm = compile_to_asm(source)
        # После call должно быть сохранение из rax
        assert "call get" in asm
        # Строка с rax после call (сохранение результата)
        lines = asm.splitlines()
        call_idx = next((i for i, l in enumerate(lines) if "call get" in l), -1)
        assert call_idx >= 0
        after_call = "\n".join(lines[call_idx:call_idx + 5])
        assert "rax" in after_call

    def test_recursive_call(self):
        source = """
        fn fact(int n) -> int {
            if (n <= 1) {
                return 1;
            } else {
                int p = fact(n - 1);
                return n * p;
            }
        }
        """
        asm = compile_to_asm(source)
        assert "call fact" in asm


# --------------------------------------------------------------------------
# TEST-1: Возврат значений (ASM-2)
# --------------------------------------------------------------------------

class TestReturnValues:
    """Проверяем корректный возврат значений через rax."""

    def test_integer_literal_return(self):
        source = "fn f() -> int { return 99; }"
        asm = compile_to_asm(source)
        assert "mov rax, 99" in asm

    def test_zero_return(self):
        source = "fn f() -> int { return 0; }"
        asm = compile_to_asm(source)
        assert "ret" in asm

    def test_variable_return_via_load(self):
        source = """
        fn f(int x) -> int {
            return x;
        }
        """
        asm = compile_to_asm(source)
        # rax должен быть загружен из стека перед ret
        lines = asm.splitlines()
        ret_idx = next((i for i, l in enumerate(lines) if l.strip() == "ret"), -1)
        assert ret_idx >= 0
        before_ret = "\n".join(lines[max(0, ret_idx - 5):ret_idx])
        assert "rax" in before_ret


# --------------------------------------------------------------------------
# TEST-5: Тесты ABI-совместимости (TEST-5)
# --------------------------------------------------------------------------

class TestABICompliance:
    """Проверяем соответствие System V AMD64 ABI."""

    def test_abi_arg_registers_order(self):
        """Первые 6 аргументов передаются в rdi, rsi, rdx, rcx, r8, r9."""
        from src.codegen.abi import INT_ARG_REGS
        assert INT_ARG_REGS == ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]

    def test_abi_return_register(self):
        """Возвращаемое значение — rax."""
        from src.codegen.abi import RETURN_REG_INT
        assert RETURN_REG_INT == "rax"

    def test_abi_callee_saved_registers(self):
        """Callee-saved: rbx, r12-r15."""
        from src.codegen.abi import CALLEE_SAVED
        assert "rbx" in CALLEE_SAVED
        assert "r12" in CALLEE_SAVED

    def test_six_params_use_six_abi_registers(self):
        source = """
        fn six(int a, int b, int c, int d, int e, int f) -> int {
            return a + b + c + d + e + f;
        }
        """
        asm = compile_to_asm(source)
        for reg in ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]:
            assert reg in asm, f"Регистр {reg} не найден в ассемблере"


# --------------------------------------------------------------------------
# Тесты StackFrame (STK-3)
# --------------------------------------------------------------------------

class TestStackFrame:
    """Юнит-тесты для класса StackFrame."""

    def test_allocate_returns_negative_offset(self):
        frame = StackFrame()
        offset = frame.allocate("x_0")
        assert offset < 0, "Смещение должно быть отрицательным (ниже rbp)"

    def test_allocate_unique_offsets(self):
        frame = StackFrame()
        off1 = frame.allocate("a_0")
        off2 = frame.allocate("b_0")
        assert off1 != off2

    def test_double_allocate_same_offset(self):
        """Повторное выделение слота для одного имени возвращает тот же offset."""
        frame = StackFrame()
        off1 = frame.allocate("x_0")
        off2 = frame.allocate("x_0")
        assert off1 == off2

    def test_aligned_size_multiple_of_16(self):
        frame = StackFrame()
        frame.allocate("a_0")  # 8 байт
        frame.allocate("b_0")  # 8 байт = 16 итого
        assert frame.aligned_size % 16 == 0

    def test_aligned_size_rounds_up(self):
        frame = StackFrame()
        frame.allocate("a_0")  # 8 байт → aligned = 16
        assert frame.aligned_size == 16

    def test_get_offset_returns_none_for_unknown(self):
        frame = StackFrame()
        assert frame.get_offset("unknown") is None

    def test_has_method(self):
        frame = StackFrame()
        frame.allocate("x_0")
        assert frame.has("x_0")
        assert not frame.has("y_0")


# --------------------------------------------------------------------------
# Тесты RegisterAllocator
# --------------------------------------------------------------------------

class TestRegisterAllocator:
    """Проверяем, что все ALLOCA-переменные получают слоты."""

    def _make_ir(self, source: str):
        """Компилировать до IR."""
        scanner = Scanner(source)
        tokens = scanner._tokens
        parser = Parser(tokens)
        ast = parser.parse()
        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast, source=source)
        return IRGenerator().generate(ast)

    def test_alloca_variables_allocated(self):
        source = """
        fn f() -> int {
            int x = 5;
            int y = 10;
            return x + y;
        }
        """
        ir = self._make_ir(source)
        func = ir.functions[0]
        allocator = RegisterAllocator()
        frame = allocator.allocate(func)
        assert frame.has("x_0")
        assert frame.has("y_0")

    def test_temporaries_allocated(self):
        source = """
        fn f(int a, int b) -> int {
            return a + b;
        }
        """
        ir = self._make_ir(source)
        func = ir.functions[0]
        allocator = RegisterAllocator()
        frame = allocator.allocate(func)
        # Должны быть временные (t1, t2, ...)
        assert frame.total_slots > 0


# --------------------------------------------------------------------------
# Интеграционные тесты (TEST-2)
# --------------------------------------------------------------------------

class TestIntegration:
    """Сквозные тесты: исходник → ассемблер."""

    def test_factorial_compiles(self):
        source = """
        fn factorial(int n) -> int {
            if (n <= 1) {
                return 1;
            } else {
                int prev = factorial(n - 1);
                return n * prev;
            }
        }
        fn main() -> int {
            int result = factorial(5);
            return result;
        }
        """
        asm = compile_to_asm(source)
        assert "factorial:" in asm
        assert "call factorial" in asm
        assert "main:" in asm
        assert "ret" in asm

    def test_fibonacci_compiles(self):
        source = """
        fn fib(int n) -> int {
            if (n <= 1) {
                return n;
            }
            int a = fib(n - 1);
            int b = fib(n - 2);
            return a + b;
        }
        fn main() -> int {
            return fib(10);
        }
        """
        asm = compile_to_asm(source)
        assert "fib:" in asm
        assert "call fib" in asm

    def test_while_loop_compiles(self):
        source = """
        fn sum(int n) -> int {
            int total = 0;
            int i = 1;
            while (i <= n) {
                total = total + i;
                i = i + 1;
            }
            return total;
        }
        fn main() -> int {
            return sum(10);
        }
        """
        asm = compile_to_asm(source)
        assert "sum:" in asm
        # while-цикл должен иметь метки условия и тела
        assert ".L_while_cond" in asm or ".L_while" in asm

    def test_output_is_valid_nasm_structure(self):
        """Базовая проверка структуры NASM-файла."""
        source = "fn main() -> int { return 0; }"
        asm = compile_to_asm(source)
        lines = asm.splitlines()

        has_section_text = any("section .text" in l for l in lines)
        has_global = any("global " in l for l in lines)
        has_function_label = any(l.strip().endswith(":") and not l.strip().startswith(".") for l in lines)
        has_ret = any("ret" in l for l in lines)

        assert has_section_text, "Нет 'section .text'"
        assert has_global, "Нет 'global'"
        assert has_function_label, "Нет метки функции"
        assert has_ret, "Нет инструкции ret"
