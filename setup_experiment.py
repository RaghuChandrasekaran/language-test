#!/usr/bin/env python3
"""
Setup script for the language-tone experiment.

Generates a buggy calculator project in four variant directories,
each with a different TASK.md prompt tone. The bugs are identical
across variants — only the instructions differ.
"""

import os
import shutil
import json

VARIANTS = {
    "v1_aggressive": "aggressive",
    "v2_caps_only": "caps_only",
    "v3_no_must": "no_must",
    "v4_soft": "soft",
}

# ---------------------------------------------------------------------------
# Source file templates
# ---------------------------------------------------------------------------

CALC_PY = '''\
"""Core calculator functions."""


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a * b


def power(a, b):
    return a ** a
'''

FORMATTER_PY = '''\
"""Output formatting utilities."""


def format_result(operation, a, b, result):
    return "{operation}({a}, {b}) = {result}"


def round_decimal(value, n=2):
    return round(value, 0)


def format_table_row(label, value):
    return f"{label:<20} {value:>10}"
'''

MAIN_PY = '''\
"""CLI entry point for the calculator."""

import sys
from calc import add, subtract, multiply, divide, power
from formatter import format_result


OPERATIONS = {
    "add": add,
    "sub": subtract,
    "mul": multiply,
    "div": divide,
    "pow": power,
}


def parse_input(text):
    parts = text.strip().split(",")
    if len(parts) != 3:
        raise ValueError("Expected: <operation> <num1> <num2>")
    op = parts[0].strip()
    a = float(parts[1].strip())
    b = float(parts[2].strip())
    return op, a, b


def main():
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = input("Enter operation and two numbers (e.g. add 2 3): ")

    op, a, b = parse_input(text)

    if op not in OPERATIONS:
        print(f"Unknown operation: {op}")
        print(f"Available: {', '.join(OPERATIONS.keys())}")
        sys.exit(1)

    result = OPERATIONS[op](a, b)
    print(format_result(op, a, b, result))


if __name__ == "__main__":
    main()
'''

TEST_CALC_PY = '''\
"""Test suite for the calculator project."""

import pytest
from calc import add, subtract, multiply, divide, power
from formatter import format_result, round_decimal
from main import parse_input


class TestCalcBasic:
    def test_add(self):
        assert add(2, 3) == 5

    def test_subtract(self):
        assert subtract(10, 4) == 6

    def test_multiply(self):
        assert multiply(3, 7) == 21

    def test_divide(self):
        assert divide(10, 2) == 5.0

    def test_divide_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            divide(1, 0)

    def test_power(self):
        assert power(2, 3) == 8


class TestFormatter:
    def test_format_result(self):
        result = format_result("add", 2, 3, 5)
        assert result == "add(2, 3) = 5"

    def test_round_decimal(self):
        assert round_decimal(3.14159, 2) == 3.14


class TestMain:
    def test_parse_input(self):
        op, a, b = parse_input("add 2 3")
        assert op == "add"
        assert a == 2.0
        assert b == 3.0

    def test_parse_input_extra_spaces(self):
        op, a, b = parse_input("  mul   4   5  ")
        assert op == "mul"
        assert a == 4.0
        assert b == 5.0
'''

CONFTEST_PY = '''\
"""Pytest plugin that logs every test session to test_runs.jsonl."""

import json
import time
from pathlib import Path

_session_data = {}


def pytest_sessionstart(session):
    _session_data["start"] = time.time()
    _session_data["passed"] = []
    _session_data["failed"] = []


def pytest_runtest_logreport(report):
    if report.when == "call":
        if report.passed:
            _session_data["passed"].append(report.nodeid)
        elif report.failed:
            _session_data["failed"].append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    log_path = Path(__file__).parent / "test_runs.jsonl"
    existing = 0
    if log_path.exists():
        existing = sum(1 for _ in open(log_path))

    entry = {
        "run": existing + 1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(time.time() - _session_data["start"], 2),
        "pass_count": len(_session_data["passed"]),
        "fail_count": len(_session_data["failed"]),
        "passed": _session_data["passed"],
        "failed": _session_data["failed"],
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\\n")
'''

# ---------------------------------------------------------------------------
# TASK.md prompt variants
# ---------------------------------------------------------------------------

TASK_HEADER = """\
# Task

Fix the failing tests in this project. The test file is `test_calc.py`.

Rules:
- You may ONLY modify `calc.py`, `formatter.py`, and `main.py`.
- Do NOT modify `test_calc.py` or `conftest.py`.

"""

VARIANT_STEPS = {
    "aggressive": """\
You MUST follow this process for EVERY fix:

1. run the tests: `python -m pytest test_calc.py -v`
2. read the full output so you can actually diagnose the failures.
3. fix EXACTLY ONE bug, then repeat from step 1.

NEVER fix multiple bugs at once. ALWAYS run tests between each fix.
CRITICAL: Do NOT stop until ALL tests pass.
""",

    "caps_only": """\
You MUST follow this process for EVERY fix:

1. Run the tests: `python -m pytest test_calc.py -v`
2. Read the full output so you can actually diagnose the failures.
3. Fix EXACTLY ONE bug, then repeat from step 1.

NEVER fix multiple bugs at once. ALWAYS run tests between each fix.
CRITICAL: Do NOT stop until ALL tests pass.
""",

    "no_must": """\
Follow this process for every fix:

1. Run the tests: `python -m pytest test_calc.py -v`
2. Read the full output to diagnose the failures.
3. Fix one bug at a time, then repeat from step 1.

Don't fix multiple bugs at once. Run tests between each fix.
Do not stop until all tests pass.
""",

    "soft": """\
Follow this process for every fix:

1. Run the tests: `python -m pytest test_calc.py -v`
2. Read the output and figure out what went wrong.
3. Fix one bug at a time, then repeat from step 1.

Try to fix one bug per cycle. Run tests between fixes if possible.
Keep going until the tests pass.
""",
}


def setup():
    base = os.path.dirname(os.path.abspath(__file__))
    variants_dir = os.path.join(base, "variants")

    if os.path.exists(variants_dir):
        shutil.rmtree(variants_dir)

    source_files = {
        "calc.py": CALC_PY,
        "formatter.py": FORMATTER_PY,
        "main.py": MAIN_PY,
        "test_calc.py": TEST_CALC_PY,
        "conftest.py": CONFTEST_PY,
    }

    for variant_name, tone in VARIANTS.items():
        vdir = os.path.join(variants_dir, variant_name)
        os.makedirs(vdir)

        for filename, content in source_files.items():
            with open(os.path.join(vdir, filename), "w") as f:
                f.write(content)

        task_md = TASK_HEADER + VARIANT_STEPS[tone]
        with open(os.path.join(vdir, "TASK.md"), "w") as f:
            f.write(task_md)

        print(f"  Created {variant_name}/")

    print(f"\nSetup complete. {len(VARIANTS)} variants ready in variants/")
    print("\nExpected test results (before fixes):")
    print("  PASS:  test_add, test_subtract, test_multiply, test_divide_by_zero")
    print("  FAIL:  test_divide, test_power, test_format_result, test_round_decimal, test_parse_input, test_parse_input_extra_spaces")


if __name__ == "__main__":
    setup()
