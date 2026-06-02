import json
from pathlib import Path
from typing import List, Dict, Set


def _load_cache(config: dict) -> Dict[str, str]:
    """Load the hash cache from disk.

    The cache maps relative file paths to their last-known content hash.
    """
    cache_file = Path(config["processing"]["cache_file"])
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(notes: List[Dict], config: dict) -> None:
    """Persist the hash cache to disk."""
    cache_file = Path(config["processing"]["cache_file"])
    cache = {note["path"]: note.get("hash", "") for note in notes}
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    print(f"save_cache: wrote {len(cache)} entries")


def _compute_hash(content: str) -> str:
    """Return a stable hash for the given content string."""
    import hashlib
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def filter_new_notes(notes: List[Dict], config: dict) -> List[Dict]:
    """Return only notes whose content has changed since the last run.

    Uses a hash cache stored at ``config['processing']['cache_file']``.
    Notes that are new or modified are returned; unchanged notes are
    skipped so that the DeepSeek API is only called for deltas.
    """
    if not config["processing"].get("incremental", True):
        return notes

    cache = _load_cache(config)
    result: List[Dict] = []
    for note in notes:
        current_hash = _compute_hash(note.get("content", ""))
        note["hash"] = current_hash
        cached_hash = cache.get(note.get("path", ""))
        if cached_hash != current_hash:
            result.append(note)
    return result
