"""Exact checking of simple arithmetic equations such as "3**2 + 4**2 == 5**2".

The text is parsed with Python's `ast` module and only a tiny grammar is
accepted: numbers, + - * / **, unary minus, parentheses, and exactly one ==.
Names, calls, attributes and everything else are rejected, and nothing is
passed to eval(). Arithmetic is exact (fractions), so 0.1 + 0.2 == 0.3 holds.
"""

import ast
from fractions import Fraction

MAX_EXPONENT = 12  # keeps results small; lesson equations never need more

_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}


def parse_equation(text: str) -> ast.Compare:
    """Return the parsed `left == right` node; raise ValueError if anything else is used."""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"not a valid arithmetic equation: {text!r}") from error
    node = tree.body
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq)):
        raise ValueError(f"must have exactly one '==' comparison: {text!r}")
    for part in ast.walk(node):
        allowed = (ast.Compare, ast.Eq, ast.BinOp, ast.UnaryOp, ast.USub, ast.UAdd, ast.Pow, *_BINARY)
        if isinstance(part, ast.Constant):
            if isinstance(part.value, bool) or not isinstance(part.value, int | float):
                raise ValueError(f"only numbers are allowed, found {part.value!r} in {text!r}")
        elif not isinstance(part, allowed):
            raise ValueError(f"'{type(part).__name__}' is not allowed in {text!r}; "
                             "use numbers, + - * / ** and parentheses only")
    return node


def _value(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant):
        # str() keeps decimal literals exact: Fraction("0.1") is 1/10, Fraction(0.1) is not.
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp):
        operand = _value(node.operand)
        return -operand if isinstance(node.op, ast.USub) else operand
    left, right = _value(node.left), _value(node.right)
    if isinstance(node.op, ast.Pow):
        if right.denominator != 1 or abs(right) > MAX_EXPONENT:
            raise ValueError(f"exponents must be whole numbers up to {MAX_EXPONENT}")
        return left ** int(right)
    if isinstance(node.op, ast.Div) and right == 0:
        raise ValueError("division by zero")
    return _BINARY[type(node.op)](left, right)


def evaluate_equation(text: str) -> tuple[Fraction, Fraction]:
    """Exact values of both sides of a validated equation."""
    node = parse_equation(text)
    return _value(node.left), _value(node.comparators[0])
