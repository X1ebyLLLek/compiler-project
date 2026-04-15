"""
Тесты генерации IR для функций и интеграционные тесты (Sprint 4).

Проверяем:
- параметры функции → ALLOCA + PARAM
- вызов рекурсивных функций
- множество функций в одной программе
- полный цикл: source → AST → IR
- сохранение семантики
"""

import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.ir.ir_instructions import IROpcode
from src.ir.control_flow import IRProgram, IRFunction


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def compile_to_ir(source: str) -> IRProgram:
    """Полный цикл компиляции до IR."""
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
    return generator.generate(ast)


def get_opcodes(ir_program: IRProgram, func_name: str) -> list:
    func = ir_program.get_function(func_name)
    assert func is not None, f"Функция '{func_name}' не найдена"
    result = []
    for block in func.cfg.blocks:
        for instr in block.instructions:
            result.append(instr.opcode)
    return result


# --------------------------------------------------------------------------
# Тест 1: Параметры функций
# --------------------------------------------------------------------------

class TestFunctionParameters:
    """Тесты трансляции параметров функций."""

    def test_params_generate_alloca(self):
        """Каждый параметр функции генерирует ALLOCA."""
        source = """
        fn add(int a, int b) -> int {
            return a + b;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "add")
        alloca_count = opcodes.count(IROpcode.ALLOCA)
        # 2 параметра → минимум 2 ALLOCA
        assert alloca_count >= 2

    def test_params_generate_param_instructions(self):
        """Параметры функции генерируют PARAM-инструкции в entry."""
        source = """
        fn multiply(int x, int y) -> int {
            return x * y;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("multiply")
        entry = func.cfg.entry_block
        assert entry is not None

        param_instrs = [i for i in entry.instructions
                        if i.opcode == IROpcode.PARAM]
        assert len(param_instrs) == 2, (
            f"Ожидалось 2 PARAM, найдено: {len(param_instrs)}"
        )

    def test_single_param(self):
        """Функция с одним параметром."""
        source = """
        fn double(int n) -> int {
            return n * 2;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "double")
        assert IROpcode.ALLOCA in opcodes
        assert IROpcode.PARAM in opcodes


# --------------------------------------------------------------------------
# Тест 2: Несколько функций в программе
# --------------------------------------------------------------------------

class TestMultipleFunctions:
    """Тесты обработки нескольких функций."""

    def test_all_functions_in_ir(self):
        """Все функции программы присутствуют в IRProgram."""
        source = """
        fn foo() -> int { return 1; }
        fn bar() -> int { return 2; }
        fn baz() -> int { return 3; }
        fn main() -> int { return foo() + bar() + baz(); }
        """
        ir = compile_to_ir(source)
        assert ir.get_function("foo") is not None
        assert ir.get_function("bar") is not None
        assert ir.get_function("baz") is not None
        assert ir.get_function("main") is not None

    def test_function_count(self):
        """Количество функций в IRProgram."""
        source = """
        fn f1() -> int { return 1; }
        fn f2() -> int { return 2; }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        assert len(ir.functions) == 3

    def test_each_function_has_entry_block(self):
        """У каждой функции есть входной блок."""
        source = """
        fn helper(int x) -> int { return x + 1; }
        fn main() -> int {
            return helper(5);
        }
        """
        ir = compile_to_ir(source)
        for func in ir.functions:
            assert func.cfg.entry_block is not None, (
                f"Функция '{func.name}' не имеет entry-блока"
            )


# --------------------------------------------------------------------------
# Тест 3: Рекурсивные функции
# --------------------------------------------------------------------------

class TestRecursion:
    """Тесты трансляции рекурсивных вызовов."""

    def test_recursive_function_generates_call(self):
        """Рекурсивный вызов генерирует CALL инструкцию."""
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
            return factorial(5);
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "factorial")
        assert IROpcode.CALL in opcodes

    def test_recursive_function_has_base_case_return(self):
        """Рекурсивная функция имеет RETURN."""
        source = """
        fn factorial(int n) -> int {
            if (n <= 1) {
                return 1;
            } else {
                int prev = factorial(n - 1);
                return n * prev;
            }
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "factorial")
        assert IROpcode.RETURN in opcodes


# --------------------------------------------------------------------------
# Тест 4: Интеграционные тесты (source → IR)
# --------------------------------------------------------------------------

class TestIntegration:
    """Интеграционные тесты полного конвейера."""

    def test_factorial_func_example(self):
        """Тест на реальном примере factorial_func.src."""
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
            int x = result + 10;
            return x;
        }
        """
        ir = compile_to_ir(source)
        assert len(ir.functions) == 2
        factorial_f = ir.get_function("factorial")
        assert factorial_f is not None
        assert factorial_f.cfg.block_count() >= 3  # entry + then + else + endif

    def test_while_loop_example(self):
        """Тест цикла while — полный конвейер."""
        source = """
        fn count_down(int n) -> int {
            int result = 0;
            while (n > 0) {
                result += n;
                n -= 1;
            }
            return result;
        }

        fn main() -> int {
            return count_down(5);
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("count_down")
        assert func is not None
        # Наличие блоков цикла
        labels = [b.label for b in func.cfg.blocks]
        assert any("while" in lb for lb in labels)

    def test_ir_dump_not_empty(self):
        """Дамп IP программы не пустой."""
        source = """
        fn main() -> int {
            int x = 2 * 3 + 4;
            return x;
        }
        """
        ir = compile_to_ir(source)
        dump = ir.dump()
        assert len(dump) > 0
        assert "main" in dump

    def test_ir_json_serialization(self):
        """IR-программа сериализуется в корректный JSON."""
        import json
        source = """
        fn main() -> int {
            int x = 5;
            return x;
        }
        """
        ir = compile_to_ir(source)
        json_str = ir.to_json()
        parsed = json.loads(json_str)
        assert "program" in parsed
        assert len(parsed["program"]) >= 1
        main_func = parsed["program"][0]
        assert main_func["name"] == "main"

    def test_ir_stats(self):
        """Статистика IR содержит корректные счётчики."""
        source = """
        fn main() -> int {
            int a = 1;
            int b = 2;
            int c = a + b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        stats = ir.stats()
        assert stats["functions"] == 1
        assert stats["total_blocks"] >= 1
        assert stats["total_instructions"] >= 1

    def test_hello_example_compiles(self):
        """Классический пример hello.src компилируется в IR без ошибок."""
        source = """
        fn main() {
            int counter = 42;
            float pi = 3.1415;
            if (counter >= 40 && true != false) {
                counter += 1;
            }
        }
        """
        ir = compile_to_ir(source)
        assert ir is not None
        main_f = ir.get_function("main")
        assert main_f is not None
        assert main_f.cfg.block_count() >= 3
