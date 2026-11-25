"""Render private Markdown with the public site's real Hugo configuration.

The short-lived project lives outside the publishing tree. Its source, output,
resource cache and diagnostics are removed together, including on failure.
Only HTML strings returned to the encryptor leave this directory.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib


class PrivateHugoError(RuntimeError):
    """Safe public error: must never contain private source or diagnostics."""


def render_markdown_batch(documents: dict[str, str], config: dict) -> dict[str, str]:
    if not documents:
        return {}
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key) for key in documents):
        raise PrivateHugoError("Private Markdown identifiers are invalid")
    project = Path(__file__).resolve().parents[1]
    try:
        native_config = tomllib.loads((project / "hugo.toml").read_text(encoding="utf-8"))
        markup = copy.deepcopy(native_config.get("markup", {}))
        # Honor the normal Hugo split-config override when present.
        split_markup = project / "config" / "_default" / "markup.toml"
        if split_markup.is_file():
            markup.update(tomllib.loads(split_markup.read_text(encoding="utf-8")))
        hooks = project / "layouts" / "_default" / "_markup"
        if not hooks.is_dir() or not markup:
            raise PrivateHugoError("The shared blog Markdown renderer is unavailable")
        with tempfile.TemporaryDirectory(prefix="private-hugo-") as directory:
            root = Path(directory)
            content = root / "content"
            layout = root / "layouts" / "_default"
            content.mkdir()
            layout.mkdir(parents=True)
            shutil.copytree(hooks, layout / "_markup")
            # These are intentionally fragment templates, not a second article
            # renderer. .Content runs the same Goldmark/render-hook pipeline as
            # layouts/_default/single.html in the normal public build.
            (layout / "single.html").write_text("{{ .Content }}", encoding="utf-8")
            (layout / "list.html").write_text("", encoding="utf-8")
            (root / "layouts" / "home.html").write_text("", encoding="utf-8")
            settings = {
                "baseURL": native_config.get("baseURL", "https://private.invalid/"),
                "markup": markup,
                "taxonomies": {},
                "disableKinds": ["home", "section", "taxonomy", "term", "RSS", "sitemap"],
                "outputs": {"page": ["HTML"]},
                "cacheDir": str(root / "cache"),
                "resourceDir": str(root / "resources"),
                "build": {"buildStats": {"enable": False}},
            }
            config_path = root / "hugo.json"
            config_path.write_text(json.dumps(settings), encoding="utf-8")
            for key, markdown in documents.items():
                (content / (key + ".md")).write_text(
                    "---\nurl: /" + key + "/\n---\n" + markdown,
                    encoding="utf-8",
                )
            output = root / "rendered"
            executable = config.get("hugo", {}).get("executable", "hugo")
            completed = subprocess.run(
                [executable, "--source", str(root), "--config", str(config_path),
                 "--destination", str(output), "--quiet"],
                text=True, capture_output=True, timeout=int(config.get("private_space", {}).get("render_timeout_seconds", 120)),
            )
            if completed.returncode:
                # Hugo math/code errors can quote Markdown. They must not be
                # forwarded into public CI logs or artifacts.
                raise PrivateHugoError("Shared Hugo private Markdown rendering failed")
            return {key: (output / key / "index.html").read_text(encoding="utf-8")
                    for key in documents}
    except PrivateHugoError:
        raise
    except Exception:
        raise PrivateHugoError("Shared Hugo private Markdown rendering failed") from None
