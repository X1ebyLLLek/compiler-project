import pytest
from pathlib import Path
from src.lexer.scanner import Scanner

BASE_DIR = Path(__file__).parent
VALID_DIR = BASE_DIR / "lexer" / "valid"
INVALID_DIR = BASE_DIR / "lexer" / "invalid"

def get_tokens_as_strings(source: str) -> list[str]:
    scanner = Scanner(source)
    return [str(token) for token in scanner._tokens]

# Collect all .src files for parameterized testing
src_files = list(VALID_DIR.glob("*.src")) + list(INVALID_DIR.glob("*.src"))

@pytest.mark.parametrize("src_path", src_files, ids=lambda p: p.name)
def test_lexer_against_expected_output(src_path: Path):
    """
    TEST-4: Automated Test Runner must:
    - Compare actual output to expected token files
    - Report success/failure for each test case
    - Provide verbose output on failure showing differences
    """
    # 1. Read source
    source = src_path.read_text(encoding="utf-8")
    
    # 2. Extract actual tokens
    actual_tokens = get_tokens_as_strings(source)
    
    # 3. Read expected tokens from .txt
    txt_path = src_path.with_suffix(".txt")
    if not txt_path.exists():
        pytest.fail(f"Missing expected output file: {txt_path.name}")
        
    expected_content = txt_path.read_text(encoding="utf-8").strip()
    # Handle potentially different line endings between systems
    expected_lines = [line.strip() for line in expected_content.splitlines() if line.strip()]
    
    # 4. Compare lengths
    assert len(actual_tokens) == len(expected_lines), f"Token count mismatch in {src_path.name}!\nExpected:\n{expected_lines}\n\nActual:\n{actual_tokens}"
    
    # 5. Compare line by line (this will show differences automatically via pytest)
    for i, (actual, expected) in enumerate(zip(actual_tokens, expected_lines)):
        assert actual == expected, f"Mismatch at token index {i} in {src_path.name}"
