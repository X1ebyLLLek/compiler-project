"""
IR-оптимизатор для MiniCompiler (Sprint 7).

Реализует три классических прохода оптимизации над списком IR-инструкций:
  1. Constant Folding — вычисление константных выражений на этапе компиляции
  2. Constant Propagation — подстановка констант вместо переменных
  3. Dead Code Elimination — удаление мёртвого кода

Использование:
    optimizer = IROptimizer()
    optimized = optimizer.optimize(instructions)
    stats = optimizer.get_stats()
"""

from __future__ import annotations

from typing import List, Dict, Optional, Any

from src.ir.ir_instructions import (
    IRInstruction, IROpcode,
    TempOperand, VarOperand, LiteralOperand, LabelOperand, IROperand,
)


class IROptimizer:
    """
    Оптимизатор промежуточного представления.

    Запускает несколько проходов по списку инструкций функции.
    Каждый проход независим — можно включать/выключать отдельно.
    """

    def __init__(
        self,
        do_folding: bool = True,
        do_propagation: bool = True,
        do_dce: bool = True,
    ):
        # Флаги включения конкретных проходов
        self.do_folding = do_folding
        self.do_propagation = do_propagation
        self.do_dce = do_dce

        # Счётчики для статистики
        self._folded = 0        # сколько операций свёрнуто в константу
        self._propagated = 0    # сколько переменных заменено константой
        self._eliminated = 0    # сколько инструкций удалено

    def optimize(self, instructions: List[IRInstruction]) -> List[IRInstruction]:
        """
        Применить все включённые оптимизационные проходы.

        Порядок важен: сначала фолдинг (создаём новые константы),
        потом пропагация (распространяем их), потом DCE (убираем ненужное).
        """
        # Сбрасываем статистику перед каждым запуском
        self._folded = 0
        self._propagated = 0
        self._eliminated = 0

        result = list(instructions)

        if self.do_folding:
            result = self._pass_constant_folding(result)

        if self.do_propagation:
            result = self._pass_constant_propagation(result)

        if self.do_dce:
            result = self._pass_dead_code_elimination(result)

        return result

    def get_stats(self) -> Dict[str, int]:
        """Вернуть статистику последнего запуска optimize()."""
        return {
            "folded": self._folded,
            "propagated": self._propagated,
            "eliminated": self._eliminated,
            "total_optimized": self._folded + self._propagated + self._eliminated,
        }

    # ----------------------------------------------------------------
    # Проход 1: Constant Folding
    # ----------------------------------------------------------------

    def _pass_constant_folding(
        self, instructions: List[IRInstruction]
    ) -> List[IRInstruction]:
        """
        Свернуть бинарные операции над двумя литералами в одну константу.

        Пример: ADD 10, 20 → MOVE 30
        """
        result = []
        for instr in instructions:
            folded = self._try_fold(instr)
            if folded is not None:
                result.append(folded)
                self._folded += 1
            else:
                result.append(instr)
        return result

    def _try_fold(self, instr: IRInstruction) -> Optional[IRInstruction]:
        """Попытаться свернуть инструкцию в MOVE с константой. None — не удалось."""
        # Арифметические бинарные операции, которые умеем сворачивать
        foldable = {
            IROpcode.ADD, IROpcode.SUB, IROpcode.MUL,
            IROpcode.DIV, IROpcode.MOD,
            IROpcode.CMP_EQ, IROpcode.CMP_NE,
            IROpcode.CMP_LT, IROpcode.CMP_LE,
            IROpcode.CMP_GT, IROpcode.CMP_GE,
        }

        if instr.opcode not in foldable:
            return None

        if not isinstance(instr.src1, LiteralOperand):
            return None
        if not isinstance(instr.src2, LiteralOperand):
            return None
        if instr.dest is None:
            return None

        v1 = instr.src1.value
        v2 = instr.src2.value

        # Оба операнда должны быть числами
        if not isinstance(v1, (int, float)) or not isinstance(v2, (int, float)):
            return None

        try:
            result_val = self._compute(instr.opcode, v1, v2)
        except (ZeroDivisionError, ArithmeticError):
            # Деление на ноль — не сворачиваем, оставляем как есть (ошибка в рантайме)
            return None

        new_src = LiteralOperand(value=result_val)
        return IRInstruction(
            opcode=IROpcode.MOVE,
            dest=instr.dest,
            src1=new_src,
            comment=f"folded: {v1} {instr.opcode.value} {v2} = {result_val}",
            source_line=instr.source_line,
        )

    @staticmethod
    def _compute(opcode: IROpcode, a: Any, b: Any) -> Any:
        """Вычислить бинарную операцию над двумя константами."""
        if opcode == IROpcode.ADD:
            return a + b
        if opcode == IROpcode.SUB:
            return a - b
        if opcode == IROpcode.MUL:
            return a * b
        if opcode == IROpcode.DIV:
            # Целочисленное деление (floor) для int
            if isinstance(a, int) and isinstance(b, int):
                return int(a / b)  # не floor, а truncate (как в C)
            return a / b
        if opcode == IROpcode.MOD:
            return int(a) % int(b)
        if opcode == IROpcode.CMP_EQ:
            return 1 if a == b else 0
        if opcode == IROpcode.CMP_NE:
            return 1 if a != b else 0
        if opcode == IROpcode.CMP_LT:
            return 1 if a < b else 0
        if opcode == IROpcode.CMP_LE:
            return 1 if a <= b else 0
        if opcode == IROpcode.CMP_GT:
            return 1 if a > b else 0
        if opcode == IROpcode.CMP_GE:
            return 1 if a >= b else 0
        raise ValueError(f"Неизвестная операция: {opcode}")

    # ----------------------------------------------------------------
    # Проход 2: Constant Propagation
    # ----------------------------------------------------------------

    def _pass_constant_propagation(
        self, instructions: List[IRInstruction]
    ) -> List[IRInstruction]:
        """
        Распространить известные константы вместо переменных.

        Если видим STORE [x], 5 или MOVE x, 5 — запоминаем x=5.
        Потом при встрече LOAD [x] или любого src, где используется x —
        подставляем LiteralOperand(5).

        Осторожность: если переменная переопределяется (STORE снова) —
        обновляем или убираем её из таблицы.
        """
        # Таблица: ключ операнда → LiteralOperand или None (если убита)
        const_table: Dict[str, LiteralOperand] = {}

        result = []
        for instr in instructions:
            # Сначала подставляем константы в src1/src2/args
            new_instr = self._substitute_constants(instr, const_table)

            # Потом обновляем таблицу по dest
            self._update_const_table(new_instr, const_table)

            result.append(new_instr)

        return result

    def _substitute_constants(
        self,
        instr: IRInstruction,
        table: Dict[str, LiteralOperand],
    ) -> IRInstruction:
        """Подставить константы из таблицы в операнды инструкции."""
        changed = False

        new_src1 = self._subst_op(instr.src1, table)
        new_src2 = self._subst_op(instr.src2, table)
        new_args = [self._subst_op(a, table) for a in instr.args]

        if new_src1 is not instr.src1:
            changed = True
        if new_src2 is not instr.src2:
            changed = True
        if any(na is not a for na, a in zip(new_args, instr.args)):
            changed = True

        if not changed:
            return instr

        self._propagated += 1
        return IRInstruction(
            opcode=instr.opcode,
            dest=instr.dest,
            src1=new_src1,
            src2=new_src2,
            args=new_args,
            comment=instr.comment + " [propagated]" if instr.comment else "[propagated]",
            source_line=instr.source_line,
        )

    def _subst_op(
        self,
        op: Optional[IROperand],
        table: Dict[str, LiteralOperand],
    ) -> Optional[IROperand]:
        """Вернуть LiteralOperand если операнд известен как константа, иначе оригинал."""
        if op is None:
            return None
        if isinstance(op, (VarOperand, TempOperand)):
            key = self._op_key(op)
            if key in table:
                return table[key]
        return op

    def _update_const_table(
        self,
        instr: IRInstruction,
        table: Dict[str, LiteralOperand],
    ) -> None:
        """Обновить таблицу констант после выполнения инструкции."""
        if instr.dest is None:
            return

        dest_key = self._op_key(instr.dest)

        # Если это присваивание константы — запоминаем
        if instr.opcode == IROpcode.MOVE and isinstance(instr.src1, LiteralOperand):
            table[dest_key] = instr.src1
        elif instr.opcode == IROpcode.STORE and isinstance(instr.src1, LiteralOperand):
            # STORE [dest], literal
            table[dest_key] = instr.src1
        else:
            # Переопределяем не константой — убиваем запись
            table.pop(dest_key, None)

    # ----------------------------------------------------------------
    # Проход 3: Dead Code Elimination
    # ----------------------------------------------------------------

    def _pass_dead_code_elimination(
        self, instructions: List[IRInstruction]
    ) -> List[IRInstruction]:
        """
        Удалить мёртвый код двумя способами:

        1. Unreachable code: инструкции после безусловного JUMP/RETURN
           до следующей LABEL — они никогда не выполнятся.

        2. Dead stores: MOVE/STORE в переменную, которая больше нигде
           не читается (не используется как src ни одной последующей инструкции).
           Применяем только к временным (TempOperand), чтобы не убивать
           переменные исходника (у них могут быть side effects или отладочные нужды).
        """
        # Шаг 1: убрать недостижимые инструкции
        result = self._remove_unreachable(instructions)

        # Шаг 2: убрать мёртвые сторы временных переменных
        result = self._remove_dead_temp_stores(result)

        return result

    def _remove_unreachable(
        self, instructions: List[IRInstruction]
    ) -> List[IRInstruction]:
        """Убрать код после JUMP/RETURN до следующей метки."""
        result = []
        skip_until_label = False

        for instr in instructions:
            if instr.opcode == IROpcode.LABEL:
                # Метка заканчивает «мёртвую» зону
                skip_until_label = False

            if skip_until_label:
                self._eliminated += 1
                continue

            result.append(instr)

            # Безусловный переход или возврат — всё до следующей метки мертво
            if instr.opcode in (IROpcode.JUMP, IROpcode.RETURN):
                skip_until_label = True

        return result

    def _remove_dead_temp_stores(
        self, instructions: List[IRInstruction]
    ) -> List[IRInstruction]:
        """
        Убрать MOVE/STORE в TempOperand если временная нигде не читается после.

        Делаем backward pass: собираем множество «живых» временных
        и проходим список сзади наперёд.
        """
        # Собрать все использования (src) временных — те что «живые»
        # Backward pass: если temp встречается как src — она живая,
        # если как dest (MOVE) и до этого не встречалась как src — мёртвая.
        live: set = set()
        result_reversed = []

        for instr in reversed(instructions):
            # Если инструкция пишет в TempOperand и этот temp нигде не используется —
            # убираем. Исключение: вызовы функций (могут иметь side effects).
            dest_is_dead_temp = (
                isinstance(instr.dest, TempOperand)
                and instr.opcode in (IROpcode.MOVE, IROpcode.LOAD)
                and self._op_key(instr.dest) not in live
                # Не убираем если это результат вызова функции
                and instr.opcode != IROpcode.CALL
            )

            if dest_is_dead_temp:
                self._eliminated += 1
                # Но src всё равно могут быть живыми — не добавляем их
                continue

            result_reversed.append(instr)

            # Отмечаем src как живые
            for op in [instr.src1, instr.src2] + list(instr.args):
                if isinstance(op, TempOperand):
                    live.add(self._op_key(op))

            # Если есть dest — убираем из live (теперь она определена)
            if isinstance(instr.dest, TempOperand):
                live.discard(self._op_key(instr.dest))

        return list(reversed(result_reversed))

    @staticmethod
    def _op_key(op: Optional[IROperand]) -> str:
        """Ключ операнда для словарей."""
        if op is None:
            return ""
        if isinstance(op, TempOperand):
            return f"__t{op.number}"
        if isinstance(op, VarOperand):
            return f"{op.name}_{op.version}"
        return str(op)
