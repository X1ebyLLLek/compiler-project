"""
Тестовый модуль для парсера (Sprint 2).
Проверяет корректность построения AST из исходных .src файлов,
работу с ошибками и разные форматы вывода.
"""

import json
import pytest
from pathlib import Path

from src.lexer.scanner import Scanner
from src.parser.parser import Parser, ParseError
from src.parser.ast_nodes import (
    ProgramNode, FunctionDeclNode, StructDeclNode,
    VarDeclStmtNode, IfStmtNode, WhileStmtNode, ForStmtNode,
    ReturnStmtNode, BlockStmtNode, BinaryExprNode,
    UnaryExprNode, CallExprNode, AssignmentExprNode,
    LiteralExprNode, IdentifierExprNode, ExprStmtNode,
)
from src.parser.ast_printer import ASTPrettyPrinter, ASTDotPrinter, ASTJsonPrinter

# Базовые директории с тестовыми файлами
BASE = Path(__file__).parent
VALID_EXPR = BASE / "valid" / "expressions"
VALID_STMT = BASE / "valid" / "statements"
VALID_DECL = BASE / "valid" / "declarations"
VALID_FULL = BASE / "valid" / "full_programs"
INVALID_DIR = BASE / "invalid" / "syntax_errors"


# ============================================================
# Вспомогательная функция: исходный код → AST
# ============================================================

def parse_source(source: str) -> ProgramNode:
    """Пропустить исходный код через лексер + парсер, вернуть AST."""
    scanner = Scanner(source)
    parser = Parser(scanner._tokens)
    return parser.parse()


def parse_file(path: Path) -> ProgramNode:
    """Прочитать .src файл и распарсить его."""
    source = path.read_text(encoding="utf-8")
    return parse_source(source)


# ============================================================
# Тесты валидных выражений (TEST-1: каждое правило грамматики)
# ============================================================

class TestExpressions:
    """Проверяем разбор выражений: арифметика, логика, вызовы и т. д."""

    def test_arithmetic_precedence(self):
        """Проверяем, что 2 + 3 * 4 трактуется как 2 + (3 * 4)."""
        ast = parse_source("fn t() { int a = 2 + 3 * 4; }")
        # Должна получиться функция с VarDecl внутри
        func = ast.declarations[0]
        assert isinstance(func, FunctionDeclNode)
        var_decl = func.body.statements[0]
        assert isinstance(var_decl, VarDeclStmtNode)
        # Инициализатор — BinaryExpr с "+" наверху
        init_expr = var_decl.initializer
        assert isinstance(init_expr, BinaryExprNode)
        assert init_expr.operator == "+"
        # Правая часть — умножение (приоритет выше)
        assert isinstance(init_expr.right, BinaryExprNode)
        assert init_expr.right.operator == "*"

    def test_parenthesized_expression(self):
        """Скобки меняют приоритет: (2 + 3) * 4."""
        ast = parse_source("fn t() { int b = (2 + 3) * 4; }")
        func = ast.declarations[0]
        var_decl = func.body.statements[0]
        init_expr = var_decl.initializer
        assert isinstance(init_expr, BinaryExprNode)
        assert init_expr.operator == "*"
        # Левая часть — сложение (из-за скобок)
        assert isinstance(init_expr.left, BinaryExprNode)
        assert init_expr.left.operator == "+"

    def test_unary_minus(self):
        """Унарный минус: -5."""
        ast = parse_source("fn t() { int a = -5; }")
        func = ast.declarations[0]
        var_decl = func.body.statements[0]
        init_expr = var_decl.initializer
        assert isinstance(init_expr, UnaryExprNode)
        assert init_expr.operator == "-"

    def test_logical_and_or(self):
        """Логические операции: true && false || true."""
        ast = parse_source("fn t() { bool a = true && false || true; }")
        func = ast.declarations[0]
        var_decl = func.body.statements[0]
        init_expr = var_decl.initializer
        # || имеет меньший приоритет, значит он наверху
        assert isinstance(init_expr, BinaryExprNode)
        assert init_expr.operator == "||"

    def test_function_call_no_args(self):
        """Вызов без аргументов: foo()"""
        ast = parse_source("fn t() { foo(); }")
        func = ast.declarations[0]
        stmt = func.body.statements[0]
        assert isinstance(stmt, ExprStmtNode)
        call_expr = stmt.expression
        assert isinstance(call_expr, CallExprNode)
        assert call_expr.callee == "foo"
        assert len(call_expr.arguments) == 0

    def test_function_call_with_args(self):
        """Вызов с аргументами: bar(1, 2)"""
        ast = parse_source("fn t() { bar(1, 2); }")
        func = ast.declarations[0]
        stmt = func.body.statements[0]
        call_expr = stmt.expression
        assert isinstance(call_expr, CallExprNode)
        assert call_expr.callee == "bar"
        assert len(call_expr.arguments) == 2

    def test_assignment(self):
        """Простое присваивание: x = 10"""
        ast = parse_source("fn t() { int x = 0; x = 10; }")
        func = ast.declarations[0]
        stmt = func.body.statements[1]
        assert isinstance(stmt, ExprStmtNode)
        assign = stmt.expression
        assert isinstance(assign, AssignmentExprNode)
        assert assign.target == "x"
        assert assign.operator == "="

    def test_compound_assignment(self):
        """Составное присваивание: x += 5"""
        ast = parse_source("fn t() { int x = 0; x += 5; }")
        func = ast.declarations[0]
        stmt = func.body.statements[1]
        assign = stmt.expression
        assert isinstance(assign, AssignmentExprNode)
        assert assign.operator == "+="

    def test_all_expression_files_parse(self):
        """Все файлы из valid/expressions/ должны парситься без ошибок."""
        for src_path in VALID_EXPR.glob("*.src"):
            ast = parse_file(src_path)
            assert isinstance(ast, ProgramNode), f"Не удалось распарсить {src_path.name}"


# ============================================================
# Тесты инструкций
# ============================================================

class TestStatements:
    """Проверяем инструкции: if, while, for, return, block."""

    def test_if_else(self):
        """if с else-веткой."""
        ast = parse_source("fn t() { if (true) { int a = 1; } else { int b = 2; } }")
        func = ast.declarations[0]
        if_stmt = func.body.statements[0]
        assert isinstance(if_stmt, IfStmtNode)
        assert if_stmt.else_branch is not None

    def test_while_loop(self):
        """Цикл while."""
        ast = parse_source("fn t() { while (true) { int x = 0; } }")
        func = ast.declarations[0]
        while_stmt = func.body.statements[0]
        assert isinstance(while_stmt, WhileStmtNode)

    def test_for_loop(self):
        """Цикл for с инициализатором, условием и обновлением."""
        ast = parse_source("fn t() { for (int i = 0; i < 10; i += 1) { int a = 0; } }")
        func = ast.declarations[0]
        for_stmt = func.body.statements[0]
        assert isinstance(for_stmt, ForStmtNode)
        assert for_stmt.init is not None
        assert for_stmt.condition is not None
        assert for_stmt.update is not None

    def test_return_with_value(self):
        """return с выражением."""
        ast = parse_source("fn t() -> int { return 42; }")
        func = ast.declarations[0]
        ret_stmt = func.body.statements[0]
        assert isinstance(ret_stmt, ReturnStmtNode)
        assert ret_stmt.value is not None

    def test_return_void(self):
        """return без выражения."""
        ast = parse_source("fn t() { return; }")
        func = ast.declarations[0]
        ret_stmt = func.body.statements[0]
        assert isinstance(ret_stmt, ReturnStmtNode)
        assert ret_stmt.value is None

    def test_nested_blocks(self):
        """Вложенные блоки."""
        ast = parse_source("fn t() { { { int x = 1; } } }")
        func = ast.declarations[0]
        block1 = func.body.statements[0]
        assert isinstance(block1, BlockStmtNode)

    def test_empty_block(self):
        """Пустой блок: { }."""
        ast = parse_source("fn t() { { } }")
        func = ast.declarations[0]
        block = func.body.statements[0]
        assert isinstance(block, BlockStmtNode)
        assert len(block.statements) == 0

    def test_all_statement_files_parse(self):
        """Все файлы из valid/statements/ парсятся без ошибок."""
        for src_path in VALID_STMT.glob("*.src"):
            ast = parse_file(src_path)
            assert isinstance(ast, ProgramNode), f"Ошибка в {src_path.name}"


# ============================================================
# Тесты объявлений
# ============================================================

class TestDeclarations:
    """Проверяем fn и struct."""

    def test_function_with_params(self):
        """Функция с параметрами и типом возврата."""
        ast = parse_source("fn add(int a, int b) -> int { return a + b; }")
        func = ast.declarations[0]
        assert isinstance(func, FunctionDeclNode)
        assert func.name == "add"
        assert func.return_type == "int"
        assert len(func.parameters) == 2

    def test_function_no_params(self):
        """Функция без параметров."""
        ast = parse_source("fn empty() { }")
        func = ast.declarations[0]
        assert isinstance(func, FunctionDeclNode)
        assert func.name == "empty"
        assert len(func.parameters) == 0

    def test_struct_declaration(self):
        """Структура с полями."""
        ast = parse_source("struct Point { int x; int y; }")
        struct = ast.declarations[0]
        assert isinstance(struct, StructDeclNode)
        assert struct.name == "Point"
        assert len(struct.fields) == 2

    def test_all_declaration_files_parse(self):
        """Все файлы из valid/declarations/ парсятся без ошибок."""
        for src_path in VALID_DECL.glob("*.src"):
            ast = parse_file(src_path)
            assert isinstance(ast, ProgramNode), f"Ошибка в {src_path.name}"


# ============================================================
# Тесты полных программ
# ============================================================

class TestFullPrograms:
    """Парсинг целых программ из valid/full_programs/."""

    def test_all_full_programs_parse(self):
        """Все полные программы должны парситься без исключений."""
        for src_path in VALID_FULL.glob("*.src"):
            ast = parse_file(src_path)
            assert isinstance(ast, ProgramNode), f"Ошибка в {src_path.name}"
            # Проверяем, что хотя бы одно объявление есть
            assert len(ast.declarations) > 0, f"Пустой AST у {src_path.name}"


# ============================================================
# Тесты обработки ошибок (TEST-4)
# ============================================================

class TestSyntaxErrors:
    """Парсер должен фиксировать ошибки, а не падать."""

    def test_invalid_files_produce_errors(self):
        """Файлы из invalid/ должны генерировать ошибки парсинга."""
        for src_path in INVALID_DIR.glob("*.src"):
            source = src_path.read_text(encoding="utf-8")
            scanner = Scanner(source)
            parser = Parser(scanner._tokens)
            _ast = parser.parse()
            errors = parser.get_errors()
            assert len(errors) > 0, f"Ожидались ошибки в {src_path.name}, но их нет"

    def test_missing_semicolon_error(self):
        """Пропуск точки с запятой должен вызвать ошибку."""
        source = "fn t() { int x = 5 }"
        scanner = Scanner(source)
        parser = Parser(scanner._tokens)
        parser.parse()
        assert len(parser.get_errors()) > 0

    def test_error_has_position(self):
        """Ошибка должна содержать информацию о строке/столбце."""
        source = "fn t() { int x = 5 }"
        scanner = Scanner(source)
        parser = Parser(scanner._tokens)
        parser.parse()
        err = parser.get_errors()[0]
        assert err.token.line >= 1
        assert err.token.column >= 1


# ============================================================
# Тесты визуализации
# ============================================================

class TestASTOutput:
    """Проверяем три формата вывода AST (VIS-1, VIS-2, VIS-3)."""

    def _sample_ast(self):
        return parse_source("fn main() { int x = 42; return x; }")

    def test_text_output(self):
        """Текстовый вывод содержит ключевые элементы."""
        ast = self._sample_ast()
        printer = ASTPrettyPrinter()
        text = printer.print_ast(ast)
        assert "Program" in text
        assert "FunctionDecl" in text
        assert "VarDecl" in text
        assert "Return" in text

    def test_dot_output(self):
        """DOT-вывод содержит необходимые элементы Graphviz."""
        ast = self._sample_ast()
        printer = ASTDotPrinter()
        dot = printer.generate(ast)
        assert "digraph AST" in dot
        assert "->" in dot   # рёбра
        assert "Program" in dot

    def test_json_output(self):
        """JSON-вывод парсится и содержит нужные поля."""
        ast = self._sample_ast()
        printer = ASTJsonPrinter()
        json_str = printer.to_json(ast)
        data = json.loads(json_str)
        assert data["type"] == "Program"
        assert "declarations" in data
        assert len(data["declarations"]) > 0

    def test_json_roundtrip_structure(self):
        """JSON-структура сохраняет основные свойства."""
        ast = self._sample_ast()
        printer = ASTJsonPrinter()
        data = json.loads(printer.to_json(ast))
        func = data["declarations"][0]
        assert func["type"] == "FunctionDecl"
        assert func["name"] == "main"


# ============================================================
# Интеграционные тесты (TEST-5): лексер → парсер → вывод
# ============================================================

class TestIntegration:
    """Тесты связки лексер → парсер → визуализация."""

    def test_full_pipeline_text(self):
        """Полный конвейер: файл -> лексер -> парсер -> text."""
        src = Path(__file__).parent.parent.parent / "examples" / "hello.src"
        if src.exists():
            ast = parse_file(src)
            printer = ASTPrettyPrinter()
            text = printer.print_ast(ast)
            assert len(text) > 0

    def test_full_pipeline_json(self):
        """Полный конвейер: файл -> лексер -> парсер -> json."""
        src = Path(__file__).parent.parent.parent / "examples" / "hello.src"
        if src.exists():
            ast = parse_file(src)
            printer = ASTJsonPrinter()
            data = json.loads(printer.to_json(ast))
            assert data["type"] == "Program"
