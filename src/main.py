"""
Единая точка входа в компилятор MiniCompiler (VIS-4).
Поддерживает команды:
  python -m src.main lex   <file>  — вывод потока токенов
  python -m src.main parse <file>  — парсинг и вывод AST
  python -m src.main check <file>  — семантический анализ (Sprint 3)
  python -m src.main ir    <file>  — генерация промежуточного представления (Sprint 4)

Опции для parse:
  --ast-format text|dot|json  (по умолчанию text)
  --output <file>             (по умолчанию stdout)
  --verbose                   (подробный вывод)

Опции для check:
  --verbose                   (подробный вывод: токены, AST, типы)
  --show-types                (показать типовые аннотации AST)
  --output <file>             (файл для вывода)

Опции для ir:
  --format text|dot|json      (по умолчанию text)
  --output <file>             (файл для записи IR / DOT)
  --stats                     (вывести статистику IR)
  --function <name>           (вывести IR только для одной функции)
"""

import argparse
import json
import sys

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast_printer import ASTPrettyPrinter, ASTDotPrinter, ASTJsonPrinter
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def read_source(path: str) -> str:
    """Прочитать исходный файл в строку (UTF-8)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Ошибка: файл '{path}' не найден.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_lex(args):
    """Команда лексического анализа — вывод всех токенов."""
    source = read_source(args.input)
    scanner = Scanner(source)
    output_lines = [str(tok) for tok in scanner._tokens]
    result = "\n".join(output_lines) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Токены записаны в {args.output}")
    else:
        print(result, end="")


def cmd_parse(args):
    """Команда парсинга — построение и вывод AST."""
    source = read_source(args.input)

    # Лексический анализ
    scanner = Scanner(source)
    tokens = scanner._tokens

    if args.verbose:
        print("=== Токены ===", file=sys.stderr)
        for tok in tokens:
            print(f"  {tok}", file=sys.stderr)
        print("==============\n", file=sys.stderr)

    # Синтаксический анализ
    parser = Parser(tokens)
    ast = parser.parse()

    # Проверяем наличие ошибок
    errors = parser.get_errors()
    if errors and args.verbose:
        print(f"\nОбнаружено ошибок парсинга: {len(errors)}", file=sys.stderr)

    # Выбираем формат вывода AST
    fmt = args.ast_format
    if fmt == "text":
        printer = ASTPrettyPrinter()
        result = printer.print_ast(ast) + "\n"
    elif fmt == "dot":
        printer = ASTDotPrinter()
        result = printer.generate(ast) + "\n"
    elif fmt == "json":
        printer = ASTJsonPrinter()
        result = printer.to_json(ast) + "\n"
    else:
        print(f"Неизвестный формат: {fmt}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"AST записан в {args.output} (формат: {fmt})")
    else:
        print(result, end="")


def cmd_check(args):
    """Команда семантического анализа (Sprint 3)."""
    source = read_source(args.input)

    # Лексический анализ
    scanner = Scanner(source)
    tokens = scanner._tokens

    if args.verbose:
        print("=== Токены ===", file=sys.stderr)
        for tok in tokens:
            print(f"  {tok}", file=sys.stderr)
        print("==============\n", file=sys.stderr)

    # Синтаксический анализ
    parser = Parser(tokens)
    ast = parser.parse()

    parse_errors = parser.get_errors()
    if parse_errors:
        print(f"Обнаружено ошибок парсинга: {len(parse_errors)}", file=sys.stderr)
        for err in parse_errors:
            print(f"  {err}", file=sys.stderr)
        if not args.verbose:
            print("Невозможно выполнить семантический анализ из-за ошибок парсинга.",
                  file=sys.stderr)
            sys.exit(1)

    # Семантический анализ
    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast, source=source)

    # Формирование вывода
    output_parts = []

    if args.show_types or args.verbose:
        output_parts.append(analyzer.format_decorated_ast(ast))
        output_parts.append("")

    if args.verbose:
        sym_table = analyzer.get_symbol_table()
        output_parts.append(sym_table.dump())
        output_parts.append("")

    # Ошибки
    sem_errors = analyzer.get_errors()
    if sem_errors:
        output_parts.append(analyzer.format_errors())
    else:
        output_parts.append("Семантических ошибок не обнаружено.")

    result = "\n".join(output_parts) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Результат семантического анализа записан в {args.output}")
    else:
        print(result, end="")

    # Код возврата
    if sem_errors:
        sys.exit(1)


def cmd_ir(args):
    """Команда генерации промежуточного представления (Sprint 4)."""
    source = read_source(args.input)

    # Лексический анализ
    scanner = Scanner(source)
    tokens = scanner._tokens

    # Синтаксический анализ
    parser = Parser(tokens)
    ast = parser.parse()

    parse_errors = parser.get_errors()
    if parse_errors:
        print(f"Ошибки парсинга: {len(parse_errors)}", file=sys.stderr)
        for err in parse_errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)

    # Семантический анализ
    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast, source=source)

    sem_errors = analyzer.get_errors()
    if sem_errors:
        print(f"Семантические ошибки: {len(sem_errors)}", file=sys.stderr)
        print(analyzer.format_errors(), file=sys.stderr)
        sys.exit(1)

    # Генерация IR
    generator = IRGenerator()
    ir_program = generator.generate(ast)

    # Вывод статистики
    if args.stats:
        stats = ir_program.stats()
        print("=== Статистика IR ===")
        print(f"  Функций:       {stats['functions']}")
        print(f"  Блоков всего:  {stats['total_blocks']}")
        print(f"  Инструкций:    {stats['total_instructions']}")
        print(f"  Временных:     {stats['total_temporaries']}")
        print("  По опкодам:")
        for opcode, count in sorted(stats["by_opcode"].items()):
            print(f"    {opcode:<16}: {count}")
        print()

    # Выбираем функцию, если указана опция --function
    if args.function:
        func = ir_program.get_function(args.function)
        if func is None:
            print(
                f"Ошибка: функция '{args.function}' не найдена в IR.",
                file=sys.stderr,
            )
            print(
                f"Доступные функции: {[f.name for f in ir_program.functions]}",
                file=sys.stderr,
            )
            sys.exit(1)
        # Создаём временную «программу» из одной функции для вывода
        from src.ir.control_flow import IRProgram as _IRProgram
        single = _IRProgram()
        single.add_function(func)
        ir_program = single

    # Формат вывода
    fmt = args.format
    if fmt == "text":
        result = ir_program.dump() + "\n"
    elif fmt == "dot":
        # Если одна функция — один DOT-файл; иначе объединяем
        dot_maps = ir_program.to_dot_all()
        if len(dot_maps) == 1:
            result = list(dot_maps.values())[0] + "\n"
        else:
            # Несколько функций — выводим по очереди
            parts = []
            for name, dot in dot_maps.items():
                parts.append(f"// === Функция: {name} ===\n{dot}")
            result = "\n\n".join(parts) + "\n"
    elif fmt == "json":
        result = ir_program.to_json() + "\n"
    else:
        print(f"Неизвестный формат: {fmt}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"IR записан в {args.output} (формат: {fmt})")
    else:
        print(result, end="")


def main():
    ap = argparse.ArgumentParser(
        description="MiniCompiler — учебный компилятор"
    )
    subparsers = ap.add_subparsers(dest="command", help="Доступные команды")

    # --- lex ---
    lex_p = subparsers.add_parser("lex", help="Лексический анализ")
    lex_p.add_argument("--input", "-i", required=True, help="Путь к .src файлу")
    lex_p.add_argument("--output", "-o", default=None, help="Файл для записи токенов")

    # --- parse ---
    parse_p = subparsers.add_parser("parse", help="Синтаксический анализ (парсинг)")
    parse_p.add_argument("--input", "-i", required=True, help="Путь к .src файлу")
    parse_p.add_argument("--output", "-o", default=None, help="Файл для записи AST")
    parse_p.add_argument("--ast-format", "-f", choices=["text", "dot", "json"],
                         default="text", help="Формат вывода AST")
    parse_p.add_argument("--verbose", "-v", action="store_true",
                         help="Подробный вывод (список токенов и т.д.)")

    # --- check (Sprint 3) ---
    check_p = subparsers.add_parser("check", help="Семантический анализ")
    check_p.add_argument("--input", "-i", required=True, help="Путь к .src файлу")
    check_p.add_argument("--output", "-o", default=None, help="Файл для записи результата")
    check_p.add_argument("--verbose", "-v", action="store_true",
                         help="Подробный вывод (токены, AST, таблица символов)")
    check_p.add_argument("--show-types", action="store_true",
                         help="Показать типовые аннотации AST")

    # --- ir (Sprint 4) ---
    ir_p = subparsers.add_parser("ir", help="Генерация промежуточного представления (IR)")
    ir_p.add_argument("--input", "-i", required=True, help="Путь к .src файлу")
    ir_p.add_argument("--output", "-o", default=None,
                      help="Файл для записи IR (по умолчанию stdout)")
    ir_p.add_argument("--format", "-f", choices=["text", "dot", "json"],
                      default="text", help="Формат вывода: text (по умолчанию), dot, json")
    ir_p.add_argument("--stats", action="store_true",
                      help="Показать статистику IR (количество блоков, инструкций и т.д.)")
    ir_p.add_argument("--function", default=None,
                      help="Вывести IR только для указанной функции")

    args = ap.parse_args()
    if args.command == "lex":
        cmd_lex(args)
    elif args.command == "parse":
        cmd_parse(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "ir":
        cmd_ir(args)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
