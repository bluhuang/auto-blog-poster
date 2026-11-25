import unittest
from pathlib import Path


class PrivateSpaceFrontendTests(unittest.TestCase):
    def test_shell_generation_uses_current_hugo_build_options(self):
        generator = Path('modules/private_bundle.py').read_text()
        self.assertIn('"build": {"list": "never", "render": "always"}', generator)
        self.assertNotIn('"_build":', generator)

    def test_locked_shell_is_generic_and_sidebar_has_one_entry(self):
        shell = Path('layouts/_default/private-space.html').read_text()
        sidebar = Path('layouts/partials/library-sidebar.html').read_text()
        self.assertIn('type="password"', shell)
        self.assertIn('data-private-workspace hidden', shell)
        self.assertIn('data-private-tree></nav>', shell)
        self.assertNotIn('private.source_dirs', shell)
        self.assertNotIn('private.directories', shell)
        self.assertIn('Content-Security-Policy', shell)
        self.assertIn("default-src 'none'", shell)
        self.assertNotIn('essentials/script', shell)
        self.assertNotIn('essentials/head', shell)
        self.assertEqual(sidebar.count('data-private-space-link'), 1)
        self.assertNotIn('source_dirs', sidebar)
        self.assertNotIn('directories', sidebar)

    def test_runtime_does_not_persist_secrets_and_cleans_up(self):
        script = Path('assets/js/private-space.js').read_text()
        for persistence in ('localStorage', 'sessionStorage', 'indexedDB', 'document.cookie'):
            self.assertNotIn(persistence, script)
        for cleanup in ('URL.revokeObjectURL', 'tree.replaceChildren()',
                        'content.replaceChildren()', 'password.value = ""',
                        'window.addEventListener("pagehide", reset)'):
            self.assertIn(cleanup, script)
        self.assertIn('"AES-GCM"', script)
        self.assertIn('"PBKDF2"', script)
        self.assertIn('window.renderMathInElement(content', script)
        self.assertIn('trust: false', script)
        self.assertIn('element.download = "attachment"', script)


if __name__ == '__main__':
    unittest.main()
