"""Configurable processing for Markdown sections identified by headings."""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Dict, List, Tuple


HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE_START_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})([^`]*)$")


def process_configured_sections(
    content: str,
    source_path: str,
    source_root: str,
    config: dict,
) -> str:
    """Run configured actions and return the publication-only Markdown."""
    rules = config.get("processing", {}).get("section_rules", [])
    if not rules:
        return content

    sections = _find_sections(content)
    removals: List[Tuple[int, int]] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        match_cfg = rule.get("match", {})
        title = match_cfg.get("title")
        if not title:
            print(
                f"  Warning: section rule {rule.get('name', '<unnamed>')} "
                "has no match.title; skipping"
            )
            continue
        level = int(match_cfg.get("level", 1))
        case_sensitive = bool(match_cfg.get("case_sensitive", False))
        expected = title if case_sensitive else title.casefold()

        for section in sections:
            actual = section["title"]
            comparable = actual if case_sensitive else actual.casefold()
            if section["level"] != level or comparable != expected:
                continue
            section_text = content[section["start"]:section["end"]]
            print(f"  [section] matched rule {rule.get('name', title)}: {actual}")
            for action in rule.get("actions", []):
                action_type = action.get("type")
                if action_type == "execute_code":
                    _execute_code_blocks(
                        section_text, source_path, source_root, config, action
                    )
                elif action_type == "exclude_from_blog":
                    removals.append((section["start"], section["end"]))
                else:
                    raise ValueError(
                        f"Unknown section action {action_type!r} in rule "
                        f"{rule.get('name', title)!r}"
                    )

    for start, end in sorted(set(removals), reverse=True):
        content = content[:start] + content[end:]
    if removals:
        print(f"  [section] excluded {len(set(removals))} section(s) from blog")
    return content.rstrip() + "\n"


def _find_sections(content: str) -> List[Dict[str, object]]:
    lines = content.splitlines(keepends=True)
    headings: List[Dict[str, object]] = []
    offset = 0
    fence_marker = ""
    for line in lines:
        stripped = line.rstrip("\r\n")
        if fence_marker:
            if re.match(rf"^[ \t]*{re.escape(fence_marker)}[ \t]*$", stripped):
                fence_marker = ""
            offset += len(line)
            continue
        fence_match = FENCE_START_RE.match(stripped)
        if fence_match:
            fence_marker = fence_match.group(1)
            offset += len(line)
            continue
        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            headings.append(
                {
                    "start": offset,
                    "level": len(heading_match.group(1)),
                    "title": heading_match.group(2).strip(),
                }
            )
        offset += len(line)

    for index, heading in enumerate(headings):
        end = len(content)
        for candidate in headings[index + 1:]:
            if candidate["level"] <= heading["level"]:
                end = int(candidate["start"])
                break
        heading["end"] = end
    return headings


def _execute_code_blocks(
    section: str,
    source_path: str,
    source_root: str,
    config: dict,
    action: dict,
) -> None:
    language = action.get("language", "python")
    fences = action.get("fence_languages", [language, f"run-{language}"])
    code_blocks = _extract_fenced_code(section, fences)
    if not code_blocks:
        raise ValueError(
            f"Section action execute_code found no {fences} fenced code blocks"
        )

    timeout = int(action.get("timeout_seconds", 120))
    execution_cfg = config.get("processing", {}).get("code_execution", {})
    environment = os.environ.copy()
    environment.update(
        {
            str(key): str(value)
            for key, value in execution_cfg.get("environment", {}).items()
        }
    )
    note_dir = str(Path(source_path).parent)

    for index, code in enumerate(code_blocks, start=1):
        compatible_code, replacements = _make_code_cross_platform(
            code, source_path, source_root, config
        )
        if replacements:
            print(
                f"  [section] remapped {replacements} Windows path(s) "
                f"in code block {index}"
            )
        print(
            f"  [section] executing {language} block "
            f"{index}/{len(code_blocks)} ..."
        )
        result = subprocess.run(
            [sys.executable, "-c", compatible_code],
            cwd=note_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Code block {index} failed with exit code {result.returncode}.\n"
                f"STDOUT: {result.stdout[-1000:]}\n"
                f"STDERR: {result.stderr[-2000:]}"
            )
        if result.stdout.strip():
            print(f"  [section] output: {result.stdout.strip()[-300:]}")


def _extract_fenced_code(section: str, languages: List[str]) -> List[str]:
    accepted = {language.casefold() for language in languages}
    blocks: List[str] = []
    lines = section.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        match = FENCE_START_RE.match(lines[index].rstrip("\r\n"))
        if not match:
            index += 1
            continue
        marker = match.group(1)
        info = match.group(2).strip().split(maxsplit=1)[0].casefold()
        index += 1
        code_lines: List[str] = []
        while index < len(lines):
            if re.match(
                rf"^[ \t]*{re.escape(marker)}[ \t]*$",
                lines[index].rstrip("\r\n"),
            ):
                break
            code_lines.append(lines[index])
            index += 1
        if info in accepted:
            blocks.append("".join(code_lines))
        index += 1
    return blocks


def _normalize_note_stem(stem: str) -> str:
    stem = re.sub(r"^\d+\s*[-.]?\s*", "", stem.casefold())
    return re.sub(r"[^\w]+", "", stem, flags=re.UNICODE)


def _make_code_cross_platform(
    code: str, source_path: str, source_root: str, config: dict
) -> Tuple[str, int]:
    if not config.get("processing", {}).get("code_execution", {}).get(
        "auto_map_windows_notes_root", True
    ):
        return code, 0

    notes_subdir = config.get("source", {}).get("notes_subdir", "")
    marker_parts = [
        part.casefold()
        for part in PureWindowsPath(notes_subdir.replace("/", "\\")).parts
        if part not in ("\\", "/")
    ]
    if not marker_parts:
        return code, 0

    tree = ast.parse(code)
    replacement_count = 0
    current_note = Path(source_path).resolve()
    current_stem = _normalize_note_stem(current_note.stem)

    class WindowsPathMapper(ast.NodeTransformer):
        def visit_Constant(self, node: ast.Constant) -> ast.AST:
            nonlocal replacement_count
            if not isinstance(node.value, str):
                return node
            windows_path = PureWindowsPath(node.value)
            if not windows_path.is_absolute():
                return node
            parts = list(windows_path.parts)
            folded = [part.casefold() for part in parts]
            marker_index = _find_subsequence(folded, marker_parts)
            if marker_index < 0:
                return node

            old_stem = _normalize_note_stem(windows_path.stem)
            if (
                windows_path.suffix.casefold() == ".md"
                and old_stem
                and current_stem
                and (
                    old_stem == current_stem
                    or old_stem in current_stem
                    or current_stem in old_stem
                )
            ):
                mapped = str(current_note)
            else:
                relative_parts = parts[marker_index + len(marker_parts):]
                mapped = str(Path(source_root).joinpath(*relative_parts))
            replacement_count += 1
            return ast.copy_location(ast.Constant(value=mapped), node)

    mapped_tree = WindowsPathMapper().visit(tree)
    ast.fix_missing_locations(mapped_tree)
    return ast.unparse(mapped_tree), replacement_count


def _find_subsequence(values: List[str], expected: List[str]) -> int:
    width = len(expected)
    for index in range(len(values) - width + 1):
        if values[index:index + width] == expected:
            return index
    return -1
