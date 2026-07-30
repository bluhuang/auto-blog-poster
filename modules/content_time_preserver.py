"""Keep recent-update timestamps tied to content edits, not path-only moves."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional


_FILE_TIMES_PATH = ".file_times.json"
_DATE_MARKER = "@@CONTENT_DATE@@"


def _format_git_date(raw: str) -> Optional[str]:
    parts = raw.strip().split()
    if len(parts) < 3:
        return None
    timezone = parts[2].replace(":", "")
    return f"{parts[0]}T{parts[1]}{timezone}"


def get_last_content_change_time(repo_root: str, file_rel_path: str) -> Optional[str]:
    """Return the newest commit time that changed Markdown content.

    Exact renames and folder moves normally appear in ``--numstat`` as
    ``0 0 old => new``. Those commits are skipped, while any commit with real
    added or deleted lines remains a content update.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                repo_root,
                "log",
                "--follow",
                "--find-renames=100%",
                f"--format={_DATE_MARKER}%ai",
                "--numstat",
                "--",
                file_rel_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    current_date: Optional[str] = None
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if line.startswith(_DATE_MARKER):
            current_date = _format_git_date(line[len(_DATE_MARKER):])
            continue
        if not current_date or not line:
            continue
        columns = line.split("\t", 2)
        if len(columns) < 3 or not columns[0].isdigit() or not columns[1].isdigit():
            continue
        if int(columns[0]) + int(columns[1]) > 0:
            return current_date
    return None


def _load_times() -> Dict[str, str]:
    if not os.path.isfile(_FILE_TIMES_PATH):
        return {}
    try:
        value = json.loads(Path(_FILE_TIMES_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _existing_time(times: Dict[str, str], rel_path: str, notes_subdir: str) -> Optional[str]:
    candidates = [rel_path]
    if notes_subdir:
        candidates.insert(0, f"{notes_subdir.strip('/')}/{rel_path}")
    for candidate in candidates:
        value = times.get(candidate)
        if isinstance(value, str) and value:
            return value
    return None


def _rewrite_lastmod(content_path: Path, timestamp: str) -> bool:
    if not content_path.is_file():
        return False
    try:
        content = content_path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not content.startswith("---"):
        return False
    end = content.find("\n---", 3)
    if end < 0:
        return False
    front_matter = content[:end]
    if re.search(r"(?m)^lastmod:\s*.*$", front_matter):
        updated = re.sub(
            r"(?m)^lastmod:\s*.*$",
            f"lastmod: {timestamp}",
            front_matter,
            count=1,
        )
    else:
        updated = front_matter + f"\nlastmod: {timestamp}"
    if updated == front_matter:
        return False
    try:
        content_path.write_text(updated + content[end:], encoding="utf-8")
    except OSError:
        return False
    return True


def reconcile_content_update_times(source_root: str, config: dict) -> int:
    """Rebuild ``lastmod`` from content-changing commits and update outputs.

    The existing ``date`` field remains untouched. ``lastmod`` is corrected in
    both ``.file_times.json`` and generated Hugo front matter before the site is
    built, so pure renames never affect the recent-update order.
    """
    repo_root = config.get("_source_repo_dir", "")
    if not repo_root or not os.path.isdir(os.path.join(repo_root, ".git")):
        raise RuntimeError("Source Git repository is unavailable for content-time reconciliation")

    source = Path(source_root)
    content_dir = Path(config.get("output", {}).get("content_dir", "content"))
    notes_subdir = config.get("source", {}).get("notes_subdir", "").strip("/")
    previous_times = _load_times()
    reconciled_times: Dict[str, str] = {}
    rewritten = 0

    for source_path in sorted(source.rglob("*.md")):
        rel_path = source_path.relative_to(source).as_posix()
        repo_rel_path = source_path.relative_to(Path(repo_root)).as_posix()
        timestamp = get_last_content_change_time(repo_root, repo_rel_path)
        if timestamp is None:
            timestamp = _existing_time(previous_times, rel_path, notes_subdir)
        if timestamp is None:
            continue

        cache_key = f"{notes_subdir}/{rel_path}" if notes_subdir else rel_path
        reconciled_times[cache_key] = timestamp
        output_path = content_dir.joinpath(*Path(rel_path).parts)
        if _rewrite_lastmod(output_path, timestamp):
            rewritten += 1

    Path(_FILE_TIMES_PATH).write_text(
        json.dumps(reconciled_times, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"Reconciled content-update time for {len(reconciled_times)} note(s); "
        f"rewrote {rewritten} front matter file(s)."
    )
    return len(reconciled_times)
