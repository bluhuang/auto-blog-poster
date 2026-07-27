import hashlib
import os
import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Tuple


def extract_image_links(
    content: str,
    source_file_path: str,
    notes_root: str,
    wiki_image_lookup: Optional[List[dict]] = None,
) -> List[Tuple[str, str, str]]:
    """Extract image references from Obsidian/Markdown content and compute
    source absolute paths and target relative paths.

    Handles two syntaxes:

    * Obsidian wiki-style: ``![[image.png]]``
    * Standard Markdown: ``![alt](path)`` (local files and remote http/https URLs)

    For wiki-style images the function follows the ordered ``wiki_image_lookup``
    strategies (e.g. ``same_dir``, ``relative_subdir``).  When omitted a
    sensible default (``[{same_dir}]``) is used.

    Args:
        content: Raw markdown content of the note.
        source_file_path: Absolute path to the source note file.
        notes_root: Root directory of all notes (e.g. ``.temp/source_repo/2 Notes``).
        wiki_image_lookup: Ordered list of lookup-strategy dicts.

    Returns:
        A list of ``(source_abs_path, target_rel_path, original_syntax)`` tuples.

        * ``source_abs_path`` — absolute local path for local images, or the
          http/https URL for remote images.
        * ``target_rel_path`` — relative path under ``static/``
          (e.g. ``images/subdir/fig.png``).
        * ``original_syntax`` — the matched text in the original content
          (e.g. ``![[fig.png]]`` or ``![alt](fig.png)``).
    """
    source_dir = os.path.dirname(source_file_path)
    note_rel_dir = _compute_note_rel_dir(source_file_path, notes_root)

    results: List[Tuple[str, str, str]] = []

    # 1) Obsidian wiki-style: ![[filename]]
    wiki_pattern = re.compile(r"!\[\[([^\]]+)\]\]")
    for match in wiki_pattern.finditer(content):
        # Obsidian embeds may carry display options, e.g. ``![[plot.png|395]]``.
        # The option is not part of the filename and must never reach lookup.
        filename = match.group(1).split("|", 1)[0].strip()
        original_syntax = match.group(0)

        source_abs = _find_wiki_image(filename, source_dir, wiki_image_lookup)
        if source_abs is None:
            line = content.count("\n", 0, match.start()) + 1
            raise FileNotFoundError(
                f"Missing Obsidian image at {source_file_path}:{line}: {filename}"
            )

        target_rel = _make_target_path(note_rel_dir, filename)
        results.append((source_abs, target_rel, original_syntax))

    # 2) Standard Markdown: ![alt](path)
    md_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    for match in md_pattern.finditer(content):
        # CommonMark permits angle-bracketed destinations for names containing
        # spaces or non-ASCII punctuation.  They are syntax, not path bytes.
        url = match.group(2).strip().strip("<>")
        original_syntax = match.group(0)

        if url.startswith("http://") or url.startswith("https://"):
            url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
            ext = _guess_extension(url)
            filename = f"{url_hash}{ext}"
            target_rel = _make_target_path(note_rel_dir, filename)
            results.append((url, target_rel, original_syntax))
            continue

        # Resolve relative to the note first, then through the same Obsidian
        # attachment-folder strategies used for wiki embeds.  A large portion
        # of exported Markdown uses ``![alt](file.png)`` while Obsidian stores
        # the file in the note's configured ``attachments/`` folder.
        if os.path.isabs(url):
            source_abs = url
        else:
            source_abs = os.path.normpath(os.path.join(source_dir, url))

        if not os.path.isfile(source_abs):
            source_abs = _find_wiki_image(url, source_dir, wiki_image_lookup)
        if source_abs is None or not os.path.isfile(source_abs):
            line = content.count("\n", 0, match.start()) + 1
            raise FileNotFoundError(
                f"Missing Markdown image at {source_file_path}:{line}: {url}"
            )

        image_basename = os.path.basename(source_abs)
        target_rel = _make_target_path(note_rel_dir, image_basename)
        results.append((source_abs, target_rel, original_syntax))

    return results


def convert_markdown_links(
    content: str, replacements: List[Tuple[str, str]]
) -> str:
    """Replace original image syntax with Hugo-compatible ``![](url)`` links.

    Args:
        content: The markdown text to transform.
        replacements: List of ``(original_syntax, new_markdown_link)`` pairs.
            Example: ``[("![[fig.png]]", "![](/images/subdir/fig.png)")]``.

    Returns:
        The transformed markdown text.
    """
    for old, new in replacements:
        content = content.replace(old, new)
    return content


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_note_rel_dir(source_file_path: str, notes_root: str) -> str:
    """Return the directory portion of the note's path relative to notes_root.

    Example: note at ``.../2 Notes/算法/note.md`` with notes_root ``.../2 Notes``
    returns ``算法``.
    """
    try:
        rel = os.path.relpath(os.path.dirname(source_file_path), notes_root)
    except ValueError:
        return ""
    return rel if rel != "." else ""


def _find_wiki_image(
    filename: str,
    source_dir: str,
    wiki_image_lookup: Optional[List[dict]] = None,
) -> Optional[str]:
    """Look for a wiki-style image using the provided lookup strategies.

    Returns the absolute path of the first match, or ``None``.

    When *wiki_image_lookup* is omitted only ``same_dir`` is tried.
    """
    strategies = wiki_image_lookup or [{"type": "same_dir"}]

    for strategy in strategies:
        stype = strategy.get("type")
        if stype == "same_dir":
            candidate = os.path.join(source_dir, filename)
            if os.path.isfile(candidate):
                return candidate

        elif stype == "relative_subdir":
            subdir = strategy.get("subdir")
            if subdir:
                candidate = os.path.normpath(
                    os.path.join(source_dir, subdir, filename)
                )
                if os.path.isfile(candidate):
                    return candidate

        elif stype == "global":
            global_dir = strategy.get("dir")
            if global_dir and os.path.isdir(global_dir):
                candidate = os.path.join(global_dir, filename)
                if os.path.isfile(candidate):
                    return candidate

    return None


def _guess_extension(url: str) -> str:
    """Extract file extension from a URL, defaulting to ``.png``."""
    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"):
        return ext
    return ".png"


def _make_target_path(note_rel_dir: str, image_basename: str) -> str:
    """Build a target relative path under ``images/`` mirroring the note's
    directory structure.

    Example: ``images/算法/fig.png``
    ``note_rel_dir`` is stripped of any leading ``images/`` to prevent
    double-nesting when combined with ``target_static_dir``.
    """
    # Strip leading "images/" from note_rel_dir to avoid duplication
    stripped = note_rel_dir
    if stripped and (stripped.startswith("images/") or stripped.startswith("images\\")):
        stripped = stripped[len("images/"):]
        stripped = stripped.lstrip("/\\")
    if stripped:
        return f"images/{stripped}/{image_basename}"
    return f"images/{image_basename}"
