import hashlib
import json
import os
import re
import shutil
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from modules.git_ops import (
    get_file_first_commit_time,
    get_obsidian_attachment_config,
    get_attachment_folder,
)
from modules.obsidian_parser import convert_markdown_links, extract_image_links


def scan_md_files(root_dir: str) -> List[str]:
    """Return a sorted list of relative paths of all .md files under root_dir.

    Paths are relative to root_dir and use forward slashes.
    """
    print(f"Scanning md files in: {root_dir}")
    root = Path(root_dir)
    md_files: List[str] = []
    for filepath in root.rglob("*.md"):
        rel_path = filepath.relative_to(root).as_posix()
        md_files.append(rel_path)
    print(f"  Found {len(md_files)} .md file(s)")
    return sorted(md_files)


def compute_md5(file_path: str) -> str:
    """Return the MD5 hex-digest of the file at file_path.

    The file is read in 8192-byte chunks to avoid loading large files entirely
    into memory.
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()


def load_hash_cache(cache_path: str) -> Dict[str, str]:
    """Load the hash cache from a JSON file.

    Supports both the old flat format (``{"path": "hash"}``) and the new
    dict format (``{"path": {"hash": "…", "mtime": "…"}}``).

    Returns an empty dict if the file does not exist or is unreadable.
    The cache maps relative file paths (forward-slash) to their last-known MD5.
    """
    if not os.path.isfile(cache_path):
        print(f"Cache file not found, starting fresh: {cache_path}")
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            raw: Dict[str, Any] = json.load(f)
        cache: Dict[str, str] = {}
        for path, value in raw.items():
            if isinstance(value, str):
                cache[path] = value
            elif isinstance(value, dict):
                h = value.get("hash")
                if h:
                    cache[path] = h
        print(f"Loaded hash cache with {len(cache)} entries from {cache_path}")
        return cache
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: failed to load cache file ({e}), starting fresh")
        return {}


def save_hash_cache(
    cache_path: str, cache: Dict[str, str], mtimes: Optional[Dict[str, str]] = None
) -> None:
    """Persist the hash cache (and optional mtimes) to a JSON file on disk.

    The saved format stores each path as ``{"hash": ..., "mtime": ...}``
    to enable both old (str) and new (dict) readers.
    """
    payload: Dict[str, Dict[str, str]] = {}
    for path, h in cache.items():
        entry: Dict[str, str] = {"hash": h}
        if mtimes and path in mtimes:
            entry["mtime"] = mtimes[path]
        payload[path] = entry
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved hash cache with {len(cache)} entries to {cache_path}")


def load_mtime_cache(cache_path: str) -> Dict[str, str]:
    """Load mtime values from the hash cache file.

    Handles both old (str values) and new (dict values) formats.
    """
    if not os.path.isfile(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        result: Dict[str, str] = {}
        for path, value in raw.items():
            if isinstance(value, dict):
                mtime = value.get("mtime")
                if mtime:
                    result[path] = mtime
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def get_local_file_time(
    config: dict, rel_path: str
) -> Optional[str]:
    """Return the local file creation-time as an ISO-8601 string, or None.

    Reads the vault path from ``OBSIDIAN_VAULT_PATH`` env var first,
    then falls back to ``config.processing.local_vault_path``.
    Returns ``None`` when the vault path is not set or the file does not
    exist (caller should fall back to Git commit time).
    """
    vault = os.getenv("OBSIDIAN_VAULT_PATH") or ""
    if not vault:
        vault = config.get("processing", {}).get("local_vault_path", "")
    if not vault or not os.path.isdir(vault):
        return None

    abs_path = os.path.join(vault, rel_path)
    if not os.path.isfile(abs_path):
        return None

    try:
        ts = os.path.getctime(abs_path)
    except OSError:
        ts = os.path.getmtime(abs_path)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d")


def _strip_title_prefix(title: str, config: dict) -> str:
    """Remove numeric prefix from title if configured."""
    cfg = config.get("processing", {}).get("title_strip_prefix", {})
    if cfg.get("enabled", False):
        pattern = cfg.get("pattern", "^\\d+\\s*[-.]?\\s*")
        return re.sub(pattern, "", title, count=1)
    return title


def _extract_first_h1(content: str) -> Optional[str]:
    """Extract the first ATX heading ``# title`` from *content*.

    Ignores YAML front matter (``--- … ---``) preceding the heading
    and returns ``None`` when no heading is found.
    """
    text = content
    # Strip leading YAML front matter if present
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def get_files_to_process(
    root_dir: str, cache_path: str
) -> Tuple[List[str], List[str]]:
    """Determine which .md files need processing and which have been deleted.

    Compares the current state of the notes directory against the hash cache
    and returns two lists:

        to_process  : new files, or existing files whose content hash changed
        to_delete   : cached files that no longer exist on disk

    The hash cache is ***not*** updated by this function; the caller decides
    when to persist it via save_hash_cache().
    """
    current_files = set(scan_md_files(root_dir))
    old_cache = load_hash_cache(cache_path)
    old_keys = set(old_cache.keys())

    to_process: List[str] = []
    new_cache: Dict[str, str] = {}
    for rel_path in sorted(current_files):
        abs_path = os.path.join(root_dir, rel_path)
        new_hash = compute_md5(abs_path)
        new_cache[rel_path] = new_hash
        old_hash = old_cache.get(rel_path)
        if old_hash is None or old_hash != new_hash:
            to_process.append(rel_path)

    to_delete: List[str] = sorted(old_keys - current_files)

    if to_process:
        print(f"Files to process ({len(to_process)}):")
        for p in to_process:
            print(f"  + {p}")
    if to_delete:
        print(f"Files to delete ({len(to_delete)}):")
        for p in to_delete:
            print(f"  - {p}")
    if not to_process and not to_delete:
        print("No changes detected.")

    return to_process, to_delete


def process_single_note(
    source_path: str,
    rel_path: str,
    source_root: str,
    config: dict,
    deepseek_client_func: Callable[[str, dict], str],
) -> bool:
    """Read a source note, process images, call DeepSeek, and write to Hugo
    content directory.

    Processing order:

    1. Read raw content from the source file.
    2. Extract image links (wiki-style and Markdown), copy images to the
       ``static/`` directory, and build a replacement map.
    3. Replace wiki image syntax (``![[...]]``) with inert placeholders
       (``<!--IMG_N-->``) so DeepSeek will not mangle the URLs.
    4. Send the placeholder-protected content to the DeepSeek API.
    5. Restore the actual ``![](/images/...)`` links from placeholders.
    6. Write the final content to ``config.output.content_dir``, preserving
       the relative path structure of the original note.

    Args:
        source_path: Absolute path to the source .md file.
        rel_path: Relative path of the note (relative to *source_root*).
        source_root: Root directory of all source notes.
        config: Full application configuration dict.
        deepseek_client_func: Callable ``(content: str, config: dict) -> str``
            that returns the processed text.  Must raise on API failure.

    Returns:
        True on success.

    Raises:
        Exception: If the DeepSeek client returns empty, or on any processing
            failure (image copy, etc.).
    """
    print(f"Processing: {rel_path} ...")

    # 1. Read raw content
    with open(source_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # 2. Extract & copy images
    image_handling_cfg = config.get("processing", {}).get(
        "image_handling", {}
    )
    image_handling_enabled = image_handling_cfg.get("enabled", False)
    target_static_dir = image_handling_cfg.get(
        "target_static_dir", "static/images"
    )

    if image_handling_enabled and raw_content.strip():
        wiki_lookup = config.get("_wiki_image_lookup")
        image_links = extract_image_links(
            raw_content, source_path, source_root, wiki_lookup
        )
        replacements: Dict[str, str] = {}
        placeholder_map: Dict[str, str] = {}
        for idx, (source_abs, target_rel, original_syntax) in enumerate(
            image_links
        ):
            dest_path = os.path.join(target_static_dir, target_rel)
            if not os.path.isfile(dest_path):
                os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
                try:
                    shutil.copy2(source_abs, dest_path)
                    print(f"  [image] copied: {os.path.basename(source_abs)}")
                except OSError as e:
                    raise Exception(
                        f"Failed to copy image {source_abs} for {rel_path}: {e}"
                    ) from e
            else:
                print(f"  [image] skipped (exists): {os.path.basename(source_abs)}")
            replacements[original_syntax] = (
                f"![](/{urllib.parse.quote(target_rel)})"
            )
            placeholder_map[original_syntax] = f"<!--IMG_{idx}-->"

        if replacements:
            # Protect wiki links with placeholders before calling API
            content_to_send = raw_content
            for old_syntax, placeholder in placeholder_map.items():
                content_to_send = content_to_send.replace(old_syntax, placeholder)
            print(f"  [image] protected {len(replacements)} link(s) with placeholders")
        else:
            content_to_send = raw_content
    else:
        content_to_send = raw_content

    # 3. Call DeepSeek API (with placeholder-protected content)
    processed = deepseek_client_func(content_to_send, config)
    if not processed:
        print(
            f"  WARNING: DeepSeek API returned empty result for {rel_path}, "
            f"using unprocessed content as fallback."
        )
        processed = content_to_send

    # 4. Restore image placeholders back to actual Markdown links
    if replacements:
        inverse_map = {v: k for k, v in placeholder_map.items()}
        for placeholder, new_url in inverse_map.items():
            processed = processed.replace(placeholder, new_url)
        print(f"  [image] restored {len(replacements)} link(s) from placeholders")

    # 5. Safeguard against Hugo YAML frontmatter mis-parsing
    if processed.startswith("---"):
        processed = "\n" + processed

    # 6. Prepend front matter with title and date
    # 根据配置决定标题来源: "filename" (默认) 或 "h1"
    title = ""
    title_source = config.get("processing", {}).get("title_source", "filename")
    if title_source == "h1":
        title = _extract_first_h1(processed)
    if not title:
        title = os.path.splitext(os.path.basename(rel_path))[0]
        title = _strip_title_prefix(title, config)
    lines = ["---", f"title: \"{title}\""]

    # Image: first extracted image URL
    first_image_url = ""
    if replacements:
        first_url = next(iter(replacements.values()))
        m = re.match(r"!\[.*?\]\((/[^)]+)\)", first_url)
        if m:
            first_image_url = m.group(1)
    if first_image_url:
        lines.append(f"image: \"{first_image_url}\"")

    # Categories: top-level directory from note path
    path_parts = rel_path.split(os.sep)
    if len(path_parts) > 1:
        lines.append(f"categories: {json.dumps([path_parts[0]], ensure_ascii=False)}")

    # Author: config → default
    author = config.get("processing", {}).get("default_author", "BluHuang")
    if author:
        lines.append(f"author: \"{author}\"")

    # Compute date: .file_times.json → local vault → Git commit
    date_val = _get_date_from_file_times(config, rel_path)
    if date_val is None:
        date_val = get_local_file_time(config, rel_path)
    if date_val is None:
        try:
            source_repo_dir = config.get("_source_repo_dir", "")
            if source_repo_dir:
                repo_path = os.path.dirname(source_repo_dir)
                file_rel = os.path.relpath(source_path, repo_path)
                date_val = get_file_first_commit_time(repo_path, file_rel)
        except Exception:
            pass
    if date_val:
        lines.append(f"date: {date_val}")
        # lastmod 与 date 一致，支持 Hugo 的 .Lastmod 排序
        lines.append(f"lastmod: {date_val}")

    lines.append("---")
    front_matter = "\n".join(lines) + "\n\n"
    processed = front_matter + processed

    # 6. Write to Hugo content directory
    content_dir = config.get("output", {}).get("content_dir", "content")
    dest_path = os.path.join(content_dir, rel_path)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(processed)

    print(f"  -> wrote {dest_path}")
    return True


def process_all_notes(
    source_root: str,
    config: dict,
    deepseek_client_func: Callable[[str, dict], str],
    hash_cache_path: str = ".hash_cache.json",
) -> None:
    """Orchestrate the full incremental processing pipeline.

    1. Compare source directory against the hash cache to find changes.
    2. Call ``process_single_note`` for every new or modified file.
    3. Remove output files that correspond to deleted source notes.
    4. Persist the updated hash cache.

    If any DeepSeek API call fails, processing is terminated immediately and
    the exception is re-raised with the offending source path in the message.

    Args:
        source_root: Root directory of the Obsidian notes.
        config: Full application configuration dict.
        deepseek_client_func: Callable ``(content: str, config: dict) -> str``.
        hash_cache_path: Path to the hash cache JSON file.
    """
    # Expose source repo path for Git-timestamp lookups
    config["_source_repo_dir"] = source_root

    # Auto-detect wiki_image_lookup: explicit config takes priority;
    # otherwise generate rules from .obsidian/app.json.
    if "wiki_image_lookup" not in config.get("processing", {}).get("image_handling", {}):
        config.setdefault("_wiki_image_lookup", _build_wiki_lookup(source_root, config))
    else:
        config["_wiki_image_lookup"] = config["processing"]["image_handling"]["wiki_image_lookup"]

    # Generate .file_times.json from local vault (no-op in CI)
    _generate_file_times_cache(config)

    processing_cfg = config.get("processing", {})
    force = processing_cfg.get("force_reprocess_all", False)

    if force:
        print("force_reprocess_all = true: deleting cache and reprocessing all files")
        if os.path.isfile(hash_cache_path):
            os.remove(hash_cache_path)
            print(f"  removed {hash_cache_path}")
        to_process = scan_md_files(source_root)
        to_delete: List[str] = []
    else:
        to_process, to_delete = get_files_to_process(source_root, hash_cache_path)

    for rel_path in to_process:
        source_path = os.path.join(source_root, rel_path)
        try:
            process_single_note(
                source_path, rel_path, source_root, config, deepseek_client_func
            )
        except Exception:
            print(f"ERROR: Failed to process {rel_path}, aborting.")
            raise

    content_dir = config.get("output", {}).get("content_dir", "content")
    if to_delete:
        for rel_path in to_delete:
            dest_path = os.path.join(content_dir, rel_path)
            if os.path.isfile(dest_path):
                os.remove(dest_path)
                print(f"Deleted: {dest_path}")

    # Ensure every content subdirectory has an _index.md so Hugo treats
    # them as proper sections (needed for tree-nav recursion).
    _ensure_section_indexes(content_dir)

    # Build new cache and collect mtimes
    new_cache: Dict[str, str] = {}
    mtimes: Dict[str, str] = {}
    for rel_path in scan_md_files(source_root):
        abs_path = os.path.join(source_root, rel_path)
        new_cache[rel_path] = compute_md5(abs_path)
        mtime = get_local_file_time(config, rel_path)
        if mtime:
            mtimes[rel_path] = mtime
    save_hash_cache(hash_cache_path, new_cache, mtimes)

    # Reset force_reprocess_all so subsequent runs are incremental
    if force:
        processing_cfg["force_reprocess_all"] = False
        _save_processing_config(config)
        print("force_reprocess_all reset to false")

    print("Processing complete.")


def _ensure_section_indexes(content_dir: str) -> None:
    """Walk the Hugo content directory and create ``_index.md`` for any
    subdirectory that lacks one.

    This ensures Hugo treats nested directories as proper *sections*,
    which is required for the recursive tree-nav partial to work.
    """
    for root, dirs, _files in os.walk(content_dir):
        # Skip the content root itself (it already has _index.md)
        if root == content_dir:
            continue
        indexPath = os.path.join(root, "_index.md")
        if not os.path.isfile(indexPath):
            section_name = os.path.basename(root)
            with open(indexPath, "w", encoding="utf-8") as f:
                f.write(f"---\ntitle: \"{section_name}\"\n---\n")
            print(f"  [section] created _index.md for {os.path.relpath(root, content_dir)}")


_FILE_TIMES_PATH = ".file_times.json"


def _build_wiki_lookup(source_root: str, config: dict) -> List[dict]:
    """Build wiki image lookup rules from an Obsidian vault's attachment
    configuration and project config.

    Priority of lookup rules:

    1. ``same_dir`` — always added first.
    2. From ``.obsidian/app.json`` ``attachmentFolderPath`` (if present):

       - ``./attachments`` (starts with ``./``) → ``global`` strategy at
         ``<vault_root>/attachments/`` (relative to vault root).
       - ``attachments`` (no ``./``) → ``relative_subdir`` subdir
         ``attachments/`` (relative to each note's directory).
       - Also tries ``relative_subdir`` with ``../attachments`` and
         ``../attachments/images`` for notes nested deeper.

    3. Fallback default: ``same_dir`` + ``relative_subdir`` subdir
       ``attachments`` + ``relative_subdir`` subdir ``attachments/images``.

    4. If ``config.image_handling.source_images_dir`` is set, also add a
       ``global`` strategy at ``<repo_root>/<source_images_dir>``.

    Returns:
        Ordered list of lookup-strategy dicts.
    """
    strategies: List[dict] = [{"type": "same_dir"}]

    # The .obsidian/ directory lives in the repo root (one level above the
    # notes subdirectory).  Try the parent first, then fall back to
    # source_root directly in case the notes *are* the repo root.
    repo_root = os.path.dirname(source_root)
    raw = get_attachment_folder(repo_root)
    if raw is None:
        raw = get_obsidian_attachment_config(source_root)
    if raw:
        subdir = raw
        if subdir.startswith("./"):
            # Relative to vault root → global strategy
            subdir = subdir[2:]
            if subdir:
                global_dir = os.path.normpath(os.path.join(repo_root, subdir))
                strategies.append({"type": "global", "dir": global_dir})
        else:
            # Relative to each note's directory → relative_subdir
            if subdir:
                strategies.append(
                    {"type": "relative_subdir", "subdir": subdir}
                )
        # Also try common parent-relative patterns as fallback
        strategies.append(
            {"type": "relative_subdir", "subdir": "../attachments"}
        )
        strategies.append(
            {"type": "relative_subdir", "subdir": "../attachments/images"}
        )
    else:
        strategies.append(
            {"type": "relative_subdir", "subdir": "attachments"}
        )
        strategies.append(
            {"type": "relative_subdir", "subdir": "attachments/images"}
        )

    # Add repo-level global strategy from source_images_dir config (optional)
    img_dir = config.get("processing", {}).get("image_handling", {}).get("source_images_dir", "")
    if img_dir:
        global_dir = os.path.normpath(os.path.join(repo_root, img_dir))
        if os.path.isdir(global_dir):
            strategies.append({"type": "global", "dir": global_dir})

    return strategies


def _get_date_from_file_times(config: dict, rel_path: str) -> Optional[str]:
    """Read the creation date of a note from the cached ``.file_times.json``."""
    if not os.path.isfile(_FILE_TIMES_PATH):
        return None
    try:
        with open(_FILE_TIMES_PATH, "r", encoding="utf-8") as f:
            times: Dict[str, str] = json.load(f)
        # .file_times.json uses paths relative to the vault root, but
        # rel_path is relative to source_root (e.g. "2 Notes/…").
        # Try with the notes_subdir prefix first.
        notes_subdir = config.get("source", {}).get("notes_subdir", "")
        for candidate in (rel_path, os.path.join(notes_subdir, rel_path)):
            val = times.get(candidate)
            if val:
                return val
        return None
    except (json.JSONDecodeError, OSError):
        return None


def _generate_file_times_cache(config: dict) -> None:
    """Scan the local vault (if accessible) and persist creation times for
    all ``.md`` files as ``.file_times.json``.

    This file is synced to the ``processed-cache`` branch so that CI
    runs can use the same timestamps.
    """
    vault = os.getenv("OBSIDIAN_VAULT_PATH") or ""
    if not vault:
        vault = config.get("processing", {}).get("local_vault_path", "")
    if not vault or not os.path.isdir(vault):
        print("Local vault not found; skipping .file_times.json generation")
        return

    print(f"Generating .file_times.json from vault: {vault}")
    times: Dict[str, str] = {}
    for filepath in Path(vault).rglob("*.md"):
        rel = filepath.relative_to(vault).as_posix()
        try:
            ts = filepath.stat().st_mtime
        except OSError:
            ts = filepath.stat().st_ctime
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        times[rel] = dt.strftime("%Y-%m-%d")

    with open(_FILE_TIMES_PATH, "w", encoding="utf-8") as f:
        json.dump(times, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {len(times)} entries to {_FILE_TIMES_PATH}")


def _save_processing_config(config: dict, config_path: str = "config.yaml") -> None:
    """Persist the in-memory config changes (e.g. force_reprocess_all) back
    to the YAML file on disk."""
    import yaml as _yaml
    with open(config_path, "w", encoding="utf-8") as f:
        _yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"Config written back to {config_path}")


def _to_slug(text: str) -> str:
    text = re.sub(r"[^\w\s\u4e00-\u9fff\-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text.lower()


def generate_navigation_json(content_dir: str = "content") -> None:
    """Scan the ``content/`` directory and write a tree-structured JSON
    to ``static/navigation.json`` for the sidebar tree navigation.

    The JSON structure:
    ::

        [
          {
            "title": "AI",
            "url": "/ai/",
            "children": [
              {
                "title": "0 基础",
                "children": [
                  { "title": "1 Agent基础必知必会", "url": "/ai/1-agent基础必知必会/" },
                  …
                ]
              },
              { "title": "link", "url": "/ai/link/" }
            ]
          },
          …
        ]
    """
    root = Path(content_dir)
    tree = _build_tree(root)
    nav_path = Path("static/navigation.json")
    nav_path.parent.mkdir(parents=True, exist_ok=True)
    with open(nav_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
    print(f"Wrote navigation tree ({_count_nodes(tree)} nodes) to {nav_path}")


def _build_tree(dir_path: Path) -> list:
    """Recursively build a navigation tree for *dir_path*."""
    nodes: list = []
    entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            children = _build_tree(entry)
            node: dict = {"title": entry.name}
            section = _get_section(entry)
            if section:
                node["url"] = f"/{section}/"
            if children:
                node["children"] = children
            if children or section:
                nodes.append(node)
        elif entry.suffix == ".md" and entry.name not in ("_index.md", "about.md"):
            name = entry.stem
            slug = _to_slug(name)
            section = _get_section(entry)
            url = f"/{section}/{slug}/" if section else f"/{slug}/"
            nodes.append({"title": name, "url": url})
    return nodes


def _get_section(path: Path) -> str:
    """Return the first content-directory segment for *path*, e.g. ``"AI"``
    for ``content/AI/0 基础/…``."""
    parts = path.relative_to("content").parts
    return parts[0] if parts else ""


def _count_nodes(nodes: list) -> int:
    """Count all leaf (url-carrying) nodes recursively."""
    count = 0
    for node in nodes:
        if "url" in node:
            count += 1
        if "children" in node:
            count += _count_nodes(node["children"])
    return count
