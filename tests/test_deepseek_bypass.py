import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from modules.content_processor import process_single_note


class DeepseekBypassTests(unittest.TestCase):
    def test_uncached_content_is_published_without_api_or_response_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / 'note.md'
            note.write_text('# New note\n\nCurrent text.\n\n$$x^2$$\n')
            config = {
                '_without_deepseek': True,
                'output': {'content_dir': str(root / 'output')},
            }
            api = Mock(side_effect=AssertionError('API must not be called'))
            cache = {}
            with patch('modules.content_processor._compute_dates', return_value=(
                '2026-11-25T00:00:00+00:00', '2026-11-25T00:00:00+00:00',
            )):
                self.assertTrue(process_single_note(
                    str(note), 'note.md', str(root), config, api, cache,
                ))
            api.assert_not_called()
            self.assertEqual(cache, {})
            self.assertEqual(config['_deepseek_bypassed_paths'], {'note.md'})
            output = (root / 'output' / 'note.md').read_text()
            self.assertIn('Current text.', output)
            self.assertIn('x^2', output)


if __name__ == '__main__':
    unittest.main()
