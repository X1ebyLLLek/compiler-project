"""
Визуализация AST в трёх форматах:
1. text  — читаемое дерево с отступами (VIS-1)
2. dot   — Graphviz DOT-файл для визуализации (VIS-2)
3. json  — JSON для автотестов и инструментов (VIS-3)
"""

import json
from typing import Any

from .ast_nodes import (
    ASTVisitor, ProgramNode,
    LiteralExprNode, IdentifierExprNode, BinaryExprNode,
    UnaryExprNode, CallExprNode, AssignmentExprNode,
    BlockStmtNode, ExprStmtNode, IfStmtNode, WhileStmtNode,
    ForStmtNode, ReturnStmtNode, VarDeclStmtNode,
    FunctionDeclNode, StructDeclNode, ParamNode,
)


# ================================================================
# Текстовый «красивый» вывод (Pretty Printer)
# ================================================================

class ASTPrettyPrinter(ASTVisitor):
    """
    Обходит AST и формирует читаемую строку с отступами.
    Пример вывода:
      Program:
        FunctionDecl: main -> void
          Parameters: []
          Body:
            Block:
              VarDecl: int x = 42
    """

    def __init__(self):
        self._indent_level = 0
        self._lines = []

    def _indent(self) -> str:
        return "  " * self._indent_level

    def _emit(self, text: str):
        self._lines.append(self._indent() + text)

    def print_ast(self, node: ProgramNode) -> str:
        """Основная точка входа — вернёт строку с деревом."""
        node.accept(self)
        return "\n".join(self._lines)

    # --- Корень ---
    def visit_program(self, node: ProgramNode) -> Any:
        self._emit(f"Program [line {node.line}]:")
        self._indent_level += 1
        for decl in node.declarations:
            decl.accept(self)
        self._indent_level -= 1

    # --- Выражения ---
    def visit_literal_expr(self, node: LiteralExprNode) -> Any:
        self._emit(f"Literal: {node.value} ({node.literal_type})")

    def visit_identifier_expr(self, node: IdentifierExprNode) -> Any:
        self._emit(f"Identifier: {node.name}")

    def visit_binary_expr(self, node: BinaryExprNode) -> Any:
        self._emit(f"Binary: {node.operator}")
        self._indent_level += 1
        node.left.accept(self)
        node.right.accept(self)
        self._indent_level -= 1

    def visit_unary_expr(self, node: UnaryExprNode) -> Any:
        self._emit(f"Unary: {node.operator}")
        self._indent_level += 1
        node.operand.accept(self)
        self._indent_level -= 1

    def visit_call_expr(self, node: CallExprNode) -> Any:
        self._emit(f"Call: {node.callee}")
        self._indent_level += 1
        for arg in node.arguments:
            arg.accept(self)
        self._indent_level -= 1

    def visit_assignment_expr(self, node: AssignmentExprNode) -> Any:
        self._emit(f"Assignment: {node.target} {node.operator}")
        self._indent_level += 1
        node.value.accept(self)
        self._indent_level -= 1

    # --- Инструкции ---
    def visit_block_stmt(self, node: BlockStmtNode) -> Any:
        self._emit("Block:")
        self._indent_level += 1
        for stmt in node.statements:
            stmt.accept(self)
        self._indent_level -= 1

    def visit_expr_stmt(self, node: ExprStmtNode) -> Any:
        self._emit("ExprStmt:")
        self._indent_level += 1
        node.expression.accept(self)
        self._indent_level -= 1

    def visit_if_stmt(self, node: IfStmtNode) -> Any:
        self._emit(f"IfStmt [line {node.line}]:")
        self._indent_level += 1
        self._emit("Condition:")
        self._indent_level += 1
        node.condition.accept(self)
        self._indent_level -= 1
        self._emit("Then:")
        self._indent_level += 1
        node.then_branch.accept(self)
        self._indent_level -= 1
        if node.else_branch is not None:
            self._emit("Else:")
            self._indent_level += 1
            node.else_branch.accept(self)
            self._indent_level -= 1
        self._indent_level -= 1

    def visit_while_stmt(self, node: WhileStmtNode) -> Any:
        self._emit(f"WhileStmt [line {node.line}]:")
        self._indent_level += 1
        self._emit("Condition:")
        self._indent_level += 1
        node.condition.accept(self)
        self._indent_level -= 1
        self._emit("Body:")
        self._indent_level += 1
        node.body.accept(self)
        self._indent_level -= 1
        self._indent_level -= 1

    def visit_for_stmt(self, node: ForStmtNode) -> Any:
        self._emit(f"ForStmt [line {node.line}]:")
        self._indent_level += 1
        if node.init:
            self._emit("Init:")
            self._indent_level += 1
            node.init.accept(self)
            self._indent_level -= 1
        if node.condition:
            self._emit("Condition:")
            self._indent_level += 1
            node.condition.accept(self)
            self._indent_level -= 1
        if node.update:
            self._emit("Update:")
            self._indent_level += 1
            node.update.accept(self)
            self._indent_level -= 1
        self._emit("Body:")
        self._indent_level += 1
        node.body.accept(self)
        self._indent_level -= 1
        self._indent_level -= 1

    def visit_return_stmt(self, node: ReturnStmtNode) -> Any:
        if node.value:
            self._emit(f"Return [line {node.line}]:")
            self._indent_level += 1
            node.value.accept(self)
            self._indent_level -= 1
        else:
            self._emit(f"Return [line {node.line}]")

    def visit_var_decl_stmt(self, node: VarDeclStmtNode) -> Any:
        if node.initializer:
            self._emit(f"VarDecl: {node.var_type} {node.name} =")
            self._indent_level += 1
            node.initializer.accept(self)
            self._indent_level -= 1
        else:
            self._emit(f"VarDecl: {node.var_type} {node.name}")

    # --- Объявления ---
    def visit_function_decl(self, node: FunctionDeclNode) -> Any:
        ret_type = node.return_type if node.return_type else "void"
        self._emit(f"FunctionDecl: {node.name} -> {ret_type} [line {node.line}]:")
        self._indent_level += 1
        params_str = ", ".join(f"{p.param_type} {p.name}" for p in node.parameters)
        self._emit(f"Parameters: [{params_str}]")
        self._emit("Body:")
        self._indent_level += 1
        node.body.accept(self)
        self._indent_level -= 1
        self._indent_level -= 1

    def visit_struct_decl(self, node: StructDeclNode) -> Any:
        self._emit(f"StructDecl: {node.name} [line {node.line}]:")
        self._indent_level += 1
        for field_node in node.fields:
            field_node.accept(self)
        self._indent_level -= 1

    def visit_param(self, node: ParamNode) -> Any:
        self._emit(f"Param: {node.param_type} {node.name}")


# ================================================================
# Graphviz DOT-формат (VIS-2)
# ================================================================

class ASTDotPrinter(ASTVisitor):
    """
    Генерирует DOT-файл для Graphviz.
    Каждый узел — прямоугольник, рёбра показывают вложенность,
    цвета зависят от типа узла.
    """

    # Цветовая схема по типам узлов
    _COLORS = {
        "program":    "#4A90D9",
        "expr":       "#50C878",
        "stmt":       "#FFA500",
        "decl":       "#E06666",
        "param":      "#9B59B6",
    }

    def __init__(self):
        self._counter = 0
        self._lines = []

    def _new_id(self) -> str:
        """Генерация уникального ID для каждого узла графа."""
        self._counter += 1
        return f"n{self._counter}"

    def _node(self, node_id: str, label: str, category: str):
        """Добавить узел в DOT-граф."""
        color = self._COLORS.get(category, "#CCCCCC")
        self._lines.append(
            f'  {node_id} [label="{label}", '
            f'style=filled, fillcolor="{color}", fontcolor=white, shape=box];'
        )

    def _edge(self, parent: str, child: str):
        """Добавить ребро в DOT-граф."""
        self._lines.append(f"  {parent} -> {child};")

    def generate(self, root: ProgramNode) -> str:
        """Сформировать DOT-содержимое."""
        self._lines = ["digraph AST {", '  rankdir=TB;',
                        '  node [fontname="Helvetica"];']
        root.accept(self)
        self._lines.append("}")
        return "\n".join(self._lines)

    # --- Визиты ---

    def visit_program(self, node: ProgramNode) -> str:
        nid = self._new_id()
        self._node(nid, "Program", "program")
        for d in node.declarations:
            child_id = d.accept(self)
            self._edge(nid, child_id)
        return nid

    def visit_literal_expr(self, node: LiteralExprNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Literal\\n{node.value}", "expr")
        return nid

    def visit_identifier_expr(self, node: IdentifierExprNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Ident\\n{node.name}", "expr")
        return nid

    def visit_binary_expr(self, node: BinaryExprNode) -> str:
        nid = self._new_id()
        self._node(nid, f"BinOp\\n{node.operator}", "expr")
        left_id = node.left.accept(self)
        right_id = node.right.accept(self)
        self._edge(nid, left_id)
        self._edge(nid, right_id)
        return nid

    def visit_unary_expr(self, node: UnaryExprNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Unary\\n{node.operator}", "expr")
        child_id = node.operand.accept(self)
        self._edge(nid, child_id)
        return nid

    def visit_call_expr(self, node: CallExprNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Call\\n{node.callee}", "expr")
        for arg in node.arguments:
            arg_id = arg.accept(self)
            self._edge(nid, arg_id)
        return nid

    def visit_assignment_expr(self, node: AssignmentExprNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Assign\\n{node.target} {node.operator}", "expr")
        val_id = node.value.accept(self)
        self._edge(nid, val_id)
        return nid

    def visit_block_stmt(self, node: BlockStmtNode) -> str:
        nid = self._new_id()
        self._node(nid, "Block", "stmt")
        for s in node.statements:
            s_id = s.accept(self)
            self._edge(nid, s_id)
        return nid

    def visit_expr_stmt(self, node: ExprStmtNode) -> str:
        nid = self._new_id()
        self._node(nid, "ExprStmt", "stmt")
        e_id = node.expression.accept(self)
        self._edge(nid, e_id)
        return nid

    def visit_if_stmt(self, node: IfStmtNode) -> str:
        nid = self._new_id()
        self._node(nid, "If", "stmt")
        c_id = node.condition.accept(self)
        self._edge(nid, c_id)
        t_id = node.then_branch.accept(self)
        self._edge(nid, t_id)
        if node.else_branch:
            e_id = node.else_branch.accept(self)
            self._edge(nid, e_id)
        return nid

    def visit_while_stmt(self, node: WhileStmtNode) -> str:
        nid = self._new_id()
        self._node(nid, "While", "stmt")
        c_id = node.condition.accept(self)
        self._edge(nid, c_id)
        b_id = node.body.accept(self)
        self._edge(nid, b_id)
        return nid

    def visit_for_stmt(self, node: ForStmtNode) -> str:
        nid = self._new_id()
        self._node(nid, "For", "stmt")
        if node.init:
            i_id = node.init.accept(self)
            self._edge(nid, i_id)
        if node.condition:
            c_id = node.condition.accept(self)
            self._edge(nid, c_id)
        if node.update:
            u_id = node.update.accept(self)
            self._edge(nid, u_id)
        b_id = node.body.accept(self)
        self._edge(nid, b_id)
        return nid

    def visit_return_stmt(self, node: ReturnStmtNode) -> str:
        nid = self._new_id()
        self._node(nid, "Return", "stmt")
        if node.value:
            v_id = node.value.accept(self)
            self._edge(nid, v_id)
        return nid

    def visit_var_decl_stmt(self, node: VarDeclStmtNode) -> str:
        nid = self._new_id()
        label = f"VarDecl\\n{node.var_type} {node.name}"
        self._node(nid, label, "decl")
        if node.initializer:
            i_id = node.initializer.accept(self)
            self._edge(nid, i_id)
        return nid

    def visit_function_decl(self, node: FunctionDeclNode) -> str:
        nid = self._new_id()
        ret = node.return_type if node.return_type else "void"
        self._node(nid, f"FnDecl\\n{node.name} -> {ret}", "decl")
        for p in node.parameters:
            p_id = p.accept(self)
            self._edge(nid, p_id)
        body_id = node.body.accept(self)
        self._edge(nid, body_id)
        return nid

    def visit_struct_decl(self, node: StructDeclNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Struct\\n{node.name}", "decl")
        for f_node in node.fields:
            f_id = f_node.accept(self)
            self._edge(nid, f_id)
        return nid

    def visit_param(self, node: ParamNode) -> str:
        nid = self._new_id()
        self._node(nid, f"Param\\n{node.param_type} {node.name}", "param")
        return nid


# ================================================================
# JSON-формат (VIS-3)
# ================================================================

class ASTJsonPrinter(ASTVisitor):
    """Преобразует AST в структуру словарей, пригодную для json.dumps()."""

    def to_json(self, root: ProgramNode, indent: int = 2) -> str:
        """Вернуть JSON-строку."""
        data = root.accept(self)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def _pos(self, node) -> dict:
        """Общая информация о позиции."""
        return {"line": node.line, "column": node.column}

    # --- Корень ---
    def visit_program(self, node: ProgramNode) -> dict:
        return {
            "type": "Program",
            **self._pos(node),
            "declarations": [d.accept(self) for d in node.declarations],
        }

    # --- Выражения ---
    def visit_literal_expr(self, node: LiteralExprNode) -> dict:
        return {
            "type": "LiteralExpr",
            **self._pos(node),
            "literal_type": node.literal_type,
            "value": node.value,
        }

    def visit_identifier_expr(self, node: IdentifierExprNode) -> dict:
        return {"type": "IdentifierExpr", **self._pos(node), "name": node.name}

    def visit_binary_expr(self, node: BinaryExprNode) -> dict:
        return {
            "type": "BinaryExpr", **self._pos(node),
            "operator": node.operator,
            "left": node.left.accept(self),
            "right": node.right.accept(self),
        }

    def visit_unary_expr(self, node: UnaryExprNode) -> dict:
        return {
            "type": "UnaryExpr", **self._pos(node),
            "operator": node.operator,
            "operand": node.operand.accept(self),
        }

    def visit_call_expr(self, node: CallExprNode) -> dict:
        return {
            "type": "CallExpr", **self._pos(node),
            "callee": node.callee,
            "arguments": [a.accept(self) for a in node.arguments],
        }

    def visit_assignment_expr(self, node: AssignmentExprNode) -> dict:
        return {
            "type": "AssignmentExpr", **self._pos(node),
            "target": node.target,
            "operator": node.operator,
            "value": node.value.accept(self),
        }

    # --- Инструкции ---
    def visit_block_stmt(self, node: BlockStmtNode) -> dict:
        return {
            "type": "BlockStmt", **self._pos(node),
            "statements": [s.accept(self) for s in node.statements],
        }

    def visit_expr_stmt(self, node: ExprStmtNode) -> dict:
        return {
            "type": "ExprStmt", **self._pos(node),
            "expression": node.expression.accept(self),
        }

    def visit_if_stmt(self, node: IfStmtNode) -> dict:
        result = {
            "type": "IfStmt", **self._pos(node),
            "condition": node.condition.accept(self),
            "then_branch": node.then_branch.accept(self),
        }
        if node.else_branch:
            result["else_branch"] = node.else_branch.accept(self)
        return result

    def visit_while_stmt(self, node: WhileStmtNode) -> dict:
        return {
            "type": "WhileStmt", **self._pos(node),
            "condition": node.condition.accept(self),
            "body": node.body.accept(self),
        }

    def visit_for_stmt(self, node: ForStmtNode) -> dict:
        result = {"type": "ForStmt", **self._pos(node)}
        if node.init:
            result["init"] = node.init.accept(self)
        if node.condition:
            result["condition"] = node.condition.accept(self)
        if node.update:
            result["update"] = node.update.accept(self)
        result["body"] = node.body.accept(self)
        return result

    def visit_return_stmt(self, node: ReturnStmtNode) -> dict:
        result = {"type": "ReturnStmt", **self._pos(node)}
        if node.value:
            result["value"] = node.value.accept(self)
        return result

    def visit_var_decl_stmt(self, node: VarDeclStmtNode) -> dict:
        result = {
            "type": "VarDeclStmt", **self._pos(node),
            "var_type": node.var_type,
            "name": node.name,
        }
        if node.initializer:
            result["initializer"] = node.initializer.accept(self)
        return result

    # --- Объявления ---
    def visit_function_decl(self, node: FunctionDeclNode) -> dict:
        return {
            "type": "FunctionDecl", **self._pos(node),
            "name": node.name,
            "return_type": node.return_type,
            "parameters": [p.accept(self) for p in node.parameters],
            "body": node.body.accept(self),
        }

    def visit_struct_decl(self, node: StructDeclNode) -> dict:
        return {
            "type": "StructDecl", **self._pos(node),
            "name": node.name,
            "fields": [f.accept(self) for f in node.fields],
        }

    def visit_param(self, node: ParamNode) -> dict:
        return {
            "type": "Param", **self._pos(node),
            "param_type": node.param_type,
            "name": node.name,
        }
