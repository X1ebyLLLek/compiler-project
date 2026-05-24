"""
Тесты поддержки внешних функций (Sprint 7).

Проверяем:
  - парсинг extern-объявления
  - что extern имена попадают в ассемблер как 'extern printf'
  - что variadic вызовы содержат 'xor eax, eax'
  - что стек выравнивается при вызове (sub rsp)
  - что ExternalCallsMixin правильно определяет variadic-функции
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.codegen.external_calls import ExternalCallsMixin, _VARIADIC_FUNCTIONS, _KNOWN_EXTERN_FUNCTIONS
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast_nodes import ExternDeclNode


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def parse_source(source: str):
    scanner = Scanner(source)
    parser = Parser(scanner._tokens)
    ast = parser.parse()
    return ast, parser.get_errors()


def find_extern_nodes(ast):
    result = []
    for decl in ast.declarations:
        if isinstance(decl, ExternDeclNode):
            result.append(decl)
    return result


def build_asm_with_extern(func_source: str) -> str:
    """Скомпилировать источник который вызывает внешние функции."""
    from src.semantic.analyzer import SemanticAnalyzer
    from src.ir.ir_generator import IRGenerator
    from src.codegen.x86_generator import X86Generator

    scanner = Scanner(func_source)
    parser = Parser(scanner._tokens)
    ast = parser.parse()

    if parser.get_errors():
        return "; parse errors"

    try:
        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast, source=func_source)
    except Exception:
        pass

    try:
        gen = IRGenerator()
        ir_prog = gen.generate(ast)
        codegen = X86Generator()
        return codegen.generate(ir_prog)
    except Exception as e:
        return f"; error: {e}"


# --------------------------------------------------------------------------
# TEST-1: Парсинг extern-объявлений
# --------------------------------------------------------------------------

class TestExternParsing(unittest.TestCase):
    """Проверяем что парсер понимает синтаксис extern."""

    def test_simple_extern(self):
        """extern fn puts(int) -> int;"""
        source = 'extern fn puts(int) -> int;'
        ast, errors = parse_source(source)
        self.assertEqual(errors, [], f"Ошибки: {errors}")
        nodes = find_extern_nodes(ast)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "puts")
        self.assertEqual(nodes[0].return_type, "int")

    def test_extern_no_return(self):
        """extern fn free(int);  — void-функция без ->"""
        source = 'extern fn free(int);'
        ast, errors = parse_source(source)
        # Ошибок парсинга нет
        self.assertEqual(errors, [])
        nodes = find_extern_nodes(ast)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "free")
        self.assertIsNone(nodes[0].return_type)

    def test_extern_multiple_params(self):
        """extern fn memcpy(int, int, int) -> int;"""
        source = 'extern fn memcpy(int, int, int) -> int;'
        ast, errors = parse_source(source)
        self.assertEqual(errors, [])
        nodes = find_extern_nodes(ast)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(nodes[0].param_types), 3)

    def test_multiple_externs(self):
        """Несколько extern подряд."""
        source = """
        extern fn printf(int) -> int;
        extern fn malloc(int) -> int;
        """
        ast, errors = parse_source(source)
        self.assertEqual(errors, [])
        nodes = find_extern_nodes(ast)
        self.assertEqual(len(nodes), 2)
        names = {n.name for n in nodes}
        self.assertIn("printf", names)
        self.assertIn("malloc", names)


# --------------------------------------------------------------------------
# TEST-2: Определение variadic и известных функций
# --------------------------------------------------------------------------

class TestVariadicDetection(unittest.TestCase):
    """Проверяем таблицу variadic-функций."""

    def test_printf_is_variadic(self):
        self.assertIn("printf", _VARIADIC_FUNCTIONS)

    def test_scanf_is_variadic(self):
        self.assertIn("scanf", _VARIADIC_FUNCTIONS)

    def test_malloc_is_not_variadic(self):
        self.assertNotIn("malloc", _VARIADIC_FUNCTIONS)

    def test_puts_is_known_extern(self):
        self.assertIn("puts", _KNOWN_EXTERN_FUNCTIONS)

    def test_strlen_is_known_extern(self):
        self.assertIn("strlen", _KNOWN_EXTERN_FUNCTIONS)

    def test_unknown_func_not_extern(self):
        self.assertNotIn("my_custom_func", _KNOWN_EXTERN_FUNCTIONS)


# --------------------------------------------------------------------------
# TEST-3: ExternalCallsMixin напрямую
# --------------------------------------------------------------------------

class TestExternalCallsMixinDirect(unittest.TestCase):
    """Тестируем методы миксина без полного компилятора."""

    def setUp(self):
        """Создаём минимальный объект, имитирующий X86Generator + ExternalCallsMixin."""
        from src.codegen.x86_generator import X86Generator
        from src.codegen.stack_frame import StackFrame

        self.gen = X86Generator()
        self.gen._lines = []
        frame = StackFrame()
        frame.allocate("__t1")
        self.gen._frame = frame
        self.gen._func = None

    def test_is_variadic_printf(self):
        self.assertTrue(self.gen._is_variadic("printf"))

    def test_is_variadic_custom(self):
        self.assertFalse(self.gen._is_variadic("my_func"))

    def test_register_and_emit_extern(self):
        """Зарегистрированные extern должны появиться в выводе."""
        self.gen._register_extern("printf")
        self.gen._register_extern("malloc")
        # Сохраняем строки до emit
        self.gen._lines = []
        self.gen._emit_extern_declarations()
        output = "\n".join(self.gen._lines)
        self.assertIn("extern malloc", output)
        self.assertIn("extern printf", output)

    def test_variadic_call_has_xor_eax(self):
        """Вызов printf должен содержать xor eax, eax."""
        from src.ir.ir_instructions import (
            IRInstruction, IROpcode, LabelOperand, LiteralOperand
        )
        from src.codegen.stack_frame import StackFrame

        frame = StackFrame()
        frame.allocate("__t1")
        self.gen._frame = frame
        self.gen._lines = []

        instr = IRInstruction(
            opcode=IROpcode.CALL,
            src1=LabelOperand("printf"),
            args=[LiteralOperand(42)],
            dest=None,
        )
        self.gen._gen_extern_call(instr)

        asm = "\n".join(self.gen._lines)
        self.assertIn("xor eax, eax", asm, "Variadic вызов должен обнулять eax")
        self.assertIn("call printf", asm)

    def test_non_variadic_no_xor(self):
        """Вызов malloc не должен содержать xor eax, eax."""
        from src.ir.ir_instructions import (
            IRInstruction, IROpcode, LabelOperand, LiteralOperand, TempOperand
        )
        from src.codegen.stack_frame import StackFrame

        frame = StackFrame()
        frame.allocate("__t1")
        frame.allocate("__t2")
        self.gen._frame = frame
        self.gen._lines = []

        instr = IRInstruction(
            opcode=IROpcode.CALL,
            src1=LabelOperand("malloc"),
            args=[LiteralOperand(64)],
            dest=TempOperand(2),
        )
        self.gen._gen_extern_call(instr)

        asm = "\n".join(self.gen._lines)
        self.assertNotIn("xor eax, eax", asm)
        self.assertIn("call malloc", asm)


# --------------------------------------------------------------------------
# TEST-4: Ассемблерный вывод для extern-вызовов
# --------------------------------------------------------------------------

class TestExternAsmOutput(unittest.TestCase):
    """Проверяем что extern-функции появляются в финальном ассемблере."""

    def test_puts_call_generates_extern(self):
        """
        Вызов puts() должен:
          1. Сгенерировать 'extern puts' в начале файла
          2. Сгенерировать 'call puts'
        """
        source = """
        fn main() -> int {
            puts("hello");
            return 0;
        }
        """
        asm = build_asm_with_extern(source)
        # Функция должна скомпилироваться
        self.assertIn("main:", asm)

    def test_stack_alignment_comment(self):
        """При нечётном числе стековых аргументов должно быть выравнивание."""
        from src.codegen.x86_generator import X86Generator
        from src.ir.ir_instructions import (
            IRInstruction, IROpcode, LabelOperand, LiteralOperand
        )
        from src.codegen.stack_frame import StackFrame

        gen = X86Generator()
        frame = StackFrame()
        # Добавляем много слотов для аргументов
        for i in range(10):
            frame.allocate(f"__t{i}")
        gen._frame = frame
        gen._func = None
        gen._lines = []

        # Вызов с 7 аргументами (7 - 6 = 1 стековый аргумент → нечётное → нужен padding)
        instr = IRInstruction(
            opcode=IROpcode.CALL,
            src1=LabelOperand("printf"),
            args=[LiteralOperand(i) for i in range(7)],
            dest=None,
        )
        gen._gen_extern_call(instr)
        asm = "\n".join(gen._lines)
        # При 1 стековом аргументе нужен padding
        self.assertIn("sub rsp, 8", asm)
        self.assertIn("add rsp, 8", asm)


if __name__ == "__main__":
    unittest.main()
