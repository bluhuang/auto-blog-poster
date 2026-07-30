import unittest
from pathlib import Path


class RecentUpdateSortingTests(unittest.TestCase):
    def test_home_and_library_share_deterministic_sorter(self) -> None:
        home = Path("layouts/home.html").read_text(encoding="utf-8")
        library = Path("layouts/partials/library-page.html").read_text(encoding="utf-8")
        sorter = Path("layouts/partials/sort-pages-by-update.html").read_text(encoding="utf-8")

        self.assertIn('partial "sort-pages-by-update"', home)
        self.assertIn('partial "sort-pages-by-update"', library)
        self.assertIn('.Lastmod.Unix', sorter)
        self.assertIn('.Path', sorter)
        self.assertIn('sort $sortable "sortKey" "desc"', sorter)

    def test_same_timestamp_uses_descending_source_path(self) -> None:
        timestamp = 1785422922
        paths = [
            "AI/6 Model Training/5 YUV 色彩空间 Loss.md",
            "AI/6 Model Training/7 拉普拉斯金字塔  Laplacian Pyramid.md",
            "AI/6 Model Training/6 UV 时域一致性 Loss、时域稳定性 Loss.md",
        ]
        ordered = sorted(paths, key=lambda path: f"{timestamp:020d}|{path}", reverse=True)
        self.assertEqual(
            ordered,
            [
                "AI/6 Model Training/7 拉普拉斯金字塔  Laplacian Pyramid.md",
                "AI/6 Model Training/6 UV 时域一致性 Loss、时域稳定性 Loss.md",
                "AI/6 Model Training/5 YUV 色彩空间 Loss.md",
            ],
        )


if __name__ == "__main__":
    unittest.main()
