# MiniCompiler

Учебный проект компилятора, написанный на **Python**. Проект реализует пошаговое создание компилятора от лексического анализа до кодогенерации (ассемблер x86-64).

## Команда
Данный проект выполняется в рамках курса "Построение компиляторов: Теория и практика".

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
```

## Формальная грамматика
Полная спецификация грамматики языка в нотации EBNF доступна в:
- [docs/grammar.md](docs/grammar.md)
- [src/parser/grammar.txt](src/parser/grammar.txt)

## Документация
Подробная спецификация лексической и синтаксической грамматики находится в папке `docs/`:
- [Спецификация языка (Спринт 1)](docs/language_spec.md)
- [Грамматика языка (Спринт 2)](docs/grammar.md)
