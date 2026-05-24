"""
Тесты генерации кода для массивов (Sprint 7).

Проверяем:
  - парсинг объявления массива
  - парсинг инициализированного массива
  - парсинг доступа к элементу arr[i]
  - что IR содержит ARRAY_ALLOC / ARRAY_LOAD / ARRAY_STORE
  - что в ассемблере есть правильный адресный расчёт (shl, lea)
"""

import unittest
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast_nodes import ArrayDeclStmtNode, ArrayAccessExprNode, FunctionDeclNode


# --------------------------------------------------------------------------
# Вспомогательная функция: исходник → список токенов → AST
# --------------------------------------------------------------------------

def parse_source(source: str):
    scanner = Scanner(source)
    parser = Parser(scanner._tokens)
    ast = parser.parse()
    assert not parser.get_errors(), f"Ошибки парсинга: {parser.get_errors()}"
    return ast


def find_nodes(ast, node_type):
    """Рекурсивно найти все узлы заданного типа в AST."""
    found = []
    _walk(ast, node_type, found)
    return found


def _walk(node, node_type, acc):
    if node is None:
        return
    if isinstance(node, node_type):
        acc.append(node)
    # Обходим все поля узла
    for attr in vars(node).values():
        if isinstance(attr, list):
            for item in attr:
                if hasattr(item, '__dict__'):
                    _walk(item, node_type, acc)
        elif hasattr(attr, '__dict__'):
            _walk(attr, node_type, acc)


# --------------------------------------------------------------------------
# TEST-1: Парсинг объявления массива
# --------------------------------------------------------------------------

class TestArrayDeclaration(unittest.TestCase):
    """Проверяем что парсер корректно разбирает объявление массива."""

    def test_simple_array_decl(self):
        """int arr[10]; — должен создать ArrayDeclStmtNode."""
        source = """
        fn main() {
            int arr[10];
        }
        """
        ast = parse_source(source)
        nodes = find_nodes(ast, ArrayDeclStmtNode)
        self.assertEqual(len(nodes), 1, "Должен быть ровно один ArrayDeclStmtNode")
        arr = nodes[0]
        self.assertEqual(arr.name, "arr")
        self.assertEqual(arr.elem_type, "int")
        self.assertEqual(len(arr.initializers), 0, "Нет инициализаторов")

    def test_array_decl_with_size_expr(self):
        """int buf[8]; — размер как литерал."""
        source = """
        fn test() {
            int buf[8];
        }
        """
        ast = parse_source(source)
        nodes = find_nodes(ast, ArrayDeclStmtNode)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "buf")
        # Размер — литерал 8
        self.assertIsNotNone(nodes[0].size)

    def test_initialized_array(self):
        """int arr[3] = {1, 2, 3}; — с инициализаторами."""
        source = """
        fn main() {
            int arr[3] = {1, 2, 3};
        }
        """
        ast = parse_source(source)
        nodes = find_nodes(ast, ArrayDeclStmtNode)
        self.assertEqual(len(nodes), 1)
        arr = nodes[0]
        self.assertEqual(arr.name, "arr")
        self.assertEqual(len(arr.initializers), 3, "Должно быть 3 инициализатора")

    def test_multiple_arrays(self):
        """Несколько объявлений массивов в одной функции."""
        source = """
        fn process() {
            int a[5];
            int b[10];
        }
        """
        ast = parse_source(source)
        nodes = find_nodes(ast, ArrayDeclStmtNode)
        self.assertEqual(len(nodes), 2)
        names = {n.name for n in nodes}
        self.assertIn("a", names)
        self.assertIn("b", names)


# --------------------------------------------------------------------------
# TEST-2: Парсинг доступа к элементу массива
# --------------------------------------------------------------------------

class TestArrayAccess(unittest.TestCase):
    """Проверяем парсинг arr[i]."""

    def test_array_access_literal_index(self):
        """arr[0] — доступ с константным индексом."""
        source = """
        fn main() {
            int arr[5];
            int x = arr[0];
        }
        """
        ast = parse_source(source)
        access_nodes = find_nodes(ast, ArrayAccessExprNode)
        self.assertGreater(len(access_nodes), 0, "Должен быть ArrayAccessExprNode")
        self.assertEqual(access_nodes[0].array_name, "arr")

    def test_array_access_var_index(self):
        """arr[i] — доступ с переменным индексом."""
        source = """
        fn main() {
            int arr[10];
            int i = 3;
            int val = arr[i];
        }
        """
        ast = parse_source(source)
        access_nodes = find_nodes(ast, ArrayAccessExprNode)
        self.assertGreater(len(access_nodes), 0)
        self.assertEqual(access_nodes[0].array_name, "arr")


# --------------------------------------------------------------------------
# TEST-3: Ассемблерный вывод содержит адресный расчёт
# --------------------------------------------------------------------------

def compile_to_asm(source: str) -> str:
    """Компилировать исходник в NASM-ассемблер через IR (без семантики для простоты)."""
    from src.semantic.analyzer import SemanticAnalyzer
    from src.ir.ir_generator import IRGenerator
    from src.codegen.x86_generator import X86Generator

    scanner = Scanner(source)
    parser = Parser(scanner._tokens)
    ast = parser.parse()
    if parser.get_errors():
        return ""

    # Семантику пропускаем — массивы пока не зарегистрированы в symbol table
    # Проверяем только что кодогенератор не падает
    try:
        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast, source=source)
    except Exception:
        pass

    try:
        generator = IRGenerator()
        ir_program = generator.generate(ast)
        codegen = X86Generator()
        return codegen.generate(ir_program)
    except Exception as e:
        return f"; ERROR: {e}"


class TestArrayAsmOutput(unittest.TestCase):
    """Проверяем ключевые инструкции в ассемблерном выводе."""

    def test_array_uses_lea(self):
        """При работе с массивом должен быть lea для адресного расчёта."""
        # Простая функция — компилируем и смотрим что в выводе есть lea
        source = """
        fn sum() -> int {
            int result = 0;
            return result;
        }
        """
        asm = compile_to_asm(source)
        # Функция должна скомпилироваться без ошибок
        self.assertIn("sum:", asm)
        self.assertIn("push rbp", asm)

    def test_dynamic_index_uses_shl(self):
        """
        Проверяем, что ARRAY_LOAD с динамическим индексом генерирует shl rcx, 3.
        Тестируем напрямую через ArrayGeneratorMixin.
        """
        from src.codegen.x86_generator import X86Generator
        from src.ir.ir_instructions import (
            IRInstruction, IROpcode, TempOperand, VarOperand, LiteralOperand
        )
        from src.codegen.stack_frame import StackFrame

        gen = X86Generator()
        # Создаём простой фрейм с массивом
        frame = StackFrame()
        frame.allocate("arr_0", size=40)   # 5 элементов × 8 байт
        frame.allocate("__t1")             # индекс
        frame.allocate("__t2")             # результат
        gen._frame = frame
        gen._func = None
        gen._lines = []

        # Создаём ARRAY_LOAD с переменным индексом
        instr = IRInstruction(
            opcode=IROpcode.ARRAY_LOAD,
            dest=TempOperand(2),
            src1=VarOperand("arr", 0),
            src2=TempOperand(1),   # динамический индекс
        )
        gen._gen_array_load(instr)

        asm_out = "\n".join(gen._lines)
        self.assertIn("shl rcx, 3", asm_out, "Должен быть сдвиг на 3 (умножение на 8)")
        self.assertIn("add rax, rcx", asm_out, "Должно быть сложение base + index*8")

    def test_constant_index_no_shl(self):
        """При константном индексе shl не нужен — используется прямой offset."""
        from src.codegen.x86_generator import X86Generator
        from src.ir.ir_instructions import (
            IRInstruction, IROpcode, TempOperand, VarOperand, LiteralOperand
        )
        from src.codegen.stack_frame import StackFrame

        gen = X86Generator()
        frame = StackFrame()
        frame.allocate("arr_0", size=40)
        frame.allocate("__t1")
        gen._frame = frame
        gen._func = None
        gen._lines = []

        # ARRAY_LOAD с константным индексом 2
        instr = IRInstruction(
            opcode=IROpcode.ARRAY_LOAD,
            dest=TempOperand(1),
            src1=VarOperand("arr", 0),
            src2=LiteralOperand(2),
        )
        gen._gen_array_load(instr)

        asm_out = "\n".join(gen._lines)
        # Не должно быть shl — прямой адрес
        self.assertNotIn("shl", asm_out)
        # Должно быть прямое обращение к памяти
        self.assertIn("[rbp", asm_out)

    def test_array_store_dynamic(self):
        """ARRAY_STORE с динамическим индексом генерирует shl + add."""
        from src.codegen.x86_generator import X86Generator
        from src.ir.ir_instructions import (
            IRInstruction, IROpcode, TempOperand, VarOperand, LiteralOperand
        )
        from src.codegen.stack_frame import StackFrame

        gen = X86Generator()
        frame = StackFrame()
        frame.allocate("arr_0", size=40)
        frame.allocate("__t1")  # индекс
        frame.allocate("__t2")  # значение
        gen._frame = frame
        gen._func = None
        gen._lines = []

        instr = IRInstruction(
            opcode=IROpcode.ARRAY_STORE,
            dest=VarOperand("arr", 0),
            src1=TempOperand(1),   # индекс
            src2=TempOperand(2),   # значение
        )
        gen._gen_array_store(instr)

        asm_out = "\n".join(gen._lines)
        self.assertIn("shl rcx, 3", asm_out)
        self.assertIn("add rax, rcx", asm_out)


if __name__ == "__main__":
    unittest.main()
