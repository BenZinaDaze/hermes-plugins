from __future__ import annotations


"""CloakBrowser Plugin - Stealth browser automation via CloakBrowser.

Overrides core browser_* tools with CloakBrowser-backed versions that
use C++ source-level fingerprint patches instead of stock Playwright.

Registers same tool names (browser_navigate, browser_click, etc.) in the
'browser' toolset, overwriting the core implementations.

To revert: remove this plugin and restart the gateway.
"""

import json
import logging
import threading
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session management - one browser per task_id
# ---------------------------------------------------------------------------
_sessions: Dict[str, Any] = {}
_sessions_lock = threading.Lock()


def _get_or_create_browser(task_id: str) -> Any:
    """Get existing browser for task_id or launch a new one."""
    if task_id in _sessions:
        return _sessions[task_id]

    from cloakbrowser import launch

    browser = launch(headless=True, humanize=False, geoip=False)
    _sessions[task_id] = browser
    return browser


def _get_page(task_id: str) -> Any:
    """Get or create a page for the given browser session."""
    browser = _get_or_create_browser(task_id)
    if browser.contexts:
        for ctx in browser.contexts:
            if ctx.pages:
                return ctx.pages[0]
    return browser.new_page()


def _cleanup_session(task_id: str) -> None:
    """Close and remove a browser session."""
    with _sessions_lock:
        browser = _sessions.pop(task_id, None)
    if browser:
        try:
            browser.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _handle_navigate(args: dict, **kw) -> str:
    """Navigate to a URL. Initializes the session."""
    url = args.get("url", "")
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(0.5)

        title = page.title()
        elements = _get_interactive_elements(page)
        snapshot = _build_snapshot_text(title, url, elements)

        return json.dumps({
            "success": True,
            "title": title,
            "url": page.url,
            "snapshot": snapshot,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_snapshot(args: dict, **kw) -> str:
    """Get a text-based snapshot of the current page."""
    task_id = kw.get("task_id", "default")
    full = args.get("full", False)
    try:
        page = _get_page(task_id)
        title = page.title()

        if full:
            text = page.text_content("body") or ""
            text = text[:8000]
            return json.dumps({"success": True, "title": title, "content": text})
        else:
            elements = _get_interactive_elements(page)
            snapshot = _build_snapshot_text(title, page.url, elements)
            return json.dumps({"success": True, "snapshot": snapshot})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_click(args: dict, **kw) -> str:
    """Click an element by ref ID."""
    ref = args.get("ref", "")
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        idx = _ref_to_index(ref)
        elements = _get_interactive_elements(page)
        if idx < 0 or idx >= len(elements):
            return json.dumps({"success": False, "error": f"Invalid ref: {ref}"})

        selector = elements[idx]["selector"]
        el = page.query_selector(selector)
        if not el:
            return json.dumps({"success": False, "error": f"Element {ref} not found on page"})

        el.click()
        time.sleep(0.3)
        return json.dumps({"success": True, "message": f"Clicked {ref}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_type(args: dict, **kw) -> str:
    """Type text into an element."""
    ref = args.get("ref", "")
    text = args.get("text", "")
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        idx = _ref_to_index(ref)
        elements = _get_interactive_elements(page)
        if idx < 0 or idx >= len(elements):
            return json.dumps({"success": False, "error": f"Invalid ref: {ref}"})

        selector = elements[idx]["selector"]
        el = page.query_selector(selector)
        if not el:
            return json.dumps({"success": False, "error": f"Element {ref} not found"})

        el.fill("")
        el.type(text, delay=20)
        return json.dumps({"success": True, "message": f"Typed into {ref}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_scroll(args: dict, **kw) -> str:
    """Scroll the page."""
    direction = args.get("direction", "down")
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        if direction == "down":
            page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        else:
            page.evaluate("window.scrollBy(0, -window.innerHeight * 0.8)")
        return json.dumps({"success": True, "message": f"Scrolled {direction}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_back(args: dict, **kw) -> str:
    """Go back in history."""
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        page.go_back()
        time.sleep(0.5)
        return json.dumps({"success": True, "title": page.title()})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_press(args: dict, **kw) -> str:
    """Press a keyboard key."""
    key = args.get("key", "")
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        page.keyboard.press(key)
        return json.dumps({"success": True, "message": f"Pressed {key}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_close(args: dict, **kw) -> str:
    """Close the browser session."""
    task_id = kw.get("task_id", "default")
    _cleanup_session(task_id)
    return json.dumps({"success": True, "message": "Browser session closed"})


def _handle_vision(args: dict, **kw) -> str:
    """Take a screenshot and return path."""
    task_id = kw.get("task_id", "default")
    try:
        page = _get_page(task_id)
        safe_id = task_id.replace("/", "_").replace(":", "_")
        screenshot_path = f"/tmp/cloak_screenshot_{safe_id}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        return json.dumps({
            "success": True,
            "screenshot_path": screenshot_path,
            "message": f"Screenshot saved. Include MEDIA:{screenshot_path} in your response.",
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_interactive_elements(page) -> list:
    """Get interactive elements with CSS selectors for targeting."""
    return page.evaluate("""() => {
        const tags = ['a', 'button', 'input', 'select', 'textarea', '[role=button]', '[tabindex]'];
        const results = [];
        const seen = new Set();
        for (const tag of tags) {
            const els = document.querySelectorAll(tag);
            for (const el of els) {
                if (seen.has(el)) continue;
                seen.add(el);
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                const tagName = el.tagName.toLowerCase();
                const type = el.type || '';
                const placeholder = el.placeholder || '';
                const text = (el.textContent || el.value || '').toString().trim().slice(0, 80);
                const href = el.href || '';
                results.push({
                    tag: tagName,
                    type: type,
                    text: text,
                    href: href,
                    placeholder: placeholder,
                    selector: _build_selector(el),
                });
            }
        }
        return results;

        function _build_selector(el) {
            if (el.id) return '#' + CSS.escape(el.id);
            if (el.name) return el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]';
            let path = [];
            let current = el;
            while (current && current !== document.body && current !== document.documentElement) {
                let selector = current.tagName.toLowerCase();
                if (current.id) { path.unshift('#' + CSS.escape(current.id)); break; }
                if (current.className && typeof current.className === 'string') {
                    const cls = current.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('_')).slice(0, 2);
                    if (cls.length) selector += '.' + cls.map(c => CSS.escape(c)).join('.');
                }
                const parent = current.parentElement;
                if (parent) {
                    const siblings = Array.from(parent.children).filter(c => c.tagName === current.tagName);
                    if (siblings.length > 1) {
                        const idx = siblings.indexOf(current) + 1;
                        selector += ':nth-of-type(' + idx + ')';
                    }
                }
                path.unshift(selector);
                current = current.parentElement;
            }
            return path.join(' > ');
        }
    }""")


def _ref_to_index(ref: str) -> int:
    """Convert '@e5' to 4 (0-indexed)."""
    ref = ref.strip().lstrip("@e")
    try:
        return int(ref) - 1
    except ValueError:
        return -1


def _build_snapshot_text(title: str, url: str, elements: list) -> str:
    """Build a compact text snapshot of interactive elements."""
    lines = [f"Title: {title}", f"URL: {url}", "", "Interactive elements:"]
    for i, el in enumerate(elements):
        ref = f"@e{i + 1}"
        tag = el.get("tag", "")
        txt = el.get("text", "")
        typ = el.get("type", "")
        href = el.get("href", "")
        place = el.get("placeholder", "")

        parts = [f"[{ref}] <{tag}"]
        if typ and typ != "text":
            parts.append(f'type="{typ}"')
        if txt:
            parts.append(f'"{txt}"')
        if place:
            parts.append(f'[placeholder="{place}"]')
        if href:
            short = href[:80]
            parts.append(f"\u2192 {short}")
        parts.append(">")
        lines.append("  " + " ".join(parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def _check_cloak_requirements() -> bool:
    """Check if CloakBrowser binary is available."""
    try:
        from cloakbrowser.download import ensure_binary
        path = ensure_binary()
        return bool(path)
    except Exception:
        return False


SCHEMAS = [
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL in the browser using CloakBrowser (stealth Chromium). Initializes the session and loads the page. Must be called before other browser tools. Returns a compact page snapshot with interactive elements and ref IDs. Overrides the default browser_navigate with anti-detection stealth (bypasses Cloudflare, reCAPTCHA, bot detection).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to navigate to"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_snapshot",
        "description": "Get a text-based snapshot of the current page via CloakBrowser. Returns interactive elements with ref IDs (@e1, @e2) for browser_click and browser_type. full=false (default): compact view. full=true: complete page text content.",
        "parameters": {
            "type": "object",
            "properties": {
                "full": {
                    "type": "boolean",
                    "description": "If true, returns full page content. If false (default), compact view.",
                    "default": False
                }
            },
            "required": []
        }
    },
    {
        "name": "browser_click",
        "description": "Click on an element by ref ID (@e5) via CloakBrowser stealth browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element ref from snapshot (e.g. '@e5')"}
            },
            "required": ["ref"]
        }
    },
    {
        "name": "browser_type",
        "description": "Type text into an input field by ref ID via CloakBrowser. Clears field first, then types.",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element ref from snapshot (e.g. '@e3')"},
                "text": {"type": "string", "description": "Text to type"}
            },
            "required": ["ref", "text"]
        }
    },
    {
        "name": "browser_scroll",
        "description": "Scroll the page in a direction via CloakBrowser.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to scroll"
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "browser_back",
        "description": "Navigate back to the previous page in browser history via CloakBrowser.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "browser_press",
        "description": "Press a keyboard key. Useful for submitting forms (Enter), navigating (Tab), or keyboard shortcuts.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to press (e.g. 'Enter', 'Tab', 'Escape')"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "browser_vision",
        "description": "Take a screenshot of the current page via CloakBrowser and return the path.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "What you want to know about the page visually"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "browser_close",
        "description": "Close the browser session via CloakBrowser. Call when done to free resources.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
]

_HANDLERS = {
    "browser_navigate": _handle_navigate,
    "browser_snapshot": _handle_snapshot,
    "browser_click": _handle_click,
    "browser_type": _handle_type,
    "browser_scroll": _handle_scroll,
    "browser_back": _handle_back,
    "browser_press": _handle_press,
    "browser_vision": _handle_vision,
    "browser_close": _handle_close,
}


def register(ctx) -> None:
    """Register CloakBrowser tools, overwriting core browser_* tools.

    IMPORTANT: import model_tools FIRST to trigger discover_builtin_tools().
    Core browser_tool.py registers all browser_* tools at import time with
    check_fn=check_browser_requirements (which returns False in environments
    without Playwright). If model_tools/discover_builtin_tools runs AFTER
    plugin registration, it overwrites our _check_cloak_requirements on the
    ToolEntry. Importing model_tools here forces discover_builtin_tools to
    run first, so our registration below takes precedence.
    """
    # Force core browser tool discovery before we register. This is safe
    # because model_tools is imported lazily per-request by the gateway;
    # importing it here just makes the first request faster.
    import model_tools  # noqa: F401

    for schema in SCHEMAS:
        name = schema["name"]
        ctx.register_tool(
            name=name,
            toolset="browser",
            schema=schema,
            handler=_HANDLERS[name],
            check_fn=_check_cloak_requirements,
            description=schema["description"],
            emoji="\U0001F575\uFE0F",
        )

    # Overwrite the toolset-level check so core check_browser_requirements
    # doesn't block our overwritten tools. Core browser_tool.py sets this
    # to check_browser_requirements (Playwright Chromium check) during
    # discover_builtin_tools(); replacing it with a pass-through ensures
    # all cloak_browser tools are visible on every platform.
    from tools.registry import registry
    registry._toolset_checks["browser"] = lambda: True

    logger.info("CloakBrowser plugin: overwrote %d browser_* tools", len(SCHEMAS))
