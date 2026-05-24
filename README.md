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

### Генерация x86-64 ассемблера (Спринт 5)

Спринт 5 добавляет модуль `src/codegen/` для генерации **x86-64 ассемблерного кода** в синтаксисе NASM, следуя соглашению о вызовах **System V AMD64 ABI**.

#### Соглашение о вызовах (System V AMD64 ABI)

```
Передача аргументов (целые):  RDI, RSI, RDX, RCX, R8, R9
Передача аргументов (float):  XMM0–XMM7
Возврат значения:             RAX (целое), XMM0 (float)
Caller-saved:                 RAX, RCX, RDX, RSI, RDI, R8–R11
Callee-saved:                 RBX, RSP, RBP, R12–R15
Выравнивание стека:           16 байт перед CALL
```

#### Структура стекового фрейма

```
Высокие адреса
┌─────────────────┐
│  ...            │
├─────────────────┤
│ 7-й аргумент   │  [rbp+32]  (если > 6 аргументов)
├─────────────────┤
│ адрес возврата  │  [rbp+8]
├─────────────────┤
│ сохранённый rbp │  [rbp]   ← rbp указывает сюда
├─────────────────┤
│ локальная var 1 │  [rbp-8]
├─────────────────┤
│ локальная var 2 │  [rbp-16]
├─────────────────┤
│ временная t1    │  [rbp-24]
└─────────────────┘  ← rsp указывает сюда
Низкие адреса
```

#### Команды CLI для генерации ассемблера

Вывести сгенерированный ассемблер в stdout:
```bash
python -m src.main compile --input examples/factorial_func.src
```

Сохранить ассемблер в файл:
```bash
python -m src.main compile --input examples/factorial_func.src --output factorial.asm
```

С выводом статистики IR:
```bash
python -m src.main compile --input examples/factorial_func.src --ir-stats --output factorial.asm
```

#### Пример трансформации: исходный код → ассемблер

```c
// Исходный код:
fn add(int a, int b) -> int {
    int result = a + b;
    return result;
}
```

```nasm
; Сгенерировано MiniCompiler (Sprint 5)
; Цель: x86-64 Linux, синтаксис: NASM

section .text

global add

; === Функция: add -> int ===
add:
    push rbp
    mov rbp, rsp
    sub rsp, 48          ; стековый фрейм
    mov qword [rbp-8], rdi   ; параметр int a
    mov qword [rbp-16], rsi  ; параметр int b
    ; a_0 = ALLOCA
    ; b_0 = ALLOCA
    ; result_0 = ALLOCA
    ; t1 = LOAD [a_0]
    mov rax, qword [rbp-8]
    mov qword [rbp-40], rax
    ; t2 = LOAD [b_0]
    mov rax, qword [rbp-16]
    mov qword [rbp-48], rax
    ; t3 = ADD t1, t2
    mov rax, qword [rbp-40]
    mov rcx, qword [rbp-48]
    add rax, rcx
    mov qword [rbp-56], rax
    ; STORE [result_0], t3
    mov rax, qword [rbp-56]
    mov qword [rbp-24], rax
    ; t4 = LOAD [result_0]
    mov rax, qword [rbp-24]
    mov qword [rbp-64], rax
    ; RETURN t4
    mov rax, qword [rbp-64]
    mov rsp, rbp
    pop rbp
    ret
```

#### Сборка и запуск (Linux / WSL)

```bash
# 1. Компилируем исходник в ассемблер
python -m src.main compile --input examples/factorial_func.src --output factorial.asm

# 2. Ассемблируем с NASM (ELF64)
nasm -f elf64 -o factorial.o factorial.asm
nasm -f elf64 -o runtime.o src/runtime/runtime.asm

# 3. Линкуем
ld -o factorial runtime.o factorial.o

# 4. Запускаем и проверяем код возврата
./factorial
echo $?   # Должно вывести возвращаемое значение main()
```

#### Минимальная runtime-библиотека (`src/runtime/runtime.asm`)

### Управляющие конструкции и логика (Спринт 6)

Спринт 6 расширяет кодогенератор поддержкой **управляющих конструкций** (`if/else`, `while`, `for`),
**короткого замыкания** для `&&` и `||`, и переводит кодогенератор на **миксин-архитектуру**.

#### Архитектура кодогенератора

```
src/codegen/
├── label_manager.py         # генерация уникальных меток (LabelManager)
├── control_flow_generator.py # миксин: if/else, while, for, ветвления
├── expression_generator.py  # миксин: арифметика, сравнения, логика
└── x86_generator.py         # главный генератор: наследует оба миксина
```

`X86Generator` использует множественное наследование:
```python
class X86Generator(ControlFlowGeneratorMixin, ExpressionGeneratorMixin):
    ...
```

#### Генерация меток

`LabelManager` выдаёт уникальные метки для каждой конструкции:

| Конструкция   | Метки                                          |
|:--------------|:-----------------------------------------------|
| `if`          | `L_then_N`, `L_else_N`, `L_endif_N`            |
| `while`       | `L_while_cond_N`, `L_while_body_N`, `L_while_end_N` |
| `for`         | `L_for_cond_N`, `L_for_body_N`, `L_for_end_N`  |
| `&&` (SC)     | `L_sc_false_N`, `L_sc_end_N`                   |
| `\|\|` (SC)   | `L_sc_true_N`, `L_sc_end_N`                    |

#### Короткое замыкание (`&&` и `||`)

Операторы `&&` и `||` реализованы через IR-уровневые переходы — правый операнд **не вычисляется**, если результат уже известен.

**Схема `&&` (AND с коротким замыканием):**
```
    ; вычислить left → t1
    mov rax, [left]
    test rax, rax
    jz  L_sc_false_1     ; left == 0 → сразу false
    ; вычислить right → t2
    mov rax, [right]
    test rax, rax
    jz  L_sc_false_1     ; right == 0 → false
    mov [result], 1
    jmp L_sc_end_1
L_sc_false_1:
    mov [result], 0
L_sc_end_1:
    mov rax, [result]
```

**Схема `||` (OR с коротким замыканием):**
```
    ; вычислить left → t1
    mov rax, [left]
    test rax, rax
    jnz L_sc_true_1      ; left != 0 → сразу true
    ; вычислить right → t2
    mov rax, [right]
    test rax, rax
    jnz L_sc_true_1      ; right != 0 → true
    mov [result], 0
    jmp L_sc_end_1
L_sc_true_1:
    mov [result], 1
L_sc_end_1:
    mov rax, [result]
```

#### Пример: if/else с &&

```c
// Исходный код:
fn check(int a, int b) -> int {
    if (a > 0 && b > 0) {
        return 1;
    } else {
        return 0;
    }
}
```

```nasm
; Сгенерировано MiniCompiler (Sprint 6)
check:
    push rbp
    mov rbp, rsp
    sub rsp, 96
    ; ... параметры a, b ...
    ; && короткое замыкание:
    mov rax, qword [rbp-8]   ; a
    mov rcx, 0
    cmp rax, rcx
    setg al
    movzx rax, al
    test rax, rax
    jz  L_sc_false_1         ; a <= 0 → пропустить правый операнд
    mov rax, qword [rbp-16]  ; b
    mov rcx, 0
    cmp rax, rcx
    setg al
    movzx rax, al
    test rax, rax
    jz  L_sc_false_1
    mov qword [rbp-32], 1
    jmp L_sc_end_1
L_sc_false_1:
    mov qword [rbp-32], 0
L_sc_end_1:
    ; if
    mov rax, qword [rbp-32]
    test rax, rax
    jz  L_else_2
L_then_2:
    mov rax, 1
    mov rsp, rbp
    pop rbp
    ret
    jmp L_endif_2
L_else_2:
    mov rax, 0
    mov rsp, rbp
    pop rbp
    ret
L_endif_2:
```

#### Тесты Sprint 6

```bash
# Тесты управляющих конструкций
pytest tests/control_flow/ -v

# Все тесты включая Sprint 5
pytest tests/codegen/ tests/control_flow/ -v
```

### Массивы, внешние функции, оптимизации (Спринт 7)

Спринт 7 добавляет поддержку **массивов**, **extern-функций** (printf, malloc и др.)
и **IR-оптимизатор** с тремя классическими проходами.

#### Массивы

Объявление и использование массивов на стеке:

```c
fn main() -> int {
    // Объявление массива из 5 int
    int arr[5];

    // Объявление с инициализатором
    int nums[3] = {10, 20, 30};

    // Чтение элемента
    int x = arr[2];

    // Запись элемента (динамический индекс)
    int i = 1;
    arr[i] = 42;

    return nums[0];
}
```

Адресный расчёт: `base + index * 8` (все элементы 8-байтные).
При константном индексе генерируется прямой offset, при переменном — `shl rcx, 3` + `add rax, rcx`.

#### Внешние функции (extern)

Объявление и вызов функций из libc:

```c
// Объявить printf как внешнюю
extern fn printf(int) -> int;
extern fn malloc(int) -> int;

fn main() -> int {
    // Вызов внешней функции
    printf("Hello, world!\n");

    // Выделить память
    int ptr = malloc(64);
    return 0;
}
```

Особенности генерации:
- `extern printf` появляется в начале ассемблерного файла
- Для variadic-функций (printf, scanf, ...) добавляется `xor eax, eax` перед `call`
- Стек выравнивается на 16 байт при наличии стековых аргументов

Известные внешние функции: `printf`, `scanf`, `malloc`, `free`, `memcpy`, `memset`,
`strlen`, `strcpy`, `strcmp`, `puts`, `getchar`, `exit`, `atoi`, `rand` и др.

Полный список сигнатур — в `src/libc/stdlib.h`.

#### IR-оптимизатор

Три оптимизационных прохода запускаются флагом `--optimize` / `-O`:

**1. Constant Folding** — вычисляет константные выражения на этапе компиляции:
```
ADD 3, 4    →    MOVE 7
MUL 6, 7    →    MOVE 42
CMP_LT 3, 5 →   MOVE 1
```

**2. Constant Propagation** — подставляет известные константы вместо переменных:
```
MOVE t1, 5
ADD t2, t1, 3   →   ADD t2, 5, 3
```

**3. Dead Code Elimination** — убирает недостижимый код и мёртвые присваивания:
```
JUMP L_end
MOVE t1, 99     ← удаляется (недостижимо)
MOVE t2, 0      ← удаляется (недостижимо)
L_end:
```

#### CLI для Sprint 7

Компиляция с оптимизацией:
```bash
python -m src.main compile --input demo/quicksort.src --optimize --output out.asm
```

Компиляция с выводом статистики оптимизации:
```bash
python -m src.main compile --input examples/factorial_func.src -O --opt-stats
```

Пример вывода статистики:
```
=== Статистика оптимизации ===
  Свёрнуто константных выражений:  3
  Подставлено констант:             5
  Удалено мёртвых инструкций:       2
  Итого оптимизировано:             10
  Инструкций до:   47
  Инструкций после:37
```

#### Тесты Sprint 7

```bash
# Тесты массивов
pytest tests/arrays/ -v

# Тесты внешних вызовов
pytest tests/external_calls/ -v

# Тесты оптимизатора
pytest tests/optimization/ -v

# Все тесты Sprint 7
pytest tests/arrays/ tests/external_calls/ tests/optimization/ -v
```

#### Структура новых файлов

```
src/
├── ir/
│   └── optimizer.py            # IROptimizer: folding, propagation, DCE
├── codegen/
│   ├── array_generator.py      # ArrayGeneratorMixin: ARRAY_ALLOC/LOAD/STORE/GET_ADDR
│   ├── external_calls.py       # ExternalCallsMixin: extern, variadic ABI
│   └── optimization_passes.py  # AsmOptimizer: peephole над NASM-строками
└── libc/
    └── stdlib.h                # Справочник сигнатур libc для MiniCompiler

demo/
└── quicksort.src               # Демо: сортировка массива + extern printf

tests/
├── arrays/
│   └── test_arrays.py
├── external_calls/
│   └── test_external_calls.py
└── optimization/
    └── test_optimization.py
```

| Функция       | Аргументы       | Описание                                 |
|:--------------|:----------------|:-----------------------------------------|
| `_start`      | —               | Точка входа процесса, вызывает `main`    |
| `exit`        | rdi = код       | Завершает процесс (syscall `exit`)       |
| `print_int`   | rdi = число     | Выводит целое + `\n` в stdout            |
| `print_string`| rdi = указатель | Выводит null-terminated строку в stdout  |
| `read_int`    | —               | Читает целое из stdin → rax              |

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

# Тесты генерации x86-64 ассемблера (Sprint 5)
pytest tests/codegen/ -v

# Тесты управляющих конструкций (Sprint 6)
pytest tests/control_flow/ -v

# Все тесты с кратким отчётом
pytest tests/ -q
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
│   │   ├── ir_instructions.py  # IR-инструкции (опкоды, операнды)
│   │   ├── basic_block.py      # базовые блоки
│   │   ├── control_flow.py     # граф потока управления (CFG)
│   │   └── ir_generator.py     # генератор IR из AST
│   ├── codegen/        # Спринт 5-6: генерация x86-64 ассемблера
│   │   ├── abi.py              # константы System V AMD64 ABI
│   │   ├── stack_frame.py      # управление стековым фреймом
│   │   ├── register_allocator.py  # распределение регистров (stack-based)
│   │   ├── label_manager.py    # Sprint 6: генератор уникальных меток
│   │   ├── control_flow_generator.py  # Sprint 6: миксин управляющих конструкций
│   │   ├── expression_generator.py    # Sprint 6: миксин выражений
│   │   └── x86_generator.py   # генератор NASM-кода из IR
│   ├── runtime/        # Спринт 5: runtime-библиотека
│   │   └── runtime.asm         # _start, exit, print_int, print_string, read_int
│   ├── utils/
│   └── main.py         # единая точка входа CLI
├── tests/
│   ├── lexer/
│   ├── parser/
│   ├── semantic/
│   ├── ir/             # тесты Sprint 4
│   │   ├── generation/
│   │   └── validation/
│   ├── codegen/        # тесты Sprint 5
│   │   ├── valid/
│   │   │   ├── arithmetic_ops/   # арифметика
│   │   │   ├── control_flow/     # if, while
│   │   │   ├── function_calls/   # вызовы, рекурсия
│   │   │   ├── io_operations/    # ввод-вывод
│   │   │   └── integration/      # комплексные программы
│   │   └── test_codegen.py       # pytest-тесты кодогенерации
│   └── control_flow/   # тесты Sprint 6
│       └── test_control_flow.py  # if/else, while, for, &&, ||
├── examples/
│   ├── hello.src
│   ├── factorial.src
│   ├── factorial_func.src
│   └── while_loop.src
└── docs/
```
