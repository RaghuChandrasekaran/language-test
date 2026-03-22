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
