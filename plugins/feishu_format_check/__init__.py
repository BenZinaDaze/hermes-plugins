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

Supports toggle via /feishu-format-check-enable and /feishu-format-check-disable
slash commands (or card buttons).
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# ── Toggle state ──────────────────────────────────────────────────────────

_STATE_FILE = os.path.join(os.path.expanduser("~"), ".hermes", "feishu_format_check_state.json")


def _load_state() -> bool:
    """Load enabled state. Default: enabled (True)."""
    try:
        with open(_STATE_FILE) as f:
            state = json.load(f)
        return state.get("enabled", True)
    except (FileNotFoundError, json.JSONDecodeError):
        return True


def _save_state(enabled: bool) -> None:
    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
    with open(_STATE_FILE, "w") as f:
        json.dump({"enabled": enabled}, f)


_ENABLED = _load_state()


# ── Regex patterns ──────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^[\s|:]*[-]{3}[\s|:-]*$", re.MULTILINE)
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
    if not _ENABLED:
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


# ── Command handlers ────────────────────────────────────────────────────

def _handle_format_enable(args: list[str] = None) -> str:
    """Enable Feishu format checking."""
    global _ENABLED
    _ENABLED = True
    _save_state(True)
    logger.info("[feishu-format-check] Enabled")
    return "✅ Feishu 格式检查已启用"


def _handle_format_disable(args: list[str] = None) -> str:
    """Disable Feishu format checking."""
    global _ENABLED
    _ENABLED = False
    _save_state(False)
    logger.info("[feishu-format-check] Disabled")
    return "⛔ Feishu 格式检查已关闭"


# ── Plugin registration ────────────────────────────────────────────────

def register(ctx) -> None:
    ctx.register_hook("transform_llm_output", _hook_transform_llm_output)
    ctx.register_command(
        "feishu-format-check-enable",
        _handle_format_enable,
        description="Enable Feishu format auto-check",
    )
    ctx.register_command(
        "feishu-format-check-disable",
        _handle_format_disable,
        description="Disable Feishu format auto-check",
    )
    logger.info(
        "[feishu-format-check] Hook + commands registered "
        "(current state: %s)",
        "enabled" if _ENABLED else "disabled",
    )
