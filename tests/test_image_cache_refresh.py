import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.content_processor import process_single_note


class ImageCacheRefreshTests(unittest.TestCase):
    def test_existing_image_is_refreshed_when_source_bytes_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            note = source / 'Topic' / 'note.md'
            image = note.parent / 'attachments' / 'plot.png'
            image.parent.mkdir(parents=True)
            note.write_text('# Note\n\n![Plot](attachments/plot.png)\n')
            image.write_bytes(b'old figure')
            static = root / 'static'
            output = root / 'content'
            config = {
                'output': {'content_dir': str(output)},
                'processing': {'image_handling': {
                    'enabled': True, 'target_static_dir': str(static),
                }},
            }

            def process():
                return process_single_note(
                    str(note), 'Topic/note.md', str(source), config,
                    lambda content, _config: content,
                )

            with patch('modules.content_processor._compute_dates', return_value=(
                '2026-11-08T00:00:00+00:00', '2026-11-08T00:00:00+00:00',
            )):
                self.assertTrue(process())
                copied = next(static.rglob('plot.png'))
                self.assertEqual(copied.read_bytes(), b'old figure')
                # Same filename and size: existence and size are insufficient.
                image.write_bytes(b'new figure')
                self.assertTrue(process())
                self.assertEqual(copied.read_bytes(), b'new figure')
                modified = copied.stat().st_mtime_ns
                self.assertTrue(process())
                self.assertEqual(copied.stat().st_mtime_ns, modified)
                self.assertIn('![](/images/Topic/plot.png)',
                              (output / 'Topic' / 'note.md').read_text())


if __name__ == '__main__':
    unittest.main()
