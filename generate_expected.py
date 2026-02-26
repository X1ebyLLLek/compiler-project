import sys
from pathlib import Path
from src.lexer.scanner import Scanner

def generate():
    tests_dir = Path("tests/lexer")
    for src_path in tests_dir.rglob("*.src"):
        source = src_path.read_text(encoding="utf-8")
        scanner = Scanner(source)
        # Capture tokens as strings
        tokens = [str(t) for t in scanner._tokens]
        # Write cleanly to txt without BOM
        out_path = src_path.with_suffix(".txt")
        out_path.write_text("\n".join(tokens) + "\n", encoding="utf-8")

if __name__ == "__main__":
    generate()
