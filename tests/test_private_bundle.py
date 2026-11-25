import base64
import json
import html as html_module
import hashlib
import os
from pathlib import Path
import tempfile
import re
import unittest
import yaml
from unittest.mock import patch, MagicMock

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from modules.private_bundle import build_bundle, PrivateBundleError


def decrypt(envelope, password="test-only-password"):
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32,
        salt=base64.b64decode(envelope["salt"]),
        iterations=envelope["iterations"],
    ).derive(password.encode())
    return json.loads(AESGCM(key).decrypt(
        base64.b64decode(envelope["iv"]),
        base64.b64decode(envelope["ciphertext"]), None,
    ))


class PrivateBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.notes = self.vault / "2 Notes"
        (self.notes / "coding").mkdir(parents=True)
        (self.notes / "Path").mkdir()
        (self.vault / "personal" / "assets").mkdir(parents=True)
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "app.json").write_text(json.dumps({
            "attachmentFolderPath": "./assets",
        }))
        (self.notes / "coding" / "Algorithm secret.md").write_text(
            "# Confidential algorithm\n\nPrivate sentence.\n\n[[Other secret]]\n"
        )
        (self.notes / "coding" / "Other secret.md").write_text("# Linked note\n")
        self.original = self.vault / "personal" / "original.md"
        self.original.write_text("# Original live note\n\nOriginal content.\n\n![[figure.png|320]]\n")
        self.image_data = b"private image bytes"
        (self.original.parent / "assets" / "figure.png").write_bytes(self.image_data)
        (self.notes / "Path" / "Reference.md").write_text("![[personal/original]]\n")
        self.config = {
            "_source_repo_dir": str(self.vault),
            "output": {"static_dir": str(self.root / "static"), "content_dir": str(self.root / "content")},
            "private_space": {
                "enabled": True, "source_dirs": ["coding", "Path"],
                "title": "Private Space", "url": "private-space/",
                "bundle_path": "private-space/bundle.json",
                "password_env": "PRIVATE_SPACE_TEST_PASSWORD", "iterations": 600000,
            },
        }
        self.env = patch.dict(os.environ, {"PRIVATE_SPACE_TEST_PASSWORD": "test-only-password"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def build(self):
        build_bundle(self.notes, self.config)
        return json.loads((self.root / "static" / "private-space" / "bundle.json").read_text())

    def test_encrypts_tree_text_assets_and_links_without_plaintext_outputs(self):
        envelope = self.build()
        serialized = json.dumps(envelope)
        for value in ("Algorithm secret", "Private sentence", "Original content", "figure.png", "test-only-password"):
            self.assertNotIn(value, serialized)
        payload = decrypt(envelope)
        self.assertEqual({folder["name"] for folder in payload["folders"]}, {"coding", "Path"})
        all_notes = [note for folder in payload["folders"] for note in folder["notes"]]
        self.assertEqual(len(all_notes), 3)
        html = "\n".join(note["html"] for note in all_notes)
        self.assertIn("Original content", html)
        self.assertIn("private-asset:", html)
        self.assertIn("private-note:", html)
        self.assertEqual(base64.b64decode(next(iter(payload["assets"].values()))["data"]), self.image_data)
        shell = (self.root / "content" / "private-space.md").read_text()
        self.assertIn("list: never", shell)
        self.assertIn("private_space: true", shell)
        self.assertNotIn("Algorithm secret", shell)
        metadata = yaml.safe_load(shell.split('---', 2)[1])
        bundle_bytes = (self.root / 'static' / 'private-space' / 'bundle.json').read_bytes()
        self.assertEqual(metadata['params']['private_bundle_revision'], hashlib.sha256(bundle_bytes).hexdigest())
        self.assertEqual(len(list((self.root / "static").rglob("*.*"))), 1)

    def test_wrong_password_and_tampering_fail_authentication(self):
        envelope = self.build()
        with self.assertRaises(InvalidTag):
            decrypt(envelope, "wrong-password")
        ciphertext = bytearray(base64.b64decode(envelope["ciphertext"]))
        ciphertext[0] ^= 1
        envelope["ciphertext"] = base64.b64encode(ciphertext).decode()
        with self.assertRaises(InvalidTag):
            decrypt(envelope)

    def test_reference_uses_current_original_without_copying_markdown(self):
        first = decrypt(self.build())
        self.original.write_text("# New version\n\nUpdated source content.\n")
        second = decrypt(self.build())
        first_html = first["folders"][0]["notes"][0]["html"]
        second_html = second["folders"][0]["notes"][0]["html"]
        self.assertIn("Original content", first_html)
        self.assertIn("Updated source content", second_html)
        self.assertEqual((self.notes / "Path" / "Reference.md").read_text(), "![[personal/original]]\n")

    def test_missing_password_fails_closed(self):
        with patch.dict(os.environ, {"PRIVATE_SPACE_TEST_PASSWORD": ""}):
            with self.assertRaises(PrivateBundleError):
                self.build()
        self.assertFalse((self.root / "static").exists())

    def test_missing_embed_cycle_and_escape_fail_without_leaking_paths(self):
        reference = self.notes / "Path" / "Reference.md"
        for text in ("![[missing-very-private-target]]", "![[2 Notes/Path/Reference]]", "![[../../../../private-target]]"):
            reference.write_text(text)
            with self.subTest(text=text):
                with self.assertRaises(PrivateBundleError) as failure:
                    self.build()
                self.assertNotIn("private-target", str(failure.exception))

    def test_code_examples_not_resolved_and_active_html_is_sanitized(self):
        (self.notes / "coding" / "Other secret.md").write_text(
            '```python\n![[missing-example]]\n```\n\n'
            '<script>alert("x")</script>\n\n'
            '<a href="javascript:alert(1)" onclick="alert(1)">Bad</a>\n'
        )
        payload = decrypt(self.build())
        html = "\n".join(note["html"] for folder in payload["folders"] for note in folder["notes"])
        # Chroma adds spans around tokens; the visible code remains exact.
        self.assertIn("![[missing-example]]", html_module.unescape(re.sub(r'<[^>]+>', '', html)))
        self.assertIn('class="code-block code-block--python"', html)
        self.assertNotIn("<script", html)
        self.assertNotIn("onclick=", html)
        self.assertNotIn("javascript:", html)

    def test_markdown_assets_resolve_relative_to_embedded_original(self):
        (self.original.parent / "assets" / "document.pdf").write_bytes(b"%PDF-private")
        self.original.write_text(
            "![Figure](assets/figure.png)\n\n[Document](assets/document.pdf)\n"
        )
        payload = decrypt(self.build())
        self.assertEqual(len(payload["assets"]), 2)
        self.assertIn("private-asset:", payload["folders"][0]["notes"][0]["html"])

    def test_math_survives_markdown_and_nested_embeds(self):
        self.original.write_text(
            '# Formula\n\n$$\nW_{x_y} = \\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}\n$$\n\n'
            'Inline $x_i * y_j < z$ and \\(a_b\\).\n'
        )
        payload = decrypt(self.build())
        text = payload["folders"][0]["notes"][0]["html"]
        self.assertIn('W_{x_y}', text)
        self.assertIn('\\begin{bmatrix}', text)
        self.assertIn('x_i * y_j &lt; z</annotation>', text)
        self.assertIn('a_b</annotation>', text)
        self.assertIn('class="katex"', text)
        self.assertIn('<math ', text)
        self.assertEqual(payload['renderer'], 'hugo')
        self.assertNotIn('<em>', text)

    def test_https_image_is_embedded_in_ciphertext_not_external_html(self):
        from io import BytesIO
        from PIL import Image
        png = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(png, format='PNG')
        self.original.write_text('![Remote](https://example.invalid/private.png)\n')
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = 'https://example.invalid/private.png'
        response.headers.get_content_type.return_value = 'image/png'
        response.read.return_value = png.getvalue()
        with patch('modules.private_bundle.urllib.request.urlopen', return_value=response):
            payload = decrypt(self.build())
        html = payload['folders'][0]['notes'][0]['html']
        self.assertIn('private-asset:', html)
        self.assertNotIn('https://', html)
        self.assertEqual(len(payload['assets']), 1)

    def test_http_image_is_rejected_instead_of_silently_removed(self):
        self.original.write_text('![Remote](http://example.invalid/private.png)\n')
        with self.assertRaises(PrivateBundleError):
            self.build()

    def test_parent_relative_assets_within_vault_are_allowed(self):
        (self.vault / 'assets').mkdir()
        (self.vault / 'assets' / 'shared.png').write_bytes(b'parent asset')
        self.original.write_text('![Shared](../assets/shared.png)\n')
        payload = decrypt(self.build())
        asset = next(iter(payload['assets'].values()))
        self.assertEqual(base64.b64decode(asset['data']), b'parent asset')

    def test_private_titles_and_duplicate_heading_follow_public_article_policy(self):
        note = self.notes / 'coding' / 'Algorithm secret.md'
        numbered = note.with_name('1 Algorithm secret.md')
        note.rename(numbered)
        numbered.write_text('# Algorithm secret\n\nBody without a duplicated article title.\n')
        self.config['processing'] = {
            'title_strip_prefix': {'enabled': True, 'pattern': r'^\d+\s*[-.]?\s*'},
            'default_author': 'Article author',
        }
        payload = decrypt(self.build())
        note = next(note for folder in payload['folders'] for note in folder['notes']
                    if note['title'] == 'Algorithm secret')
        self.assertEqual(note['author'], 'Article author')
        self.assertNotIn('<h1', note['html'])
        self.assertIn('Body without a duplicated article title.', note['html'])


if __name__ == "__main__":
    unittest.main()
