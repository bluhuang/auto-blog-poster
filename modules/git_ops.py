import os
import subprocess
from pathlib import Path


def pull_source_repo(config: dict) -> Path:
    """Clone or pull the source Obsidian notes repository.

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

    if not os.path.isdir(temp_dir):
        print(f"Cloning {repository} to {temp_dir} ...")
        subprocess.run(
            ["git", "clone", clone_url, temp_dir],
            check=True,
            timeout=60,
        )
    else:
        print(f"Pulling latest changes for {repository} ...")
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=temp_dir,
            check=True,
            timeout=60,
        )
        subprocess.run(
            ["git", "checkout", branch],
            cwd=temp_dir,
            check=True,
            timeout=60,
        )
        subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=temp_dir,
            check=True,
            timeout=60,
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
