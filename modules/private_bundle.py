"""Build a password-encrypted, self-contained private reading space.

Private source text is rendered only in memory. The public build receives an
authenticated ciphertext and a generic unlock page, never private Markdown,
titles, attachment names, or plaintext assets.
"""

from __future__ import annotations

import base64
import hashlib
import html
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import urllib.request

import bleach
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import markdown
import yaml

from modules.git_ops import get_attachment_folder


class PrivateBundleError(RuntimeError):
    """Intentionally non-sensitive build error safe for public CI logs."""


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise PrivateBundleError("Private reference escapes its permitted root")
    return resolved


def _relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise PrivateBundleError("Invalid private-space path configuration")
    return path


def _identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _Renderer:
    def __init__(self, notes_root: Path, vault: Path, private_notes: list[Path], settings: dict):
        self.notes_root = notes_root.resolve()
        self.vault = vault.resolve()
        self.note_ids = {
            note.resolve(): _identifier(note.relative_to(notes_root).as_posix())
            for note in private_notes
        }
        self.assets: dict[str, dict[str, str]] = {}
        self.asset_paths: set[Path] = set()
        self.settings = settings
        self.remote_assets: dict[str, str] = {}
        self.attachment_folder = get_attachment_folder(
            str(vault), notes_root.relative_to(vault).as_posix()
        )

    def resolve(self, target: str, source: Path, is_note: bool = False) -> Path:
        target = unquote(target.split("#", 1)[0].strip().strip("<>"))
        if not target or urlsplit(target).scheme or Path(target).is_absolute():
            raise PrivateBundleError("Invalid private reference")
        raw = Path(target)
        candidates = [source.parent / raw, self.vault / raw, self.notes_root / raw]
        attachment = self.attachment_folder
        if attachment:
            if attachment.startswith("./"):
                candidates.append(source.parent / attachment[2:] / raw)
            else:
                candidates.append(self.vault / attachment / raw)
        else:
            candidates.append(self.vault / raw)
        # A normal ../ attachment link may be valid relative to its source
        # while the same spelling is outside the vault from a fallback root.
        # Only candidates that stay inside the vault participate in lookup.
        safe_candidates = []
        for candidate in candidates:
            try:
                safe_candidates.append(_inside(candidate, self.vault))
            except PrivateBundleError:
                continue
        if not safe_candidates:
            raise PrivateBundleError("Private reference escapes its permitted root")
        variants = []
        for candidate in safe_candidates:
            variants.append(candidate)
            if is_note and candidate.suffix.lower() != ".md":
                variants.append(Path(str(candidate) + ".md"))
        for candidate in variants:
            if candidate.is_file():
                return _inside(candidate, self.vault)
        # Obsidian permits unambiguous basename links. Explicit paths must
        # resolve exactly, rather than silently choosing a different file.
        if len(raw.parts) == 1:
            names = {raw.name}
            if is_note and raw.suffix.lower() != ".md":
                names.add(raw.name + ".md")
            matches = [
                path.resolve() for name in names for path in self.vault.rglob(name)
                if path.is_file() and not any(
                    part in {".git", ".obsidian"}
                    for part in path.relative_to(self.vault).parts
                )
            ]
            if len(set(matches)) == 1:
                return _inside(matches[0], self.vault)
        raise PrivateBundleError("A private reference could not be resolved uniquely")

    def asset(self, path: Path) -> str:
        path = _inside(path, self.vault)
        max_bytes = int(self.settings.get("max_asset_bytes", 20_000_000))
        if path.stat().st_size > max_bytes:
            raise PrivateBundleError("Private attachment exceeds its configured size limit")
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime == "image/svg+xml":
            # Rasterize SVG rather than publish a navigable active SVG blob.
            try:
                import pymupdf
                with pymupdf.open(stream=data, filetype="svg") as document:
                    data = document[0].get_pixmap(alpha=True).tobytes("png")
                mime = "image/png"
            except Exception:
                raise PrivateBundleError("Private vector image could not be safely rendered") from None
        asset_id = hashlib.sha256(mime.encode() + b"\0" + data).hexdigest()
        self.assets[asset_id] = {
            "mime": mime,
            "data": base64.b64encode(data).decode("ascii"),
        }
        self.asset_paths.add(path)
        return "private-asset:" + asset_id

    def remote_image(self, url: str) -> str:
        if url in self.remote_assets:
            return self.remote_assets[url]
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise PrivateBundleError("Private remote images require HTTPS without URL credentials")
        max_bytes = int(self.settings.get("max_asset_bytes", 20_000_000))
        timeout = int(self.settings.get("asset_timeout_seconds", 20))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "PrivateSpaceBuilder/1"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if urlsplit(response.geturl()).scheme != "https":
                    raise PrivateBundleError("Private image redirect is not HTTPS")
                mime = response.headers.get_content_type()
                if mime not in {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}:
                    raise PrivateBundleError("Private remote image has an unsupported media type")
                data = response.read(max_bytes + 1)
                if not data or len(data) > max_bytes:
                    raise PrivateBundleError("Private remote image exceeds its configured size limit")
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(data)) as image:
                image.verify()
        except Exception:
            raise PrivateBundleError("Private remote image could not be securely imported") from None
        asset_id = hashlib.sha256(mime.encode() + b"\0" + data).hexdigest()
        self.assets[asset_id] = {"mime": mime, "data": base64.b64encode(data).decode("ascii")}
        self.remote_assets[url] = "private-asset:" + asset_id
        return self.remote_assets[url]

    def url(self, value: str, source: Path, image: bool = False) -> str:
        if value.startswith(("private-asset:", "private-note:", "#")):
            return value
        scheme = urlsplit(value).scheme.lower()
        if scheme in {"http", "https", "mailto"}:
            if image:
                return self.remote_image(value)
            return value
        if scheme:
            return "#"
        if not image and (Path(unquote(value.split("#", 1)[0])).suffix.lower() in {"", ".md"}):
            target = self.resolve(value, source, is_note=True)
            note_id = self.note_ids.get(target)
            return "private-note:" + note_id if note_id else "#"
        return self.asset(self.resolve(value, source))

    def render(self, source: Path, trail: tuple[Path, ...] = ()) -> str:
        source = _inside(source, self.vault)
        if source in trail or len(trail) >= 32:
            raise PrivateBundleError("A private note reference is cyclic or too deeply nested")
        text = source.read_text(encoding="utf-8")
        text = re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|$)", "", text, count=1, flags=re.S)

        def embed(match: re.Match) -> str:
            destination, _, options = match.group(1).partition("|")
            destination = destination.strip()
            suffix = Path(destination.split("#", 1)[0]).suffix.lower()
            if not suffix or suffix == ".md":
                target = self.resolve(destination, source, is_note=True)
                return "\n\n" + self.render(target, trail + (source,)) + "\n\n"
            target = self.resolve(destination, source)
            url = self.asset(target)
            label = html.escape(options if options and not options.isdigit() else target.stem)
            if (mimetypes.guess_type(target.name)[0] or "").startswith("image/"):
                width = f' width="{int(options)}"' if options.isdigit() else ""
                return f'<img src="{url}" alt="{label}"{width}>'
            return f'<a href="{url}">{label}</a>'

        def wiki_link(match: re.Match) -> str:
            destination, _, label = match.group(1).partition("|")
            label = label or destination.rsplit("/", 1)[-1].removesuffix(".md")
            try:
                url = self.url(destination, source)
            except PrivateBundleError:
                return html.escape(label)
            return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'

        # Never interpret Obsidian syntax inside fenced examples/code. Protect
        # LaTeX before Markdown sees underscores, asterisks, or backslashes.
        pieces = re.split(r"(^```[^\n]*\n.*?^```[ \t]*$|^~~~[^\n]*\n.*?^~~~[ \t]*$)", text, flags=re.M | re.S)
        math_spans: dict[str, str] = {}
        marker_prefix = "PRIVATEMATH" + os.urandom(8).hex().upper()

        def protect_math(match: re.Match) -> str:
            marker = marker_prefix + str(len(math_spans)) + "END"
            math_spans[marker] = match.group(0)
            return marker

        math_pattern = re.compile(
            r"(?<!\\)\$\$.*?(?<!\\)\$\$"
            r"|(?<!\\)\\\[.*?(?<!\\)\\\]"
            r"|(?<!\\)\\\(.*?(?<!\\)\\\)"
            r"|(?<!\\)\$(?!\$)(?:\\.|[^$\n])+?(?<!\\)\$",
            re.S,
        )
        for index in range(0, len(pieces), 2):
            pieces[index] = math_pattern.sub(protect_math, pieces[index])
            pieces[index] = re.sub(r"!\[\[([^\]\n]+)\]\]", embed, pieces[index])
            pieces[index] = re.sub(r"(?<!!)\[\[([^\]\n]+)\]\]", wiki_link, pieces[index])
        rendered = markdown.markdown(
            "".join(pieces), extensions=["tables", "fenced_code", "sane_lists"]
        )
        for marker, math_text in math_spans.items():
            rendered = rendered.replace(marker, html.escape(math_text, quote=False))
        rewriter = _URLRewriter(self, source)
        rewriter.feed(rendered)
        return bleach.clean(
            "".join(rewriter.output),
            tags={
                "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "a",
                "img", "ul", "ol", "li", "strong", "em", "del", "s", "blockquote",
                "pre", "code", "table", "thead", "tbody", "tr", "th", "td",
                "div", "span", "sup", "sub", "details", "summary", "input",
            },
            attributes={
                "a": ["href", "title"], "img": ["src", "alt", "title", "width", "height"],
                "code": ["class"], "th": ["align"], "td": ["align"],
                "input": ["type", "checked", "disabled"],
            },
            protocols={"http", "https", "mailto", "private-asset", "private-note"},
            strip=True,
        )


class _URLRewriter(HTMLParser):
    def __init__(self, renderer: _Renderer, source: Path):
        super().__init__(convert_charrefs=False)
        self.renderer, self.source = renderer, source
        self.output: list[str] = []

    def handle_starttag(self, tag, attrs):
        rewritten = []
        for key, value in attrs:
            if value is not None and ((tag == "img" and key == "src") or (tag == "a" and key == "href")):
                value = self.renderer.url(value, self.source, image=tag == "img")
            rewritten.append(key if value is None else f'{key}="{html.escape(value, quote=True)}"')
        attributes = " " + " ".join(rewritten) if rewritten else ""
        self.output.append(f"<{tag}{attributes}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(data)

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")


def build_bundle(notes_root: Path, config: dict) -> None:
    """Generate ciphertext plus a non-listable shell; never call an AI API."""
    settings = config.get("private_space", {})
    if not settings.get("enabled", False):
        return
    password = os.environ.get(settings.get("password_env", "PRIVATE_SPACE_PASSWORD"))
    if not password:
        raise PrivateBundleError("Private-space password is missing; refusing to publish")
    notes_root = Path(notes_root).resolve()
    vault = Path(config.get("_source_repo_dir", notes_root.parent)).resolve()
    _inside(notes_root, vault)
    source_dirs = [_relative_path(value) for value in settings.get("source_dirs", [])]
    if not source_dirs:
        raise PrivateBundleError("Private-space source directories are not configured")
    private_notes = sorted({
        _inside(note, notes_root)
        for folder in source_dirs for note in _inside(notes_root / folder, notes_root).rglob("*.md")
        if note.is_file()
    })
    renderer = _Renderer(notes_root, vault, private_notes, settings)
    folders: dict[str, list[dict]] = {}
    try:
        for note in private_notes:
            folder = note.parent.relative_to(notes_root).as_posix()
            folders.setdefault(folder, []).append({
                "id": renderer.note_ids[note], "title": note.stem,
                "html": renderer.render(note),
            })
    except (OSError, ValueError, PrivateBundleError) as error:
        raise PrivateBundleError("Private content rendering failed; refusing to publish") from None
    payload = json.dumps({
        "folders": [{"name": name, "notes": notes} for name, notes in sorted(folders.items())],
        "assets": renderer.assets,
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    iterations = int(settings.get("iterations", 600000))
    if iterations < 600000:
        raise PrivateBundleError("Private-space key derivation requires at least 600000 iterations")
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations).derive(password.encode("utf-8"))
    encode = lambda data: base64.b64encode(data).decode("ascii")
    envelope = {
        "version": 1, "kdf": "PBKDF2-SHA256", "iterations": iterations,
        "salt": encode(salt), "iv": encode(iv),
        "ciphertext": encode(AESGCM(key).encrypt(iv, payload, None)),
    }
    static_root = Path(config.get("output", {}).get("static_dir", "static")).resolve()
    bundle_path = _inside(static_root / _relative_path(settings.get("bundle_path", "private-space/bundle.json")), static_root)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
    content_root = Path(config.get("output", {}).get("content_dir", "content"))
    content_root.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "title": settings.get("title", "Private Space"), "layout": "private-space",
        "url": settings.get("url", "private-space/"),
        "params": {"private_space": True},
        "build": {"list": "never", "render": "always"},
        "outputs": ["HTML"], "sitemap": {"disable": True},
    }
    (content_root / "private-space.md").write_text(
        "---\n" + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + "---\n",
        encoding="utf-8",
    )
    # Used by the parent pipeline to verify that private attachments were not
    # accidentally retained in restored public caches. Paths stay in memory.
    config["_private_asset_paths"] = renderer.asset_paths
    print("Private Space encrypted successfully.")
