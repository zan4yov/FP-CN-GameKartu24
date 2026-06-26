"""
game_logic.py — Card generation dan validasi expression "= 24".

DUA fungsi utama:
1. generate_cards() — random 4 card values, dijamin punya solusi.
2. validate_expression(expr, cards) — parse + evaluate user expression dengan AMAN
   pakai ast.parse + walk manual (bukan eval, biar anti-injection).
"""

from __future__ import annotations

import ast
import operator
import random
from dataclasses import dataclass
from itertools import permutations, product
from typing import Optional

from config import (
    CARD_MIN,
    CARD_MAX,
    CARDS_PER_ROUND,
    TARGET_VALUE,
    FLOAT_TOLERANCE,
)


_BINOPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
}
_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def to_math_value(card_value: int) -> int:
    """
    Konversi card value ke nilai matematis untuk perhitungan.
    A (1) = 1
    2-10  = nilai sendiri
    J (11), Q (12), K (13) = 10
    """
    if card_value >= 11:
        return 10
    return card_value


def has_solution(cards: list[int]) -> bool:
    """Brute-force cek apakah 4 cards bisa = 24 (pakai math values)."""
    math_cards = [to_math_value(c) for c in cards]
    ops = ["+", "-", "*", "/"]
    for a, b, c, d in permutations(math_cards, 4):
        for o1, o2, o3 in product(ops, repeat=3):
            templates = [
                f"(({a}{o1}{b}){o2}{c}){o3}{d}",
                f"({a}{o1}({b}{o2}{c})){o3}{d}",
                f"({a}{o1}{b}){o2}({c}{o3}{d})",
                f"{a}{o1}(({b}{o2}{c}){o3}{d})",
                f"{a}{o1}({b}{o2}({c}{o3}{d}))",
            ]
            for expr in templates:
                try:
                    if abs(eval(expr) - TARGET_VALUE) < FLOAT_TOLERANCE:  # noqa: S307
                        return True
                except ZeroDivisionError:
                    continue
    return False


def find_solution(cards: list[int]) -> Optional[str]:
    """Cari satu solusi (pakai math values). None kalau ga ada."""
    math_cards = [to_math_value(c) for c in cards]
    ops = ["+", "-", "*", "/"]
    for a, b, c, d in permutations(math_cards, 4):
        for o1, o2, o3 in product(ops, repeat=3):
            templates = [
                f"(({a}{o1}{b}){o2}{c}){o3}{d}",
                f"({a}{o1}({b}{o2}{c})){o3}{d}",
                f"({a}{o1}{b}){o2}({c}{o3}{d})",
                f"{a}{o1}(({b}{o2}{c}){o3}{d})",
                f"{a}{o1}({b}{o2}({c}{o3}{d}))",
            ]
            for expr in templates:
                try:
                    if abs(eval(expr) - TARGET_VALUE) < FLOAT_TOLERANCE:  # noqa: S307
                        return expr
                except ZeroDivisionError:
                    continue
    return None


def generate_cards(max_attempts: int = 200) -> list[int]:
    """Generate 4 cards yang dijamin solvable."""
    for _ in range(max_attempts):
        cards = [random.randint(CARD_MIN, CARD_MAX) for _ in range(CARDS_PER_ROUND)]
        if has_solution(cards):
            return cards
    return [3, 3, 8, 8]


@dataclass
class ValidationResult:
    valid: bool
    value: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {"valid": self.valid, "value": self.value, "error": self.error}


def _extract_numbers(node: ast.AST, acc: list[float]) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            acc.append(float(node.value))
        else:
            raise ValueError(f"Konstanta tidak valid: {node.value!r}")
    elif isinstance(node, ast.BinOp):
        _extract_numbers(node.left, acc)
        _extract_numbers(node.right, acc)
    elif isinstance(node, ast.UnaryOp):
        _extract_numbers(node.operand, acc)
    else:
        raise ValueError(f"Node tidak diizinkan: {type(node).__name__}")


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise ValueError(f"Konstanta tidak valid: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op_fn = _BINOPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Operator tidak diizinkan: {type(node.op).__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        try:
            return op_fn(left, right)
        except ZeroDivisionError:
            raise ValueError("Pembagian dengan nol")
    if isinstance(node, ast.UnaryOp):
        op_fn = _UNARYOPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unary tidak diizinkan: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.operand))
    raise ValueError(f"Node tidak diizinkan: {type(node).__name__}")


def validate_expression(expr: str, cards: list[int]) -> ValidationResult:
    if not expr or not isinstance(expr, str):
        return ValidationResult(False, error="Expression kosong")
    if len(expr) > 200:
        return ValidationResult(False, error="Expression terlalu panjang")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return ValidationResult(False, error=f"Syntax error: {e.msg}")
    if not isinstance(tree, ast.Expression):
        return ValidationResult(False, error="Bukan expression yang valid")
    try:
        numbers: list[float] = []
        _extract_numbers(tree.body, numbers)
    except ValueError as e:
        return ValidationResult(False, error=str(e))
    if not all(n.is_integer() for n in numbers):
        return ValidationResult(False, error="Hanya boleh pakai bilangan bulat")
    used_ints = sorted(int(n) for n in numbers)
    # Bandingkan dengan MATH VALUES (J/Q/K = 10, A = 1), bukan card value mentah
    expected = sorted(to_math_value(c) for c in cards)
    if used_ints != expected:
        return ValidationResult(
            False,
            error=(
                f"Harus pakai persis 4 kartu = {expected} "
                f"(ingat: J/Q/K = 10, A = 1). "
                f"Kamu pakai {used_ints}"
            ),
        )
    try:
        value = _safe_eval(tree.body)
    except ValueError as e:
        return ValidationResult(False, error=str(e))
    if abs(value - TARGET_VALUE) > FLOAT_TOLERANCE:
        return ValidationResult(
            False,
            value=value,
            error=f"Hasil = {value:g}, bukan {TARGET_VALUE}",
        )
    return ValidationResult(True, value=value)
