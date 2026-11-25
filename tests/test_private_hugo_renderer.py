from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from modules.private_hugo_renderer import render_markdown_batch, PrivateHugoError
from modules.private_bundle import _sanitize_rendered_html


class PrivateHugoRendererTests(unittest.TestCase):
    def test_uses_real_public_hooks_for_heading_code_math_table_and_mermaid(self):
        fixture = '''## Shared heading

- [x] Done
- [ ] Pending

| Name | Value |
| --- | --- |
| A | B |

```python
def example(x):
    return x + 1
```

```mermaid
graph LR
  A --> B
```

$$\\frac{x_1}{\\sqrt{x^2+1}} + \\sum_{i=1}^{n} i$$

![Private figure](private-asset:abc123)
'''
        rendered = render_markdown_batch({'fixture': fixture}, {})['fixture']
        safe = _sanitize_rendered_html(rendered)
        for marker in (
            '<h2 id="shared-heading">', 'class="code-block code-block--python"',
            'class="highlight"', 'data-language="python"', 'class="language-python"',
            '<table>', 'type="checkbox"', 'class="mermaid"', 'data-mermaid-source=',
            'class="katex"', 'class="katex-mathml"', '<math ', '<mfrac>', '<svg ', '<path ',
            'private-asset:abc123', 'loading="lazy"', 'decoding="async"', 'tabindex="0"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rendered)
                self.assertIn(marker, safe)
        for style in ('background-color:#272822', 'color:#f8f8f2', 'vertical-align:', 'top:', 'height:', 'tab-size:4'):
            with self.subTest(style=style):
                self.assertIn(style, safe)
        self.assertNotIn('#ZgotmplZ', safe)
        self.assertNotIn('/blogs-of-bluhuang/private-asset:', safe)

    def test_no_private_temporary_source_or_output_survives_success(self):
        real_temporary_directory = tempfile.TemporaryDirectory
        directories = []
        def create(*args, **kwargs):
            temporary = real_temporary_directory(*args, **kwargs)
            directories.append(Path(temporary.name))
            return temporary
        with patch('modules.private_hugo_renderer.tempfile.TemporaryDirectory', side_effect=create):
            output = render_markdown_batch({'privateid': '# Private fixture\n'}, {})
        self.assertIn('Private fixture', output['privateid'])
        self.assertTrue(directories)
        self.assertTrue(all(not path.exists() for path in directories))

    def test_hugo_error_is_generic_and_temporary_data_is_removed(self):
        real_temporary_directory = tempfile.TemporaryDirectory
        directories = []
        def create(*args, **kwargs):
            temporary = real_temporary_directory(*args, **kwargs)
            directories.append(Path(temporary.name))
            return temporary
        diagnostic = 'PRIVATE_DIAGNOSTIC containing secret source and private path'
        with patch('modules.private_hugo_renderer.tempfile.TemporaryDirectory', side_effect=create), \
             patch('modules.private_hugo_renderer.subprocess.run', return_value=SimpleNamespace(returncode=1, stderr=diagnostic)):
            with self.assertRaises(PrivateHugoError) as failure:
                render_markdown_batch({'privateid': diagnostic}, {})
        self.assertNotIn('PRIVATE_DIAGNOSTIC', str(failure.exception))
        self.assertTrue(all(not path.exists() for path in directories))

    def test_html_sanitizer_preserves_math_but_removes_active_attributes(self):
        source = '''<span class="katex" style="height:1em;color:#fff;background-image:url(https://tracker.invalid)">
<math xmlns="http://www.w3.org/1998/Math/MathML"><mi onclick="alert(1)">x</mi></math>
<svg viewBox="0 0 10 10" width="10" height="10"><path d="M0 0L1 1" onload="alert(1)"></path><foreignObject>Bad</foreignObject></svg>
<script>alert(1)</script><a href="javascript:alert(1)">Bad</a></span>'''
        safe = _sanitize_rendered_html(source)
        self.assertIn('class="katex"', safe)
        self.assertIn('height:1em;', safe)
        self.assertIn('color:#fff;', safe)
        self.assertIn('viewBox=', safe)
        for unsafe in ('onclick', 'onload', '<script', 'javascript:', 'foreignObject', 'background-image', 'tracker.invalid'):
            self.assertNotIn(unsafe, safe)


if __name__ == '__main__':
    unittest.main()
