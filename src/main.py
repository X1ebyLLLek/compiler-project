"""
Единая точка входа в компилятор MiniCompiler (VIS-4).
Поддерживает команды:
  python -m src.main lex   <file>  — вывод потока токенов
  python -m src.main parse <file>  — парсинг и вывод AST

Опции для parse:
  --ast-format text|dot|json  (по умолчанию text)
  --output <file>             (по умолчанию stdout)
  --verbose                   (подробный вывод)
"""

import argparse
import sys

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast_printer import ASTPrettyPrinter, ASTDotPrinter, ASTJsonPrinter


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

    args = ap.parse_args()
    if args.command == "lex":
        cmd_lex(args)
    elif args.command == "parse":
        cmd_parse(args)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
