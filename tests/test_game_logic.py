"""
tests/test_game_logic.py — Unit tests untuk card generation dan validator.

Run: python -m unittest tests.test_game_logic -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_logic import (
    find_solution,
    generate_cards,
    has_solution,
    to_math_value,
    validate_expression,
)


class TestMathValueMapping(unittest.TestCase):
    """A=1, 2-10=face value, J/Q/K=10."""

    def test_ace_is_one(self):
        self.assertEqual(to_math_value(1), 1)

    def test_face_value_2_to_10(self):
        for v in range(2, 11):
            self.assertEqual(to_math_value(v), v)

    def test_jack_queen_king_are_ten(self):
        self.assertEqual(to_math_value(11), 10)   # J
        self.assertEqual(to_math_value(12), 10)   # Q
        self.assertEqual(to_math_value(13), 10)   # K

    def test_validator_accepts_face_as_ten(self):
        # Kartu [J, Q, K, 4] = [11, 12, 13, 4], math values = [10, 10, 10, 4]
        # User submit jawaban pakai angka 10 ber-3
        # 10*10 - 10*4 - ... hmm let's find: actually [10,10,10,4] mungkin ga solvable
        # Try [J, 4, 6, A] = [11,4,6,1], math = [10,4,6,1]
        # 4 * 6 = 24, sisanya 10 dan 1 — ga muat
        # Try [J, 5, 5, A] = math [10,5,5,1] — 5*5 + (10/1)*... = 25+... bigger; (10-5)*5*1 = 25 no
        # Try simpler — [J, 3, 8, A] = [10,3,8,1], math same — 10-8 = 2, 2*3 = 6, +1=7, no
        # Try [J, 2, 4, 3] = math [10,2,4,3] — 10 * 2 * (4-3) = 20, no
        # ((10-4)*2)*3 = 12*3 = 36, no
        # 3*(10-4+2) = 24 ✓!
        result = validate_expression("3*(10-4+2)", [11, 2, 4, 3])
        self.assertTrue(result.valid, f"Expected valid, got error: {result.error}")
        self.assertAlmostEqual(result.value, 24, places=4)

    def test_validator_rejects_jack_as_eleven(self):
        # User mau pakai J sebagai 11 — harus DITOLAK
        # [J, 11, 1, 1] tidak mungkin (max 13 dan satu kartu = satu nilai)
        # Tapi yang sering: kartu [J, ...] dan user nulis 11.
        # Kartu [J, 4, 6, 3]: math = [10,4,6,3]. User submit "11+4+6+3" = 24
        result = validate_expression("11+4+6+3", [11, 4, 6, 3])
        self.assertFalse(result.valid)
        # Error message should mention math values
        self.assertIn("10", result.error)


class TestHasSolution(unittest.TestCase):

    def test_classic_3388(self):
        # 8 / (3 - 8/3) = 24
        self.assertTrue(has_solution([3, 3, 8, 8]))

    def test_simple_1234(self):
        # 1*2*3*4 = 24
        self.assertTrue(has_solution([1, 2, 3, 4]))

    def test_all_aces_impossible(self):
        # 1+1+1+1 = 4, can't reach 24
        self.assertFalse(has_solution([1, 1, 1, 1]))

    def test_kings_impossible(self):
        # 13+13+13+13 = 52, but no way to get 24
        self.assertFalse(has_solution([13, 13, 13, 13]))

    def test_4444_solution(self):
        # 4+4+4*4 doesn't work, but 4*4 + 4 + 4 = 24
        self.assertTrue(has_solution([4, 4, 4, 4]))


class TestFindSolution(unittest.TestCase):

    def test_finds_for_solvable(self):
        sol = find_solution([1, 2, 3, 4])
        self.assertIsNotNone(sol)
        self.assertAlmostEqual(eval(sol), 24, places=4)

    def test_none_for_unsolvable(self):
        self.assertIsNone(find_solution([1, 1, 1, 1]))


class TestGenerateCards(unittest.TestCase):

    def test_returns_4_cards(self):
        cards = generate_cards()
        self.assertEqual(len(cards), 4)

    def test_cards_in_range(self):
        for _ in range(10):
            cards = generate_cards()
            for c in cards:
                self.assertGreaterEqual(c, 1)
                self.assertLessEqual(c, 13)

    def test_always_solvable(self):
        for _ in range(20):
            cards = generate_cards()
            self.assertTrue(has_solution(cards),
                            f"Generated unsolvable cards: {cards}")


class TestValidateExpression(unittest.TestCase):

    def test_valid_simple(self):
        result = validate_expression("1+2+3+4*5", [1, 2, 3, 4, 5][:4])
        # Should fail because we have 5 numbers but only 4 cards
        self.assertFalse(result.valid)

    def test_valid_correct(self):
        result = validate_expression("(3+5)*3*1", [1, 3, 3, 5])
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.value, 24, places=4)

    def test_invalid_wrong_result(self):
        result = validate_expression("1+2+3+4", [1, 2, 3, 4])
        self.assertFalse(result.valid)
        self.assertIn("bukan 24", result.error.lower())

    def test_invalid_wrong_cards(self):
        result = validate_expression("1*2*3*4", [5, 6, 7, 8])
        self.assertFalse(result.valid)
        self.assertIn("kartu", result.error.lower())

    def test_invalid_extra_number(self):
        result = validate_expression("1*2*3*4*5", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_invalid_missing_number(self):
        result = validate_expression("1+2+3", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_division_by_zero(self):
        result = validate_expression("1/(2-2)+3+4", [1, 2, 2, 3])
        # Note: 2-2=0, division by zero. Also wrong cards but error catches earlier.
        self.assertFalse(result.valid)

    def test_classic_3388(self):
        result = validate_expression("8/(3-8/3)", [3, 3, 8, 8])
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.value, 24, places=4)

    def test_with_parentheses(self):
        result = validate_expression("(1+2)*(3+5)", [1, 2, 3, 5])
        self.assertTrue(result.valid)

    def test_negative_intermediate(self):
        # Cards 1-10 saja (no face cards) supaya math value sama dengan raw
        # 10*3 - 5 - 1 = 24
        result = validate_expression("10*3 - 5 - 1", [1, 3, 5, 10])
        self.assertTrue(result.valid, f"Got error: {result.error}")

    def test_unary_minus(self):
        # -3 * -4 * 2 * 1 = 24, but unary requires same card set
        result = validate_expression("-1*-2*-3*-4", [1, 2, 3, 4])
        self.assertTrue(result.valid)

    def test_empty(self):
        result = validate_expression("", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_none(self):
        result = validate_expression(None, [1, 2, 3, 4])
        self.assertFalse(result.valid)


class TestAntiInjection(unittest.TestCase):
    """Anti-injection — validator NEVER call eval on raw input."""

    def test_blocks_function_call(self):
        result = validate_expression("__import__('os').system('ls')", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_blocks_attribute_access(self):
        result = validate_expression("(1).__class__", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_blocks_string(self):
        result = validate_expression("'24'", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_blocks_variable_name(self):
        result = validate_expression("a+b+c+d", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_blocks_list(self):
        result = validate_expression("[1,2,3,4]", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_too_long(self):
        result = validate_expression("1+" * 200 + "2", [1, 2, 3, 4])
        self.assertFalse(result.valid)

    def test_syntax_error(self):
        result = validate_expression("1++2", [1, 2, 3, 4])
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
