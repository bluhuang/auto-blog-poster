from pathlib import Path
from typing import List, Dict


def parse_notes(source_path: Path, config: dict) -> List[Dict]:
    """Scan the source directory for markdown files and parse frontmatter.

    Returns a list of dicts with keys: 'path', 'frontmatter', 'content'.
    """
    print("parse_notes: not yet implemented")
    return []


def extract_frontmatter(file_path: Path) -> Dict:
    """Extract YAML frontmatter from a markdown file."""
    print("extract_frontmatter: not yet implemented")
    return {}
