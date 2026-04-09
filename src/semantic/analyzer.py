"""
Семантический анализатор MiniCompiler.

Обходит AST через Visitor, заполняет таблицу символов,
проверяет типы и области видимости,
декорирует узлы AST типовыми аннотациями.
"""

from __future__ import annotations
import sys
from typing import Optional, List, Dict

from src.parser.ast_nodes import (
    ASTVisitor, ASTNode, ProgramNode,
    LiteralExprNode, IdentifierExprNode, BinaryExprNode,
    UnaryExprNode, CallExprNode, AssignmentExprNode,
    BlockStmtNode, ExprStmtNode, IfStmtNode, WhileStmtNode,
    ForStmtNode, ReturnStmtNode, VarDeclStmtNode,
    FunctionDeclNode, StructDeclNode, ParamNode,
    ExpressionNode,
)

from .symbol_table import SymbolTable, SymbolInfo, SymbolKind
from .type_system import (
    Type, FunctionType, StructType,
    INT_TYPE, FLOAT_TYPE, BOOL_TYPE, VOID_TYPE, STRING_TYPE, ERROR_TYPE,
    BUILTIN_TYPES, resolve_type_name,
    is_assignable, binary_result_type, unary_result_type,
    is_numeric, is_boolean,
)
from .errors import SemanticError, SemanticErrorCollector, SemanticErrorKind


class SemanticAnalyzer(ASTVisitor):
    """
    Семантический анализатор — обход AST с проверкой типов
    и заполнением таблицы символов.
    """

    def __init__(self):
        self._symbol_table = SymbolTable()
        self._errors = SemanticErrorCollector()
        self._struct_types: Dict[str, StructType] = {}
        # Текущая функция (для проверки return)
        self._current_function: Optional[FunctionDeclNode] = None
        self._current_function_return_type: Optional[Type] = None
        # AST после декорирования
        self._ast: Optional[ProgramNode] = None
        # Кэш source-строк для красивых ошибок
        self._source_lines: Optional[List[str]] = None

    # --- Публичный интерфейс ---

    def analyze(self, ast: ProgramNode, source: Optional[str] = None) -> ProgramNode:
        """Выполнить полный семантический анализ AST."""
        self._ast = ast
        if source:
            self._source_lines = source.splitlines()

        # Первый проход: собираем объявления функций и структур
        # (позволяет forward references для функций, SEM-2)
        self._collect_declarations(ast)

        # Второй проход: полный анализ
        ast.accept(self)

        return ast

    def get_errors(self) -> List[SemanticError]:
        """Вернуть список семантических ошибок."""
        return self._errors.errors

    def get_symbol_table(self) -> SymbolTable:
        """Вернуть заполненную таблицу символов."""
        return self._symbol_table

    def get_decorated_ast(self) -> Optional[ProgramNode]:
        """Вернуть декорированный AST."""
        return self._ast

    def has_errors(self) -> bool:
        return self._errors.has_errors

    def format_errors(self) -> str:
        return self._errors.format_all(self._source_lines)

    # --- Первый проход: сбор объявлений (forward references) ---

    def _collect_declarations(self, program: ProgramNode):
        """
        Обход верхнего уровня для регистрации функций и структур.
        Это позволяет функциям вызывать друг друга в любом порядке.
        """
        for decl in program.declarations:
            if isinstance(decl, FunctionDeclNode):
                self._register_function(decl)
            elif isinstance(decl, StructDeclNode):
                self._register_struct(decl)

    def _register_function(self, node: FunctionDeclNode):
        """Зарегистрировать сигнатуру функции в глобальной области."""
        # Разрешаем тип возврата
        ret_type = self._resolve_type(node.return_type) if node.return_type else VOID_TYPE

        # Разрешаем типы параметров
        param_types = []
        for p in node.parameters:
            pt = self._resolve_type(p.param_type)
            param_types.append(pt)

        func_type = FunctionType(
            name=node.name,
            param_types=tuple(param_types),
            return_type=ret_type,
        )

        sym = SymbolInfo(
            name=node.name,
            type=func_type,
            kind=SymbolKind.FUNCTION,
            line=node.line,
            column=node.column,
            params=param_types,
            return_type=ret_type,
            initialized=True,
        )

        if not self._symbol_table.insert(sym):
            self._errors.add_error(
                kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                message=f"повторное объявление функции '{node.name}'",
                line=node.line,
                column=node.column,
                suggestion=f"функция '{node.name}' уже объявлена ранее",
            )

    def _register_struct(self, node: StructDeclNode):
        """Зарегистрировать структуру в глобальной области."""
        fields_dict: Dict[str, Type] = {}
        fields_tuple = []
        seen_fields = set()

        for f in node.fields:
            ft = self._resolve_type(f.var_type)
            if f.name in seen_fields:
                self._errors.add_error(
                    kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                    message=f"повторное объявление поля '{f.name}' в структуре '{node.name}'",
                    line=f.line,
                    column=f.column,
                )
            else:
                seen_fields.add(f.name)
                fields_dict[f.name] = ft
                fields_tuple.append((f.name, ft))

        struct_type = StructType(
            name=node.name,
            fields=tuple(fields_tuple),
        )
        self._struct_types[node.name] = struct_type

        sym = SymbolInfo(
            name=node.name,
            type=struct_type,
            kind=SymbolKind.STRUCT,
            line=node.line,
            column=node.column,
            fields=fields_dict,
            initialized=True,
        )

        if not self._symbol_table.insert(sym):
            self._errors.add_error(
                kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                message=f"повторное объявление структуры '{node.name}'",
                line=node.line,
                column=node.column,
            )

    # --- Разрешение типов ---

    def _resolve_type(self, type_name: Optional[str]) -> Type:
        """Преобразовать строковое имя типа в объект Type."""
        if type_name is None:
            return VOID_TYPE
        t = resolve_type_name(type_name, self._struct_types)
        if t is None:
            # Неизвестный тип — сообщаем, но не падаем
            return ERROR_TYPE
        return t

    # --- Визит: корень программы ---

    def visit_program(self, node: ProgramNode):
        for decl in node.declarations:
            decl.accept(self)

    # --- Визит: объявления ---

    def visit_function_decl(self, node: FunctionDeclNode):
        """Анализ тела функции: параметры, тело, return."""
        ret_type = self._resolve_type(node.return_type) if node.return_type else VOID_TYPE

        # Сохраняем контекст функции для проверки return
        prev_func = self._current_function
        prev_ret = self._current_function_return_type
        self._current_function = node
        self._current_function_return_type = ret_type

        # Новая область: параметры + тело
        self._symbol_table.enter_scope(f"function:{node.name}")

        for p in node.parameters:
            pt = self._resolve_type(p.param_type)
            if pt == VOID_TYPE:
                self._errors.add_error(
                    kind=SemanticErrorKind.VOID_VARIABLE,
                    message=f"параметр '{p.name}' не может иметь тип void",
                    line=p.line,
                    column=p.column,
                    context=f"в функции '{node.name}'",
                )
            sym = SymbolInfo(
                name=p.name,
                type=pt,
                kind=SymbolKind.PARAMETER,
                line=p.line,
                column=p.column,
                initialized=True,
            )
            if not self._symbol_table.insert(sym):
                self._errors.add_error(
                    kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                    message=f"повторное объявление параметра '{p.name}'",
                    line=p.line,
                    column=p.column,
                    context=f"в функции '{node.name}'",
                )

        # Анализ тела (без дополнительного enter_scope — блок сам откроет)
        if node.body:
            # Не вызываем visit_block_stmt напрямую, чтобы избежать
            # двойного вложения scope — обходим statements блока
            for stmt in node.body.statements:
                stmt.accept(self)

        self._symbol_table.exit_scope()

        # Восстанавливаем контекст
        self._current_function = prev_func
        self._current_function_return_type = prev_ret

    def visit_struct_decl(self, node: StructDeclNode):
        """Структуры уже обработаны в первом проходе."""
        pass

    def visit_param(self, node: ParamNode):
        pass

    # --- Визит: инструкции ---

    def visit_block_stmt(self, node: BlockStmtNode):
        """Блок создаёт новую область видимости."""
        self._symbol_table.enter_scope("block")
        for stmt in node.statements:
            stmt.accept(self)
        self._symbol_table.exit_scope()

    def visit_var_decl_stmt(self, node: VarDeclStmtNode):
        """Объявление переменной: проверка типа и инициализатора."""
        var_type = self._resolve_type(node.var_type)

        if var_type == VOID_TYPE:
            self._errors.add_error(
                kind=SemanticErrorKind.VOID_VARIABLE,
                message=f"переменная '{node.name}' не может иметь тип void",
                line=node.line,
                column=node.column,
            )

        initialized = False
        if node.initializer:
            init_type = self._check_expression(node.initializer)
            initialized = True

            if var_type != ERROR_TYPE and init_type != ERROR_TYPE:
                if not is_assignable(var_type, init_type):
                    self._errors.add_error(
                        kind=SemanticErrorKind.TYPE_MISMATCH,
                        message=f"несовместимые типы при инициализации '{node.name}'",
                        line=node.line,
                        column=node.column,
                        expected=str(var_type),
                        actual=str(init_type),
                    )

        sym = SymbolInfo(
            name=node.name,
            type=var_type,
            kind=SymbolKind.VARIABLE,
            line=node.line,
            column=node.column,
            initialized=initialized,
        )

        if not self._symbol_table.insert(sym):
            existing = self._symbol_table.lookup_local(node.name)
            self._errors.add_error(
                kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                message=f"повторное объявление переменной '{node.name}'",
                line=node.line,
                column=node.column,
                suggestion=(f"уже объявлена в строке {existing.line}"
                            if existing else None),
            )

    def visit_expr_stmt(self, node: ExprStmtNode):
        """Инструкция-выражение."""
        self._check_expression(node.expression)

    def visit_if_stmt(self, node: IfStmtNode):
        """Условие if: должно быть bool."""
        cond_type = self._check_expression(node.condition)
        if cond_type != ERROR_TYPE and not is_boolean(cond_type):
            self._errors.add_error(
                kind=SemanticErrorKind.INVALID_CONDITION_TYPE,
                message="условие if должно быть типа bool",
                line=node.line,
                column=node.column,
                expected="bool",
                actual=str(cond_type),
            )
        node.then_branch.accept(self)
        if node.else_branch:
            node.else_branch.accept(self)

    def visit_while_stmt(self, node: WhileStmtNode):
        """Условие while: должно быть bool."""
        cond_type = self._check_expression(node.condition)
        if cond_type != ERROR_TYPE and not is_boolean(cond_type):
            self._errors.add_error(
                kind=SemanticErrorKind.INVALID_CONDITION_TYPE,
                message="условие while должно быть типа bool",
                line=node.line,
                column=node.column,
                expected="bool",
                actual=str(cond_type),
            )
        node.body.accept(self)

    def visit_for_stmt(self, node: ForStmtNode):
        """Цикл for: инит, условие, обновление."""
        # init может быть VarDecl или ExprStmt — открываем scope для init переменной
        self._symbol_table.enter_scope("for")

        if node.init:
            node.init.accept(self)

        if node.condition:
            cond_type = self._check_expression(node.condition)
            if cond_type != ERROR_TYPE and not is_boolean(cond_type):
                self._errors.add_error(
                    kind=SemanticErrorKind.INVALID_CONDITION_TYPE,
                    message="условие for должно быть типа bool",
                    line=node.line,
                    column=node.column,
                    expected="bool",
                    actual=str(cond_type),
                )

        if node.update:
            self._check_expression(node.update)

        node.body.accept(self)
        self._symbol_table.exit_scope()

    def visit_return_stmt(self, node: ReturnStmtNode):
        """Проверка return: тип должен совпадать с объявленным."""
        if self._current_function is None:
            self._errors.add_error(
                kind=SemanticErrorKind.INVALID_RETURN_TYPE,
                message="return вне функции",
                line=node.line,
                column=node.column,
            )
            return

        expected_ret = self._current_function_return_type or VOID_TYPE

        if node.value is not None:
            actual_type = self._check_expression(node.value)
            if expected_ret == VOID_TYPE:
                self._errors.add_error(
                    kind=SemanticErrorKind.INVALID_RETURN_TYPE,
                    message=f"функция '{self._current_function.name}' объявлена как void, но возвращает значение",
                    line=node.line,
                    column=node.column,
                    expected="void",
                    actual=str(actual_type),
                    context=f"в функции '{self._current_function.name}'",
                )
            elif actual_type != ERROR_TYPE and not is_assignable(expected_ret, actual_type):
                self._errors.add_error(
                    kind=SemanticErrorKind.INVALID_RETURN_TYPE,
                    message=f"несовместимый тип возврата в функции '{self._current_function.name}'",
                    line=node.line,
                    column=node.column,
                    expected=str(expected_ret),
                    actual=str(actual_type),
                    context=f"в функции '{self._current_function.name}'",
                )
        else:
            # return без значения
            if expected_ret != VOID_TYPE:
                self._errors.add_error(
                    kind=SemanticErrorKind.INVALID_RETURN_TYPE,
                    message=f"функция '{self._current_function.name}' должна возвращать '{expected_ret}', но return без значения",
                    line=node.line,
                    column=node.column,
                    expected=str(expected_ret),
                    actual="void",
                    context=f"в функции '{self._current_function.name}'",
                )

    # --- Проверка выражений ---

    def _check_expression(self, node: ExpressionNode) -> Type:
        """
        Вычислить тип выражения и установить аннотацию.
        Возвращает Type выражения.
        """
        result = node.accept(self)
        if result is None:
            return ERROR_TYPE
        # сохраняем тип на узле AST
        node._resolved_type = result
        return result

    def visit_literal_expr(self, node: LiteralExprNode) -> Type:
        """Тип литерала."""
        type_map = {
            "int": INT_TYPE,
            "float": FLOAT_TYPE,
            "string": STRING_TYPE,
            "bool": BOOL_TYPE,
        }
        t = type_map.get(node.literal_type, ERROR_TYPE)
        node._resolved_type = t
        return t

    def visit_identifier_expr(self, node: IdentifierExprNode) -> Type:
        """Поиск переменной в таблице символов."""
        sym = self._symbol_table.lookup(node.name)
        if sym is None:
            # Попытка найти похожее имя для подсказки
            suggestion = self._find_similar_name(node.name)
            self._errors.add_error(
                kind=SemanticErrorKind.UNDECLARED_VARIABLE,
                message=f"необъявленная переменная '{node.name}'",
                line=node.line,
                column=node.column,
                suggestion=suggestion,
            )
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        node._resolved_type = sym.type
        return sym.type

    def visit_binary_expr(self, node: BinaryExprNode) -> Type:
        """Проверка типов бинарной операции."""
        left_type = self._check_expression(node.left)
        right_type = self._check_expression(node.right)

        result = binary_result_type(node.operator, left_type, right_type)
        if result is None:
            self._errors.add_error(
                kind=SemanticErrorKind.INVALID_OPERATOR,
                message=f"оператор '{node.operator}' не применим к типам '{left_type}' и '{right_type}'",
                line=node.line,
                column=node.column,
                expected=f"совместимые типы для '{node.operator}'",
                actual=f"{left_type} {node.operator} {right_type}",
            )
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        node._resolved_type = result
        return result

    def visit_unary_expr(self, node: UnaryExprNode) -> Type:
        """Проверка типов унарной операции."""
        operand_type = self._check_expression(node.operand)

        result = unary_result_type(node.operator, operand_type)
        if result is None:
            self._errors.add_error(
                kind=SemanticErrorKind.INVALID_OPERATOR,
                message=f"оператор '{node.operator}' не применим к типу '{operand_type}'",
                line=node.line,
                column=node.column,
            )
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        node._resolved_type = result
        return result

    def visit_call_expr(self, node: CallExprNode) -> Type:
        """Проверка вызова функции: сигнатура, аргументы, типы."""
        sym = self._symbol_table.lookup(node.callee)

        if sym is None:
            self._errors.add_error(
                kind=SemanticErrorKind.UNDECLARED_FUNCTION,
                message=f"необъявленная функция '{node.callee}'",
                line=node.line,
                column=node.column,
                suggestion=self._find_similar_name(node.callee),
            )
            # Всё равно проверяем аргументы
            for arg in node.arguments:
                self._check_expression(arg)
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        if sym.kind != SymbolKind.FUNCTION:
            self._errors.add_error(
                kind=SemanticErrorKind.NOT_A_FUNCTION,
                message=f"'{node.callee}' не является функцией",
                line=node.line,
                column=node.column,
            )
            for arg in node.arguments:
                self._check_expression(arg)
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        # Проверка количества аргументов
        expected_count = len(sym.params) if sym.params else 0
        actual_count = len(node.arguments)
        if actual_count != expected_count:
            func_sig = f"{node.callee}({', '.join(str(p) for p in sym.params)})" if sym.params else f"{node.callee}()"
            self._errors.add_error(
                kind=SemanticErrorKind.ARGUMENT_COUNT_MISMATCH,
                message=f"несоответствие количества аргументов при вызове '{node.callee}'",
                line=node.line,
                column=node.column,
                expected=f"{expected_count} аргумент(ов)",
                actual=f"{actual_count} аргумент(ов)",
                suggestion=f"сигнатура: {func_sig}",
            )

        # Проверка типов аргументов
        param_types = sym.params or []
        for i, arg in enumerate(node.arguments):
            arg_type = self._check_expression(arg)
            if i < len(param_types):
                if arg_type != ERROR_TYPE and not is_assignable(param_types[i], arg_type):
                    self._errors.add_error(
                        kind=SemanticErrorKind.ARGUMENT_TYPE_MISMATCH,
                        message=f"несовместимый тип аргумента {i + 1} при вызове '{node.callee}'",
                        line=arg.line,
                        column=arg.column,
                        expected=str(param_types[i]),
                        actual=str(arg_type),
                        context=f"при вызове '{node.callee}'",
                    )

        ret = sym.return_type if sym.return_type else VOID_TYPE
        node._resolved_type = ret
        return ret

    def visit_assignment_expr(self, node: AssignmentExprNode) -> Type:
        """Проверка присваивания: совместимость типов."""
        sym = self._symbol_table.lookup(node.target)

        if sym is None:
            self._errors.add_error(
                kind=SemanticErrorKind.UNDECLARED_VARIABLE,
                message=f"необъявленная переменная '{node.target}'",
                line=node.line,
                column=node.column,
                suggestion=self._find_similar_name(node.target),
            )
            self._check_expression(node.value)
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        if sym.kind == SymbolKind.FUNCTION:
            self._errors.add_error(
                kind=SemanticErrorKind.INVALID_ASSIGNMENT_TARGET,
                message=f"нельзя присваивать значение функции '{node.target}'",
                line=node.line,
                column=node.column,
            )
            self._check_expression(node.value)
            node._resolved_type = ERROR_TYPE
            return ERROR_TYPE

        value_type = self._check_expression(node.value)

        target_type = sym.type

        # Для составных операторов (+=, -= и т.д.) проверяем арифметику
        if node.operator != "=":
            # Определяем базовый оператор из составного
            base_op = node.operator[0]  # '+' из '+='
            result = binary_result_type(base_op, target_type, value_type)
            if result is None and target_type != ERROR_TYPE and value_type != ERROR_TYPE:
                self._errors.add_error(
                    kind=SemanticErrorKind.TYPE_MISMATCH,
                    message=f"оператор '{node.operator}' не применим к типам '{target_type}' и '{value_type}'",
                    line=node.line,
                    column=node.column,
                )
                node._resolved_type = ERROR_TYPE
                return ERROR_TYPE
        else:
            if target_type != ERROR_TYPE and value_type != ERROR_TYPE:
                if not is_assignable(target_type, value_type):
                    self._errors.add_error(
                        kind=SemanticErrorKind.TYPE_MISMATCH,
                        message=f"несовместимые типы при присваивании '{node.target}'",
                        line=node.line,
                        column=node.column,
                        expected=str(target_type),
                        actual=str(value_type),
                    )

        # Помечаем переменную как инициализированную
        sym.initialized = True

        node._resolved_type = target_type
        return target_type

    # --- Подсказки ---

    def _find_similar_name(self, name: str) -> Optional[str]:
        """Поиск похожего имени в текущей и родительских областях."""
        scope = self._symbol_table.current_scope
        best = None
        best_dist = float("inf")

        while scope is not None:
            for sym_name in scope.symbols:
                d = self._levenshtein(name, sym_name)
                if d < best_dist and d <= 2:  # порог: расстояние ≤ 2
                    best_dist = d
                    sym = scope.symbols[sym_name]
                    best = f"возможно, вы имели в виду '{sym_name}'? (объявлено в строке {sym.line})"
            scope = scope.parent

        return best

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        """Расстояние Левенштейна для подсказок."""
        if len(a) < len(b):
            return SemanticAnalyzer._levenshtein(b, a)
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                cost = 0 if ca == cb else 1
                curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
            prev = curr
        return prev[-1]

    # --- Вывод декорированного AST ---

    def format_decorated_ast(self, node: ProgramNode) -> str:
        """Текстовый вывод AST с типовыми аннотациями."""
        lines = ["=== Декорированное AST ==="]
        self._format_node(node, lines, indent=0)
        return "\n".join(lines)

    def _format_node(self, node, lines, indent=0):
        prefix = "  " * indent

        if isinstance(node, ProgramNode):
            lines.append(f"{prefix}Program [global scope]:")
            # Дамп таблицы символов
            lines.append(f"{prefix}  Symbol Table:")
            for sym_name, sym_info in self._symbol_table.global_scope.symbols.items():
                kind = sym_info.kind
                extra = ""
                if kind == SymbolKind.FUNCTION:
                    params = ", ".join(str(p) for p in (sym_info.params or []))
                    ret = str(sym_info.return_type) if sym_info.return_type else "void"
                    extra = f"({params}) -> {ret}"
                elif kind == SymbolKind.STRUCT and sym_info.fields:
                    flds = ", ".join(f"{k}: {v}" for k, v in sym_info.fields.items())
                    extra = f"{{ {flds} }}"
                lines.append(f"{prefix}    - {sym_name}: {kind} {extra} (строка {sym_info.line})")
            lines.append("")

            for decl in node.declarations:
                self._format_node(decl, lines, indent + 1)

        elif isinstance(node, FunctionDeclNode):
            ret = node.return_type if node.return_type else "void"
            lines.append(f"{prefix}FunctionDecl: {node.name} -> {ret} (строка {node.line}):")
            if node.parameters:
                params_str = ", ".join(f"{p.param_type} {p.name}" for p in node.parameters)
                lines.append(f"{prefix}  Parameters: [{params_str}]")
            if node.body:
                lines.append(f"{prefix}  Body:")
                self._format_node(node.body, lines, indent + 2)

        elif isinstance(node, BlockStmtNode):
            lines.append(f"{prefix}Block:")
            for stmt in node.statements:
                self._format_node(stmt, lines, indent + 1)

        elif isinstance(node, VarDeclStmtNode):
            init_info = ""
            if node.initializer and hasattr(node.initializer, '_resolved_type'):
                init_info = f" [тип: {node.initializer._resolved_type}]"
            lines.append(f"{prefix}VarDecl: {node.var_type} {node.name}{init_info}")

        elif isinstance(node, ReturnStmtNode):
            type_info = ""
            if node.value and hasattr(node.value, '_resolved_type'):
                type_info = f" [тип: {node.value._resolved_type}]"
            lines.append(f"{prefix}Return{type_info}")

        elif isinstance(node, IfStmtNode):
            lines.append(f"{prefix}IfStmt:")
            if node.then_branch:
                self._format_node(node.then_branch, lines, indent + 1)
            if node.else_branch:
                lines.append(f"{prefix}  Else:")
                self._format_node(node.else_branch, lines, indent + 1)

        elif isinstance(node, WhileStmtNode):
            lines.append(f"{prefix}WhileStmt:")
            if node.body:
                self._format_node(node.body, lines, indent + 1)

        elif isinstance(node, ForStmtNode):
            lines.append(f"{prefix}ForStmt:")
            if node.body:
                self._format_node(node.body, lines, indent + 1)

        elif isinstance(node, ExprStmtNode):
            type_info = ""
            if hasattr(node.expression, '_resolved_type'):
                type_info = f" [тип: {node.expression._resolved_type}]"
            lines.append(f"{prefix}ExprStmt{type_info}")

        elif isinstance(node, StructDeclNode):
            lines.append(f"{prefix}StructDecl: {node.name}")
            for f in node.fields:
                lines.append(f"{prefix}  Field: {f.var_type} {f.name}")

    def format_validation_report(self) -> str:
        """Отчёт валидации."""
        lines = ["=== Отчёт семантического анализа ==="]
        lines.append(f"Ошибок: {self._errors.count}")
        lines.append("")
        lines.append(self._symbol_table.dump())
        if self._errors.has_errors:
            lines.append("")
            lines.append(self._errors.format_all(self._source_lines))
        return "\n".join(lines)
