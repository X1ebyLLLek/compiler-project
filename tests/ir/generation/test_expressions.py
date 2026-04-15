"""
Тесты генерации IR для выражений (Sprint 4).

Проверяем, что IR-генератор корректно транслирует:
- литералы
- идентификаторы
- бинарные арифметические выражения
- бинарные логические выражения
- операции сравнения
- унарные операции
- вызовы функций
- присваивание и составное присваивание
"""

import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.ir.ir_instructions import IROpcode, TempOperand, LiteralOperand, VarOperand
from src.ir.control_flow import IRProgram


# --------------------------------------------------------------------------
# Вспомогательная функция: компилируем строку кода и получаем IRProgram
# --------------------------------------------------------------------------

def compile_to_ir(source: str) -> IRProgram:
    """Полный цикл: исходник → токены → AST → семантика → IR."""
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
    return ir_program


def get_opcodes(ir_program: IRProgram, func_name: str = "main") -> list:
    """Получить список опкодов всех инструкций заданной функции."""
    func = ir_program.get_function(func_name)
    assert func is not None, f"Функция '{func_name}' не найдена в IR"
    opcodes = []
    for block in func.cfg.blocks:
        for instr in block.instructions:
            opcodes.append(instr.opcode)
    return opcodes


# --------------------------------------------------------------------------
# Тест 1: Литерал int
# --------------------------------------------------------------------------

class TestLiterals:
    """Тесты трансляции литеральных выражений."""

    def test_int_literal_no_extra_instrs(self):
        """Литерал в return не должен генерировать LOAD."""
        source = """
        fn main() -> int {
            return 42;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        # Должен быть RETURN, но не LOAD (константа не требует загрузки)
        assert IROpcode.RETURN in opcodes
        assert IROpcode.LOAD not in opcodes

    def test_bool_literal(self):
        """Присваивание bool-литерала генерирует ALLOCA + STORE."""
        source = """
        fn main() -> int {
            bool flag = true;
            return 0;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.ALLOCA in opcodes
        assert IROpcode.STORE in opcodes

    def test_float_literal(self):
        """Присваивание float-литерала."""
        source = """
        fn main() -> int {
            float x = 3.14;
            return 0;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.ALLOCA in opcodes
        assert IROpcode.STORE in opcodes


# --------------------------------------------------------------------------
# Тест 2: Идентификаторы (переменные)
# --------------------------------------------------------------------------

class TestIdentifiers:
    """Тесты обращения к переменным."""

    def test_var_load_on_use(self):
        """При использовании переменной в выражении генерируется LOAD."""
        source = """
        fn main() -> int {
            int x = 10;
            return x;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.LOAD in opcodes

    def test_var_decl_generates_alloca(self):
        """Объявление переменной генерирует ALLOCA."""
        source = """
        fn main() -> int {
            int counter = 0;
            int total = 0;
            return 0;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        # По одному ALLOCA на каждую переменную
        alloca_count = opcodes.count(IROpcode.ALLOCA)
        assert alloca_count >= 2


# --------------------------------------------------------------------------
# Тест 3: Бинарные арифметические выражения
# --------------------------------------------------------------------------

class TestArithmeticExpressions:
    """Тесты трансляции арифметических операций."""

    def test_addition(self):
        """a + b → ADD t1, t2, t3"""
        source = """
        fn main() -> int {
            int a = 2;
            int b = 3;
            int c = a + b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.ADD in opcodes

    def test_subtraction(self):
        """a - b → SUB"""
        source = """
        fn main() -> int {
            int a = 10;
            int b = 3;
            int c = a - b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.SUB in get_opcodes(ir)

    def test_multiplication(self):
        """a * b → MUL"""
        source = """
        fn main() -> int {
            int a = 4;
            int b = 5;
            int c = a * b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.MUL in get_opcodes(ir)

    def test_division(self):
        """a / b → DIV"""
        source = """
        fn main() -> int {
            int a = 10;
            int b = 2;
            int c = a / b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.DIV in get_opcodes(ir)

    def test_modulo(self):
        """a % b → MOD"""
        source = """
        fn main() -> int {
            int a = 10;
            int b = 3;
            int c = a % b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.MOD in get_opcodes(ir)

    def test_complex_arithmetic(self):
        """(a + b) * c — несколько инструкций в правильном порядке."""
        source = """
        fn main() -> int {
            int a = 2;
            int b = 3;
            int c = 4;
            int d = (a + b) * c;
            return d;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        # Должны быть и ADD и MUL
        assert IROpcode.ADD in opcodes
        assert IROpcode.MUL in opcodes


# --------------------------------------------------------------------------
# Тест 4: Логические операции и сравнения
# --------------------------------------------------------------------------

class TestLogicalAndComparisonExpressions:
    """Тесты логических операций и операций сравнения."""

    def test_comparison_less_equal(self):
        """n <= 1 → CMP_LE"""
        source = """
        fn check(int n) -> bool {
            return n <= 1;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "check")
        assert IROpcode.CMP_LE in opcodes

    def test_comparison_greater(self):
        """a > b → CMP_GT"""
        source = """
        fn check(int a, int b) -> bool {
            return a > b;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        assert IROpcode.CMP_GT in get_opcodes(ir, "check")

    def test_comparison_equal(self):
        """a == b → CMP_EQ"""
        source = """
        fn equal(int a, int b) -> bool {
            return a == b;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        assert IROpcode.CMP_EQ in get_opcodes(ir, "equal")

    def test_logical_and(self):
        """a && b → AND"""
        source = """
        fn main() -> int {
            bool a = true;
            bool b = false;
            bool c = a && b;
            return 0;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.AND in get_opcodes(ir)

    def test_logical_or(self):
        """a || b → OR"""
        source = """
        fn main() -> int {
            bool a = true;
            bool b = false;
            bool c = a || b;
            return 0;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.OR in get_opcodes(ir)


# --------------------------------------------------------------------------
# Тест 5: Унарные операции
# --------------------------------------------------------------------------

class TestUnaryExpressions:
    """Тесты унарных операций."""

    def test_negation(self):
        """-x → NEG"""
        source = """
        fn main() -> int {
            int x = 5;
            int y = -x;
            return y;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.NEG in get_opcodes(ir)

    def test_logical_not(self):
        """!flag → NOT"""
        source = """
        fn main() -> int {
            bool flag = true;
            bool result = !flag;
            return 0;
        }
        """
        ir = compile_to_ir(source)
        assert IROpcode.NOT in get_opcodes(ir)


# --------------------------------------------------------------------------
# Тест 6: Присваивание
# --------------------------------------------------------------------------

class TestAssignment:
    """Тесты трансляции операций присваивания."""

    def test_simple_assignment(self):
        """x = expr → STORE"""
        source = """
        fn main() -> int {
            int x = 0;
            x = 42;
            return x;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        store_count = opcodes.count(IROpcode.STORE)
        # Первый STORE — инициализация, второй — присваивание
        assert store_count >= 2

    def test_compound_add_assignment(self):
        """x += n → LOAD + ADD + STORE"""
        source = """
        fn main() -> int {
            int x = 10;
            x += 5;
            return x;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.LOAD in opcodes
        assert IROpcode.ADD in opcodes
        assert IROpcode.STORE in opcodes

    def test_compound_sub_assignment(self):
        """x -= n → LOAD + SUB + STORE"""
        source = """
        fn main() -> int {
            int x = 10;
            x -= 3;
            return x;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.SUB in opcodes


# --------------------------------------------------------------------------
# Тест 7: Вызов функции
# --------------------------------------------------------------------------

class TestFunctionCall:
    """Тесты трансляции вызовов функций."""

    def test_function_call_generates_call_instr(self):
        """Вызов функции → PARAM + CALL."""
        source = """
        fn add(int a, int b) -> int {
            return a + b;
        }
        fn main() -> int {
            int result = add(3, 4);
            return result;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "main")
        assert IROpcode.CALL in opcodes
        assert IROpcode.PARAM in opcodes

    def test_function_call_param_count(self):
        """Количество PARAM соответствует количеству аргументов."""
        source = """
        fn f(int a, int b, int c) -> int {
            return a + b + c;
        }
        fn main() -> int {
            return f(1, 2, 3);
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "main")
        param_count = opcodes.count(IROpcode.PARAM)
        # 3 аргумента → 3 PARAM
        assert param_count == 3

    def test_no_arg_function_call(self):
        """Вызов без аргументов — только CALL, без PARAM."""
        source = """
        fn greet() -> int {
            return 0;
        }
        fn main() -> int {
            return greet();
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir, "main")
        assert IROpcode.CALL in opcodes
        # Параметров нет
        assert opcodes.count(IROpcode.PARAM) == 0
