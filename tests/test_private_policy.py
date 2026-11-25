import json
import os
import tempfile
import unittest
from pathlib import Path

from modules.private_policy import (
    clean_public_outputs,
    clear_rendered_output,
    is_private,
    private_dirs,
    public_paths,
    validate_public_output,
)


class PrivatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {
            'private_space': {'enabled': True, 'source_dirs': ['coding', 'Path']},
            'source': {'notes_subdir': '2 Notes'},
            'output': {'content_dir': str(self.root / 'content')},
            'processing': {'image_handling': {'target_static_dir': str(self.root / 'static')}},
            'validation': {'public_dir': str(self.root / 'public')},
        }

    def write(self, relative, text='unchanged'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_public_paths_use_directory_boundaries_and_exclude_nested_notes(self):
        for path in ('source/coding/nested/hidden.md', 'source/Path/reference.md',
                     'source/AI/public.md', 'source/coding-guide/public.md',
                     'source/Pathology/public.md'):
            self.write(path)
        self.assertEqual(public_paths(self.root / 'source', self.config), [
            'AI/public.md', 'Pathology/public.md', 'coding-guide/public.md',
        ])
        self.assertTrue(is_private('coding', self.config))
        self.assertTrue(is_private('coding\\nested\\hidden.md', self.config))
        self.assertFalse(is_private('coding-guide/public.md', self.config))
        self.assertEqual(private_dirs({'private_space': {'enabled': False}}), ())

    def test_cleanup_removes_all_private_cache_keys_but_preserves_public_pages(self):
        for path in ('content/coding/note.md', 'content/coding/_index.md',
                     'content/Path/nested/reference.md', 'static/images/coding/figure.png',
                     'static/images/Path/figure.png', 'content/AI/public.md',
                     'content/about.md', 'content/guestbook.md',
                     'static/images/AI/public.png'):
            self.write(path)
        cached = {
            'coding/note.md': 'hidden', 'Path/note.md': 'hidden',
            '2 Notes/coding/note.md': 'hidden', '2 Notes/Path/note.md': 'hidden',
            'AI/public.md': 'keep', '2 Notes/AI/public.md': 'keep',
            'coding-guide/public.md': 'keep',
        }
        for name in ('.hash_cache.json', '.deepseek_cache.json', '.file_times.json'):
            self.write(name, json.dumps(cached))
        # These legacy cache defaults are relative to the project CWD.
        original = Path.cwd()
        try:
            os.chdir(self.root)
            clean_public_outputs(self.config)
        finally:
            os.chdir(original)
        for path in ('content/coding', 'content/Path',
                     'static/images/coding', 'static/images/Path'):
            self.assertFalse((self.root / path).exists(), path)
        for path in ('content/AI/public.md', 'content/about.md', 'content/guestbook.md',
                     'static/images/AI/public.png'):
            self.assertEqual((self.root / path).read_text(), 'unchanged')
        for name in ('.hash_cache.json', '.deepseek_cache.json', '.file_times.json'):
            self.assertEqual(json.loads((self.root / name).read_text()), {
                key: value for key, value in cached.items() if value == 'keep'
            })

    def test_invalid_private_directories_fail_closed(self):
        for directories in ([], [''], ['.'], ['/coding'], ['../coding'], ['x/../../coding']):
            with self.subTest(directories=directories):
                self.config['private_space']['source_dirs'] = directories
                with self.assertRaises(ValueError):
                    private_dirs(self.config)

    def test_cleanup_rejects_symlink_escape(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.write('outside/preserve.md')
        (self.root / 'content').mkdir()
        (self.root / 'content/coding').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            clean_public_outputs(self.config)
        self.assertTrue((outside / 'preserve.md').is_file())

    def test_validation_rejects_plaintext_tree_and_cached_metadata(self):
        hidden = self.write('public/coding/note/index.html')
        with self.assertRaises(RuntimeError):
            validate_public_output(self.config)
        hidden.unlink()
        hidden.parent.rmdir()
        hidden.parent.parent.rmdir()
        cache = self.write('.file_times.json', json.dumps({'2 Notes/Path/note.md': 'date'}))
        original = Path.cwd()
        try:
            os.chdir(self.root)
            with self.assertRaises(RuntimeError):
                validate_public_output(self.config)
            cache.write_text('{}')
            validate_public_output(self.config)
        finally:
            os.chdir(original)

    def test_public_cleanup_only_removes_dedicated_rendered_directory(self):
        self.write('public/old-coding.html')
        self.write('source/preserve.md')
        original = Path.cwd()
        try:
            os.chdir(self.root)
            clear_rendered_output(self.config)
            self.assertFalse((self.root / 'public').exists())
            self.assertTrue((self.root / 'source/preserve.md').is_file())
            self.config['validation']['public_dir'] = str(self.root)
            with self.assertRaises(ValueError):
                clear_rendered_output(self.config)
        finally:
            os.chdir(original)

    def test_validation_honors_configured_cache_locations(self):
        cache = self.write('custom/hashes.json', json.dumps({'coding/note.md': 'hash'}))
        self.config['processing']['cache_file'] = str(cache)
        original = Path.cwd()
        try:
            os.chdir(self.root)
            with self.assertRaises(RuntimeError):
                validate_public_output(self.config)
            clean_public_outputs(self.config)
            self.assertEqual(json.loads(cache.read_text()), {})
            validate_public_output(self.config)
        finally:
            os.chdir(original)


if __name__ == '__main__':
    unittest.main()
