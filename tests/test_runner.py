import sys
import os
import pytest
from src.lexer.scanner import Scanner

def get_tokens_as_strings(source: str) -> list[str]:
    scanner = Scanner(source)
    return [str(token) for token in scanner._tokens]

def test_keywords():
    source = "if else while for int float bool return true false void struct fn"
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 14  # 13 + EOF
    assert "KW_IF" in tokens[0]
    assert "KW_FN" in tokens[12]
    assert "END_OF_FILE" in tokens[13]

def test_identifiers():
    source = "myVar My_Var2 _hidden"
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 4
    assert 'IDENTIFIER "myVar"' in tokens[0]
    assert 'IDENTIFIER "My_Var2"' in tokens[1]
    assert 'IDENTIFIER "_hidden"' in tokens[2]

def test_numbers():
    source = "42 3.1415"
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 3
    assert 'INT_LITERAL "42" 42' in tokens[0]
    assert 'FLOAT_LITERAL "3.1415" 3.1415' in tokens[1]

def test_strings():
    source = '"hello world"'
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 2
    assert 'STRING_LITERAL ""hello world"" hello world' in tokens[0]

def test_operators():
    source = "+ - * / % == != < <= > >= && || ! = += -= *= /="
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 20

def test_delimiters():
    source = "( ) { } [ ] ; , :"
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 10

def test_comments():
    source = "1 // this is a comment\n2 /* this is a\n block comment */ 3"
    tokens = get_tokens_as_strings(source)
    assert len(tokens) == 4
    assert 'INT_LITERAL "1"' in tokens[0]
    assert 'INT_LITERAL "2"' in tokens[1]
    assert 'INT_LITERAL "3"' in tokens[2]

def test_invalid_chars():
    source = "int a = 42; $ @"
    tokens = get_tokens_as_strings(source)
    # scanner adds ERROR tokens for invalid chars
    error_tokens = [t for t in tokens if "ERROR" in t]
    assert len(error_tokens) == 2

def test_unterminated_string():
    source = '"hello \n world"'
    tokens = get_tokens_as_strings(source)
    error_tokens = [t for t in tokens if "ERROR" in t]
    assert len(error_tokens) >= 1
