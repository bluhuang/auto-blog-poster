import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


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

    Returns an empty dict if the file does not exist or is unreadable.
    The cache maps relative file paths (forward-slash) to their last-known MD5.
    """
    if not os.path.isfile(cache_path):
        print(f"Cache file not found, starting fresh: {cache_path}")
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache: Dict[str, str] = json.load(f)
        print(f"Loaded hash cache with {len(cache)} entries from {cache_path}")
        return cache
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: failed to load cache file ({e}), starting fresh")
        return {}


def save_hash_cache(cache_path: str, cache: Dict[str, str]) -> None:
    """Persist the hash cache dict to a JSON file on disk."""
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    print(f"Saved hash cache with {len(cache)} entries to {cache_path}")


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
