# MiniCompiler

Учебный проект компилятора, написанный на **Python**. Проект реализует пошаговое создание компилятора от лексического анализа до генерации промежуточного представления (IR).

## Команда
Данный проект выполняется в рамках курса «Построение компиляторов: Теория и практика».

## Сборка и запуск

Проект написан на Python 3.9+ и использует встроенные библиотеки.

### Подготовка окружения
Настоятельно рекомендуется создать виртуальное окружение:
```bash
python -m venv venv
# Активация на Windows:
venv\Scripts\activate
# Активация на Linux/Mac:
source venv/bin/activate
```

Установка необходимых пакетов для разработки и тестирования (например, `pytest`):
```bash
pip install -e .[dev]
```

### Использование лексера (Спринт 1)
Для вывода потока токенов из исходного файла:
```bash
python -m src.main lex --input examples/hello.src
```

### Использование парсера (Спринт 2)
Парсинг файла и вывод AST в текстовом формате:
```bash
python -m src.main parse --input examples/hello.src
```

Генерация Graphviz DOT-файла для визуализации дерева:
```bash
python -m src.main parse --input examples/hello.src --ast-format dot --output ast.dot
# Конвертация в PNG (при наличии Graphviz):
# dot -Tpng ast.dot -o ast.png
```

Вывод AST в JSON (для автотестов или анализа):
```bash
python -m src.main parse --input examples/hello.src --ast-format json
```

Подробный режим (печатает также список токенов):
```bash
python -m src.main parse --input examples/hello.src --verbose
```

### Семантический анализ (Спринт 3)
Проверка корректности типов, объявлений и областей видимости:
```bash
python -m src.main check --input examples/factorial.src
```

Подробный режим с выводом таблицы символов и типовых аннотаций:
```bash
python -m src.main check --input examples/factorial.src --verbose --show-types
```

Вывод результата в файл:
```bash
python -m src.main check --input examples/factorial.src --output report.txt
```

#### Пример вывода ошибок
```
semantic error: необъявленная переменная 'z'
  --> строка 4:15
   |
   |     int y = z + x;
   |               ^
   |
   = подсказка: возможно, вы имели в виду 'x'? (объявлено в строке 3)
```

### Генерация промежуточного представления (Спринт 4)

Спринт 4 добавляет модуль `src/ir/` для генерации **трёхадресного кода** (three-address code) на основе декорированного AST из спринта 3.

#### Формат промежуточного представления

IR использует трёхадресные инструкции следующего вида:

```
# Арифметика
t1 = ADD t2, t3       # t1 = t2 + t3
t1 = SUB t2, t3       # t1 = t2 - t3
t1 = MUL t2, t3       # t1 = t2 * t3
t1 = DIV t2, t3       # t1 = t2 / t3
t1 = MOD t2, t3       # t1 = t2 % t3
t1 = NEG t2           # t1 = -t2

# Сравнения
t1 = CMP_LT t2, t3    # t1 = (t2 < t3)
t1 = CMP_LE t2, t3    # t1 = (t2 <= t3)
t1 = CMP_GT t2, t3    # t1 = (t2 > t3)
t1 = CMP_GE t2, t3    # t1 = (t2 >= t3)
t1 = CMP_EQ t2, t3    # t1 = (t2 == t3)
t1 = CMP_NE t2, t3    # t1 = (t2 != t3)

# Логика
t1 = AND t2, t3       # t1 = t2 && t3
t1 = OR  t2, t3       # t1 = t2 || t3
t1 = NOT t2           # t1 = !t2

# Память
x_0 = ALLOCA          # выделить стек-переменную
STORE [x_0], t1       # записать значение в переменную
t1 = LOAD [x_0]       # загрузить значение переменной

# Управление потоком
JUMP L1               # безусловный переход
JUMP_IF t1, L1        # прыжок если t1 истинно
JUMP_IF_NOT t1, L1    # прыжок если t1 ложно
RETURN t1             # вернуть значение
RETURN                # return void

# Функции
PARAM 0, t1           # передать аргумент 0
t1 = CALL func, args  # вызвать функцию
```

#### Команды CLI для IR

Вывод IR в текстовом формате (по умолчанию):
```bash
python -m src.main ir --input examples/factorial_func.src
```

Генерация Graphviz DOT для граф потока управления (CFG):
```bash
python -m src.main ir --input examples/factorial_func.src --format dot --output factorial_cfg.dot
# Конвертация в PNG (при наличии Graphviz):
# dot -Tpng factorial_cfg.dot -o factorial_cfg.png
```

Вывод IR в машиночитаемом JSON-формате:
```bash
python -m src.main ir --input examples/factorial_func.src --format json
```

Вывод статистики IR (количество блоков, инструкций, временных переменных):
```bash
python -m src.main ir --input examples/factorial_func.src --stats
```

Вывод IR только для одной функции:
```bash
python -m src.main ir --input examples/factorial_func.src --function factorial
```

#### Пример трансформации: исходный код → IR

```c
// Исходный код:
fn factorial(int n) -> int {
    if (n <= 1) {
        return 1;
    } else {
        int prev = factorial(n - 1);
        return n * prev;
    }
}
```

```
// Сгенерированный IR:
function factorial: int (int n)
  entry:
    n_0 = ALLOCA                    # параметр int n
    PARAM 0, n_0                    # аргумент n
    t1 = LOAD [n_0]                 # загрузить n
    t2 = CMP_LE t1, 1               # n <= 1
    JUMP_IF t2, L_then_1            # если условие истинно
    JUMP L_else_2

  L_then_1:
    RETURN 1                        # return 1

  L_else_2:
    prev_0 = ALLOCA                 # int prev
    t3 = LOAD [n_0]                 # загрузить n
    t4 = SUB t3, 1                  # n - 1
    PARAM 0, t4                     # аргумент 0 для factorial
    t5 = CALL factorial             # вызов factorial
    STORE [prev_0], t5              # prev = result
    t6 = LOAD [n_0]                 # загрузить n
    t7 = LOAD [prev_0]              # загрузить prev
    t8 = MUL t6, t7                 # n * prev
    RETURN t8                       # return n * prev
```

### Пример AST-вывода (текстовый формат)
```
Program [line 1]:
  FunctionDecl: main -> void [line 2]:
    Parameters: []
    Body:
      Block:
        VarDecl: int counter =
          Literal: 42 (int)
        Return [line 10]:
          Identifier: counter
```

### Тестирование
Для запуска всех юнит-тестов (требуется `pytest`):
```bash
# Все тесты
pytest tests/ -v

# Только тесты лексера
pytest tests/test_runner.py -v

# Только тесты парсера
pytest tests/parser/test_parser.py -v

# Только тесты семантического анализатора
pytest tests/semantic/test_semantic.py -v

# Тесты IR-генерации (Sprint 4)
pytest tests/ir/ -v

# Только тесты генерации IR (выражения, управление, функции)
pytest tests/ir/generation/ -v

# Только структурные тесты валидации IR
pytest tests/ir/validation/ -v
```

## Формальная грамматика
Полная спецификация грамматики языка в нотации EBNF доступна в:
- [docs/grammar.md](docs/grammar.md)
- [src/parser/grammar.txt](src/parser/grammar.txt)

## Документация
Подробная спецификация лексической и синтаксической грамматики находится в папке `docs/`:
- [Спецификация языка (Спринт 1)](docs/language_spec.md)
- [Грамматика языка (Спринт 2)](docs/grammar.md)

## Структура проекта

```
compiler-project/
├── src/
│   ├── lexer/          # Спринт 1: лексический анализ
│   ├── parser/         # Спринт 2: синтаксический анализ + AST
│   ├── semantic/       # Спринт 3: семантический анализ
│   ├── ir/             # Спринт 4: генерация промежуточного представления
│   │   ├── ir_instructions.py  # набор IR-инструкций (опкоды, операнды)
│   │   ├── basic_block.py      # базовые блоки кода
│   │   ├── control_flow.py     # граф потока управления (CFG), IRFunction, IRProgram
│   │   └── ir_generator.py     # генератор IR из AST (паттерн Visitor)
│   ├── utils/
│   └── main.py         # единая точка входа CLI
├── tests/
│   ├── lexer/
│   ├── parser/
│   ├── semantic/
│   └── ir/             # тесты Sprint 4
│       ├── generation/
│       │   ├── test_expressions.py   # выражения
│       │   ├── test_control_flow.py  # if/while/for/return
│       │   └── test_functions.py     # функции + интеграция
│       └── validation/
│           └── test_structural.py    # структурные свойства IR
├── examples/
│   ├── hello.src
│   ├── factorial.src
│   ├── factorial_func.src  # рекурсивная функция (Sprint 4)
│   └── while_loop.src      # пример с циклом (Sprint 4)
└── docs/
```
