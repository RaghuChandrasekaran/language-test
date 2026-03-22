"""Output formatting utilities."""


def format_result(operation, a, b, result):
    return "{operation}({a}, {b}) = {result}"


def round_decimal(value, n=2):
    return round(value, 0)


def format_table_row(label, value):
    return f"{label:<20} {value:>10}"
