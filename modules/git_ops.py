import json
import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path
from typing import Optional


def _git_version() -> tuple:
    """Return (major, minor) git version tuple, e.g. (2, 25)."""
    out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


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
    clone_url = _authenticated_clone_url(repository, token)

    # Always start fresh to ensure consistent shallow-clone state
    if os.path.isdir(temp_dir):
        print(f"Removing previous clone: {temp_dir}")
        shutil.rmtree(temp_dir)

    print(f"Cloning {repository} (branch={branch}, full history)...")
    clone_cmd = [
        "git", "clone",
        "--branch", branch,
        clone_url,
        temp_dir,
    ]
    git_ver = _git_version()
    if git_ver >= (2, 25):
        clone_cmd.insert(2, "--filter=blob:none")
    try:
        subprocess.run(clone_cmd, check=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        # Do not include the authenticated URL (and therefore GH_PAT) in the
        # exception propagated to CI logs.
        raise RuntimeError(
            f"Failed to clone private source repository {repository}"
        ) from exc

    notes_path = os.path.join(temp_dir, notes_subdir)
    if not os.path.isdir(notes_path):
        raise RuntimeError(f"Notes subdirectory not found: {notes_path}")

    print(f"Source notes ready at: {notes_path}")
    return Path(os.path.abspath(notes_path))


def _authenticated_clone_url(repository: str, token: str) -> str:
    """Build GitHub's documented PAT-over-HTTPS clone URL."""
    encoded_token = urllib.parse.quote(token, safe="")
    return (
        f"https://x-access-token:{encoded_token}@github.com/"
        f"{repository}.git"
    )


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
            # git log --format=%ai outputs: "2026-06-03 10:30:00 +0000"
            # Convert to ISO-8601: "2026-06-03T10:30:00+0000"
            parts = raw.strip().split()
            if len(parts) >= 3:
                tz = parts[2].replace(":", "")
                return f"{parts[0]}T{parts[1]}{tz}"
            return raw.strip().split(" ")[0]
    except (subprocess.SubprocessError, OSError):
        pass

    full_path = os.path.join(repo_path, file_rel_path)
    if os.path.isfile(full_path):
        ts = os.path.getmtime(full_path)
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


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


def get_attachment_folder(repo_root: str, notes_subdir: str = "2 Notes") -> Optional[str]:
    """Auto-detect Obsidian attachment folder from ``.obsidian/app.json``.

    Tries the repo root first, then the notes subdirectory.

    Args:
        repo_root: Root of the cloned repository.
        notes_subdir: Notes subdirectory name (default ``"2 Notes"``).

    Returns:
        The configured ``attachmentFolderPath`` value, or ``None``.
    """
    cfg = get_obsidian_attachment_config(repo_root)
    if cfg is None:
        cfg = get_obsidian_attachment_config(
            os.path.join(repo_root, notes_subdir)
        )
    return cfg
