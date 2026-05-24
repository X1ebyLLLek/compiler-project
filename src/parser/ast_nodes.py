"""
Модуль AST-узлов для MiniCompiler.
Определяет иерархию классов для представления абстрактного синтаксического дерева.
Каждый узел хранит позицию (строка, столбец) для качественных сообщений об ошибках.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any


# ============================================================
# Базовый класс ASTNode — хранит позицию в исходном коде
# ============================================================

@dataclass
class ASTNode:
    """Абстрактный базовый узел дерева. Все узлы наследуются от него."""
    line: int = 0
    column: int = 0

    def accept(self, visitor: 'ASTVisitor') -> Any:
        """Метод-диспетчер паттерна Visitor. Переопределяется в потомках."""
        raise NotImplementedError("Подклассы должны реализовать accept()")


# ============================================================
# Выражения (Expressions)
# ============================================================

@dataclass
class ExpressionNode(ASTNode):
    """Базовый класс для всех выражений."""
    pass


@dataclass
class LiteralExprNode(ExpressionNode):
    """Литерал: число, строка, bool."""
    value: Any = None         # Само значение (int, float, str, bool)
    literal_type: str = ""    # Тип: "int", "float", "string", "bool"

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_literal_expr(self)


@dataclass
class IdentifierExprNode(ExpressionNode):
    """Обращение к переменной по имени."""
    name: str = ""

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_identifier_expr(self)


@dataclass
class BinaryExprNode(ExpressionNode):
    """Бинарная операция: left OP right (например, a + b)."""
    left: ExpressionNode = None
    operator: str = ""        # Текстовое представление оператора ("+", "==", ...)
    right: ExpressionNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_binary_expr(self)


@dataclass
class UnaryExprNode(ExpressionNode):
    """Унарная операция: OP operand (например, -x, !flag)."""
    operator: str = ""
    operand: ExpressionNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_unary_expr(self)


@dataclass
class CallExprNode(ExpressionNode):
    """Вызов функции: callee(arg1, arg2, ...)."""
    callee: str = ""                          # Имя вызываемой функции
    arguments: List[ExpressionNode] = field(default_factory=list)

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_call_expr(self)


@dataclass
class AssignmentExprNode(ExpressionNode):
    """Присваивание: target OP value (например, x = 5, x += 3)."""
    target: str = ""         # Имя переменной-цели
    operator: str = ""       # "=", "+=", "-=", "*=", "/="
    value: ExpressionNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_assignment_expr(self)


@dataclass
class ArrayAccessExprNode(ExpressionNode):
    """Обращение к элементу массива: arr[index]"""
    array_name: str = ""
    index: ExpressionNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_array_access_expr(self)


@dataclass
class ArrayAssignExprNode(ExpressionNode):
    """Присваивание элементу массива: arr[index] = value"""
    array_name: str = ""
    index: ExpressionNode = None
    value: ExpressionNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_array_assign_expr(self)


# ============================================================
# Инструкции (Statements)
# ============================================================

@dataclass
class StatementNode(ASTNode):
    """Базовый класс для всех инструкций."""
    pass


@dataclass
class BlockStmtNode(StatementNode):
    """Блок: { stmt1; stmt2; ... }"""
    statements: List[StatementNode] = field(default_factory=list)

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_block_stmt(self)


@dataclass
class ExprStmtNode(StatementNode):
    """Инструкция-выражение: expression;"""
    expression: ExpressionNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_expr_stmt(self)


@dataclass
class IfStmtNode(StatementNode):
    """Условная конструкция: if (condition) then_branch [else else_branch]"""
    condition: ExpressionNode = None
    then_branch: StatementNode = None
    else_branch: Optional[StatementNode] = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_if_stmt(self)


@dataclass
class WhileStmtNode(StatementNode):
    """Цикл while: while (condition) body"""
    condition: ExpressionNode = None
    body: StatementNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_while_stmt(self)


@dataclass
class ForStmtNode(StatementNode):
    """Цикл for: for (init; condition; update) body"""
    init: Optional[StatementNode] = None           # Может быть VarDecl или ExprStmt
    condition: Optional[ExpressionNode] = None
    update: Optional[ExpressionNode] = None
    body: StatementNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_for_stmt(self)


@dataclass
class ReturnStmtNode(StatementNode):
    """Инструкция return: return [expression];"""
    value: Optional[ExpressionNode] = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_return_stmt(self)


@dataclass
class VarDeclStmtNode(StatementNode):
    """Объявление переменной: type name [= initializer];"""
    var_type: str = ""                             # "int", "float", "bool", ...
    name: str = ""
    initializer: Optional[ExpressionNode] = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_var_decl_stmt(self)


@dataclass
class ArrayDeclStmtNode(StatementNode):
    """Объявление массива: int arr[10]; или int arr[3] = {1, 2, 3};"""
    elem_type: str = ""           # тип элементов: "int", "float", ...
    name: str = ""
    size: ExpressionNode = None   # выражение с размером
    # Список инициализаторов (может быть пустым)
    initializers: List[ExpressionNode] = field(default_factory=list)

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_array_decl_stmt(self)


# ============================================================
# Объявления верхнего уровня (Declarations)
# ============================================================

@dataclass
class DeclarationNode(ASTNode):
    """Базовый класс для объявлений верхнего уровня."""
    pass


@dataclass
class ParamNode(ASTNode):
    """Параметр функции: type name"""
    param_type: str = ""
    name: str = ""

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_param(self)


@dataclass
class FunctionDeclNode(DeclarationNode):
    """Объявление функции: fn name(params) [-> return_type] { body }"""
    name: str = ""
    parameters: List[ParamNode] = field(default_factory=list)
    return_type: Optional[str] = None    # None => void
    body: BlockStmtNode = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_function_decl(self)


@dataclass
class StructDeclNode(DeclarationNode):
    """Объявление структуры: struct Name { поля }"""
    name: str = ""
    fields: List[VarDeclStmtNode] = field(default_factory=list)

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_struct_decl(self)


@dataclass
class ExternDeclNode(DeclarationNode):
    """Объявление внешней функции: extern fn name(params) -> return_type;"""
    name: str = ""
    param_types: List[str] = field(default_factory=list)  # типы параметров
    return_type: Optional[str] = None
    is_variadic: bool = False  # функция с переменным числом аргументов

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_extern_decl(self)


# ============================================================
# Корневой узел программы
# ============================================================

@dataclass
class ProgramNode(ASTNode):
    """Корень AST — набор объявлений верхнего уровня."""
    declarations: List[ASTNode] = field(default_factory=list)

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_program(self)


# ============================================================
# Visitor-паттерн: базовый класс визитора (AST-5)
# ============================================================

class ASTVisitor:
    """
    Базовый визитор для обхода AST.
    Каждый конкретный визитор (pretty-printer, codegen, type-checker)
    наследуется от этого класса и переопределяет нужные методы.
    """

    def visit_program(self, node: ProgramNode) -> Any:
        raise NotImplementedError

    # -- Выражения --
    def visit_literal_expr(self, node: LiteralExprNode) -> Any:
        raise NotImplementedError

    def visit_identifier_expr(self, node: IdentifierExprNode) -> Any:
        raise NotImplementedError

    def visit_binary_expr(self, node: BinaryExprNode) -> Any:
        raise NotImplementedError

    def visit_unary_expr(self, node: UnaryExprNode) -> Any:
        raise NotImplementedError

    def visit_call_expr(self, node: CallExprNode) -> Any:
        raise NotImplementedError

    def visit_assignment_expr(self, node: AssignmentExprNode) -> Any:
        raise NotImplementedError

    def visit_array_access_expr(self, node: 'ArrayAccessExprNode') -> Any:
        raise NotImplementedError

    def visit_array_assign_expr(self, node: 'ArrayAssignExprNode') -> Any:
        raise NotImplementedError

    # -- Инструкции --
    def visit_block_stmt(self, node: BlockStmtNode) -> Any:
        raise NotImplementedError

    def visit_expr_stmt(self, node: ExprStmtNode) -> Any:
        raise NotImplementedError

    def visit_if_stmt(self, node: IfStmtNode) -> Any:
        raise NotImplementedError

    def visit_while_stmt(self, node: WhileStmtNode) -> Any:
        raise NotImplementedError

    def visit_for_stmt(self, node: ForStmtNode) -> Any:
        raise NotImplementedError

    def visit_return_stmt(self, node: ReturnStmtNode) -> Any:
        raise NotImplementedError

    def visit_var_decl_stmt(self, node: VarDeclStmtNode) -> Any:
        raise NotImplementedError

    def visit_array_decl_stmt(self, node: 'ArrayDeclStmtNode') -> Any:
        raise NotImplementedError

    # -- Объявления --
    def visit_function_decl(self, node: FunctionDeclNode) -> Any:
        raise NotImplementedError

    def visit_struct_decl(self, node: StructDeclNode) -> Any:
        raise NotImplementedError

    def visit_extern_decl(self, node: 'ExternDeclNode') -> Any:
        raise NotImplementedError

    def visit_param(self, node: ParamNode) -> Any:
        raise NotImplementedError
