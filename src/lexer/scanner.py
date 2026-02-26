from typing import List
from .tokens import Token, TokenType, KEYWORDS

class ScannerError(Exception):
    """Исключение для ошибок лексики (опционально, используем для восстановления)"""
    pass

class Scanner:
    """
    Лексический анализатор (сканер) по требованию LEX-2.
    """
    def __init__(self, source: str):
        self._source = source
        self._tokens: List[Token] = []
        
        # Указатели сканирования
        self._start = 0      # Начало текущей сканируемой лексемы
        self._current = 0    # Текущий символ (lookahead)
        self._line = 1       # Текущая строка (1-based)
        self._column_start_of_line = 0 # Индекс символа, где началась текущая строка
        
        # Кэш для next_token/peek_token
        self._scanned = False
        self._token_index = 0
        
        # Сразу сканируем весь файл в конструкторе (можно было бы лениво, 
        # но для упрощения интерфейса next/peek сделаем так)
        self._scan_all()
        
    def next_token(self) -> Token:
        """Метод для получения следующего токена с продвижением (LEX-2)"""
        if self._token_index < len(self._tokens):
            token = self._tokens[self._token_index]
            self._token_index += 1
            return token
        # Если вышли за пределы, всегда возвращаем EOF с последней позицией
        return Token(TokenType.END_OF_FILE, "", self._line, self._get_column() - 1, None)

    def peek_token(self) -> Token:
        """Просмотр следующего токена без продвижения (LEX-2)"""
        if self._token_index < len(self._tokens):
            return self._tokens[self._token_index]
        return Token(TokenType.END_OF_FILE, "", self._line, self._get_column() - 1, None)

    def is_at_end(self) -> bool:
        """Достигнут ли конец списка токенов"""
        if self._token_index >= len(self._tokens):
            return True
        return self._tokens[self._token_index].type == TokenType.END_OF_FILE

    def get_line(self) -> int:
        """Возвращает текущую строку сканера или следующего токена"""
        return self.peek_token().line
        
    def get_column(self) -> int:
        """Возвращает текущий столбец сканера или следующего токена"""
        return self.peek_token().column

    # --- Внутренние методы сканирования ---
    
    def _is_at_source_end(self) -> bool:
        return self._current >= len(self._source)

    def _get_column(self) -> int:
        """Вычисляет столбец для начала текущей лексемы (1-based)"""
        return self._start - self._column_start_of_line + 1
        
    def _get_current_column(self) -> int:
        return self._current - self._column_start_of_line + 1

    def _advance(self) -> str:
        """Прочитать следующий символ и сдвинуть указатель"""
        char = self._source[self._current]
        self._current += 1
        if char == '\n':
            self._line += 1
            self._column_start_of_line = self._current
        return char

    def _peek(self) -> str:
        """Посмотреть текущий символ (lookahead = 1)"""
        if self._is_at_source_end():
            return '\0'
        return self._source[self._current]

    def _peek_next(self) -> str:
        """Посмотреть следующий символ (lookahead = 2)"""
        if self._current + 1 >= len(self._source):
            return '\0'
        return self._source[self._current + 1]

    def _match(self, expected: str) -> bool:
        """Если текущий символ совпадает с expected, продвинуться вперед"""
        if self._is_at_source_end(): return False
        if self._source[self._current] != expected: return False
        
        self._current += 1
        return True

    def _add_token(self, type_t: TokenType, literal_value=None):
        """Создать токен и добавить в список"""
        text = self._source[self._start:self._current]
        self._tokens.append(Token(
            type=type_t,
            lexeme=text,
            line=self._line if text != '\n' else self._line - 1, # Если это перенос, позиция на предыдущей строке
            column=self._get_column(),
            literal_value=literal_value
        ))

    def _add_error_token(self, message: str):
        """Добавить токен ошибки для восстановления (LEX-5)"""
        text = self._source[self._start:self._current]
        # Выводим сообщение в sys.stderr или сохраняем как лексему ошибки
        import sys
        print(f"[{self._line}:{self._get_column()}] Ошибка: {message}. Лексема: '{text}'", file=sys.stderr)
        self._tokens.append(Token(
            type=TokenType.ERROR,
            lexeme=text,
            line=self._line,
            column=self._get_column(),
            literal_value=message
        ))

    def _scan_all(self):
        """Основной цикл лексического анализатора"""
        while not self._is_at_source_end():
            self._start = self._current
            self._scan_token()
            
        # Вставляем EOF последним
        self._start = self._current
        self._tokens.append(Token(
            type=TokenType.END_OF_FILE,
            lexeme="",
            line=self._line,
            column=self._get_current_column(),
            literal_value=None
        ))
        
    def _scan_token(self):
        c = self._advance()
        
        # Пробельные символы (LEX-6)
        if c in (' ', '\r', '\t', '\n'):
            return  # Игнорируем
        
        # Односимвольные или потенциально двусимвольные
        if c == '(': self._add_token(TokenType.LPAREN)
        elif c == ')': self._add_token(TokenType.RPAREN)
        elif c == '{': self._add_token(TokenType.LBRACE)
        elif c == '}': self._add_token(TokenType.RBRACE)
        elif c == '[': self._add_token(TokenType.LBRACKET)
        elif c == ']': self._add_token(TokenType.RBRACKET)
        elif c == ';': self._add_token(TokenType.SEMICOLON)
        elif c == ',': self._add_token(TokenType.COMMA)
        elif c == ':': self._add_token(TokenType.COLON)
        
        # Операторы
        elif c == '+':
            self._add_token(TokenType.PLUS_ASSIGN if self._match('=') else TokenType.PLUS)
        elif c == '-':
            self._add_token(TokenType.MINUS_ASSIGN if self._match('=') else TokenType.MINUS)
        elif c == '*':
            self._add_token(TokenType.STAR_ASSIGN if self._match('=') else TokenType.STAR)
        elif c == '%':
            self._add_token(TokenType.PERCENT)
            
        elif c == '=':
            self._add_token(TokenType.EQUAL_EQUAL if self._match('=') else TokenType.ASSIGN)
        elif c == '!':
            self._add_token(TokenType.BANG_EQUAL if self._match('=') else TokenType.BANG)
        elif c == '<':
            self._add_token(TokenType.LESS_EQUAL if self._match('=') else TokenType.LESS)
        elif c == '>':
            self._add_token(TokenType.GREATER_EQUAL if self._match('=') else TokenType.GREATER)
            
        elif c == '&':
            if self._match('&'):
                self._add_token(TokenType.AND_AND)
            else:
                self._add_error_token("Неожиданный символ '&', ожидалось '&&'")
        elif c == '|':
            if self._match('|'):
                self._add_token(TokenType.OR_OR)
            else:
                self._add_error_token("Неожиданный символ '|', ожидалось '||'")
                
        # Деление или комментарий (LEX-6)
        elif c == '/':
            if self._match('/'):
                # Однострочный комментарий
                while self._peek() != '\n' and not self._is_at_source_end():
                    self._advance()
            elif self._match('*'):
                # Многострочный комментарий
                self._block_comment()
            else:
                # Обычное деление
                self._add_token(TokenType.SLASH_ASSIGN if self._match('=') else TokenType.SLASH)
                
        # Строковые литералы
        elif c == '"':
            self._string()
            
        # Числа (целые и с плавающей точкой)
        elif c.isdigit():
            self._number()
            
        # Идентификаторы и Ключевые слова
        elif self._is_alpha_or_underscore(c):
            self._identifier()
            
        else:
            # Недопустимый символ (LEX-5: report invalid chars)
            self._add_error_token(f"Недопустимый символ '{c}'")

    def _block_comment(self):
        """Обработка многострочного комментария"""
        nesting = 1 # Если бы поддерживали вложенные комментарии. Спринт 1 разрешает просто до */
        while nesting > 0 and not self._is_at_source_end():
            if self._peek() == '*' and self._peek_next() == '/':
                self._advance() # *
                self._advance() # /
                nesting -= 1
            # Дополнительно: поддержка вложенных (опционально)
            # elif self._peek() == '/' and self._peek_next() == '*':
            #     self._advance()
            #     self._advance()
            #     nesting += 1
            else:
                self._advance()

        if nesting > 0:
            self._add_error_token("Незавершенный многострочный комментарий (EOF)")

    def _string(self):
        """Строковый литерал (LEX-4)"""
        while self._peek() != '"' and not self._is_at_source_end():
            if self._peek() == '\n':
                self._add_error_token("Незавершенная строка (перенос в строке)")
                return
            self._advance()

        if self._is_at_source_end():
            self._add_error_token("Незавершенная строка (достигнут конец файла)")
            return

        # Закрывающая кавычка
        self._advance()

        # Извлекаем значение (без кавычек)
        value = self._source[self._start + 1 : self._current - 1]
        self._add_token(TokenType.STRING_LITERAL, value)

    def _number(self):
        """Числовой литерал (LEX-4)"""
        is_float = False
        
        while self._peek().isdigit():
            self._advance()

        # Дробная часть
        if self._peek() == '.' and self._peek_next().isdigit():
            is_float = True
            self._advance() # Поглощаем '.'
            while self._peek().isdigit():
                self._advance()

        value_str = self._source[self._start:self._current]
        if is_float:
            self._add_token(TokenType.FLOAT_LITERAL, float(value_str))
        else:
            # Для Sprint 1 диапазон [-2³¹, 2³¹-1] проверяться строго может на этапе парсинга, 
            # но мы ограничимся сохранением int()
            self._add_token(TokenType.INT_LITERAL, int(value_str))

    def _is_alpha_or_underscore(self, c: str) -> bool:
        return c.isalpha() or c == '_'

    def _is_alphanumeric_or_underscore(self, c: str) -> bool:
        return self._is_alpha_or_underscore(c) or c.isdigit()

    def _identifier(self):
        """Идентификатор или Ключевое слово (LEX-2, LEX-3)"""
        while self._is_alphanumeric_or_underscore(self._peek()):
            self._advance()

        text = self._source[self._start:self._current]
        
        # Проверка длины (MAX 255)
        if len(text) > 255:
            self._add_error_token(f"Идентификатор слишком длинный ({len(text)} > 255)")
            return

        # Проверяем, не ключевое ли это слово
        type_t = KEYWORDS.get(text, TokenType.IDENTIFIER)
        
        if type_t == TokenType.KW_TRUE:
            self._add_token(TokenType.BOOL_LITERAL, True)
        elif type_t == TokenType.KW_FALSE:
            self._add_token(TokenType.BOOL_LITERAL, False)
        elif type_t == TokenType.IDENTIFIER:
            self._add_token(TokenType.IDENTIFIER, text)
        else:
            self._add_token(type_t)
