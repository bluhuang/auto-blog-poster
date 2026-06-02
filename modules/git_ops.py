from pathlib import Path
from typing import Optional


def pull_source_repo(config: dict) -> Optional[Path]:
    """Clone or pull the source Obsidian notes repository.

    Uses GH_PAT from environment to authenticate. Returns the local path
    to the cloned repository, or None on failure.
    """
    print("pull_source_repo: not yet implemented")
    return None


def push_output_repo(output_path: Path, config: dict) -> bool:
    """Commit and push the built Hugo site to the output repository."""
    print("push_output_repo: not yet implemented")
    return False
