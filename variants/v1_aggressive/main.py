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
