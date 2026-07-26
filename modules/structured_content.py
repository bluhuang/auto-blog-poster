"""Protect Markdown structures that must survive LLM processing verbatim."""

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


PLACEHOLDER_RE = re.compile(r"@@PROTECTED_[A-F0-9]{12}_\d{4}@@")


@dataclass(frozen=True)
class ProtectedItem:
    placeholder: str
    original: str
    restored: str


class StructuredContentProtector:
    """Replace sensitive spans with unique, validated ASCII placeholders."""

    def __init__(self, content: str, replacements: Optional[Dict[str, str]] = None):
        self.content = content
        self.replacements = replacements or {}
        self.items: List[ProtectedItem] = []

    def protect(self) -> str:
        spans = self._find_spans()
        digest = hashlib.sha256(self.content.encode("utf-8")).hexdigest()[:12].upper()
        chunks: List[str] = []
        cursor = 0
        for index, (start, end) in enumerate(spans):
            original = self.content[start:end]
            placeholder = f"@@PROTECTED_{digest}_{index:04d}@@"
            restored = self.replacements.get(original, original)
            self.items.append(ProtectedItem(placeholder, original, restored))
            chunks.extend((self.content[cursor:start], placeholder))
            cursor = end
        chunks.append(self.content[cursor:])
        return "".join(chunks)

    def restore(self, processed: str) -> str:
        expected = {item.placeholder for item in self.items}
        found = PLACEHOLDER_RE.findall(processed)
        if len(found) != len(expected) or set(found) != expected:
            missing = sorted(expected - set(found))
            unexpected = sorted(set(found) - expected)
            raise ValueError(
                "Structured placeholder integrity check failed: "
                f"expected={len(expected)}, found={len(found)}, "
                f"missing={missing[:3]}, unexpected={unexpected[:3]}"
            )

        restored = processed
        for item in self.items:
            if restored.count(item.placeholder) != 1:
                raise ValueError(
                    f"Placeholder must occur exactly once: {item.placeholder}"
                )
            restored = restored.replace(item.placeholder, item.restored)

        remnants = PLACEHOLDER_RE.findall(restored)
        if remnants:
            raise ValueError(f"Unrestored placeholders remain: {remnants[:3]}")
        return restored

    def _find_spans(self) -> List[Tuple[int, int]]:
        patterns = [
            # Fenced code includes Mermaid and must take precedence over math.
            re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$"),
            # Obsidian embeds and standard Markdown images.
            re.compile(r"!\[\[[^\]\n]+\]\]"),
            re.compile(r"!\[[^\]\n]*\]\((?:\\.|[^)\n])+\)"),
            # HTML comments and block-level HTML.
            re.compile(r"(?s)<!--.*?-->"),
            re.compile(
                r"(?ims)^[ \t]*<(?:address|article|aside|blockquote|details|"
                r"dialog|div|dl|fieldset|figure|footer|form|h[1-6]|header|"
                r"hr|main|nav|ol|p|pre|script|section|style|summary|table|"
                r"ul)\b.*?</(?:address|article|aside|blockquote|details|"
                r"dialog|div|dl|fieldset|figure|footer|form|h[1-6]|header|"
                r"main|nav|ol|p|pre|script|section|style|summary|table|ul)>[ \t]*$"
            ),
            # Display math before inline math.
            re.compile(r"(?s)\$\$.*?\$\$"),
            re.compile(r"(?s)\\\[.*?\\\]"),
            re.compile(r"(?s)\\\(.*?\\\)"),
            # Single-dollar inline math (not escaped, not $$, no newline).
            re.compile(r"(?<!\\)(?<!\$)\$(?!\$)(?:\\.|[^$\n\\])+(?<!\\)\$(?!\$)"),
        ]

        candidates: List[Tuple[int, int, int]] = []
        for priority, pattern in enumerate(patterns):
            candidates.extend(
                (match.start(), match.end(), priority)
                for match in pattern.finditer(self.content)
            )
        candidates.sort(key=lambda value: (value[0], value[2], -(value[1] - value[0])))

        selected: List[Tuple[int, int]] = []
        cursor = -1
        for start, end, _priority in candidates:
            if start >= cursor:
                selected.append((start, end))
                cursor = end
        return selected


def validate_math_delimiters(content: str) -> None:
    """Reject unbalanced supported math delimiters outside fenced code."""
    without_fences = re.sub(
        r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", "", content
    )
    errors: List[str] = []
    if len(re.findall(r"(?<!\\)\$\$", without_fences)) % 2:
        errors.append("$$")
    for opening, closing, label in (
        (r"\\\(", r"\\\)", r"\(...\)"),
        (r"\\\[", r"\\\]", r"\[...\]"),
    ):
        if len(re.findall(opening, without_fences)) != len(
            re.findall(closing, without_fences)
        ):
            errors.append(label)
    if errors:
        raise ValueError(f"Unbalanced math delimiters: {', '.join(errors)}")


def normalize_math_delimiters(content: str) -> str:
    """Put display delimiters on canonical lines for Goldmark passthrough."""
    fence_pattern = re.compile(
        r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$"
    )
    chunks: List[str] = []
    cursor = 0
    for fence in fence_pattern.finditer(content):
        chunks.append(_normalize_prose_math(content[cursor:fence.start()]))
        chunks.append(fence.group(0))
        cursor = fence.end()
    chunks.append(_normalize_prose_math(content[cursor:]))
    return "".join(chunks)


def _normalize_prose_math(content: str) -> str:
    """Normalize display math in prose, including Obsidian block quotes."""
    display_pattern = re.compile(r"(?s)(\$\$|\\\[).*?(\$\$|\\\])")

    # Work backwards so replacing a complete line range cannot invalidate later
    # match offsets. A quoted display formula becomes a normal top-level block.
    matches = list(display_pattern.finditer(content))
    for match in reversed(matches):
        line_start = content.rfind("\n", 0, match.start()) + 1
        line_end_pos = content.find("\n", match.end())
        line_end = len(content) if line_end_pos == -1 else line_end_pos
        block = content[line_start:line_end]
        lines = block.splitlines()
        nonempty = [line for line in lines if line.strip()]
        if nonempty and all(re.match(r"^[ \t]*>[ \t]?", line) for line in nonempty):
            normalized = "\n".join(
                re.sub(r"^[ \t]*>[ \t]?", "", line, count=1)
                if line.strip()
                else line
                for line in lines
            )
            content = content[:line_start] + normalized + content[line_end:]

    content = re.sub(
        r"(?m)^[ \t]*(\$\$|\\\[|\\\])[ \t]*(?:  )?$",
        lambda match: match.group(1),
        content,
    )
    for opening, closing in ((r"\$\$", r"\$\$"), (r"\\\[", r"\\\]")):
        pattern = re.compile(rf"(?s)({opening})\n?(.*?)(?:\n)?({closing})")

        def compact(match: re.Match) -> str:
            inner = re.sub(r"\n[ \t]*\n+", "\n", match.group(2)).strip()
            return f"{match.group(1)}\n{inner}\n{match.group(3)}"

        content = pattern.sub(compact, content)
    return content
