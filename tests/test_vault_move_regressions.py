import json
import os
import tempfile
import unittest
from pathlib import Path

from modules.content_processor import compute_processing_hash
from modules.rename_migrator import migrate_cache_preserving_renames
from modules.section_processor import _make_code_cross_platform


class VaultMoveRegressionTests(unittest.TestCase):
    def test_stale_note_path_maps_to_current_note(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_root = Path(temporary_directory) / "2 Notes"
            current_note = (
                source_root
                / "AI"
                / "0 Paper"
                / "GAN"
                / "1  GAN - Generative Adversarial Nets.md"
            )
            current_note.parent.mkdir(parents=True)
            current_note.write_text("# GAN\n", encoding="utf-8")
            code = (
                "from pathlib import Path\n"
                "note_path = Path(\"D:/bluhuang/notes/blu-obsidian-main/"
                "2 Notes/AI/0 Paper/CV/GAN Generative Adversarial Nets.md\")\n"
                "output_dir = note_path.parent / \"attachments\"\n"
            )
            mapped, replacements = _make_code_cross_platform(
                code,
                str(current_note),
                str(source_root),
                {
                    "source": {"notes_subdir": "2 Notes"},
                    "processing": {
                        "code_execution": {"auto_map_windows_notes_root": True}
                    },
                },
            )
            self.assertEqual(replacements, 1)
            self.assertIn(str(current_note.resolve()), mapped)
            self.assertNotIn("AI/0 Paper/CV", mapped)

    def test_exact_content_move_preserves_generated_output_and_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                source_root = root / "source"
                content_root = root / "content"
                old_path = "z_mixed/skills/Example.md"
                new_path = "Workflow and Tools/skills/Example.md"
                new_source = source_root.joinpath(*Path(new_path).parts)
                new_source.parent.mkdir(parents=True)
                new_source.write_text("# Example\n\nUnchanged body.\n", encoding="utf-8")

                processing_hash = compute_processing_hash(str(new_source))
                hash_cache = root / ".hash_cache.json"
                hash_cache.write_text(
                    json.dumps(
                        {old_path: {"hash": processing_hash, "mtime": "2026-07-01"}},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                old_output = content_root.joinpath(*Path(old_path).parts)
                old_output.parent.mkdir(parents=True)
                old_output.write_text(
                    "---\n"
                    "title: \"Example\"\n"
                    "categories: [\"z_mixed\"]\n"
                    "---\n\n"
                    "Edited body.\n",
                    encoding="utf-8",
                )

                deepseek_cache = root / ".deepseek_cache.json"
                deepseek_cache.write_text(
                    json.dumps(
                        {old_path: {"key": "cache-key", "response": "Edited body."}},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                Path(".file_times.json").write_text(
                    json.dumps(
                        {
                            old_path: "2026-07-01T00:00:00+0800",
                            f"2 Notes/{old_path}": "2026-07-01T00:00:00+0800",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                migrations = migrate_cache_preserving_renames(
                    str(source_root),
                    {
                        "source": {"notes_subdir": "2 Notes"},
                        "output": {"content_dir": str(content_root)},
                        "processing": {
                            "deepseek_cache_file": str(deepseek_cache)
                        },
                    },
                    str(hash_cache),
                )

                self.assertEqual(migrations, [(old_path, new_path)])
                new_output = content_root.joinpath(*Path(new_path).parts)
                self.assertTrue(new_output.is_file())
                self.assertFalse(old_output.exists())
                self.assertIn(
                    'categories: ["Workflow and Tools"]',
                    new_output.read_text(encoding="utf-8"),
                )

                migrated_hash_cache = json.loads(hash_cache.read_text(encoding="utf-8"))
                self.assertIn(new_path, migrated_hash_cache)
                self.assertNotIn(old_path, migrated_hash_cache)

                migrated_deepseek_cache = json.loads(
                    deepseek_cache.read_text(encoding="utf-8")
                )
                self.assertIn(new_path, migrated_deepseek_cache)
                self.assertNotIn(old_path, migrated_deepseek_cache)

                migrated_times = json.loads(
                    Path(".file_times.json").read_text(encoding="utf-8")
                )
                self.assertIn(new_path, migrated_times)
                self.assertIn(f"2 Notes/{new_path}", migrated_times)
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
