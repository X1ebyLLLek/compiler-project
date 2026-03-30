# Формальная грамматика языка MiniCompiler (EBNF)

## Обзор
Контекстно-свободная грамматика описана в расширенной форме Бэкуса-Наура (EBNF).
Терминалы соответствуют типам токенов из лексера (Спринт 1).

## Стартовый символ
```
Program ::= { Declaration }
```

## Объявления (Declarations)
```
Declaration    ::= FunctionDecl | StructDecl | VarDecl

FunctionDecl   ::= "fn" IDENTIFIER "(" [ Parameters ] ")" [ "->" Type ] Block

StructDecl     ::= "struct" IDENTIFIER "{" { VarDecl } "}"

VarDecl        ::= Type IDENTIFIER [ "=" Expression ] ";"
```

## Параметры функций
```
Parameters     ::= Parameter { "," Parameter }
Parameter      ::= Type IDENTIFIER
```

## Инструкции (Statements)
```
Statement      ::= Block
                  | IfStmt
                  | WhileStmt
                  | ForStmt
                  | ReturnStmt
                  | VarDecl
                  | ExprStmt

Block          ::= "{" { Statement } "}"

IfStmt         ::= "if" "(" Expression ")" Statement [ "else" Statement ]

WhileStmt      ::= "while" "(" Expression ")" Statement

ForStmt        ::= "for" "(" [ VarDecl | ExprStmt ] [ Expression ] ";" [ Expression ] ")" Statement

ReturnStmt     ::= "return" [ Expression ] ";"

ExprStmt       ::= Expression ";"
```

## Выражения (Expressions) — порядок приоритетов (от низшего к высшему)
```
Expression     ::= Assignment

Assignment     ::= LogicalOr { ("=" | "+=" | "-=" | "*=" | "/=") Assignment }

LogicalOr      ::= LogicalAnd { "||" LogicalAnd }

LogicalAnd     ::= Equality { "&&" Equality }

Equality       ::= Relational { ("==" | "!=") Relational }

Relational     ::= Additive { ("<" | "<=" | ">" | ">=") Additive }

Additive       ::= Multiplicative { ("+" | "-") Multiplicative }

Multiplicative ::= Unary { ("*" | "/" | "%") Unary }

Unary          ::= ("-" | "!") Unary
                  | Primary

Primary        ::= INT_LITERAL
                  | FLOAT_LITERAL
                  | STRING_LITERAL
                  | BOOL_LITERAL
                  | IDENTIFIER [ "(" [ Arguments ] ")" ]
                  | "(" Expression ")"

Arguments      ::= Expression { "," Expression }
```

## Типы
```
Type           ::= "int" | "float" | "bool" | "void" | IDENTIFIER
```

## Приоритеты и ассоциативность
| Уровень | Операторы | Ассоциативность |
|---------|-----------|-----------------|
| 1 (высший) | `- !` (унарные) | Правая |
| 2 | `* / %` | Левая |
| 3 | `+ -` | Левая |
| 4 | `< <= > >=` | Неассоциативные |
| 5 | `== !=` | Неассоциативные |
| 6 | `&&` | Левая |
| 7 | `\|\|` | Левая |
| 8 (низший) | `= += -= *= /=` | Правая |
