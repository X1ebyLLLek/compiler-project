from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Optional

class TokenType(Enum):
    # Ключевые слова (Keywords)
    KW_IF = auto()
    KW_ELSE = auto()
    KW_WHILE = auto()
    KW_FOR = auto()
    KW_INT = auto()
    KW_FLOAT = auto()
    KW_BOOL = auto()
    KW_RETURN = auto()
    KW_TRUE = auto()
    KW_FALSE = auto()
    KW_VOID = auto()
    KW_STRUCT = auto()
    KW_FN = auto()

    # Идентификаторы (Identifiers)
    IDENTIFIER = auto()

    # Литералы (Literals)
    INT_LITERAL = auto()
    FLOAT_LITERAL = auto()
    STRING_LITERAL = auto()
    BOOL_LITERAL = auto()

    # Операторы (Operators)
    PLUS = auto()           # +
    MINUS = auto()          # -
    STAR = auto()           # *
    SLASH = auto()          # /
    PERCENT = auto()        # %
    EQUAL_EQUAL = auto()    # ==
    BANG_EQUAL = auto()     # !=
    LESS = auto()           # <
    LESS_EQUAL = auto()     # <=
    GREATER = auto()        # >
    GREATER_EQUAL = auto()  # >=
    AND_AND = auto()        # &&
    OR_OR = auto()          # ||
    BANG = auto()           # !
    ASSIGN = auto()         # =
    PLUS_ASSIGN = auto()    # +=
    MINUS_ASSIGN = auto()   # -=
    STAR_ASSIGN = auto()    # *=
    SLASH_ASSIGN = auto()   # /=

    # Разделители (Delimiters)
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACE = auto()         # {
    RBRACE = auto()         # }
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    SEMICOLON = auto()      # ;
    COMMA = auto()          # ,
    COLON = auto()          # :

    # Специальные токены
    END_OF_FILE = auto()    # EOF
    ERROR = auto()          # Токен ошибки лексики

# Словарь для быстрого поиска ключевых слов
KEYWORDS = {
    "if": TokenType.KW_IF,
    "else": TokenType.KW_ELSE,
    "while": TokenType.KW_WHILE,
    "for": TokenType.KW_FOR,
    "int": TokenType.KW_INT,
    "float": TokenType.KW_FLOAT,
    "bool": TokenType.KW_BOOL,
    "return": TokenType.KW_RETURN,
    "true": TokenType.KW_TRUE,
    "false": TokenType.KW_FALSE,
    "void": TokenType.KW_VOID,
    "struct": TokenType.KW_STRUCT,
    "fn": TokenType.KW_FN,
}

@dataclass
class Token:
    """Обязательная структура токена по требованию LEX-1"""
    type: TokenType            # Тип токена (перечисление)
    lexeme: str                # Исходный текст (строка)
    line: int                  # Номер строки (1-индексация)
    column: int                # Номер столбца (1-индексация)
    literal_value: Optional[Any] = None # Извлеченное значение (например, int или float)

    def __str__(self) -> str:
        """Формат вывода как запрошено в TEST-3"""
        base = f'{self.line}:{self.column} {self.type.name} "{self.lexeme}"'
        if self.literal_value is not None:
            # Для отладки добавляем значение литерала
            if isinstance(self.literal_value, bool):
                val_str = str(self.literal_value).lower()
            else:
                val_str = str(self.literal_value)
            return f"{base} {val_str}"
        return base
