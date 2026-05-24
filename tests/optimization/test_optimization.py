"""
Тесты IR-оптимизатора (Sprint 7).

Проверяем напрямую класс IROptimizer:
  - Constant Folding: ADD 10, 20 → MOVE 30
  - Constant Propagation: STORE x=5, потом src с x заменяется на 5
  - Dead Code Elimination: код после JUMP удаляется
  - Dead store elimination: MOVE в temp без последующего чтения удаляется
  - Статистика считается корректно
  - Флаги включения/выключения проходов работают
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.ir.optimizer import IROptimizer
from src.ir.ir_instructions import (
    IRInstruction, IROpcode,
    TempOperand, VarOperand, LiteralOperand, LabelOperand,
)


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def make_instr(opcode, dest=None, src1=None, src2=None, args=None, comment=""):
    """Сокращённое создание IRInstruction."""
    return IRInstruction(
        opcode=opcode,
        dest=dest,
        src1=src1,
        src2=src2,
        args=args or [],
        comment=comment,
    )


def lit(val):
    return LiteralOperand(val)


def tmp(n):
    return TempOperand(n)


def var(name, ver=0):
    return VarOperand(name, ver)


def label(name):
    return LabelOperand(name)


# --------------------------------------------------------------------------
# TEST-1: Constant Folding
# --------------------------------------------------------------------------

class TestConstantFolding(unittest.TestCase):
    """Проверяем свёртку константных выражений."""

    def setUp(self):
        self.opt = IROptimizer(do_folding=True, do_propagation=False, do_dce=False)

    def test_fold_add(self):
        """ADD 10, 20 → MOVE 30"""
        instr = make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(10), src2=lit(20))
        result = self.opt.optimize([instr])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].opcode, IROpcode.MOVE)
        self.assertEqual(result[0].src1.value, 30)

    def test_fold_sub(self):
        """SUB 100, 37 → MOVE 63"""
        instr = make_instr(IROpcode.SUB, dest=tmp(1), src1=lit(100), src2=lit(37))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 63)

    def test_fold_mul(self):
        """MUL 6, 7 → MOVE 42"""
        instr = make_instr(IROpcode.MUL, dest=tmp(1), src1=lit(6), src2=lit(7))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 42)

    def test_fold_div(self):
        """DIV 10, 2 → MOVE 5"""
        instr = make_instr(IROpcode.DIV, dest=tmp(1), src1=lit(10), src2=lit(2))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 5)

    def test_fold_mod(self):
        """MOD 17, 5 → MOVE 2"""
        instr = make_instr(IROpcode.MOD, dest=tmp(1), src1=lit(17), src2=lit(5))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 2)

    def test_fold_cmp_eq_true(self):
        """CMP_EQ 5, 5 → MOVE 1"""
        instr = make_instr(IROpcode.CMP_EQ, dest=tmp(1), src1=lit(5), src2=lit(5))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 1)

    def test_fold_cmp_eq_false(self):
        """CMP_EQ 5, 6 → MOVE 0"""
        instr = make_instr(IROpcode.CMP_EQ, dest=tmp(1), src1=lit(5), src2=lit(6))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 0)

    def test_fold_cmp_lt(self):
        """CMP_LT 3, 7 → MOVE 1"""
        instr = make_instr(IROpcode.CMP_LT, dest=tmp(1), src1=lit(3), src2=lit(7))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].src1.value, 1)

    def test_no_fold_if_var_operand(self):
        """ADD t1, 20 — t1 не константа, фолдинг невозможен."""
        instr = make_instr(IROpcode.ADD, dest=tmp(2), src1=tmp(1), src2=lit(20))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].opcode, IROpcode.ADD, "Не должно было свернуться")

    def test_no_fold_division_by_zero(self):
        """DIV x, 0 — не сворачиваем (деление на ноль в рантайме)."""
        instr = make_instr(IROpcode.DIV, dest=tmp(1), src1=lit(10), src2=lit(0))
        result = self.opt.optimize([instr])
        self.assertEqual(result[0].opcode, IROpcode.DIV, "Не должно было свернуться")

    def test_fold_stats(self):
        """Статистика: одна свёрнутая операция."""
        instr = make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(3), src2=lit(4))
        self.opt.optimize([instr])
        stats = self.opt.get_stats()
        self.assertEqual(stats["folded"], 1)

    def test_fold_multiple(self):
        """Несколько операций — все сворачиваются."""
        instrs = [
            make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(1), src2=lit(2)),
            make_instr(IROpcode.MUL, dest=tmp(2), src1=lit(3), src2=lit(4)),
            make_instr(IROpcode.SUB, dest=tmp(3), src1=lit(10), src2=lit(3)),
        ]
        result = self.opt.optimize(instrs)
        self.assertEqual(len(result), 3)
        vals = [r.src1.value for r in result]
        self.assertEqual(vals, [3, 12, 7])
        self.assertEqual(self.opt.get_stats()["folded"], 3)


# --------------------------------------------------------------------------
# TEST-2: Constant Propagation
# --------------------------------------------------------------------------

class TestConstantPropagation(unittest.TestCase):
    """Проверяем подстановку констант."""

    def setUp(self):
        self.opt = IROptimizer(do_folding=False, do_propagation=True, do_dce=False)

    def test_propagate_move(self):
        """
        MOVE t1, 5
        ADD t2, t1, 3   → ADD t2, 5, 3  (t1 заменяется на 5)
        """
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(5)),
            make_instr(IROpcode.ADD, dest=tmp(2), src1=tmp(1), src2=lit(3)),
        ]
        result = self.opt.optimize(instrs)
        # В ADD src1 должен стать LiteralOperand(5)
        add_instr = result[1]
        self.assertIsInstance(add_instr.src1, LiteralOperand)
        self.assertEqual(add_instr.src1.value, 5)

    def test_propagate_kills_on_reassign(self):
        """
        MOVE t1, 5
        MOVE t1, 10     ← переопределение
        ADD t2, t1, 1   → ADD t2, 10, 1  (не 5)
        """
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(5)),
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(10)),
            make_instr(IROpcode.ADD, dest=tmp(2), src1=tmp(1), src2=lit(1)),
        ]
        result = self.opt.optimize(instrs)
        add_instr = result[2]
        self.assertIsInstance(add_instr.src1, LiteralOperand)
        self.assertEqual(add_instr.src1.value, 10)

    def test_propagate_non_const_kills(self):
        """
        MOVE t1, 5
        ADD t1, t2, t3   ← не константное присваивание, убивает t1=5
        MUL t3, t1, 2    → MUL t3, t1, 2  (t1 неизвестна)
        """
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(5)),
            make_instr(IROpcode.ADD, dest=tmp(1), src1=tmp(2), src2=tmp(3)),
            make_instr(IROpcode.MUL, dest=tmp(4), src1=tmp(1), src2=lit(2)),
        ]
        result = self.opt.optimize(instrs)
        mul_instr = result[2]
        # t1 уже не известна как константа
        self.assertIsInstance(mul_instr.src1, TempOperand)

    def test_propagate_stats(self):
        """Статистика пропагации."""
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(7)),
            make_instr(IROpcode.ADD, dest=tmp(2), src1=tmp(1), src2=tmp(1)),
        ]
        self.opt.optimize(instrs)
        stats = self.opt.get_stats()
        # src1 и src2 обе заменились → одна инструкция изменена
        self.assertGreater(stats["propagated"], 0)


# --------------------------------------------------------------------------
# TEST-3: Dead Code Elimination
# --------------------------------------------------------------------------

class TestDeadCodeElimination(unittest.TestCase):
    """Проверяем удаление мёртвого кода."""

    def setUp(self):
        self.opt = IROptimizer(do_folding=False, do_propagation=False, do_dce=True)

    def test_remove_after_jump(self):
        """Код после JUMP до следующей метки должен быть удалён."""
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(1)),
            make_instr(IROpcode.JUMP, src1=label("L_end")),
            # Эти две инструкции мёртвые:
            make_instr(IROpcode.MOVE, dest=tmp(2), src1=lit(99)),
            make_instr(IROpcode.ADD, dest=tmp(3), src1=tmp(2), src2=lit(1)),
            # Метка заканчивает мёртвую зону:
            make_instr(IROpcode.LABEL, src1=label("L_end")),
            make_instr(IROpcode.RETURN, src1=tmp(1)),
        ]
        result = self.opt.optimize(instrs)
        opcodes = [i.opcode for i in result]
        self.assertNotIn(IROpcode.ADD, opcodes, "ADD после JUMP должен быть удалён")
        # MOVE до JUMP остаётся, MOVE после — убирается
        move_instrs = [i for i in result if i.opcode == IROpcode.MOVE]
        self.assertEqual(len(move_instrs), 1)

    def test_remove_after_return(self):
        """Код после RETURN должен быть удалён."""
        instrs = [
            make_instr(IROpcode.RETURN, src1=lit(0)),
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(42)),  # мёртвый
        ]
        result = self.opt.optimize(instrs)
        opcodes = [i.opcode for i in result]
        self.assertNotIn(IROpcode.MOVE, opcodes)

    def test_label_after_jump_reachable(self):
        """Код после метки, следующей за JUMP, достижим."""
        instrs = [
            make_instr(IROpcode.JUMP, src1=label("L1")),
            make_instr(IROpcode.LABEL, src1=label("L1")),
            make_instr(IROpcode.RETURN, src1=lit(0)),
        ]
        result = self.opt.optimize(instrs)
        opcodes = [i.opcode for i in result]
        self.assertIn(IROpcode.RETURN, opcodes, "RETURN после метки должен остаться")

    def test_dead_temp_store_removed(self):
        """MOVE в temp без последующего чтения удаляется."""
        instrs = [
            # t1 нигде не используется после этого MOVE
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(99)),
            # t2 используется в RETURN
            make_instr(IROpcode.MOVE, dest=tmp(2), src1=lit(42)),
            make_instr(IROpcode.RETURN, src1=tmp(2)),
        ]
        result = self.opt.optimize(instrs)
        # Первый MOVE (t1=99) должен быть удалён
        dests = [str(i.dest) for i in result if i.dest is not None]
        self.assertNotIn("t1", dests, "Мёртвый MOVE в t1 должен быть удалён")

    def test_live_temp_kept(self):
        """Используемый temp не удаляется."""
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(5)),
            make_instr(IROpcode.ADD, dest=tmp(2), src1=tmp(1), src2=lit(3)),
            make_instr(IROpcode.RETURN, src1=tmp(2)),
        ]
        result = self.opt.optimize(instrs)
        opcodes = [i.opcode for i in result]
        # ADD должен остаться (t2 используется в RETURN)
        self.assertIn(IROpcode.ADD, opcodes)

    def test_dce_stats(self):
        """Статистика: две инструкции удалены."""
        instrs = [
            make_instr(IROpcode.JUMP, src1=label("end")),
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(1)),  # удалится
            make_instr(IROpcode.MOVE, dest=tmp(2), src1=lit(2)),  # удалится
            make_instr(IROpcode.LABEL, src1=label("end")),
        ]
        self.opt.optimize(instrs)
        stats = self.opt.get_stats()
        self.assertEqual(stats["eliminated"], 2)


# --------------------------------------------------------------------------
# TEST-4: Комбинированные проходы
# --------------------------------------------------------------------------

class TestCombinedPasses(unittest.TestCase):
    """Проверяем взаимодействие проходов."""

    def test_fold_then_propagate(self):
        """
        ADD t1, 3, 4   → (folding) MOVE t1, 7
        MUL t2, t1, 2  → (propagation) MUL t2, 7, 2
        """
        opt = IROptimizer(do_folding=True, do_propagation=True, do_dce=False)
        instrs = [
            make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(3), src2=lit(4)),
            make_instr(IROpcode.MUL, dest=tmp(2), src1=tmp(1), src2=lit(2)),
        ]
        result = opt.optimize(instrs)
        # t1 свёрнут в 7
        self.assertEqual(result[0].src1.value, 7)
        # MUL получил 7 вместо t1
        self.assertIsInstance(result[1].src1, LiteralOperand)
        self.assertEqual(result[1].src1.value, 7)

    def test_all_passes_together(self):
        """Все три прохода вместе."""
        opt = IROptimizer()
        instrs = [
            make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(2), src2=lit(3)),  # → 5
            make_instr(IROpcode.MOVE, dest=tmp(2), src1=tmp(1)),               # → 5
            make_instr(IROpcode.JUMP, src1=label("end")),
            make_instr(IROpcode.MOVE, dest=tmp(3), src1=lit(999)),             # мёртвый
            make_instr(IROpcode.LABEL, src1=label("end")),
            make_instr(IROpcode.RETURN, src1=tmp(2)),
        ]
        result = opt.optimize(instrs)
        opcodes = [i.opcode for i in result]
        # Мёртвый MOVE(999) удалён
        for i in result:
            if i.opcode == IROpcode.MOVE:
                self.assertNotEqual(
                    getattr(i.src1, 'value', None), 999,
                    "MOVE 999 должен быть удалён"
                )

    def test_get_stats_total(self):
        """total_optimized = folded + propagated + eliminated."""
        opt = IROptimizer()
        instrs = [
            make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(1), src2=lit(2)),
        ]
        opt.optimize(instrs)
        stats = opt.get_stats()
        self.assertEqual(
            stats["total_optimized"],
            stats["folded"] + stats["propagated"] + stats["eliminated"],
        )


# --------------------------------------------------------------------------
# TEST-5: Флаги включения/выключения
# --------------------------------------------------------------------------

class TestOptimizerFlags(unittest.TestCase):
    """Проверяем что флаги do_folding/do_propagation/do_dce работают."""

    def test_folding_disabled(self):
        """При do_folding=False — ADD с константами не сворачивается."""
        opt = IROptimizer(do_folding=False, do_propagation=False, do_dce=False)
        instr = make_instr(IROpcode.ADD, dest=tmp(1), src1=lit(5), src2=lit(5))
        result = opt.optimize([instr])
        self.assertEqual(result[0].opcode, IROpcode.ADD)

    def test_dce_disabled(self):
        """При do_dce=False — мёртвый код не удаляется."""
        opt = IROptimizer(do_folding=False, do_propagation=False, do_dce=False)
        instrs = [
            make_instr(IROpcode.JUMP, src1=label("end")),
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(42)),
            make_instr(IROpcode.LABEL, src1=label("end")),
        ]
        result = opt.optimize(instrs)
        opcodes = [i.opcode for i in result]
        self.assertIn(IROpcode.MOVE, opcodes, "DCE выключен — MOVE должен остаться")

    def test_propagation_disabled(self):
        """При do_propagation=False — подстановка не происходит."""
        opt = IROptimizer(do_folding=False, do_propagation=False, do_dce=False)
        instrs = [
            make_instr(IROpcode.MOVE, dest=tmp(1), src1=lit(5)),
            make_instr(IROpcode.ADD, dest=tmp(2), src1=tmp(1), src2=lit(3)),
        ]
        result = opt.optimize(instrs)
        # src1 ADD остаётся TempOperand, не LiteralOperand
        self.assertIsInstance(result[1].src1, TempOperand)


if __name__ == "__main__":
    unittest.main()
