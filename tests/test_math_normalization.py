import unittest

from modules.structured_content import normalize_math_delimiters, validate_math_lint


class MathNormalizationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
