from __future__ import annotations

"""
Feishu Format Check Plugin — auto-fix LLM output for Feishu compatibility.

Fires on the transform_llm_output hook: after the tool-calling loop completes
and the model produces a final response, before that response is delivered.

What it does:
- Detects Feishu-incompatible formatting (headings, tables, horizontal rules,
  blockquotes) in the response text
- Converts them to Feishu-compatible equivalents (bold text, lists, blank lines)
- Only applies when the platform is 'feishu'
- Logs a warning when violations are found
- Passes through unchanged for all other platforms
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Regex patterns ──────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^[\|\s]*:?-{3,}:?[\s\|:]*$", re.MULTILINE)
_HR_RE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s+(.+)$", re.MULTILINE)


def _fix_heading(m: re.Match) -> str:
    return f"**{m.group(1).strip()}**"


def _fix_blockquote(m: re.Match) -> str:
    return m.group(1).strip()


def _convert_table_to_list(text: str) -> str:
    """Convert markdown tables to Feishu-friendly list format."""
    lines = text.split("\n")
    result = []
    i = 0
    in_table = False
    table_buffer = []

    while i < len(lines):
        line = lines[i]
        is_table_row = "|" in line and line.strip().startswith("|")
        next_is_sep = (
            i + 1 < len(lines)
            and _TABLE_SEP_RE.match(lines[i + 1]) is not None
        ) if is_table_row else False

        if is_table_row and next_is_sep:
            in_table = True
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table_buffer = [header_cells]
            i += 2
            continue

        if in_table:
            if "|" in line and line.strip().startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                table_buffer.append(cells)
                i += 1
                continue
            else:
                in_table = False
                result.append(_format_table_as_text(table_buffer))
                table_buffer = []
                continue

        result.append(line)
        i += 1

    if in_table and table_buffer:
        result.append(_format_table_as_text(table_buffer))

    sep = "\n"
    return sep.join(result) + ("\n" if text.endswith("\n") else "")


def _format_table_as_text(rows: list[list[str]]) -> str:
    """Format a parsed table as Feishu-friendly text."""
    if not rows:
        return ""
    header = rows[0]
    data = rows[1:]
    parts = [f"**{' / '.join(header)}**"]
    for row in data:
        parts.append(f"· {'  |  '.join(row)}")
    return "\n".join(parts)


def _transform_feishu_format(response_text: str) -> str:
    text = response_text
    text = _convert_table_to_list(text)
    text = _HEADING_RE.sub(_fix_heading, text)
    text = _BLOCKQUOTE_RE.sub(_fix_blockquote, text)
    text = _HR_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _check_violations(response_text: str) -> list[str]:
    violations = []
    if _HEADING_RE.search(response_text):
        violations.append(f"heading(s) → bold")
    if _BLOCKQUOTE_RE.search(response_text):
        violations.append("blockquote(s) → plain text")
    if "|" in response_text and _TABLE_SEP_RE.search(response_text):
        violations.append("table(s) → list format")
    if _HR_RE.search(response_text):
        violations.append("horizontal rule(s) → removed")
    return violations


# ── Hook handler ────────────────────────────────────────────────────────

def _hook_transform_llm_output(
    response_text: str = "",
    platform: str = "",
    **kwargs,
) -> str | None:
    """Check and fix Feishu format violations in LLM output."""
    if not response_text:
        return None
    if platform != "feishu":
        return None

    violations = _check_violations(response_text)
    if not violations:
        return None

    logger.warning(
        "[feishu-format-check] %d violation(s): %s",
        len(violations),
        "; ".join(violations),
    )

    transformed = _transform_feishu_format(response_text)
    if transformed != response_text:
        logger.info(
            "[feishu-format-check] Fixed %d — %d→%d chars",
            len(violations),
            len(response_text),
            len(transformed),
        )

    return transformed


# ── Plugin registration ────────────────────────────────────────────────

def register(ctx) -> None:
    ctx.register_hook("transform_llm_output", _hook_transform_llm_output)
    logger.info("[feishu-format-check] Hook registered — will auto-fix Feishu format violations")
