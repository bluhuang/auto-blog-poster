import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def pull_source_repo(config: dict) -> Path:
    """Clone the source Obsidian notes repository using shallow clone and
    sparse checkout — only the configured notes subdirectory is fetched.

    Uses GH_PAT from environment to authenticate. Returns the absolute path
    to the notes subdirectory (e.g. .temp/source_repo/2 Notes).

    Raises ValueError if GH_PAT is missing.
    Raises RuntimeError if the notes subdirectory is not found after clone.
    """
    source_cfg = config["source"]
    repository = f"{source_cfg['owner']}/{source_cfg['repo']}"
    branch = source_cfg["branch"]
    notes_subdir = source_cfg["notes_subdir"]

    token = os.getenv("GH_PAT")
    if not token:
        raise ValueError("Missing GH_PAT environment variable")

    temp_dir = os.path.join(".temp", "source_repo")
    clone_url = f"https://{token}@github.com/{repository}.git"

    # Always start fresh to ensure consistent shallow-clone state
    if os.path.isdir(temp_dir):
        print(f"Removing previous clone: {temp_dir}")
        shutil.rmtree(temp_dir)

    print(f"Shallow cloning {repository} (branch={branch}, sparse)...")
    subprocess.run(
        [
            "git", "clone",
            "--depth", "1",
            "--filter=blob:none",
            "--sparse",
            "--branch", branch,
            clone_url,
            temp_dir,
        ],
        check=True,
        timeout=120,
    )

    print(f"Setting sparse-checkout to: {notes_subdir}")
    subprocess.run(
        ["git", "-C", temp_dir, "sparse-checkout", "set", notes_subdir],
        check=True,
        timeout=30,
    )

    notes_path = os.path.join(temp_dir, notes_subdir)
    if not os.path.isdir(notes_path):
        raise RuntimeError(f"Notes subdirectory not found: {notes_path}")

    print(f"Source notes ready at: {notes_path}")
    return Path(os.path.abspath(notes_path))


def push_output_repo(output_path: Path, config: dict) -> bool:
    """Commit and push the built Hugo site to the output repository."""
    print("push_output_repo: not yet implemented")
    return False


def get_file_first_commit_time(repo_path: str, file_rel_path: str) -> str:
    """Return the first commit date for a file as an ISO-8601 string.

    Uses ``git log --follow --format=%ai --reverse`` to obtain the
    creation date.  Falls back to ``os.path.getmtime`` on failure.
    """
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--follow",
             "--format=%ai", "--reverse", file_rel_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            raw = lines[0].strip()
            # Convert "2025-01-15 10:30:00 +0800" → "2025-01-15T10:30:00+08:00"
            # git log --format=%ai outputs: "2026-06-03 10:30:00 +0000"
            date_part = raw.strip().split(" ")[0]  # just "2026-06-03"
            return date_part
    except (subprocess.SubprocessError, OSError):
        pass

    full_path = os.path.join(repo_path, file_rel_path)
    if os.path.isfile(full_path):
        ts = os.path.getmtime(full_path)
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d")

    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")


def get_obsidian_attachment_config(repo_path: str) -> Optional[str]:
    """Read the ``attachmentFolderPath`` from ``.obsidian/app.json``.

    Args:
        repo_path: Root of the cloned Obsidian repository (contains ``.obsidian/``).

    Returns:
        The configured path (e.g. ``"./attachments"``) or ``None`` if
        the file / key does not exist.
    """
    app_json = os.path.join(repo_path, ".obsidian", "app.json")
    if not os.path.isfile(app_json):
        return None
    try:
        with open(app_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("attachmentFolderPath")
    except (json.JSONDecodeError, OSError):
        return None
