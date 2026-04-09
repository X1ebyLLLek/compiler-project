"""
Тестовый модуль семантического анализатора (Sprint 3).

Проверяет:
- Таблицу символов (вставка, поиск, вложенные области)
- Совместимость типов (int→float, операторы)
- Сигнатуры функций (количество и типы аргументов)
- Ошибки: необъявленные переменные, дубликаты, типовые несоответствия
- Интеграцию: lex → parse → semantic
"""

import pytest
from pathlib import Path

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast_nodes import ProgramNode
from src.semantic.analyzer import SemanticAnalyzer
from src.semantic.symbol_table import SymbolTable, SymbolInfo, SymbolKind
from src.semantic.type_system import (
    INT_TYPE, FLOAT_TYPE, BOOL_TYPE, VOID_TYPE, STRING_TYPE, ERROR_TYPE,
    is_assignable, binary_result_type, unary_result_type,
)
from src.semantic.errors import SemanticErrorKind

BASE = Path(__file__).parent
VALID_TYPE   = BASE / "valid" / "type_compatibility"
VALID_SCOPE  = BASE / "valid" / "nested_scopes"
VALID_COMPLEX = BASE / "valid" / "complex_programs"
INVALID_UNDECL = BASE / "invalid" / "undeclared_variable"
INVALID_TYPE   = BASE / "invalid" / "type_mismatch"
INVALID_DUP    = BASE / "invalid" / "duplicate_declaration"
INVALID_ARGS   = BASE / "invalid" / "argument_errors"
INVALID_SCOPE  = BASE / "invalid" / "scope_errors"


# ============================================================
# Вспомогательные функции
# ============================================================

def analyze_source(source: str) -> SemanticAnalyzer:
    """Пропустить исходный код через lex → parse → semantic."""
    scanner = Scanner(source)
    parser = Parser(scanner._tokens)
    ast = parser.parse()
    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast, source=source)
    return analyzer


def analyze_file(path: Path) -> SemanticAnalyzer:
    source = path.read_text(encoding="utf-8")
    return analyze_source(source)


# ============================================================
# Тесты таблицы символов (TEST-1: symbol table operations)
# ============================================================

class TestSymbolTable:
    """Unit-тесты для SymbolTable."""

    def test_insert_and_lookup(self):
        st = SymbolTable()
        sym = SymbolInfo(name="x", type=INT_TYPE, kind=SymbolKind.VARIABLE, line=1, column=1)
        assert st.insert(sym) is True
        found = st.lookup("x")
        assert found is not None
        assert found.name == "x"
        assert found.type == INT_TYPE

    def test_duplicate_insert_fails(self):
        st = SymbolTable()
        sym1 = SymbolInfo(name="x", type=INT_TYPE, kind=SymbolKind.VARIABLE, line=1, column=1)
        sym2 = SymbolInfo(name="x", type=FLOAT_TYPE, kind=SymbolKind.VARIABLE, line=2, column=1)
        assert st.insert(sym1) is True
        assert st.insert(sym2) is False

    def test_scope_nesting(self):
        st = SymbolTable()
        sym_global = SymbolInfo(name="g", type=INT_TYPE, kind=SymbolKind.VARIABLE, line=1, column=1)
        st.insert(sym_global)

        st.enter_scope("func")
        sym_local = SymbolInfo(name="l", type=FLOAT_TYPE, kind=SymbolKind.VARIABLE, line=2, column=1)
        st.insert(sym_local)

        # Из внутренней области видно и g, и l
        assert st.lookup("g") is not None
        assert st.lookup("l") is not None
        # lookup_local видит только l
        assert st.lookup_local("g") is None
        assert st.lookup_local("l") is not None

        st.exit_scope()
        # После выхода l не видно
        assert st.lookup("g") is not None
        assert st.lookup("l") is None

    def test_scope_shadowing(self):
        st = SymbolTable()
        sym1 = SymbolInfo(name="x", type=INT_TYPE, kind=SymbolKind.VARIABLE, line=1, column=1)
        st.insert(sym1)

        st.enter_scope("block")
        sym2 = SymbolInfo(name="x", type=FLOAT_TYPE, kind=SymbolKind.VARIABLE, line=3, column=1)
        st.insert(sym2)

        found = st.lookup("x")
        assert found.type == FLOAT_TYPE  # внутренний затеняет внешний

        st.exit_scope()
        found = st.lookup("x")
        assert found.type == INT_TYPE  # снова видно внешний

    def test_depth_tracking(self):
        st = SymbolTable()
        assert st.depth == 0
        st.enter_scope("a")
        assert st.depth == 1
        st.enter_scope("b")
        assert st.depth == 2
        st.exit_scope()
        assert st.depth == 1
        st.exit_scope()
        assert st.depth == 0

    def test_dump(self):
        st = SymbolTable()
        st.insert(SymbolInfo(name="main", type=VOID_TYPE, kind=SymbolKind.FUNCTION, line=1, column=1))
        dump = st.dump()
        assert "main" in dump
        assert "Scope" in dump


# ============================================================
# Тесты системы типов (TEST-1: type compatibility)
# ============================================================

class TestTypeSystem:
    """Unit-тесты совместимости типов и операторов."""

    def test_same_type_assignable(self):
        assert is_assignable(INT_TYPE, INT_TYPE)
        assert is_assignable(FLOAT_TYPE, FLOAT_TYPE)
        assert is_assignable(BOOL_TYPE, BOOL_TYPE)

    def test_int_to_float_widening(self):
        assert is_assignable(FLOAT_TYPE, INT_TYPE)

    def test_float_to_int_not_allowed(self):
        assert not is_assignable(INT_TYPE, FLOAT_TYPE)

    def test_incompatible_types(self):
        assert not is_assignable(INT_TYPE, STRING_TYPE)
        assert not is_assignable(BOOL_TYPE, INT_TYPE)
        assert not is_assignable(INT_TYPE, BOOL_TYPE)

    def test_error_type_compatible_with_anything(self):
        assert is_assignable(INT_TYPE, ERROR_TYPE)
        assert is_assignable(ERROR_TYPE, FLOAT_TYPE)

    def test_binary_arithmetic(self):
        assert binary_result_type("+", INT_TYPE, INT_TYPE) == INT_TYPE
        assert binary_result_type("+", FLOAT_TYPE, FLOAT_TYPE) == FLOAT_TYPE
        assert binary_result_type("+", INT_TYPE, FLOAT_TYPE) == FLOAT_TYPE
        assert binary_result_type("-", INT_TYPE, INT_TYPE) == INT_TYPE
        assert binary_result_type("*", FLOAT_TYPE, INT_TYPE) == FLOAT_TYPE
        assert binary_result_type("/", INT_TYPE, INT_TYPE) == INT_TYPE
        assert binary_result_type("%", INT_TYPE, INT_TYPE) == INT_TYPE

    def test_binary_arithmetic_invalid(self):
        assert binary_result_type("+", BOOL_TYPE, INT_TYPE) is None
        assert binary_result_type("+", STRING_TYPE, INT_TYPE) is None

    def test_binary_comparison(self):
        assert binary_result_type("<", INT_TYPE, INT_TYPE) == BOOL_TYPE
        assert binary_result_type(">=", FLOAT_TYPE, INT_TYPE) == BOOL_TYPE
        assert binary_result_type("==", INT_TYPE, INT_TYPE) == BOOL_TYPE
        assert binary_result_type("!=", BOOL_TYPE, BOOL_TYPE) == BOOL_TYPE

    def test_binary_logical(self):
        assert binary_result_type("&&", BOOL_TYPE, BOOL_TYPE) == BOOL_TYPE
        assert binary_result_type("||", BOOL_TYPE, BOOL_TYPE) == BOOL_TYPE
        assert binary_result_type("&&", INT_TYPE, BOOL_TYPE) is None

    def test_unary_minus(self):
        assert unary_result_type("-", INT_TYPE) == INT_TYPE
        assert unary_result_type("-", FLOAT_TYPE) == FLOAT_TYPE
        assert unary_result_type("-", BOOL_TYPE) is None

    def test_unary_not(self):
        assert unary_result_type("!", BOOL_TYPE) == BOOL_TYPE
        assert unary_result_type("!", INT_TYPE) is None


# ============================================================
# Тесты семантического анализатора: валидные программы
# ============================================================

class TestValidPrograms:
    """Валидные программы не должны давать ошибок."""

    def test_simple_function(self):
        a = analyze_source("fn main() -> int { int x = 42; return x; }")
        assert not a.has_errors()

    def test_function_with_params(self):
        a = analyze_source("fn add(int a, int b) -> int { return a + b; }")
        assert not a.has_errors()

    def test_int_to_float_assignment(self):
        a = analyze_source("fn t() { float x = 10; }")
        assert not a.has_errors()

    def test_nested_scopes(self):
        a = analyze_source("""
            fn main() {
                int x = 1;
                { int y = 2; int z = x + y; }
                { int y = 100; }
            }
        """)
        assert not a.has_errors()

    def test_forward_reference_functions(self):
        a = analyze_source("""
            fn main() { int r = helper(5); }
            fn helper(int n) -> int { return n * 2; }
        """)
        assert not a.has_errors()

    def test_struct_declaration(self):
        a = analyze_source("""
            struct Point { int x; int y; }
            fn main() { int a = 1; }
        """)
        assert not a.has_errors()

    def test_void_function_return(self):
        a = analyze_source("fn doStuff() { return; }")
        assert not a.has_errors()

    def test_while_loop(self):
        a = analyze_source("""
            fn main() {
                int i = 0;
                while (i < 10) { i += 1; }
            }
        """)
        assert not a.has_errors()

    def test_for_loop(self):
        a = analyze_source("""
            fn main() {
                for (int i = 0; i < 10; i += 1) {
                    int x = i * 2;
                }
            }
        """)
        assert not a.has_errors()

    def test_if_else(self):
        a = analyze_source("""
            fn main() {
                int x = 5;
                if (x > 0) { x = x - 1; } else { x = 0; }
            }
        """)
        assert not a.has_errors()

    def test_all_valid_type_files(self):
        for src in VALID_TYPE.glob("*.src"):
            a = analyze_file(src)
            assert not a.has_errors(), f"Ожидалась корректная программа: {src.name}\n{a.format_errors()}"

    def test_all_valid_scope_files(self):
        for src in VALID_SCOPE.glob("*.src"):
            a = analyze_file(src)
            assert not a.has_errors(), f"Ожидалась корректная программа: {src.name}\n{a.format_errors()}"

    def test_all_valid_complex_files(self):
        for src in VALID_COMPLEX.glob("*.src"):
            a = analyze_file(src)
            assert not a.has_errors(), f"Ожидалась корректная программа: {src.name}\n{a.format_errors()}"


# ============================================================
# Тесты семантического анализатора: ошибки
# ============================================================

class TestUndeclaredVariables:
    """Обнаружение необъявленных переменных (SEM-5)."""

    def test_undeclared_var(self):
        a = analyze_source("fn main() { int x = y; }")
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.UNDECLARED_VARIABLE for e in a.get_errors())

    def test_undeclared_in_expression(self):
        a = analyze_source("fn main() { int x = 5; int y = x + z; }")
        assert a.has_errors()

    def test_files_produce_errors(self):
        for src in INVALID_UNDECL.glob("*.src"):
            a = analyze_file(src)
            assert a.has_errors(), f"Ожидались ошибки в: {src.name}"


class TestTypeMismatch:
    """Обнаружение несовместимых типов (SEM-3)."""

    def test_assign_string_to_int(self):
        a = analyze_source('fn main() { int x = 10; x = "hello"; }')
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.TYPE_MISMATCH for e in a.get_errors())

    def test_bool_arithmetic(self):
        a = analyze_source("fn main() { bool b = true; int x = b + 5; }")
        assert a.has_errors()

    def test_files_produce_errors(self):
        for src in INVALID_TYPE.glob("*.src"):
            a = analyze_file(src)
            assert a.has_errors(), f"Ожидались ошибки в: {src.name}"


class TestDuplicateDeclarations:
    """Обнаружение дублирования объявлений (SEM-2)."""

    def test_duplicate_var(self):
        a = analyze_source("fn main() { int x = 1; int x = 2; }")
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.DUPLICATE_DECLARATION for e in a.get_errors())

    def test_duplicate_function(self):
        a = analyze_source("fn foo() { } fn foo() { }")
        assert a.has_errors()

    def test_files_produce_errors(self):
        for src in INVALID_DUP.glob("*.src"):
            a = analyze_file(src)
            assert a.has_errors(), f"Ожидались ошибки в: {src.name}"


class TestArgumentErrors:
    """Ошибки аргументов функций (SEM-4)."""

    def test_too_few_args(self):
        a = analyze_source("""
            fn add(int a, int b) -> int { return a + b; }
            fn main() { int r = add(1); }
        """)
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.ARGUMENT_COUNT_MISMATCH for e in a.get_errors())

    def test_too_many_args(self):
        a = analyze_source("""
            fn add(int a, int b) -> int { return a + b; }
            fn main() { int r = add(1, 2, 3); }
        """)
        assert a.has_errors()

    def test_wrong_arg_type(self):
        a = analyze_source("""
            fn add(int a, int b) -> int { return a + b; }
            fn main() { int r = add("x", true); }
        """)
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.ARGUMENT_TYPE_MISMATCH for e in a.get_errors())

    def test_files_produce_errors(self):
        for src in INVALID_ARGS.glob("*.src"):
            a = analyze_file(src)
            assert a.has_errors(), f"Ожидались ошибки в: {src.name}"


class TestScopeErrors:
    """Ошибки областей видимости."""

    def test_var_outside_scope(self):
        a = analyze_source("fn main() { { int x = 1; } int y = x; }")
        assert a.has_errors()

    def test_files_produce_errors(self):
        for src in INVALID_SCOPE.glob("*.src"):
            a = analyze_file(src)
            assert a.has_errors(), f"Ожидались ошибки в: {src.name}"


class TestReturnTypeErrors:
    """Ошибки типа возврата (SEM-4)."""

    def test_wrong_return_type(self):
        a = analyze_source('fn foo() -> int { return "hello"; }')
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.INVALID_RETURN_TYPE for e in a.get_errors())

    def test_void_returns_value(self):
        a = analyze_source("fn foo() { return 42; }")
        assert a.has_errors()

    def test_non_void_empty_return(self):
        a = analyze_source("fn foo() -> int { return; }")
        assert a.has_errors()


class TestConditionType:
    """Условие в if/while/for должно быть bool (SEM-6)."""

    def test_if_int_condition(self):
        a = analyze_source("fn main() { if (42) { int x = 1; } }")
        assert a.has_errors()
        assert any(e.kind == SemanticErrorKind.INVALID_CONDITION_TYPE for e in a.get_errors())

    def test_while_string_condition(self):
        a = analyze_source('fn main() { while ("yes") { int x = 1; } }')
        assert a.has_errors()


# ============================================================
# Тесты вывода и декорирования (DEC-1, DEC-2)
# ============================================================

class TestDecoratedOutput:
    """Проверяем, что декорированный AST содержит типовые аннотации."""

    def test_decorated_ast_has_types(self):
        a = analyze_source("fn main() { int x = 42; }")
        ast = a.get_decorated_ast()
        output = a.format_decorated_ast(ast)
        assert "Program" in output
        assert "FunctionDecl" in output

    def test_symbol_table_dump(self):
        a = analyze_source("fn main() { int x = 42; }")
        st = a.get_symbol_table()
        dump = st.dump()
        assert "main" in dump

    def test_validation_report(self):
        a = analyze_source("fn main() { int x = y; }")
        report = a.format_validation_report()
        assert "Ошибок:" in report

    def test_error_has_position(self):
        a = analyze_source("fn main() { int x = y; }")
        errors = a.get_errors()
        assert len(errors) > 0
        e = errors[0]
        assert e.line >= 1
        assert e.column >= 1


# ============================================================
# Интеграционные тесты: lex → parse → semantic
# ============================================================

class TestIntegration:
    """Полный конвейер на примерных файлах."""

    def test_example_hello(self):
        src = Path(__file__).parent.parent.parent / "examples" / "hello.src"
        if src.exists():
            a = analyze_file(src)
            # hello.src использует string — тут может быть ошибка парсинга
            # но не должно быть исключений
            assert isinstance(a, SemanticAnalyzer)

    def test_example_factorial(self):
        src = Path(__file__).parent.parent.parent / "examples" / "factorial.src"
        if src.exists():
            a = analyze_file(src)
            assert not a.has_errors(), a.format_errors()

    def test_error_recovery_multiple(self):
        """Анализатор должен находить несколько ошибок за один прогон (ERR-3)."""
        a = analyze_source("""
            fn main() {
                int x = y;
                int z = w;
            }
        """)
        errors = a.get_errors()
        assert len(errors) >= 2  # y и w — оба не объявлены
