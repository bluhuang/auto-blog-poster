import unittest
from pathlib import Path


class HomeCopyTests(unittest.TestCase):
    def test_home_does_not_include_design_commentary(self):
        template = Path('layouts/home.html').read_text(encoding='utf-8')
        removed_copy = (
            '首页只展示最值得继续阅读的入口，完整时间线放在博客知识库中。',
            '不把完整目录树搬到首页，只保留四个高价值入口。',
            '流程和高级能力合并在同一套四阶段系统里，直接说明它为什么能够长期稳定运行。',
        )
        for text in removed_copy:
            with self.subTest(text=text):
                self.assertNotIn(text, template)
        for section in ('home-recent-title', 'home-topics-title', 'home-story-title'):
            self.assertIn(f'id="{section}"', template)


if __name__ == '__main__':
    unittest.main()
