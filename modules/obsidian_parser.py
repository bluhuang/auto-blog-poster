import os
import re
from pathlib import Path
from typing import List, Optional, Tuple


def extract_image_links(
    content: str,
    source_file_path: str,
    notes_root: str,
    config: Optional[dict] = None,
) -> List[Tuple[str, str, str]]:
    """Extract image references from Obsidian/Markdown content and compute
    source absolute paths and target relative paths.

    Handles two syntaxes:

    * Obsidian wiki-style: ``![[image.png]]``
    * Standard Markdown: ``![alt](path)`` (local files only; http/https skipped)

    For wiki-style images the function follows the lookup strategies from
    ``config.processing.image_handling.wiki_image_lookup`` (e.g. ``same_dir``,
    ``relative_subdir`` with ``subdir``).

    Args:
        content: Raw markdown content of the note.
        source_file_path: Absolute path to the source note file.
        notes_root: Root directory of all notes (e.g. ``.temp/source_repo/2 Notes``).
        config: Full application configuration dict (optional).

    Returns:
        A list of ``(source_abs_path, target_rel_path, original_syntax)`` tuples.

        * ``source_abs_path`` — absolute path where the image currently lives.
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
        filename = match.group(1).strip()
        original_syntax = match.group(0)

        source_abs = _find_wiki_image(filename, source_dir, config)
        if source_abs is None:
            print(f"  Warning: wiki image not found: {filename}")
            continue

        target_rel = _make_target_path(note_rel_dir, filename)
        results.append((source_abs, target_rel, original_syntax))

    # 2) Standard Markdown: ![alt](path)
    md_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    for match in md_pattern.finditer(content):
        url = match.group(2).strip()
        original_syntax = match.group(0)

        if url.startswith("http://") or url.startswith("https://"):
            continue

        # Resolve relative to the note's directory
        if os.path.isabs(url):
            source_abs = url
        else:
            source_abs = os.path.normpath(os.path.join(source_dir, url))

        if not os.path.isfile(source_abs):
            print(f"  Warning: markdown image not found: {url}")
            continue

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
    filename: str, source_dir: str, config: Optional[dict] = None
) -> Optional[str]:
    """Look for a wiki-style image using configured lookup strategies.

    Returns the absolute path of the first match, or None.

    When *config* is provided, the strategies are read from
    ``processing.image_handling.wiki_image_lookup``.  Without config only
    ``same_dir`` is tried.
    """
    strategies = _get_lookup_strategies(config)

    for strategy in strategies:
        stype = strategy.get("type")
        if stype == "same_dir":
            candidate = os.path.join(source_dir, filename)
            if os.path.isfile(candidate):
                return candidate

        elif stype == "relative_subdir":
            subdir = strategy.get("subdir")
            if subdir:
                candidate = os.path.join(source_dir, subdir, filename)
                if os.path.isfile(candidate):
                    return candidate

        elif stype == "global":
            global_dir = strategy.get("dir")
            if global_dir and os.path.isdir(global_dir):
                candidate = os.path.join(global_dir, filename)
                if os.path.isfile(candidate):
                    return candidate

    return None


def _get_lookup_strategies(
    config: Optional[dict],
) -> List[dict]:
    """Return the ordered list of wiki-image lookup strategies from config,
    falling back to a sensible default if not set."""
    if config is None:
        return [{"type": "same_dir"}]

    image_handling = config.get("processing", {}).get("image_handling", {})
    strategies = image_handling.get("wiki_image_lookup", None)
    if strategies:
        # Resolve global dir if a strategy references it
        global_dir = image_handling.get("source_images_dir", "") or None
        for s in strategies:
            if s.get("type") == "global" and not s.get("dir"):
                s["dir"] = global_dir if global_dir else ""
        return strategies

    # Default if no config key present
    return [{"type": "same_dir"}]


def _make_target_path(note_rel_dir: str, image_basename: str) -> str:
    """Build a target relative path under ``images/`` mirroring the note's
    directory structure.

    Example: ``images/算法/fig.png``
    """
    if note_rel_dir:
        return f"images/{note_rel_dir}/{image_basename}"
    return f"images/{image_basename}"
