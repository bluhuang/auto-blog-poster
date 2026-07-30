"""Preserve generated content and caches when source notes only move paths."""

from __future__ import annotations

import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Tuple

from modules.content_processor import compute_processing_hash


_FILE_TIMES_PATH = ".file_times.json"


def _load_json_dict(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file:
            value = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save_json_dict(path: str, value: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, ensure_ascii=False, sort_keys=True)


def _entry_hash(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("hash"), str):
        return value["hash"]
    return ""


def _content_path(content_dir: str, rel_path: str) -> Path:
    return Path(content_dir).joinpath(*PurePosixPath(rel_path).parts)


def _rewrite_front_matter_category(content: str, rel_path: str) -> str:
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    if end < 0:
        return content
    category = PurePosixPath(rel_path).parts[0]
    front_matter = content[:end]
    replacement = f"categories: {json.dumps([category], ensure_ascii=False)}"
    if re.search(r"(?m)^categories:\s*.*$", front_matter):
        front_matter = re.sub(
            r"(?m)^categories:\s*.*$", replacement, front_matter, count=1
        )
    return front_matter + content[end:]


def _move_generated_content(content_dir: str, old_path: str, new_path: str) -> bool:
    old_content = _content_path(content_dir, old_path)
    new_content = _content_path(content_dir, new_path)
    if not old_content.is_file() or new_content.exists():
        return False

    text = old_content.read_text(encoding="utf-8")
    text = _rewrite_front_matter_category(text, new_path)
    new_content.parent.mkdir(parents=True, exist_ok=True)
    new_content.write_text(text, encoding="utf-8")
    old_content.unlink()
    return True


def _migrate_file_time_key(
    file_times: Dict[str, Any], old_path: str, new_path: str, notes_subdir: str
) -> None:
    candidates: List[Tuple[str, str]] = [(old_path, new_path)]
    if notes_subdir:
        prefix = notes_subdir.strip("/")
        candidates.append((f"{prefix}/{old_path}", f"{prefix}/{new_path}"))
    for old_key, new_key in candidates:
        if old_key in file_times and new_key not in file_times:
            file_times[new_key] = file_times.pop(old_key)


def _remove_empty_section_directories(content_dir: str) -> None:
    root = Path(content_dir)
    if not root.is_dir():
        return
    for current_root, directories, files in os.walk(root, topdown=False):
        current = Path(current_root)
        if current == root:
            continue
        remaining_directories = [name for name in directories if (current / name).exists()]
        remaining_files = [name for name in files if (current / name).exists()]
        if remaining_directories:
            continue
        if set(remaining_files).issubset({"_index.md"}):
            index = current / "_index.md"
            if index.exists():
                index.unlink()
            try:
                current.rmdir()
            except OSError:
                pass


def migrate_cache_preserving_renames(
    source_root: str,
    config: dict,
    hash_cache_path: str = ".hash_cache.json",
) -> List[Tuple[str, str]]:
    """Migrate exact-content note moves before incremental processing.

    The migration is deliberately conservative: a move is accepted only when
    one missing cached path and one new source path share one unique processing
    hash, the old generated Markdown exists, and the new generated path does
    not. Changed or ambiguous notes continue through the normal processing path.
    """

    raw_hash_cache = _load_json_dict(hash_cache_path)
    if not raw_hash_cache:
        return []

    source = Path(source_root)
    current_paths = sorted(
        path.relative_to(source).as_posix() for path in source.rglob("*.md")
    )
    current_set = set(current_paths)
    old_set = set(raw_hash_cache)
    new_paths = sorted(current_set - old_set)
    missing_paths = sorted(old_set - current_set)
    if not new_paths or not missing_paths:
        return []

    old_by_hash: Dict[str, List[str]] = defaultdict(list)
    for rel_path in missing_paths:
        value_hash = _entry_hash(raw_hash_cache.get(rel_path))
        if value_hash:
            old_by_hash[value_hash].append(rel_path)

    new_by_hash: Dict[str, List[str]] = defaultdict(list)
    for rel_path in new_paths:
        value_hash = compute_processing_hash(str(source / PurePosixPath(rel_path)))
        new_by_hash[value_hash].append(rel_path)

    content_dir = config.get("output", {}).get("content_dir", "content")
    deepseek_cache_path = config.get("processing", {}).get(
        "deepseek_cache_file", ".deepseek_cache.json"
    )
    deepseek_cache = _load_json_dict(deepseek_cache_path)
    file_times = _load_json_dict(_FILE_TIMES_PATH)
    notes_subdir = config.get("source", {}).get("notes_subdir", "")

    migrations: List[Tuple[str, str]] = []
    for value_hash, old_matches in sorted(old_by_hash.items()):
        new_matches = new_by_hash.get(value_hash, [])
        if len(old_matches) != 1 or len(new_matches) != 1:
            continue
        old_path = old_matches[0]
        new_path = new_matches[0]
        if not _move_generated_content(content_dir, old_path, new_path):
            continue

        raw_hash_cache[new_path] = raw_hash_cache.pop(old_path)
        if old_path in deepseek_cache and new_path not in deepseek_cache:
            deepseek_cache[new_path] = deepseek_cache.pop(old_path)
        _migrate_file_time_key(file_times, old_path, new_path, notes_subdir)
        migrations.append((old_path, new_path))
        print(f"  [rename] preserved cache: {old_path} -> {new_path}")

    if migrations:
        _save_json_dict(hash_cache_path, raw_hash_cache)
        _save_json_dict(deepseek_cache_path, deepseek_cache)
        if file_times:
            _save_json_dict(_FILE_TIMES_PATH, file_times)
        _remove_empty_section_directories(content_dir)
        print(f"Preserved generated content for {len(migrations)} renamed note(s).")

    return migrations
