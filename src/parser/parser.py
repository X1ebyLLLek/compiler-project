"""
Рекурсивный нисходящий парсер (Recursive Descent Parser) для MiniCompiler.
Принимает список токенов от лексера и строит абстрактное синтаксическое дерево (AST).

Реализует LL(1) грамматику с обработкой приоритетов операторов
через разделение на уровни (Pratt-подобная организация, но без таблицы приоритетов).
"""

import sys
from typing import List, Optional

from src.lexer.tokens import Token, TokenType
from .ast_nodes import (
    ProgramNode, ASTNode,
    LiteralExprNode, IdentifierExprNode, BinaryExprNode,
    UnaryExprNode, CallExprNode, AssignmentExprNode,
    BlockStmtNode, ExprStmtNode, IfStmtNode, WhileStmtNode,
    ForStmtNode, ReturnStmtNode, VarDeclStmtNode,
    FunctionDeclNode, StructDeclNode, ParamNode,
    ExpressionNode, StatementNode,
    # Sprint 7: новые узлы
    ArrayDeclStmtNode, ArrayAccessExprNode, ArrayAssignExprNode,
    ExternDeclNode,
)


class ParseError(Exception):
    """Ошибка синтаксического анализа с информацией о позиции."""
    def __init__(self, token: Token, message: str):
        self.token = token
        self.message = message
        super().__init__(f"[{token.line}:{token.column}] Ошибка: {message}")


class Parser:
    """
    Парсер рекурсивного спуска.
    Конструктор принимает список токенов, метод parse() возвращает ProgramNode (корень AST).
    """

    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._current = 0     # Индекс текущего токена
        self._errors: List[ParseError] = []   # Список накопленных ошибок

    # ================================================================
    # Публичный интерфейс (PAR-1)
    # ================================================================

    def parse(self) -> ProgramNode:
        """Запустить парсинг и вернуть корневой узел AST."""
        declarations = []
        while not self._is_at_end():
            decl = self._parse_declaration()
            if decl is not None:
                declarations.append(decl)

        program = ProgramNode(
            line=1, column=1,
            declarations=declarations,
        )
        return program

    def get_errors(self) -> List[ParseError]:
        """Вернуть накопленные ошибки парсинга."""
        return list(self._errors)

    # ================================================================
    # Вспомогательные методы (PAR-2: match, consume, peek, isAtEnd)
    # ================================================================

    def _peek(self) -> Token:
        """Текущий токен (без продвижения)."""
        return self._tokens[self._current]

    def _previous(self) -> Token:
        """Предыдущий токен (уже потреблённый)."""
        return self._tokens[self._current - 1]

    def _is_at_end(self) -> bool:
        """Достигнут ли конец потока токенов."""
        return self._peek().type == TokenType.END_OF_FILE

    def _advance(self) -> Token:
        """Потребить текущий токен и вернуть его."""
        if not self._is_at_end():
            self._current += 1
        return self._previous()

    def _check(self, token_type: TokenType) -> bool:
        """Проверить, совпадает ли текущий токен с указанным типом."""
        if self._is_at_end():
            return False
        return self._peek().type == token_type

    def _match(self, *types: TokenType) -> bool:
        """Если текущий токен совпадает с одним из типов — продвинуться и вернуть True."""
        for t in types:
            if self._check(t):
                self._advance()
                return True
        return False

    def _consume(self, token_type: TokenType, message: str) -> Token:
        """Потребить ожидаемый токен или выбросить ошибку."""
        if self._check(token_type):
            return self._advance()
        raise self._error(self._peek(), message)

    def _error(self, token: Token, message: str) -> ParseError:
        """Создать ошибку парсинга и добавить в список."""
        err = ParseError(token, message)
        self._errors.append(err)
        # Выводим ошибку сразу, чтобы пользователь видел
        print(str(err), file=sys.stderr)
        return err

    # ================================================================
    # Восстановление после ошибок (panic-mode, ERR-1/ERR-2)
    # ================================================================

    def _synchronize(self):
        """
        Сброс до следующей «точки синхронизации» —
        обычно это начало нового оператора или объявления.
        """
        self._advance()

        while not self._is_at_end():
            # Точка с запятой завершает инструкцию — можно продолжить
            if self._previous().type == TokenType.SEMICOLON:
                return

            # Ключевые слова, которые начинают новое выражение/объявление
            if self._peek().type in (
                TokenType.KW_FN,
                TokenType.KW_STRUCT,
                TokenType.KW_INT,
                TokenType.KW_FLOAT,
                TokenType.KW_BOOL,
                TokenType.KW_VOID,
                TokenType.KW_IF,
                TokenType.KW_WHILE,
                TokenType.KW_FOR,
                TokenType.KW_RETURN,
            ):
                return

            self._advance()

    # ================================================================
    # Парсинг объявлений верхнего уровня
    # ================================================================

    def _parse_declaration(self) -> Optional[ASTNode]:
        """Разобрать объявление верхнего уровня (fn, struct, extern или глобальная переменная)."""
        try:
            # Функция
            if self._check(TokenType.KW_FN):
                return self._parse_function_decl()

            # Структура
            if self._check(TokenType.KW_STRUCT):
                return self._parse_struct_decl()

            # Sprint 7: внешняя функция
            if self._check(TokenType.KW_EXTERN):
                return self._parse_extern_decl()

            # Объявление переменной (тип + имя) или обычный statement
            return self._parse_statement()
        except ParseError:
            # Восстановление: пропускаем до точки синхронизации
            self._synchronize()
            return None

    def _parse_function_decl(self) -> FunctionDeclNode:
        """
        Разбор объявления функции:
        fn IDENTIFIER ( [params] ) [-> Type] { body }
        """
        fn_token = self._consume(TokenType.KW_FN, "Ожидалось 'fn'")
        name_token = self._consume(TokenType.IDENTIFIER, "Ожидалось имя функции после 'fn'")

        self._consume(TokenType.LPAREN, "Ожидалось '(' после имени функции")
        params = self._parse_parameters()
        self._consume(TokenType.RPAREN, "Ожидалось ')' после параметров")

        # Необязательный тип возврата: -> Type
        return_type = None
        if self._match(TokenType.MINUS):
            self._consume(TokenType.GREATER, "Ожидалось '>' после '-' (стрелка '->')")
            return_type = self._parse_type()

        body = self._parse_block()

        return FunctionDeclNode(
            line=fn_token.line,
            column=fn_token.column,
            name=name_token.lexeme,
            parameters=params,
            return_type=return_type,
            body=body,
        )

    def _parse_parameters(self) -> List[ParamNode]:
        """Разбор списка параметров: Type IDENT { , Type IDENT }"""
        params = []
        if not self._check(TokenType.RPAREN):
            # Первый параметр
            params.append(self._parse_single_param())
            while self._match(TokenType.COMMA):
                params.append(self._parse_single_param())
        return params

    def _parse_single_param(self) -> ParamNode:
        """Один параметр: Type IDENTIFIER"""
        type_name = self._parse_type()
        name_token = self._consume(TokenType.IDENTIFIER, "Ожидалось имя параметра")
        return ParamNode(
            line=name_token.line,
            column=name_token.column,
            param_type=type_name,
            name=name_token.lexeme,
        )

    def _parse_struct_decl(self) -> StructDeclNode:
        """
        Разбор объявления структуры:
        struct IDENTIFIER { VarDecl* }
        """
        struct_token = self._consume(TokenType.KW_STRUCT, "Ожидалось 'struct'")
        name_token = self._consume(TokenType.IDENTIFIER, "Ожидалось имя структуры")
        self._consume(TokenType.LBRACE, "Ожидалось '{' после имени структуры")

        fields = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            fields.append(self._parse_var_decl())

        self._consume(TokenType.RBRACE, "Ожидалось '}' в конце определения структуры")

        return StructDeclNode(
            line=struct_token.line,
            column=struct_token.column,
            name=name_token.lexeme,
            fields=fields,
        )

    # ================================================================
    # Парсинг типов
    # ================================================================

    def _parse_type(self) -> str:
        """Разобрать тип: int | float | bool | void | IDENTIFIER"""
        if self._match(TokenType.KW_INT):
            return "int"
        if self._match(TokenType.KW_FLOAT):
            return "float"
        if self._match(TokenType.KW_BOOL):
            return "bool"
        if self._match(TokenType.KW_VOID):
            return "void"
        if self._match(TokenType.IDENTIFIER):
            return self._previous().lexeme
        raise self._error(self._peek(), "Ожидался тип (int, float, bool, void или имя)")

    # ================================================================
    # Парсинг инструкций (Statements)
    # ================================================================

    def _parse_statement(self) -> StatementNode:
        """Выбрать тип инструкции по текущему токену."""
        if self._check(TokenType.LBRACE):
            return self._parse_block()
        if self._check(TokenType.KW_IF):
            return self._parse_if_stmt()
        if self._check(TokenType.KW_WHILE):
            return self._parse_while_stmt()
        if self._check(TokenType.KW_FOR):
            return self._parse_for_stmt()
        if self._check(TokenType.KW_RETURN):
            return self._parse_return_stmt()

        # Попытка: VarDecl (тип + идентификатор, или тип + идентификатор[...] — массив)
        if self._is_type_token():
            return self._parse_var_decl()

        # Иначе — инструкция-выражение (может быть arr[i] = ...)
        return self._parse_expr_stmt()

    def _is_type_token(self) -> bool:
        """Проверить, может ли текущий токен быть началом типа (для различения VarDecl и ExprStmt)."""
        return self._peek().type in (
            TokenType.KW_INT, TokenType.KW_FLOAT,
            TokenType.KW_BOOL, TokenType.KW_VOID,
        )

    def _parse_block(self) -> BlockStmtNode:
        """Блок: { statement* }"""
        brace = self._consume(TokenType.LBRACE, "Ожидалось '{'")
        stmts = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            decl = self._parse_declaration()
            if decl is not None:
                stmts.append(decl)

        self._consume(TokenType.RBRACE, "Ожидалось '}'")
        return BlockStmtNode(line=brace.line, column=brace.column, statements=stmts)

    def _parse_if_stmt(self) -> IfStmtNode:
        """if ( expression ) statement [else statement]"""
        if_tok = self._consume(TokenType.KW_IF, "Ожидалось 'if'")
        self._consume(TokenType.LPAREN, "Ожидалось '(' после 'if'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Ожидалось ')' после условия")

        then_branch = self._parse_statement()

        # Обработка dangling else: привязываем else к ближайшему if (PAR-4)
        else_branch = None
        if self._match(TokenType.KW_ELSE):
            else_branch = self._parse_statement()

        return IfStmtNode(
            line=if_tok.line, column=if_tok.column,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def _parse_while_stmt(self) -> WhileStmtNode:
        """while ( expression ) statement"""
        wh_tok = self._consume(TokenType.KW_WHILE, "Ожидалось 'while'")
        self._consume(TokenType.LPAREN, "Ожидалось '(' после 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Ожидалось ')' после условия цикла")
        body = self._parse_statement()

        return WhileStmtNode(
            line=wh_tok.line, column=wh_tok.column,
            condition=condition, body=body,
        )

    def _parse_for_stmt(self) -> ForStmtNode:
        """for ( [init] ; [condition] ; [update] ) statement"""
        for_tok = self._consume(TokenType.KW_FOR, "Ожидалось 'for'")
        self._consume(TokenType.LPAREN, "Ожидалось '(' после 'for'")

        # Инициализация (VarDecl или ExprStmt, или ничего)
        init = None
        if not self._check(TokenType.SEMICOLON):
            if self._is_type_token():
                init = self._parse_var_decl()  # var decl уже съедает ';'
            else:
                init = self._parse_expr_stmt()  # expr stmt тоже съедает ';'
        else:
            self._advance()  # пропускаем ';'

        # Условие
        condition = None
        if not self._check(TokenType.SEMICOLON):
            condition = self._parse_expression()
        self._consume(TokenType.SEMICOLON, "Ожидалось ';' после условия for")

        # Обновление
        update = None
        if not self._check(TokenType.RPAREN):
            update = self._parse_expression()
        self._consume(TokenType.RPAREN, "Ожидалось ')' после заголовка for")

        body = self._parse_statement()

        return ForStmtNode(
            line=for_tok.line, column=for_tok.column,
            init=init, condition=condition, update=update, body=body,
        )

    def _parse_return_stmt(self) -> ReturnStmtNode:
        """return [expression] ;"""
        ret_tok = self._consume(TokenType.KW_RETURN, "Ожидалось 'return'")
        value = None
        if not self._check(TokenType.SEMICOLON):
            value = self._parse_expression()
        self._consume(TokenType.SEMICOLON, "Ожидалось ';' после return")
        return ReturnStmtNode(line=ret_tok.line, column=ret_tok.column, value=value)

    def _parse_var_decl(self) -> StatementNode:
        """
        Type IDENTIFIER [= Expression] ;
        или
        Type IDENTIFIER [ Expression ] [= { Expression, ... }] ;   — массив (Sprint 7)
        """
        type_name = self._parse_type()
        name_token = self._consume(TokenType.IDENTIFIER,
                                   "Ожидалось имя переменной после типа")

        # Проверяем: если следует '[' — это объявление массива
        if self._check(TokenType.LBRACKET):
            return self._parse_array_decl_tail(type_name, name_token)

        initializer = None
        if self._match(TokenType.ASSIGN):
            initializer = self._parse_expression()

        self._consume(TokenType.SEMICOLON, "Ожидалось ';' после объявления переменной")

        return VarDeclStmtNode(
            line=name_token.line, column=name_token.column,
            var_type=type_name,
            name=name_token.lexeme,
            initializer=initializer,
        )

    def _parse_array_decl_tail(self, elem_type: str, name_token) -> ArrayDeclStmtNode:
        """
        Разобрать хвост объявления массива после 'Type IDENT':
        [ Expression ] [= { expr, expr, ... }] ;
        """
        self._consume(TokenType.LBRACKET, "Ожидалось '[' в объявлении массива")
        size_expr = self._parse_expression()
        self._consume(TokenType.RBRACKET, "Ожидалось ']' после размера массива")

        # Необязательная инициализация: = { 1, 2, 3 }
        initializers = []
        if self._match(TokenType.ASSIGN):
            self._consume(TokenType.LBRACE, "Ожидалось '{' в инициализаторе массива")
            if not self._check(TokenType.RBRACE):
                initializers.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    if self._check(TokenType.RBRACE):
                        break  # trailing comma допускаем
                    initializers.append(self._parse_expression())
            self._consume(TokenType.RBRACE, "Ожидалось '}' в конце инициализатора")

        self._consume(TokenType.SEMICOLON, "Ожидалось ';' после объявления массива")

        return ArrayDeclStmtNode(
            line=name_token.line, column=name_token.column,
            elem_type=elem_type,
            name=name_token.lexeme,
            size=size_expr,
            initializers=initializers,
        )

    def _parse_extern_decl(self) -> ExternDeclNode:
        """
        extern fn IDENTIFIER ( [Type, Type, ...] ) [-> Type] ;

        Объявляет внешнюю функцию (из libc или другого объектника).
        Тела нет — только сигнатура.
        """
        ext_tok = self._consume(TokenType.KW_EXTERN, "Ожидалось 'extern'")
        self._consume(TokenType.KW_FN, "Ожидалось 'fn' после 'extern'")
        name_token = self._consume(TokenType.IDENTIFIER,
                                   "Ожидалось имя внешней функции")

        self._consume(TokenType.LPAREN, "Ожидалось '(' после имени функции")

        # Разбираем список типов параметров (без имён — только типы)
        param_types = []
        is_variadic = False
        if not self._check(TokenType.RPAREN):
            param_types.append(self._parse_type())
            while self._match(TokenType.COMMA):
                # Проверяем на variadic: IDENTIFIER "..." (просто игнорируем как знак)
                if self._check(TokenType.RPAREN):
                    break
                # Если встречаем IDENTIFIER с лексемой "..." — конец
                if (self._peek().type == TokenType.IDENTIFIER
                        and self._peek().lexeme == "..."):
                    self._advance()
                    is_variadic = True
                    break
                param_types.append(self._parse_type())

        self._consume(TokenType.RPAREN, "Ожидалось ')' после параметров extern")

        # Необязательный тип возврата
        return_type = None
        if self._match(TokenType.MINUS):
            self._consume(TokenType.GREATER, "Ожидалось '>' (стрелка '->')")
            return_type = self._parse_type()

        self._consume(TokenType.SEMICOLON, "Ожидалось ';' после extern-объявления")

        return ExternDeclNode(
            line=ext_tok.line, column=ext_tok.column,
            name=name_token.lexeme,
            param_types=param_types,
            return_type=return_type,
            is_variadic=is_variadic,
        )

    def _parse_expr_stmt(self) -> ExprStmtNode:
        """Expression ;"""
        expr = self._parse_expression()
        self._consume(TokenType.SEMICOLON, "Ожидалось ';' после выражения")
        return ExprStmtNode(
            line=expr.line, column=expr.column,
            expression=expr,
        )

    # ================================================================
    # Парсинг выражений (по уровням приоритета, GRAM-3)
    # ================================================================

    def _parse_expression(self) -> ExpressionNode:
        """Точка входа разбора выражений — Assignment."""
        return self._parse_assignment()

    def _parse_assignment(self) -> ExpressionNode:
        """
        Assignment ::= LogicalOr { ('=' | '+=' | '-=' | '*=' | '/=') Assignment }
        Правая ассоциативность: рекурсивный вызов самого себя справа.
        Также поддерживает arr[i] = value (Sprint 7).
        """
        expr = self._parse_logical_or()

        if self._match(TokenType.ASSIGN, TokenType.PLUS_ASSIGN,
                       TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN,
                       TokenType.SLASH_ASSIGN):
            op_token = self._previous()
            # Правая ассоциативность — рекурсия вправо
            value = self._parse_assignment()

            # Простое присваивание переменной
            if isinstance(expr, IdentifierExprNode):
                return AssignmentExprNode(
                    line=op_token.line, column=op_token.column,
                    target=expr.name,
                    operator=op_token.lexeme,
                    value=value,
                )

            # Sprint 7: присваивание элементу массива arr[i] = value
            if isinstance(expr, ArrayAccessExprNode) and op_token.lexeme == "=":
                return ArrayAssignExprNode(
                    line=op_token.line, column=op_token.column,
                    array_name=expr.array_name,
                    index=expr.index,
                    value=value,
                )

            raise self._error(op_token, "Некорректная цель присваивания")

        return expr

    def _parse_logical_or(self) -> ExpressionNode:
        """LogicalOr ::= LogicalAnd { '||' LogicalAnd }"""
        left = self._parse_logical_and()
        while self._match(TokenType.OR_OR):
            op = self._previous()
            right = self._parse_logical_and()
            left = BinaryExprNode(
                line=op.line, column=op.column,
                left=left, operator=op.lexeme, right=right,
            )
        return left

    def _parse_logical_and(self) -> ExpressionNode:
        """LogicalAnd ::= Equality { '&&' Equality }"""
        left = self._parse_equality()
        while self._match(TokenType.AND_AND):
            op = self._previous()
            right = self._parse_equality()
            left = BinaryExprNode(
                line=op.line, column=op.column,
                left=left, operator=op.lexeme, right=right,
            )
        return left

    def _parse_equality(self) -> ExpressionNode:
        """Equality ::= Relational { ('==' | '!=') Relational }"""
        left = self._parse_relational()
        while self._match(TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL):
            op = self._previous()
            right = self._parse_relational()
            left = BinaryExprNode(
                line=op.line, column=op.column,
                left=left, operator=op.lexeme, right=right,
            )
        return left

    def _parse_relational(self) -> ExpressionNode:
        """Relational ::= Additive { ('<' | '<=' | '>' | '>=') Additive }"""
        left = self._parse_additive()
        while self._match(TokenType.LESS, TokenType.LESS_EQUAL,
                          TokenType.GREATER, TokenType.GREATER_EQUAL):
            op = self._previous()
            right = self._parse_additive()
            left = BinaryExprNode(
                line=op.line, column=op.column,
                left=left, operator=op.lexeme, right=right,
            )
        return left

    def _parse_additive(self) -> ExpressionNode:
        """Additive ::= Multiplicative { ('+' | '-') Multiplicative }"""
        left = self._parse_multiplicative()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            op = self._previous()
            right = self._parse_multiplicative()
            left = BinaryExprNode(
                line=op.line, column=op.column,
                left=left, operator=op.lexeme, right=right,
            )
        return left

    def _parse_multiplicative(self) -> ExpressionNode:
        """Multiplicative ::= Unary { ('*' | '/' | '%') Unary }"""
        left = self._parse_unary()
        while self._match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._previous()
            right = self._parse_unary()
            left = BinaryExprNode(
                line=op.line, column=op.column,
                left=left, operator=op.lexeme, right=right,
            )
        return left

    def _parse_unary(self) -> ExpressionNode:
        """Unary ::= ('-' | '!') Unary | Primary"""
        if self._match(TokenType.MINUS, TokenType.BANG):
            op = self._previous()
            operand = self._parse_unary()
            return UnaryExprNode(
                line=op.line, column=op.column,
                operator=op.lexeme, operand=operand,
            )
        return self._parse_primary()

    def _parse_primary(self) -> ExpressionNode:
        """
        Primary ::= INT_LITERAL | FLOAT_LITERAL | STRING_LITERAL | BOOL_LITERAL
                   | IDENTIFIER [ '(' [Arguments] ')' ]
                   | '(' Expression ')'
        """
        # Целочисленный литерал
        if self._match(TokenType.INT_LITERAL):
            tok = self._previous()
            return LiteralExprNode(
                line=tok.line, column=tok.column,
                value=tok.literal_value, literal_type="int",
            )

        # Вещественный литерал
        if self._match(TokenType.FLOAT_LITERAL):
            tok = self._previous()
            return LiteralExprNode(
                line=tok.line, column=tok.column,
                value=tok.literal_value, literal_type="float",
            )

        # Строковый литерал
        if self._match(TokenType.STRING_LITERAL):
            tok = self._previous()
            return LiteralExprNode(
                line=tok.line, column=tok.column,
                value=tok.literal_value, literal_type="string",
            )

        # Булев литерал
        if self._match(TokenType.BOOL_LITERAL):
            tok = self._previous()
            return LiteralExprNode(
                line=tok.line, column=tok.column,
                value=tok.literal_value, literal_type="bool",
            )

        # Идентификатор (вызов функции, доступ к массиву или просто переменная)
        if self._match(TokenType.IDENTIFIER):
            tok = self._previous()

            # Вызов функции: IDENT ( args )
            if self._match(TokenType.LPAREN):
                args = self._parse_arguments()
                self._consume(TokenType.RPAREN, "Ожидалось ')' после аргументов")
                return CallExprNode(
                    line=tok.line, column=tok.column,
                    callee=tok.lexeme, arguments=args,
                )

            # Sprint 7: доступ к элементу массива: IDENT [ expr ]
            if self._check(TokenType.LBRACKET):
                self._advance()  # съедаем '['
                index = self._parse_expression()
                self._consume(TokenType.RBRACKET, "Ожидалось ']' после индекса массива")
                return ArrayAccessExprNode(
                    line=tok.line, column=tok.column,
                    array_name=tok.lexeme,
                    index=index,
                )

            return IdentifierExprNode(
                line=tok.line, column=tok.column,
                name=tok.lexeme,
            )

        # Скобочное выражение
        if self._match(TokenType.LPAREN):
            expr = self._parse_expression()
            self._consume(TokenType.RPAREN, "Ожидалось ')' после выражения")
            return expr

        # Ничего не подошло — ошибка
        raise self._error(self._peek(), "Ожидалось выражение")

    def _parse_arguments(self) -> List[ExpressionNode]:
        """Список аргументов вызова: Expression { ',' Expression }"""
        args = []
        if not self._check(TokenType.RPAREN):
            args.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                args.append(self._parse_expression())
        return args
