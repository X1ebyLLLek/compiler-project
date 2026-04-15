"""
Тесты генерации IR для управляющих конструкций (Sprint 4).

Проверяем корректную трансляцию:
- if-else → JUMP_IF + JUMP + блоки
- while → JUMP_IF + обратная дуга
- for → такая же структура, как while
- return → RETURN инструкция
"""

import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.ir.ir_instructions import IROpcode
from src.ir.control_flow import IRProgram


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


def get_opcodes(ir_program: IRProgram, func_name: str = "main") -> list:
    """Все опкоды инструкций заданной функции."""
    func = ir_program.get_function(func_name)
    assert func is not None
    result = []
    for block in func.cfg.blocks:
        for instr in block.instructions:
            result.append(instr.opcode)
    return result


def get_block_labels(ir_program: IRProgram, func_name: str = "main") -> list:
    """Метки всех блоков заданной функции."""
    func = ir_program.get_function(func_name)
    assert func is not None
    return [b.label for b in func.cfg.blocks]


# --------------------------------------------------------------------------
# Тест 1: if без else
# --------------------------------------------------------------------------

class TestIfStatement:
    """Тесты трансляции условных операторов."""

    def test_if_generates_jump_if(self):
        """Конструкция if генерирует JUMP_IF."""
        source = """
        fn main() -> int {
            int x = 10;
            if (x > 5) {
                x = 0;
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.JUMP_IF in opcodes

    def test_if_generates_multiple_blocks(self):
        """if создаёт минимум 3 блока: entry, then, endif."""
        source = """
        fn main() -> int {
            int x = 5;
            if (x > 3) {
                x = 100;
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        # entry + then + else (пустой) + endif
        assert func.cfg.block_count() >= 3

    def test_if_else_generates_both_branches(self):
        """if-else создаёт блоки для обеих веток."""
        source = """
        fn main() -> int {
            int x = 10;
            if (x > 5) {
                x = 1;
            } else {
                x = 2;
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        labels = get_block_labels(ir)
        # Должны быть блоки then и else
        has_then = any("then" in lb for lb in labels)
        has_else = any("else" in lb for lb in labels)
        assert has_then, f"Нет блока then. Блоки: {labels}"
        assert has_else, f"Нет блока else. Блоки: {labels}"

    def test_if_has_unconditional_jump(self):
        """В конце then-блока должен быть JUMP на endif."""
        source = """
        fn main() -> int {
            int x = 5;
            if (x > 3) {
                x = 0;
            } else {
                x = 1;
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        # JUMP_IF (вход в then) + JUMP (безусловные: из then, из else, по else)
        unconditional_jumps = opcodes.count(IROpcode.JUMP)
        assert unconditional_jumps >= 1

    def test_nested_if(self):
        """Вложенный if корректно создаёт блоки."""
        source = """
        fn main() -> int {
            int x = 5;
            int y = 3;
            if (x > 0) {
                if (y > 0) {
                    x = x + y;
                }
            }
            return x;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        # Два вложенных if → не менее 5 блоков
        assert func.cfg.block_count() >= 5


# --------------------------------------------------------------------------
# Тест 2: while
# --------------------------------------------------------------------------

class TestWhileStatement:
    """Тесты трансляции цикла while."""

    def test_while_generates_cond_and_body_blocks(self):
        """while создаёт блоки условия и тела."""
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
        labels = get_block_labels(ir)
        has_cond = any("while_cond" in lb for lb in labels)
        has_body = any("while_body" in lb for lb in labels)
        assert has_cond, f"Нет блока условия while. Блоки: {labels}"
        assert has_body, f"Нет блока тела while. Блоки: {labels}"

    def test_while_has_back_edge(self):
        """Тело while имеет обратную дугу к блоку условия."""
        source = """
        fn main() -> int {
            int i = 0;
            while (i < 5) {
                i += 1;
            }
            return i;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        cfg = func.cfg

        # Находим блок тела
        body_block = next(
            (b for b in cfg.blocks if "while_body" in b.label), None
        )
        assert body_block is not None

        # Тело должно иметь преемника — блок условия (back edge)
        cond_block = next(
            (b for b in cfg.blocks if "while_cond" in b.label), None
        )
        assert cond_block is not None
        assert cond_block in body_block.successors, (
            "Отсутствует обратная дуга тела → условие"
        )

    def test_while_generates_jump_if(self):
        """Блок условия while содержит JUMP_IF."""
        source = """
        fn main() -> int {
            int n = 10;
            while (n > 0) {
                n -= 1;
            }
            return n;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.JUMP_IF in opcodes

    def test_while_end_block_exists(self):
        """После while должен быть блок выхода."""
        source = """
        fn main() -> int {
            int i = 0;
            while (i < 3) {
                i += 1;
            }
            return i;
        }
        """
        ir = compile_to_ir(source)
        labels = get_block_labels(ir)
        has_end = any("while_end" in lb for lb in labels)
        assert has_end, f"Нет блока выхода из while. Блоки: {labels}"


# --------------------------------------------------------------------------
# Тест 3: for
# --------------------------------------------------------------------------

class TestForStatement:
    """Тесты трансляции цикла for."""

    def test_for_generates_cond_and_body_blocks(self):
        """for создаёт блоки условия и тела."""
        source = """
        fn main() -> int {
            int sum = 0;
            for (int i = 0; i < 5; i += 1) {
                sum += i;
            }
            return sum;
        }
        """
        ir = compile_to_ir(source)
        labels = get_block_labels(ir)
        has_cond = any("for_cond" in lb for lb in labels)
        has_body = any("for_body" in lb for lb in labels)
        assert has_cond, f"Нет блока условия for. Блоки: {labels}"
        assert has_body, f"Нет блока тела for. Блоки: {labels}"

    def test_for_has_back_edge(self):
        """Тело for имеет обратную дугу к блоку условия."""
        source = """
        fn main() -> int {
            int s = 0;
            for (int i = 0; i < 3; i += 1) {
                s += i;
            }
            return s;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        cfg = func.cfg

        body_block = next(
            (b for b in cfg.blocks if "for_body" in b.label), None
        )
        cond_block = next(
            (b for b in cfg.blocks if "for_cond" in b.label), None
        )
        assert body_block is not None
        assert cond_block is not None
        assert cond_block in body_block.successors, (
            "Отсутствует обратная дуга for-тела → условие"
        )

    def test_for_generates_init_instructions(self):
        """Инициализация for (int i = 0) генерирует ALLOCA + STORE."""
        source = """
        fn main() -> int {
            int total = 0;
            for (int i = 0; i < 5; i += 1) {
                total += i;
            }
            return total;
        }
        """
        ir = compile_to_ir(source)
        opcodes = get_opcodes(ir)
        assert IROpcode.ALLOCA in opcodes
        assert IROpcode.STORE in opcodes


# --------------------------------------------------------------------------
# Тест 4: return
# --------------------------------------------------------------------------

class TestReturnStatement:
    """Тесты трансляции инструкции return."""

    def test_return_with_value(self):
        """return expr → RETURN с операндом."""
        source = """
        fn main() -> int {
            return 42;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        all_instrs = []
        for b in func.cfg.blocks:
            all_instrs.extend(b.instructions)

        return_instrs = [i for i in all_instrs if i.opcode == IROpcode.RETURN]
        assert len(return_instrs) >= 1
        # Первый return с константой 42 (src1 = LiteralOperand(42))
        has_value = any(i.src1 is not None for i in return_instrs)
        assert has_value, "RETURN должен иметь операнд-значение"

    def test_void_return(self):
        """return без значения → RETURN без операнда."""
        source = """
        fn greet() {
            return;
        }
        fn main() -> int {
            greet();
            return 0;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("greet")
        all_instrs = []
        for b in func.cfg.blocks:
            all_instrs.extend(b.instructions)

        return_instrs = [i for i in all_instrs if i.opcode == IROpcode.RETURN]
        # greet() имеет return без значения
        void_returns = [i for i in return_instrs if i.src1 is None]
        assert len(void_returns) >= 1

    def test_early_return_terminates_block(self):
        """Блок с return должен быть помечен как завершённый."""
        source = """
        fn main() -> int {
            return 0;
        }
        """
        ir = compile_to_ir(source)
        func = ir.get_function("main")
        # Все блоки с RETURN должны быть is_terminated()
        for block in func.cfg.blocks:
            if any(i.opcode == IROpcode.RETURN for i in block.instructions):
                assert block.is_terminated(), (
                    f"Блок {block.label} с RETURN не помечен как завершённый"
                )
