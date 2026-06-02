import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Tuple


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


def process_single_note(
    source_path: str,
    rel_path: str,
    config: dict,
    deepseek_client_func: Callable[[str, dict], str],
) -> bool:
    """Read a source note, call the DeepSeek API, and write the result to the
    Hugo content directory.

    Args:
        source_path: Absolute path to the source .md file.
        rel_path: Relative path of the note, preserved in the output directory.
        config: Full application configuration dict.
        deepseek_client_func: Callable ``(content: str, config: dict) -> str``
            that returns the processed text.  Must raise on API failure.

    Returns:
        True on success.

    Raises:
        Exception: If the DeepSeek client returns None/empty or raises.
    """
    print(f"Processing: {rel_path} ...")

    with open(source_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    processed = deepseek_client_func(raw_content, config)
    if not processed:
        raise Exception(
            f"DeepSeek API returned empty result for: {source_path}"
        )

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
    to_process, to_delete = get_files_to_process(source_root, hash_cache_path)

    for rel_path in to_process:
        source_path = os.path.join(source_root, rel_path)
        try:
            process_single_note(source_path, rel_path, config, deepseek_client_func)
        except Exception:
            print(f"ERROR: DeepSeek API call failed for {rel_path}, aborting.")
            raise

    if to_delete:
        content_dir = config.get("output", {}).get("content_dir", "content")
        for rel_path in to_delete:
            dest_path = os.path.join(content_dir, rel_path)
            if os.path.isfile(dest_path):
                os.remove(dest_path)
                print(f"Deleted: {dest_path}")

    new_cache: Dict[str, str] = {}
    for rel_path in scan_md_files(source_root):
        abs_path = os.path.join(source_root, rel_path)
        new_cache[rel_path] = compute_md5(abs_path)
    save_hash_cache(hash_cache_path, new_cache)

    print("Processing complete.")
