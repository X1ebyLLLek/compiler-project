"""
Генератор промежуточного представления (IR) для MiniCompiler.

Обходит декорированное AST (после семантического анализа)
и генерирует трёхадресный код (three-address code).

Архитектура:
  - IRGenerator наследуется от ASTVisitor
  - generate(ast) → IRProgram
  - Для каждой FunctionDeclNode создаётся IRFunction с CFG
  - Внутри функции поддерживается «текущий блок» (current_block)
  - Временные переменные (t1, t2, ...) нумеруются внутри функции

Sprint 4: IR Generation.
"""

from __future__ import annotations

from typing import Optional, Dict, List

from src.parser.ast_nodes import (
    ASTVisitor,
    ProgramNode,
    FunctionDeclNode, StructDeclNode, ParamNode,
    BlockStmtNode, ExprStmtNode, IfStmtNode, WhileStmtNode,
    ForStmtNode, ReturnStmtNode, VarDeclStmtNode,
    LiteralExprNode, IdentifierExprNode, BinaryExprNode,
    UnaryExprNode, CallExprNode, AssignmentExprNode,
    ExpressionNode,
)
from .ir_instructions import (
    IRInstruction, IROpcode, IROperand,
    TempOperand, VarOperand, LiteralOperand, LabelOperand,
    BINARY_OP_TO_OPCODE,
)
from .basic_block import BasicBlock
from .control_flow import ControlFlowGraph, IRFunction, IRProgram


class IRGenerator(ASTVisitor):
    """
    Генератор промежуточного представления.

    Принцип работы:
      1. Обходит AST через Visitor
      2. Для каждой функции создаёт IRFunction с CFG
      3. Выражения транслируются в инструкции трёхадресного кода
         и возвращают операнд-результат (TempOperand или VarOperand)
      4. Инструкции добавляются в текущий базовый блок (_current_block)
      5. При встрече ветвления/цикла создаются новые блоки и связываются рёбрами CFG

    Использование:
        generator = IRGenerator()
        ir_program = generator.generate(ast)
    """

    def __init__(self):
        # Текущая обрабатываемая функция
        self._current_func: Optional[IRFunction] = None

        # Текущий базовый блок, в который добавляются инструкции
        self._current_block: Optional[BasicBlock] = None

        # Счётчик временных переменных (сбрасывается при входе в функцию)
        self._temp_counter: int = 0

        # Счётчик меток (глобальный, для уникальности)
        self._label_counter: int = 0

        # Отображение: имя переменной → VarOperand (в рамках текущей функции)
        self._var_map: Dict[str, VarOperand] = {}

    # ----------------------------------------------------------------
    # Публичный интерфейс
    # ----------------------------------------------------------------

    def generate(self, ast: ProgramNode) -> IRProgram:
        """
        Сгенерировать IR для всей программы.

        :param ast: декорированное AST программы
        :return: IRProgram с IR всех функций
        """
        self._program = IRProgram()
        self._temp_counter = 0
        self._label_counter = 0
        ast.accept(self)
        return self._program

    # ----------------------------------------------------------------
    # Вспомогательные методы
    # ----------------------------------------------------------------

    def _new_temp(self) -> TempOperand:
        """Создать новую временную переменную."""
        self._temp_counter += 1
        if self._current_func:
            self._current_func.temp_count = self._temp_counter
        return TempOperand(self._temp_counter)

    def _new_label(self, prefix: str = "L") -> str:
        """Создать уникальное имя метки."""
        self._label_counter += 1
        return f"{prefix}_{self._label_counter}"

    def _new_block(self, label: str) -> BasicBlock:
        """Создать новый базовый блок и зарегистрировать его в CFG."""
        block = BasicBlock(label)
        if self._current_func:
            self._current_func.cfg.add_block(block)
        return block

    def _emit(self, instr: IRInstruction) -> None:
        """Добавить инструкцию в текущий блок."""
        if self._current_block is not None:
            self._current_block.add_instruction(instr)

    def _switch_block(self, block: BasicBlock) -> None:
        """Переключиться на новый текущий блок."""
        self._current_block = block

    def _var_operand(self, name: str) -> VarOperand:
        """Получить или создать VarOperand для переменной."""
        if name not in self._var_map:
            self._var_map[name] = VarOperand(name, 0)
        return self._var_map[name]

    def _literal_operand(self, value, type_name: str = "") -> LiteralOperand:
        """Создать операнд-литерал."""
        return LiteralOperand(value, type_name)

    # ----------------------------------------------------------------
    # Visitor: корень программы
    # ----------------------------------------------------------------

    def visit_program(self, node: ProgramNode):
        for decl in node.declarations:
            decl.accept(self)

    # ----------------------------------------------------------------
    # Visitor: объявления
    # ----------------------------------------------------------------

    def visit_function_decl(self, node: FunctionDeclNode):
        """Обработка объявления функции — создаём IRFunction и CFG."""
        ret_type = node.return_type if node.return_type else "void"
        params = [(p.name, p.param_type) for p in node.parameters]

        func = IRFunction(
            name=node.name,
            return_type=ret_type,
            params=params,
        )

        # Инициализируем состояние генератора для новой функции
        self._current_func = func
        self._temp_counter = 0
        self._var_map = {}

        # Создаём входной блок
        entry = self._new_block("entry")
        self._switch_block(entry)

        # Параметры функции: выделяем «ячейки» и копируем значения
        for p in node.parameters:
            var_op = self._var_operand(p.name)
            # ALLOCA — выделить место для параметра
            self._emit(IRInstruction(
                opcode=IROpcode.ALLOCA,
                dest=var_op,
                comment=f"параметр {p.param_type} {p.name}",
            ))
            # Параметр уже доступен через имя — помечаем как инициализированный
            # (специальный PARAM-маркер для аргументов в начале блока)
            param_temp = self._new_temp()
            self._emit(IRInstruction(
                opcode=IROpcode.PARAM,
                src1=LiteralOperand(params.index((p.name, p.param_type))),
                src2=var_op,
                comment=f"аргумент {p.name}",
            ))

        # Генерируем тело функции
        if node.body:
            for stmt in node.body.statements:
                stmt.accept(self)

        # Если последний блок не завершён RETURN — добавляем неявный return
        if self._current_block and not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.RETURN,
                comment="неявный return void",
            ))

        # Добавляем функцию в программу
        if self._program:
            self._program.add_function(func)

        self._current_func = None
        self._current_block = None

    def visit_struct_decl(self, node: StructDeclNode):
        """Структуры не генерируют IR (только объявления типов)."""
        pass

    def visit_param(self, node: ParamNode):
        pass

    # ----------------------------------------------------------------
    # Visitor: инструкции
    # ----------------------------------------------------------------

    def visit_block_stmt(self, node: BlockStmtNode):
        """Блок инструкций — last просто обходим по очереди."""
        for stmt in node.statements:
            stmt.accept(self)

    def visit_var_decl_stmt(self, node: VarDeclStmtNode):
        """
        Объявление переменной: выделяем место, если есть инициализатор —
        вычисляем его и сохраняем.
        """
        var_op = self._var_operand(node.name)

        # ALLOCA — выделить место в стеке
        self._emit(IRInstruction(
            opcode=IROpcode.ALLOCA,
            dest=var_op,
            comment=f"{node.var_type} {node.name}",
        ))

        if node.initializer:
            # Вычислить значение инициализатора
            val_op = self._gen_expr(node.initializer)
            # STORE значение в переменную
            self._emit(IRInstruction(
                opcode=IROpcode.STORE,
                dest=var_op,
                src1=val_op,
                comment=f"{node.name} = ...",
            ))

    def visit_expr_stmt(self, node: ExprStmtNode):
        """Инструкция-выражение — генерируем код, результат игнорируем."""
        self._gen_expr(node.expression)

    def visit_if_stmt(self, node: IfStmtNode):
        """
        Генерация кода для if-else:

            [вычисление условия]
            JUMP_IF cond, L_then
            JUMP L_else

          L_then:
            [then-ветка]
            JUMP L_endif

          L_else:      (если есть else)
            [else-ветка]
            JUMP L_endif

          L_endif:
        """
        # Метки
        then_label  = self._new_label("L_then")
        else_label  = self._new_label("L_else")
        endif_label = self._new_label("L_endif")

        # Вычисляем условие
        cond_op = self._gen_expr(node.condition)

        # Переход по условию
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP_IF,
            src1=cond_op,
            src2=LabelOperand(then_label),
            comment="если условие истинно",
        ))
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP,
            src1=LabelOperand(else_label),
        ))

        # --- Блок then ---
        then_block = self._new_block(then_label)
        self._current_block.add_successor(then_block)
        self._switch_block(then_block)
        node.then_branch.accept(self)
        if not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(endif_label),
            ))

        # --- Блок else ---
        else_block = self._new_block(else_label)
        # else_block — преемник предыдущего блока if (при отрицательном условии)
        # Ищем блок условия по предшественникам then
        if then_block.predecessors:
            then_block.predecessors[0].add_successor(else_block)

        self._switch_block(else_block)
        if node.else_branch:
            node.else_branch.accept(self)
        if not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(endif_label),
            ))

        # --- Блок endif (точка слияния) ---
        endif_block = self._new_block(endif_label)
        # then-блок и else-блок → endif
        self._current_func.cfg.blocks[-3].add_successor(endif_block) \
            if len(self._current_func.cfg.blocks) >= 3 else None

        # Находим актуальные блоки then и else
        then_blk = self._current_func.cfg.get_block(then_label)
        else_blk = self._current_func.cfg.get_block(else_label)
        if then_blk and endif_block not in then_blk.successors:
            then_blk.add_successor(endif_block)
        if else_blk and endif_block not in else_blk.successors:
            else_blk.add_successor(endif_block)

        self._switch_block(endif_block)

    def visit_while_stmt(self, node: WhileStmtNode):
        """
        Генерация кода для цикла while:

          L_while_cond:
            [вычисление условия]
            JUMP_IF cond, L_while_body
            JUMP L_while_end

          L_while_body:
            [тело цикла]
            JUMP L_while_cond

          L_while_end:
        """
        cond_label = self._new_label("L_while_cond")
        body_label = self._new_label("L_while_body")
        end_label  = self._new_label("L_while_end")

        # Переход в блок условия
        if not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(cond_label),
            ))

        # --- Блок проверки условия ---
        cond_block = self._new_block(cond_label)
        prev_block = self._current_block
        prev_block.add_successor(cond_block)
        self._switch_block(cond_block)

        cond_op = self._gen_expr(node.condition)
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP_IF,
            src1=cond_op,
            src2=LabelOperand(body_label),
            comment="тело цикла если условие истинно",
        ))
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP,
            src1=LabelOperand(end_label),
        ))

        # --- Блок тела цикла ---
        body_block = self._new_block(body_label)
        cond_block.add_successor(body_block)
        self._switch_block(body_block)
        node.body.accept(self)

        # Обратная дуга: тело → условие (back edge)
        if not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(cond_label),
            ))
        self._current_block.add_successor(cond_block)

        # --- Блок выхода из цикла ---
        end_block = self._new_block(end_label)
        cond_block.add_successor(end_block)
        self._switch_block(end_block)

    def visit_for_stmt(self, node: ForStmtNode):
        """
        Генерация кода для цикла for:

            [инициализация]
          L_for_cond:
            [условие]
            JUMP_IF cond, L_for_body
            JUMP L_for_end
          L_for_body:
            [тело]
            [обновление]
            JUMP L_for_cond
          L_for_end:
        """
        cond_label = self._new_label("L_for_cond")
        body_label = self._new_label("L_for_body")
        end_label  = self._new_label("L_for_end")

        # Инициализация (может быть VarDecl или ExprStmt)
        if node.init:
            node.init.accept(self)

        # Переход к проверке условия
        if not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(cond_label),
            ))

        # --- Блок проверки условия ---
        cond_block = self._new_block(cond_label)
        self._current_block.add_successor(cond_block)
        self._switch_block(cond_block)

        if node.condition:
            cond_op = self._gen_expr(node.condition)
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP_IF,
                src1=cond_op,
                src2=LabelOperand(body_label),
            ))
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(end_label),
            ))
        else:
            # Бесконечный цикл без условия
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(body_label),
            ))

        # --- Блок тела цикла ---
        body_block = self._new_block(body_label)
        cond_block.add_successor(body_block)
        self._switch_block(body_block)
        node.body.accept(self)

        # Шаг обновления
        if node.update:
            self._gen_expr(node.update)

        # Обратная дуга
        if not self._current_block.is_terminated():
            self._emit(IRInstruction(
                opcode=IROpcode.JUMP,
                src1=LabelOperand(cond_label),
            ))
        self._current_block.add_successor(cond_block)

        # --- Блок выхода ---
        end_block = self._new_block(end_label)
        cond_block.add_successor(end_block)
        self._switch_block(end_block)

    def visit_return_stmt(self, node: ReturnStmtNode):
        """Инструкция return."""
        if node.value is not None:
            val_op = self._gen_expr(node.value)
            self._emit(IRInstruction(
                opcode=IROpcode.RETURN,
                src1=val_op,
                comment="return значение",
            ))
        else:
            self._emit(IRInstruction(
                opcode=IROpcode.RETURN,
                comment="return void",
            ))

    # ----------------------------------------------------------------
    # Генерация кода для выражений
    # ----------------------------------------------------------------

    def _gen_expr(self, node: ExpressionNode) -> IROperand:
        """
        Сгенерировать код для выражения.
        Возвращает операнд, содержащий результат.
        """
        result = node.accept(self)
        return result

    def visit_literal_expr(self, node: LiteralExprNode) -> IROperand:
        """Литерал → операнд-константа (без инструкций)."""
        return self._literal_operand(node.value, node.literal_type)

    def visit_identifier_expr(self, node: IdentifierExprNode) -> IROperand:
        """
        Идентификатор → загрузка значения переменной.
        Генерирует LOAD t_i, [var].
        """
        var_op = self._var_operand(node.name)
        dest = self._new_temp()
        self._emit(IRInstruction(
            opcode=IROpcode.LOAD,
            dest=dest,
            src1=var_op,
            comment=f"загрузить {node.name}",
        ))
        return dest

    def visit_binary_expr(self, node: BinaryExprNode) -> IROperand:
        """
        Бинарное выражение → трёхадресная инструкция.

        Операторы && и || используют короткое замыкание:
        правый операнд вычисляется только при необходимости.
        """
        # Короткое замыкание: && и || обрабатываются отдельно
        if node.operator == "&&":
            return self._gen_short_circuit_and(node.left, node.right)
        if node.operator == "||":
            return self._gen_short_circuit_or(node.left, node.right)

        left_op = self._gen_expr(node.left)
        right_op = self._gen_expr(node.right)

        opcode = BINARY_OP_TO_OPCODE.get(node.operator)
        if opcode is None:
            opcode = IROpcode.MOVE

        dest = self._new_temp()
        self._emit(IRInstruction(
            opcode=opcode,
            dest=dest,
            src1=left_op,
            src2=right_op,
            comment=f"{node.operator}",
        ))
        return dest

    # ----------------------------------------------------------------
    # Короткое замыкание для && и ||
    # ----------------------------------------------------------------

    def _gen_short_circuit_and(self, left_node, right_node) -> IROperand:
        """
        Генерация && с коротким замыканием.

        Схема:
            [вычислить левый]
            JUMP_IF_NOT left, L_sc_false_N    ; если ложь — пропустить правый
            [вычислить правый]
            JUMP_IF_NOT right, L_sc_false_N
            STORE result, 1
            JUMP L_sc_end_N

          L_sc_false_N:
            STORE result, 0

          L_sc_end_N:
            dest = LOAD result
        """
        sc_id = self._label_counter + 1  # уникальный идентификатор этой пары меток
        false_label = self._new_label("L_sc_false")
        end_label   = self._new_label("L_sc_end")

        # Временная переменная для хранения булевого результата
        result_var = VarOperand(f"__sc_and_{sc_id}", 0)
        self._emit(IRInstruction(
            opcode=IROpcode.ALLOCA,
            dest=result_var,
            comment="&&: выделить место под результат",
        ))

        # Вычислить левый операнд
        left_op = self._gen_expr(left_node)

        # Если левый ложь → перейти к false-блоку (правый не вычисляется)
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP_IF_NOT,
            src1=left_op,
            src2=LabelOperand(false_label),
            comment="&&: короткое замыкание, левый ложь",
        ))

        # Вычислить правый операнд (достигается только если левый истина)
        right_op = self._gen_expr(right_node)

        # Если правый ложь → перейти к false-блоку
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP_IF_NOT,
            src1=right_op,
            src2=LabelOperand(false_label),
            comment="&&: короткое замыкание, правый ложь",
        ))

        # Оба истина: результат = 1
        self._emit(IRInstruction(
            opcode=IROpcode.STORE,
            dest=result_var,
            src1=LiteralOperand(1),
            comment="&&: оба истина, результат = 1",
        ))
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP,
            src1=LabelOperand(end_label),
        ))

        # --- Блок «ложь» ---
        false_block = self._new_block(false_label)
        self._current_block.add_successor(false_block)
        self._switch_block(false_block)
        self._emit(IRInstruction(
            opcode=IROpcode.STORE,
            dest=result_var,
            src1=LiteralOperand(0),
            comment="&&: один из операндов ложь, результат = 0",
        ))
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP,
            src1=LabelOperand(end_label),
        ))

        # --- Блок «конец» ---
        end_block = self._new_block(end_label)
        false_block.add_successor(end_block)
        self._switch_block(end_block)

        # Загрузить результат в новую временную
        dest = self._new_temp()
        self._emit(IRInstruction(
            opcode=IROpcode.LOAD,
            dest=dest,
            src1=result_var,
            comment="&&: загрузить итоговый результат",
        ))
        return dest

    def _gen_short_circuit_or(self, left_node, right_node) -> IROperand:
        """
        Генерация || с коротким замыканием.

        Схема:
            [вычислить левый]
            JUMP_IF left, L_sc_true_N    ; если истина — пропустить правый
            [вычислить правый]
            JUMP_IF right, L_sc_true_N
            STORE result, 0
            JUMP L_sc_end_N

          L_sc_true_N:
            STORE result, 1

          L_sc_end_N:
            dest = LOAD result
        """
        sc_id = self._label_counter + 1
        true_label = self._new_label("L_sc_true")
        end_label  = self._new_label("L_sc_end")

        result_var = VarOperand(f"__sc_or_{sc_id}", 0)
        self._emit(IRInstruction(
            opcode=IROpcode.ALLOCA,
            dest=result_var,
            comment="||: выделить место под результат",
        ))

        # Вычислить левый операнд
        left_op = self._gen_expr(left_node)

        # Если левый истина → перейти к true-блоку (правый не вычисляется)
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP_IF,
            src1=left_op,
            src2=LabelOperand(true_label),
            comment="||: короткое замыкание, левый истина",
        ))

        # Вычислить правый операнд
        right_op = self._gen_expr(right_node)

        self._emit(IRInstruction(
            opcode=IROpcode.JUMP_IF,
            src1=right_op,
            src2=LabelOperand(true_label),
            comment="||: короткое замыкание, правый истина",
        ))

        # Оба ложь: результат = 0
        self._emit(IRInstruction(
            opcode=IROpcode.STORE,
            dest=result_var,
            src1=LiteralOperand(0),
            comment="||: оба ложь, результат = 0",
        ))
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP,
            src1=LabelOperand(end_label),
        ))

        # --- Блок «истина» ---
        true_block = self._new_block(true_label)
        self._current_block.add_successor(true_block)
        self._switch_block(true_block)
        self._emit(IRInstruction(
            opcode=IROpcode.STORE,
            dest=result_var,
            src1=LiteralOperand(1),
            comment="||: хотя бы один истина, результат = 1",
        ))
        self._emit(IRInstruction(
            opcode=IROpcode.JUMP,
            src1=LabelOperand(end_label),
        ))

        # --- Блок «конец» ---
        end_block = self._new_block(end_label)
        true_block.add_successor(end_block)
        self._switch_block(end_block)

        dest = self._new_temp()
        self._emit(IRInstruction(
            opcode=IROpcode.LOAD,
            dest=dest,
            src1=result_var,
            comment="||: загрузить итоговый результат",
        ))
        return dest

    def visit_unary_expr(self, node: UnaryExprNode) -> IROperand:
        """
        Унарное выражение: NEG или NOT.
        dest = OP src
        """
        operand_op = self._gen_expr(node.operand)
        dest = self._new_temp()

        if node.operator == "-":
            opcode = IROpcode.NEG
        elif node.operator == "!":
            opcode = IROpcode.NOT
        else:
            opcode = IROpcode.MOVE  # заглушка

        self._emit(IRInstruction(
            opcode=opcode,
            dest=dest,
            src1=operand_op,
            comment=f"унарный {node.operator}",
        ))
        return dest

    def visit_call_expr(self, node: CallExprNode) -> IROperand:
        """
        Вызов функции:
          PARAM 0, arg0
          PARAM 1, arg1
          ...
          dest = CALL func_name
        """
        # Вычисляем аргументы и передаём через PARAM
        arg_operands = []
        for i, arg in enumerate(node.arguments):
            arg_op = self._gen_expr(arg)
            self._emit(IRInstruction(
                opcode=IROpcode.PARAM,
                src1=LiteralOperand(i),
                src2=arg_op,
                comment=f"аргумент {i} для {node.callee}",
            ))
            arg_operands.append(arg_op)

        dest = self._new_temp()
        self._emit(IRInstruction(
            opcode=IROpcode.CALL,
            dest=dest,
            src1=LabelOperand(node.callee),
            args=arg_operands,
            comment=f"вызов {node.callee}",
        ))
        return dest

    def visit_assignment_expr(self, node: AssignmentExprNode) -> IROperand:
        """
        Присваивание: x = expr  или  x += expr  и т.д.

        Для составных операторов (+=, -= и т.д.) сначала загружаем
        текущее значение, применяем операцию, затем сохраняем.
        """
        var_op = self._var_operand(node.target)
        val_op = self._gen_expr(node.value)

        if node.operator == "=":
            # Простое присваивание
            self._emit(IRInstruction(
                opcode=IROpcode.STORE,
                dest=var_op,
                src1=val_op,
                comment=f"{node.target} = ...",
            ))
            return val_op

        # Составное присваивание: x OP= val
        # Шаг 1: загрузить текущее значение x
        cur_temp = self._new_temp()
        self._emit(IRInstruction(
            opcode=IROpcode.LOAD,
            dest=cur_temp,
            src1=var_op,
            comment=f"загрузить {node.target} для {node.operator}",
        ))

        # Шаг 2: выполнить операцию
        base_op_str = node.operator[:-1]  # "+=" -> "+"
        ir_opcode = BINARY_OP_TO_OPCODE.get(base_op_str, IROpcode.ADD)
        result_temp = self._new_temp()
        self._emit(IRInstruction(
            opcode=ir_opcode,
            dest=result_temp,
            src1=cur_temp,
            src2=val_op,
            comment=f"{node.target} {node.operator} ...",
        ))

        # Шаг 3: сохранить результат
        self._emit(IRInstruction(
            opcode=IROpcode.STORE,
            dest=var_op,
            src1=result_temp,
            comment=f"сохранить {node.target}",
        ))
        return result_temp
