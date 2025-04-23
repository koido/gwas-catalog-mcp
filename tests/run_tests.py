#!/usr/bin/env python3
from typing import Dict, Any, List, Optional, Tuple
import json
import os
import sys
import shutil
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.input.input_data import success_cases, error_cases, TestCase
import server

# Constants
OUTPUT_DIR = Path(__file__).parent / "output"
SUCCESS_DIR = OUTPUT_DIR / "success"
ERROR_DIR = OUTPUT_DIR / "error"

def setup_test_directories() -> None:
    """
    Set up test output directories, cleaning any existing output.
    """
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    SUCCESS_DIR.mkdir(parents=True, exist_ok=True)
    ERROR_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["TEST_OUTPUT_SUCCESS_DIR"] = str(SUCCESS_DIR)

def write_test_result(
    func_name: str,
    result: Dict[str, Any],
    is_success: bool
) -> str:
    """
    Write test result to appropriate output directory.
    
    Args:
        func_name (str): Name of the tested function
        result (Dict[str, Any]): Test result to write
        is_success (bool): Whether the test was successful
    
    Returns:
        str: Path to the output file
    """
    dest_dir = SUCCESS_DIR if is_success else ERROR_DIR
    status = "SUCCESS" if is_success else "ERROR"
    filepath = dest_dir / f"{func_name}.json"
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"[{status}] Wrote output for {func_name}: {filepath}")
    return str(filepath)

def execute_test_case(test_case: TestCase) -> Tuple[Dict[str, Any], bool]:
    """
    Execute a single test case.
    
    Args:
        test_case (TestCase): Test case to execute
    
    Returns:
        Tuple[Dict[str, Any], bool]: (test result, success flag)
    """
    func = getattr(server, test_case.name, None)
    
    if func is None:
        return {
            "error": f"Function '{test_case.name}' not found in server module.",
            "function": test_case.name,
            "args": test_case.args
        }, False
    
    try:
        result = func(**test_case.args)
        # Check if result indicates an error
        is_success = not (isinstance(result, dict) and "error" in result)
        return result, is_success
    except Exception as e:
        return {
            "error": str(e),
            "function": test_case.name,
            "args": test_case.args
        }, False

def main() -> None:
    """
    Main test execution function.
    """
    setup_test_directories()
    
    for test_case in success_cases + error_cases:
        result, is_success = execute_test_case(test_case)
        write_test_result(test_case.name, result, is_success)

if __name__ == "__main__":
    main() 