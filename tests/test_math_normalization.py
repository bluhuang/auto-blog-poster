import unittest

from modules.structured_content import (
    StructuredContentProtector,
    normalize_math_delimiters,
    validate_math_delimiters,
    validate_math_lint,
)


class MathNormalizationTests(unittest.TestCase):
    def test_aligned_row_spacing_is_not_a_display_delimiter(self) -> None:
        for opening, closing in (("$$", "$$"), (r"\[", r"\]")):
            with self.subTest(opening=opening):
                source = opening + r"""
\begin{aligned}
\mathbb E[Z\mid I]&=\frac{I}{K}\\[4pt]
\mathbb E[KZ\mid I]&=I
\end{aligned}
""" + closing
                validate_math_delimiters(source)
                normalized = normalize_math_delimiters(source)
                validate_math_delimiters(normalized)
                validate_math_lint(normalized)
                self.assertIn(r"\\[4pt]", normalized)
                protector = StructuredContentProtector(source)
                self.assertEqual(protector.restore(protector.protect()), source)

    def test_escaped_brackets_do_not_absorb_following_math(self) -> None:
        source = r"Literal \\[ and \\( are not math delimiters." + "\n\n$$x=1$$\n"
        validate_math_delimiters(source)
        normalized = normalize_math_delimiters(source)
        self.assertIn(r"Literal \\[ and \\(", normalized)
        self.assertIn("$$\nx=1\n$$", normalized)
        protector = StructuredContentProtector(source)
        protector.protect()
        self.assertEqual([item.original for item in protector.items], ["$$x=1$$"])

    def test_real_unclosed_display_math_is_still_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, 'Unbalanced math delimiters'):
            validate_math_delimiters(r"\[x=1")

    def test_repairs_single_matrix_row_separators_before_lint(self) -> None:
        source = r"""# $$
\begin{bmatrix}
R'\
G'\
B'
\end{bmatrix}
\begin{bmatrix}
m_{11}&m_{12}&m_{13}\
m_{21}&m_{22}&m_{23}\
m_{31}&m_{32}&m_{33}
\end{bmatrix}
\begin{bmatrix}
R\
G\
B
\end{bmatrix}
$$
"""

        normalized = normalize_math_delimiters(source)
        validate_math_lint(source)

        self.assertNotIn("# $$", normalized)
        self.assertIn(r"R'\\ G'\\ B'", normalized)
        self.assertIn(r"m_{11}&m_{12}&m_{13}\\", normalized)
        self.assertIn(r"R\\ G\\ B", normalized)

    def test_preserves_existing_double_row_separator(self) -> None:
        source = r"""$$
\begin{bmatrix}
R\\
G\\
B
\end{bmatrix}
$$
"""

        normalized = normalize_math_delimiters(source)
        validate_math_lint(source)

        self.assertIn(r"R\\ G\\ B", normalized)
        self.assertNotIn("R" + "\\" * 3, normalized)

    def test_repairs_numeric_row_start_in_cases_environment(self) -> None:
        source = r"""$$
U_{l+1}(i,j)=\begin{cases}G_{l+1}(i/2,j/2),&i,j\text{ 均为偶数}\0,&\text{其他位置}\end{cases}
$$
"""

        normalized = normalize_math_delimiters(source)
        validate_math_lint(source)

        self.assertIn(r"\text{ 均为偶数}\\0,&\text{其他位置}", normalized)


if __name__ == "__main__":
    unittest.main()
