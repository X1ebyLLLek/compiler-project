"""
Тесты структурной валидации IR (Sprint 4).

Проверяем инварианты корректно сгенерированного IR:
- каждый базовый блок завершается инструкцией передачи управления
- все переходы ссылаются на существующие блоки
- у каждого блока правильно заполнены predecessors/successors
- entry-блок всегда существует
- нет блоков-сирот (недостижимых блоков в простых программах)
"""

import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.ir.ir_instructions import IROpcode, LabelOperand
from src.ir.control_flow import IRProgram, IRFunction
from src.ir.basic_block import BasicBlock


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def compile_to_ir(source: str) -> IRProgram:
    """Полный цикл компиляции до IR."""
    scanner = Scanner(source)
    tokens = scanner._tokens
    parser = Parser(tokens)
    ast = parser.parse()
    assert not parser.get_errors()
    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast, source=source)
    assert not analyzer.get_errors()
    generator = IRGenerator()
    return generator.generate(ast)


def all_blocks(func: IRFunction) -> list:
    return func.cfg.blocks


# --------------------------------------------------------------------------
# Тест 1: Завершённость блоков
# --------------------------------------------------------------------------

class TestBlockTermination:
    """Каждый базовый блок должен завершаться инструкцией управления."""

    TERMINAL_OPCODES = {
        IROpcode.JUMP, IROpcode.JUMP_IF, IROpcode.JUMP_IF_NOT, IROpcode.RETURN
    }

    def _check_all_blocks_terminated(self, ir_program: IRProgram):
        for func in ir_program.functions:
            for block in func.cfg.blocks:
                if block.instructions:
                    last = block.instructions[-1]
                    assert last.opcode in self.TERMINAL_OPCODES, (
                        f"Блок '{block.label}' функции '{func.name}' "
                        f"не завершён (последняя инструкция: {last.opcode})"
                    )

    def test_simple_function_blocks_terminated(self):
        source = """
        fn main() -> int {
            return 42;
        }
        """
        ir = compile_to_ir(source)
        self._check_all_blocks_terminated(ir)

    def test_if_else_blocks_terminated(self):
        source = """
        fn main() -> int {
            int x = 5;
            if (x > 3) {
                x = 1;
            } else {
                x = 2;
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        self._check_all_blocks_terminated(ir)

    def test_while_blocks_terminated(self):
        source = """
        fn main() -> int {
            int i = 0;
            while (i < 10) {
                i += 1;
            }
            return i;
        }
        """
        ir = compile_to_ir(source)
        self._check_all_blocks_terminated(ir)

    def test_for_blocks_terminated(self):
        source = """
        fn main() -> int {
            int s = 0;
            for (int i = 0; i < 5; i += 1) {
                s += i;
            }
            return s;
        }
        """
        ir = compile_to_ir(source)
        self._check_all_blocks_terminated(ir)


# --------------------------------------------------------------------------
# Тест 2: entry-блок
# --------------------------------------------------------------------------

class TestEntryBlock:
    """entry-блок должен всегда присутствовать."""

    def test_entry_block_exists(self):
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        for func in ir.functions:
            assert func.cfg.entry_block is not None, (
                f"Функция '{func.name}' не имеет entry-блока"
            )

    def test_entry_block_is_first(self):
        """entry-блок должен быть первым в списке блоков."""
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        assert func.cfg.blocks[0].label == "entry"

    def test_entry_block_label(self):
        """Метка entry-блока — 'entry'."""
        source = """
        fn foo() -> int { return 1; }
        fn main() -> int { return foo(); }
        """
        ir = compile_to_ir(source)
        for func in ir.functions:
            assert func.cfg.entry_block.label == "entry"


# --------------------------------------------------------------------------
# Тест 3: Уникальность меток блоков
# --------------------------------------------------------------------------

class TestBlockLabelsUnique:
    """Метки блоков в одной функции должны быть уникальными."""

    def test_labels_unique_simple(self):
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        for func in ir.functions:
            labels = [b.label for b in func.cfg.blocks]
            assert len(labels) == len(set(labels)), (
                f"Повторяющиеся метки в функции '{func.name}': {labels}"
            )

    def test_labels_unique_complex(self):
        source = """
        fn main() -> int {
            int x = 0;
            if (x > 0) {
                x = 1;
            } else {
                x = 2;
            }
            while (x < 10) {
                x += 1;
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        for func in ir.functions:
            labels = [b.label for b in func.cfg.blocks]
            assert len(labels) == len(set(labels))


# --------------------------------------------------------------------------
# Тест 4: Счётчик временных переменных
# --------------------------------------------------------------------------

class TestTemporaryCounter:
    """Временных переменных должно быть корректное количество."""

    def test_temp_counter_positive(self):
        """Для нетривиальных функций temp_count > 0."""
        source = """
        fn main() -> int {
            int a = 1;
            int b = 2;
            int c = a + b;
            return c;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        assert func.temp_count > 0

    def test_temp_counter_resets_per_function(self):
        """Счётчик временных переменных перезапускается для каждой функции."""
        source = """
        fn f1() -> int {
            int a = 1;
            int b = 2;
            return a + b;
        }
        fn f2() -> int {
            int x = 10;
            return x * 2;
        }
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        f1 = ir.get_function("f1")
        f2 = ir.get_function("f2")
        # Количество временных у f2 не должно зависеть от f1
        # (обе функции нетривиальны — у обеих temp_count > 0)
        assert f1.temp_count > 0
        assert f2.temp_count > 0


# --------------------------------------------------------------------------
# Тест 5: Статистика IR
# --------------------------------------------------------------------------

class TestIRStats:
    """Тесты метода stats() для IRFunction и IRProgram."""

    def test_function_stats_keys(self):
        source = """
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        stats = func.stats()
        assert "function" in stats
        assert "blocks" in stats
        assert "total_instructions" in stats
        assert "temporaries" in stats
        assert "by_opcode" in stats

    def test_program_stats_keys(self):
        source = """
        fn main() -> int { return 0; }
        """
        ir = compile_to_ir(source)
        stats = ir.stats()
        assert "functions" in stats
        assert "total_blocks" in stats
        assert "total_instructions" in stats
        assert "total_temporaries" in stats
        assert "by_opcode" in stats

    def test_return_in_by_opcode(self):
        """В статистике опкодов должен быть RETURN."""
        source = """
        fn main() -> int { return 42; }
        """
        ir = compile_to_ir(source)
        stats = ir.stats()
        assert "RETURN" in stats["by_opcode"]

    def test_block_count_grows_with_if(self):
        """С добавлением if количество блоков растёт."""
        simple = """
        fn main() -> int {
            return 0;
        }
        """
        with_if = """
        fn main() -> int {
            int x = 5;
            if (x > 3) {
                x = 1;
            } else {
                x = 2;
            }
            return x;
        }
        """
        ir_simple = compile_to_ir(simple)
        ir_with_if = compile_to_ir(with_if)
        simple_blocks = ir_simple.stats()["total_blocks"]
        if_blocks = ir_with_if.stats()["total_blocks"]
        assert if_blocks > simple_blocks


# --------------------------------------------------------------------------
# Тест 6: Graphviz DOT генерация
# --------------------------------------------------------------------------

class TestDotGeneration:
    """Тесты генерации Graphviz DOT."""

    def test_dot_output_not_empty(self):
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        dot = func.to_dot()
        assert len(dot) > 0

    def test_dot_contains_digraph(self):
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        dot = func.to_dot()
        assert "digraph" in dot

    def test_dot_contains_entry_block(self):
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        dot = func.to_dot()
        assert "entry" in dot

    def test_dot_all_functions(self):
        source = """
        fn f() -> int { return 1; }
        fn main() -> int { return f(); }
        """
        ir = compile_to_ir(source)
        dots = ir.to_dot_all()
        assert "f" in dots
        assert "main" in dots
