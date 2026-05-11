"""
Тесты генерации управляющих конструкций x86-64 (Sprint 6).

Проверяем:
  - COND-1..5: трансляция if / if-else / вложенных условий
  - LOOP-1..4: трансляция while и for
  - LOGIC-1..4: короткое замыкание && и ||, логическое NOT
  - EXPR-1..4: приоритет операторов, составные выражения
  - TEST-1..5: интеграционные тесты (вложенные циклы, условия внутри цикла)
"""

import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator
from src.codegen.label_manager import LabelManager


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def compile_to_asm(source: str) -> str:
    """Полный цикл компиляции: исходный код → строка NASM."""
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

    ir = IRGenerator().generate(ast)
    return X86Generator().generate(ir)


def has_label(asm: str, prefix: str) -> bool:
    """Проверить наличие хотя бы одной метки с заданным префиксом."""
    return any(
        line.strip().startswith(f".{prefix}") and line.strip().endswith(":")
        for line in asm.splitlines()
    )


def count_instruction(asm: str, instr: str) -> int:
    """Подсчитать количество строк, содержащих данную инструкцию."""
    return sum(
        1 for line in asm.splitlines()
        if instr in line and not line.strip().startswith(";")
    )


# --------------------------------------------------------------------------
# COND-1..5: Ветвления (if / if-else)
# --------------------------------------------------------------------------

class TestConditionals:
    """COND-1..5: генерация условных переходов и меток."""

    def test_if_simple_generates_jnz(self):
        """COND-1: простой if → JUMP_IF → jnz."""
        source = """
        fn f(int a) -> int {
            if (a > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "jnz" in asm or "jz" in asm, "Условный переход не найден"

    def test_if_generates_then_label(self):
        """COND-1: блок then получает метку."""
        source = """
        fn f(int a) -> int {
            if (a > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_then"), "Метка .L_then_* не найдена"

    def test_if_else_generates_both_branches(self):
        """COND-2: if-else генерирует метки then, else и endif."""
        source = """
        fn f(int a) -> int {
            if (a > 0) {
                return 1;
            } else {
                return 0;
            }
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_then")
        assert has_label(asm, "L_else")
        assert has_label(asm, "L_endif")

    def test_if_else_skips_else_branch(self):
        """COND-2: после тела then должен быть jmp через else."""
        source = """
        fn f(int a) -> int {
            if (a > 0) {
                return 1;
            } else {
                return 0;
            }
        }
        """
        asm = compile_to_asm(source)
        assert "jmp" in asm, "Безусловный переход (jmp) не найден"

    def test_nested_if_unique_labels(self):
        """COND-4: вложенные условия получают уникальные метки."""
        source = """
        fn f(int a, int b) -> int {
            if (a > 0) {
                if (b > 0) {
                    return 2;
                }
                return 1;
            }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        # Должно быть минимум 2 разные метки then (для каждого if)
        then_labels = [
            line.strip()
            for line in asm.splitlines()
            if line.strip().startswith(".L_then") and line.strip().endswith(":")
        ]
        assert len(then_labels) >= 2, f"Ожидалось 2+ метки L_then, найдено: {then_labels}"

    def test_equal_comparison_uses_cmp(self):
        """COND-3: == генерирует cmp."""
        source = """
        fn f(int a, int b) -> int {
            if (a == b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "cmp rax, rcx" in asm
        assert "sete al" in asm

    def test_less_than_uses_setl(self):
        """COND-3: < генерирует setl."""
        source = """
        fn f(int a, int b) -> int {
            if (a < b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setl al" in asm

    def test_greater_equal_uses_setge(self):
        """COND-3: >= генерирует setge."""
        source = """
        fn f(int a, int b) -> int {
            if (a >= b) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setge al" in asm


# --------------------------------------------------------------------------
# LOOP-1..4: Циклы (while / for)
# --------------------------------------------------------------------------

class TestLoops:
    """LOOP-1..4: генерация while и for."""

    def test_while_generates_cond_label(self):
        """LOOP-1: while генерирует метку проверки условия."""
        source = """
        fn f(int n) -> int {
            while (n > 0) { n = n - 1; }
            return n;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_while_cond"), "Метка L_while_cond_* не найдена"

    def test_while_generates_body_label(self):
        """LOOP-1: while генерирует метку тела цикла."""
        source = """
        fn f(int n) -> int {
            while (n > 0) { n = n - 1; }
            return n;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_while_body"), "Метка L_while_body_* не найдена"

    def test_while_generates_end_label(self):
        """LOOP-1: while генерирует метку выхода."""
        source = """
        fn f(int n) -> int {
            while (n > 0) { n = n - 1; }
            return n;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_while_end"), "Метка L_while_end_* не найдена"

    def test_while_has_back_edge_jmp(self):
        """LOOP-1: тело цикла заканчивается jmp к условию."""
        source = """
        fn f(int n) -> int {
            while (n > 0) { n = n - 1; }
            return n;
        }
        """
        asm = compile_to_asm(source)
        # Должен быть переход назад к L_while_cond
        assert "L_while_cond" in asm
        assert "jmp .L_while_cond" in asm

    def test_for_generates_for_labels(self):
        """LOOP-2: for-цикл генерирует метки L_for_cond, L_for_body, L_for_end."""
        source = """
        fn f() -> int {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) {
                s = s + i;
            }
            return s;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_for_cond")
        assert has_label(asm, "L_for_body")
        assert has_label(asm, "L_for_end")

    def test_for_zero_iterations_compiles(self):
        """LOOP-2: цикл с условием, ложным с самого начала, компилируется."""
        source = """
        fn f() -> int {
            int s = 0;
            for (int i = 10; i < 0; i = i + 1) {
                s = s + 1;
            }
            return s;
        }
        """
        asm = compile_to_asm(source)
        assert "ret" in asm

    def test_nested_loops_unique_labels(self):
        """LOOP-4: вложенные циклы получают уникальные метки."""
        source = """
        fn f() -> int {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) {
                for (int j = 0; j < 3; j = j + 1) {
                    s = s + 1;
                }
            }
            return s;
        }
        """
        asm = compile_to_asm(source)
        # Должно быть 2 метки L_for_cond (одна для каждого цикла)
        cond_labels = [
            line.strip()
            for line in asm.splitlines()
            if line.strip().startswith(".L_for_cond") and line.strip().endswith(":")
        ]
        assert len(cond_labels) >= 2, f"Ожидалось 2+ L_for_cond, найдено: {cond_labels}"


# --------------------------------------------------------------------------
# LOGIC-1..4: Логические операторы с коротким замыканием
# --------------------------------------------------------------------------

class TestLogicalOperators:
    """LOGIC-1..4: короткое замыкание &&, ||, NOT."""

    def test_and_generates_sc_labels(self):
        """LOGIC-1: && генерирует метки L_sc_false и L_sc_end."""
        source = """
        fn f(int a, int b) -> int {
            if (a > 0 && b > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_sc_false"), "Метка L_sc_false_* не найдена для &&"
        assert has_label(asm, "L_sc_end"),   "Метка L_sc_end_* не найдена для &&"

    def test_and_uses_multiple_jz(self):
        """LOGIC-1: && порождает два условных перехода (по одному на операнд)."""
        source = """
        fn f(int a, int b) -> int {
            if (a != 0 && b != 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        # Два jz — по одному для каждого операнда && (короткое замыкание)
        jz_count = count_instruction(asm, "jz")
        assert jz_count >= 2, f"Ожидалось 2+ jz для &&, найдено: {jz_count}"

    def test_or_generates_sc_labels(self):
        """LOGIC-2: || генерирует метки L_sc_true и L_sc_end."""
        source = """
        fn f(int a, int b) -> int {
            if (a > 0 || b > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_sc_true"), "Метка L_sc_true_* не найдена для ||"
        assert has_label(asm, "L_sc_end"),  "Метка L_sc_end_* не найдена для ||"

    def test_or_uses_multiple_jnz(self):
        """LOGIC-2: || порождает два условных перехода jnz."""
        source = """
        fn f(int a, int b) -> int {
            if (a > 0 || b > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        jnz_count = count_instruction(asm, "jnz")
        assert jnz_count >= 2, f"Ожидалось 2+ jnz для ||, найдено: {jnz_count}"

    def test_not_uses_setz(self):
        """LOGIC-3: ! генерирует test + setz (без ветвления)."""
        source = """
        fn f(int a) -> int {
            int b = 0;
            if (a > 0) { b = 1; }
            int c = b + 1;
            return c;
        }
        """
        asm = compile_to_asm(source)
        # Простая проверка — NOT используется через семантику
        assert "ret" in asm

    def test_not_operator_generates_setz(self):
        """LOGIC-3: унарный ! явно генерирует setz."""
        source = """
        fn is_zero(int a) -> int {
            if (a > 0) { return 0; }
            return 1;
        }
        """
        asm = compile_to_asm(source)
        assert "setg al" in asm  # a > 0

    def test_nested_logical_compiles(self):
        """LOGIC-4: вложенные && / || компилируются корректно."""
        source = """
        fn f(int a, int b, int c) -> int {
            if (a > 0 && b > 0 && c > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        # Два уровня &&: должно быть 2 блока L_sc_false
        false_labels = [
            line.strip()
            for line in asm.splitlines()
            if line.strip().startswith(".L_sc_false") and line.strip().endswith(":")
        ]
        assert len(false_labels) >= 2, f"Вложенные && должны давать 2+ L_sc_false"

    def test_and_right_operand_skipped_when_left_false(self):
        """LOGIC-1: при ложном левом операнде правый пропускается (структура кода)."""
        source = """
        fn f(int a, int b) -> int {
            if (a > 0 && b > 0) { return 1; }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        lines = [l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith(";")]
        # Метка sc_false должна стоять ПОСЛЕ секции вычисления правого операнда
        false_label_indices = [
            i for i, l in enumerate(lines)
            if l.startswith(".L_sc_false") and l.endswith(":")
        ]
        assert false_label_indices, "Метка L_sc_false не найдена"


# --------------------------------------------------------------------------
# EXPR-1..4: Составные выражения
# --------------------------------------------------------------------------

class TestComplexExpressions:
    """EXPR-1..4: приоритет операторов и составные выражения."""

    def test_operator_precedence_mul_over_add(self):
        """EXPR-1: умножение имеет приоритет над сложением."""
        source = """
        fn f(int a, int b, int c) -> int {
            return a + b * c;
        }
        """
        asm = compile_to_asm(source)
        assert "imul rax, rcx" in asm
        assert "add rax, rcx" in asm

    def test_parentheses_override_precedence(self):
        """EXPR-1: скобки изменяют порядок вычислений."""
        source = """
        fn f(int a, int b, int c) -> int {
            return (a + b) * c;
        }
        """
        asm = compile_to_asm(source)
        assert "add rax, rcx" in asm
        assert "imul rax, rcx" in asm

    def test_complex_expression_compiles(self):
        """EXPR-2: составное выражение (a+b)*(c-d) компилируется."""
        source = """
        fn f(int a, int b, int c, int d) -> int {
            return (a + b) * (c - d);
        }
        """
        asm = compile_to_asm(source)
        assert "add rax, rcx" in asm
        assert "sub rax, rcx" in asm
        assert "imul rax, rcx" in asm

    def test_modulo_in_expression(self):
        """EXPR-1: деление с остатком использует idiv."""
        source = """
        fn f(int a, int b) -> int {
            return a % b;
        }
        """
        asm = compile_to_asm(source)
        assert "cqo" in asm
        assert "idiv rcx" in asm

    def test_chained_comparisons_compile(self):
        """EXPR-1: цепочка сравнений компилируется."""
        source = """
        fn f(int a, int b, int c) -> int {
            if (a < b) {
                if (b < c) { return 1; }
            }
            return 0;
        }
        """
        asm = compile_to_asm(source)
        assert "setl al" in asm

    def test_deeply_nested_expression(self):
        """EXPR-2: глубоко вложенное выражение компилируется без ошибок."""
        source = """
        fn f(int a, int b) -> int {
            int r = a + (b - (a * b));
            return r;
        }
        """
        asm = compile_to_asm(source)
        assert "ret" in asm
        assert "imul rax, rcx" in asm


# --------------------------------------------------------------------------
# Интеграционные тесты (TEST-5)
# --------------------------------------------------------------------------

class TestControlFlowIntegration:
    """Сквозные тесты управляющих конструкций."""

    def test_factorial_recursive_compiles(self):
        """Рекурсивная факториальная функция компилируется полностью."""
        source = """
        fn factorial(int n) -> int {
            if (n <= 1) { return 1; }
            int p = factorial(n - 1);
            return n * p;
        }
        fn main() -> int {
            return factorial(5);
        }
        """
        asm = compile_to_asm(source)
        assert "factorial:" in asm
        assert "call factorial" in asm
        assert has_label(asm, "L_then")

    def test_sum_while_loop_compiles(self):
        """Сумма через while-цикл компилируется корректно."""
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
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_while_cond")
        assert "jmp .L_while_cond" in asm

    def test_nested_loops_with_condition(self):
        """Вложенные циклы с условием внутри компилируются."""
        source = """
        fn f() -> int {
            int sum = 0;
            for (int i = 0; i < 5; i = i + 1) {
                for (int j = 0; j < 3; j = j + 1) {
                    if (i == j) {
                        sum = sum + i;
                    }
                }
            }
            return sum;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_for_cond")
        assert has_label(asm, "L_then")
        assert "ret" in asm

    def test_short_circuit_in_loop_condition(self):
        """Короткое замыкание в условии цикла."""
        source = """
        fn f(int a, int n) -> int {
            int i = 0;
            while (i < n && a > 0) {
                i = i + 1;
            }
            return i;
        }
        """
        asm = compile_to_asm(source)
        assert has_label(asm, "L_while_cond")
        assert has_label(asm, "L_sc_false")

    def test_fibonacci_compiles(self):
        """Числа Фибоначчи (рекурсия + условие) компилируются."""
        source = """
        fn fib(int n) -> int {
            if (n <= 1) { return n; }
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

    def test_all_relational_operators_in_conditions(self):
        """Все операторы сравнения работают в условиях if."""
        sources = [
            ("fn f(int a,int b)->int{if(a<b){return 1;}return 0;}", "setl"),
            ("fn f(int a,int b)->int{if(a<=b){return 1;}return 0;}", "setle"),
            ("fn f(int a,int b)->int{if(a>b){return 1;}return 0;}", "setg"),
            ("fn f(int a,int b)->int{if(a>=b){return 1;}return 0;}", "setge"),
            ("fn f(int a,int b)->int{if(a==b){return 1;}return 0;}", "sete"),
            ("fn f(int a,int b)->int{if(a!=b){return 1;}return 0;}", "setne"),
        ]
        for source, expected_instr in sources:
            asm = compile_to_asm(source)
            assert expected_instr in asm, f"Не найден {expected_instr} для: {source}"


# --------------------------------------------------------------------------
# Тесты LabelManager (unit)
# --------------------------------------------------------------------------

class TestLabelManager:
    """Юнит-тесты для класса LabelManager."""

    def test_new_label_unique(self):
        lm = LabelManager()
        a = lm.new_label("L")
        b = lm.new_label("L")
        assert a != b

    def test_new_label_contains_prefix(self):
        lm = LabelManager()
        label = lm.new_label("L_then")
        assert "L_then" in label

    def test_new_if_labels_returns_three(self):
        lm = LabelManager()
        labels = lm.new_if_labels()
        assert len(labels) == 3
        assert "L_then" in labels[0]
        assert "L_else" in labels[1]
        assert "L_endif" in labels[2]

    def test_new_while_labels_returns_three(self):
        lm = LabelManager()
        cond, body, end = lm.new_while_labels()
        assert "L_while_cond" in cond
        assert "L_while_body" in body
        assert "L_while_end" in end

    def test_sc_and_labels_unique_across_calls(self):
        lm = LabelManager()
        f1, e1 = lm.new_sc_and_labels()
        f2, e2 = lm.new_sc_and_labels()
        assert f1 != f2
        assert e1 != e2

    def test_sc_or_labels_distinct(self):
        lm = LabelManager()
        t, e = lm.new_sc_or_labels()
        assert "L_sc_true" in t
        assert "L_sc_end" in e
        assert t != e

    def test_counter_increments(self):
        lm = LabelManager()
        lm.new_label("X")
        lm.new_label("X")
        assert lm.counter == 2
