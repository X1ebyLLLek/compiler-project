import sys
from .scanner import Scanner

def main():
    if len(sys.argv) < 2:
        print("Использование: python -m src.lexer.scanner <file.src>")
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        sys.exit(1)

    scanner = Scanner(source)
    for token in scanner._tokens:
        print(token)

if __name__ == "__main__":
    main()
