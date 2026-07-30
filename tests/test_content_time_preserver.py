import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from modules.content_time_preserver import get_last_content_change_time


class ContentTimePreserverTests(unittest.TestCase):
    def _run(self, root: Path, *args: str, env: dict | None = None) -> None:
        subprocess.run(
            list(args),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def _commit(self, root: Path, message: str, date: str) -> None:
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
        self._run(root, "git", "add", "-A", env=env)
        self._run(root, "git", "commit", "-m", message, env=env)

    def test_pure_move_does_not_change_last_content_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._run(root, "git", "init")
            self._run(root, "git", "config", "user.name", "Test")
            self._run(root, "git", "config", "user.email", "test@example.com")

            original = root / "2 Notes" / "Old Folder" / "Note.md"
            original.parent.mkdir(parents=True)
            original.write_text("# Note\n\nOriginal content.\n", encoding="utf-8")
            self._commit(root, "Add note", "2026-01-02T03:04:05+0000")

            moved = root / "2 Notes" / "New Folder" / "Note.md"
            moved.parent.mkdir(parents=True)
            self._run(root, "git", "mv", str(original.relative_to(root)), str(moved.relative_to(root)))
            self._commit(root, "Move note only", "2026-02-03T04:05:06+0000")

            timestamp = get_last_content_change_time(root.as_posix(), moved.relative_to(root).as_posix())
            self.assertEqual(timestamp, "2026-01-02T03:04:05+0000")

            moved.write_text("# Note\n\nActually updated content.\n", encoding="utf-8")
            self._commit(root, "Edit note", "2026-03-04T05:06:07+0000")

            timestamp = get_last_content_change_time(root.as_posix(), moved.relative_to(root).as_posix())
            self.assertEqual(timestamp, "2026-03-04T05:06:07+0000")


if __name__ == "__main__":
    unittest.main()
