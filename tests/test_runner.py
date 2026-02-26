import pytest
import os
from pathlib import Path
from src.lexer.scanner import Scanner

# Helpers
def get_tokens_as_strings(source: str) -> list[str]:
    scanner = Scanner(source)
    return [str(token) for token in scanner._tokens]

def get_tokens_from_file(filepath: str) -> list[str]:
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    return get_tokens_as_strings(source)

# ----------------- INLINE TESTS -----------------

def test_keywords():
    source = "if else while for int float bool return true false void struct fn"
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 14  # 13 + EOF
    assert "KW_IF" in tokens[0]
    assert "KW_FN" in tokens[12]
    assert "END_OF_FILE" in tokens[13]

def test_strings():
    source = '"hello world"'
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 2
    assert 'STRING_LITERAL ""hello world"" hello world' in tokens[0]

# ----------------- FILE-BASED TESTS -----------------

BASE_DIR = Path(__file__).parent
VALID_DIR = BASE_DIR / "lexer" / "valid"
INVALID_DIR = BASE_DIR / "lexer" / "invalid"

def test_file_identifiers():
    filepath = VALID_DIR / "test_identifiers.src"
    tokens = get_tokens_from_file(str(filepath))
    assert 'IDENTIFIER "myVar"' in tokens[1]
    assert 'IDENTIFIER "_hidden"' in tokens[6]
    
def test_file_numbers():
    filepath = VALID_DIR / "test_numbers.src"
    tokens = get_tokens_from_file(str(filepath))
    # 0, \n, 42, \n, 2147483647, \n, 3.1415, \n, 0.0, EOF
    assert 'INT_LITERAL "0" 0' in tokens[0]
    assert 'INT_LITERAL "42" 42' in tokens[1]
    assert 'INT_LITERAL "2147483647" 2147483647' in tokens[2]
    assert 'FLOAT_LITERAL "3.1415" 3.1415' in tokens[3]

def test_file_operators():
    filepath = VALID_DIR / "test_operators.src"
    tokens = get_tokens_from_file(str(filepath))
    assert 'PLUS "+"' in tokens[1]
    assert 'EQUAL_EQUAL "=="' in tokens[12]

def test_file_comments():
    filepath = VALID_DIR / "test_comments.src"
    tokens = get_tokens_from_file(str(filepath))
    # Comments shouldn't produce tokens
    assert 'KW_INT "int"' in tokens[0]
    assert 'IDENTIFIER "x"' in tokens[1]
    
def test_file_invalid_char():
    filepath = INVALID_DIR / "test_invalid_char.src"
    tokens = get_tokens_from_file(str(filepath))
    error_tokens = [t for t in tokens if "ERROR" in t]
    assert len(error_tokens) >= 2 # $ and @ should be flagged
    assert "Недопустимый символ '$'" in error_tokens[0]

def test_file_unterminated_string():
    filepath = INVALID_DIR / "test_unterminated_string.src"
    tokens = get_tokens_from_file(str(filepath))
    error_tokens = [t for t in tokens if "ERROR" in t]
    assert len(error_tokens) >= 1
    assert "Незавершенная строка" in error_tokens[0]

def test_file_unterminated_comment():
    filepath = INVALID_DIR / "test_unterminated_comment.src"
    tokens = get_tokens_from_file(str(filepath))
    error_tokens = [t for t in tokens if "ERROR" in t]
    assert len(error_tokens) == 1
    assert "Незавершенный многострочный комментарий" in error_tokens[0]

def test_file_malformed_number():
    filepath = INVALID_DIR / "test_malformed_number.src"
    tokens = get_tokens_from_file(str(filepath))
    # The scanner should pick up 3.14 as a float, then .15 as a dot then 15, or flag an error
    # With the ad-hoc scanner, `3.14.15` will be scanned as FLOAT `3.14`, then `.`, then `15`
    # Let's just ensure it scans to the end without crashing
    assert "END_OF_FILE" in tokens[-1]
