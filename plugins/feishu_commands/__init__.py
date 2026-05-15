from __future__ import annotations

"""Feishu Commands Plugin — send interactive card with clickable buttons."""

import asyncio
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

# ── Feishu Markdown Sanitizer ────────────────────────────────────────────
# Converts table/heading/horizontal-rule markdown to Feishu-compatible
# formats. Only applied to TEXT/POST messages, not interactive cards.

_FEISHU_HEADING_RE = re.compile(r'^ {0,3}#{1,6}\s+(.*)$', re.MULTILINE)
_FEISHU_HR_RE = re.compile(r'^ {0,3}(?:[-*_]){3,}\s*$', re.MULTILINE)
_FEISHU_TABLE_LINE_RE = re.compile(r'^.*?\|.*$', re.MULTILINE)


def _sanitize_for_feishu(text: str) -> str:
    """Strip or convert markdown elements Feishu doesn't render.

    - Headings (# → **bold**)
    - Horizontal rules (--- / *** / ___) → removed
    - Table rows (|...|) → removed entirely (header + separator + data)
    """
    if not text:
        return text

    # 1. Convert headings to bold
    #    "# Title" → "**Title**"
    text = _FEISHU_HEADING_RE.sub(r'**\1**', text)

    # 2. Remove horizontal rules (replace with empty line, preserving spacing)
    text = _FEISHU_HR_RE.sub('', text)

    # 3. Remove table rows entirely
    #    This catches both header rows (| A | B |), separator rows (|---|---|),
    #    and data rows.  Each row is removed individually so adjacent text
    #    survives.
    text = _FEISHU_TABLE_LINE_RE.sub('', text)

    # 4. Clean up excessive blank lines left by removals
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

logger = logging.getLogger(__name__)

_CARD_BUTTON_RE = re.compile(
    r"^/card\s+button\s+(?P<json>\{.*\})\s*$",
    re.DOTALL,
)


# ── Monkey-patch send_slash_confirm onto FeishuAdapter ──────────────────

_PATCHED = False


def _patch_feishu_adapter() -> None:
    """Add send_slash_confirm button support to the Feishu adapter.

    The base adapter returns "Not supported" for send_slash_confirm, causing
    the gateway to fall back to "Text fallback: reply /approve, /always, or
    /cancel".  This monkey-patch adds an interactive card with 3 buttons.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from gateway.platforms.feishu import FeishuAdapter
    except ImportError:
        logger.debug("[feishu-commands] FeishuAdapter not available yet, skipping patch")
        return

    if getattr(FeishuAdapter, '_feishu_commands_patched', False):
        _PATCHED = True
        return

    # ── send_slash_confirm async method ─────────────────────────────────
    async def _send_slash_confirm(self, *, chat_id, title, message, session_key, confirm_id, metadata=None, **kw):
        """Send a 3-button confirm card (Approve Once / Always / Cancel)."""
        if not getattr(self, '_client', None):
            return _make_send_result(False, 'Not connected')

        def _btn(label, choice, btn_type='default'):
            return {
                'tag': 'button',
                'text': {'tag': 'plain_text', 'content': label},
                'type': btn_type,
                'value': {
                    'hermes_action': 'slash_confirm',
                    'confirm_id': str(confirm_id),
                    'session_key': str(session_key),
                    'choice': choice,
                },
            }

        card = {
            'config': {'wide_screen_mode': True},
            'header': {
                'title': {'content': title or '确认操作', 'tag': 'plain_text'},
                'template': 'blue',
            },
            'elements': [
                {'tag': 'markdown', 'content': message},
                {
                    'tag': 'action',
                    'actions': [
                        _btn('✅ 批准一次', 'once', 'primary'),
                        _btn('✅ 总是批准', 'always'),
                        _btn('❌ 取消', 'cancel', 'danger'),
                    ],
                },
            ],
        }

        payload = json.dumps(card, ensure_ascii=False)
        try:
            response = await self._feishu_send_with_retry(
                chat_id=chat_id,
                msg_type='interactive',
                payload=payload,
                reply_to=None,
                metadata=metadata,
            )
            logger.info(
                "[feishu-commands] Slash-confirm card sent for %s (confirm_id=%s)",
                session_key, confirm_id,
            )
            return _make_send_result(True, '', message_id=getattr(getattr(response, 'data', None), 'message_id', ''))
        except Exception as exc:
            logger.warning("[feishu-commands] send_slash_confirm failed: %s", exc)
            return _make_send_result(False, str(exc))

    # ── _on_card_action_trigger SYNC patch ─────────────────────────────
    original_on_trigger = FeishuAdapter._on_card_action_trigger

    def _patched_on_card_action_trigger(self, data):
        """Forward slash_confirm actions to async resolution; delegate others."""
        loop = self._loop
        event = getattr(data, 'event', None)
        action = getattr(event, 'action', None)
        action_value = getattr(action, 'value', {}) or {}

        if action_value.get('hermes_action') == 'slash_confirm':
            logger.info("[feishu-commands] Intercepting slash_confirm action")
            # Extract chat_id from the card event context so we can send
            # the result message back to the user.
            context = getattr(event, 'context', None)
            chat_id = str(getattr(context, 'open_chat_id', '') or '')
            if loop and not getattr(loop, 'is_closed', lambda: False)():
                asyncio.run_coroutine_threadsafe(
                    _resolve_slash_confirm(action_value, chat_id=chat_id),
                    loop,
                )
            # Return a response to keep the Feishu SDK happy
            return _make_p2_card_response()

        return original_on_trigger(self, data)

    FeishuAdapter.send_slash_confirm = _send_slash_confirm
    FeishuAdapter._on_card_action_trigger = _patched_on_card_action_trigger

    # ── format_message sanitizer patch ──────────────────────────────────
    original_format = FeishuAdapter.format_message

    def _patched_format_message(self, content: str) -> str:
        text = original_format(self, content)
        return _sanitize_for_feishu(text)

    FeishuAdapter.format_message = _patched_format_message
    FeishuAdapter._feishu_commands_patched = True

    logger.info("[feishu-commands] Patched FeishuAdapter: send_slash_confirm + card action handler + format_message")
    _PATCHED = True


async def _resolve_slash_confirm(action_value: dict, *, chat_id: str = '') -> None:
    """Resolve a pending slash confirm from a button callback.

    Sends the handler's result message back to the Feishu chat.
    """
    from tools.slash_confirm import resolve
    confirm_id = action_value.get('confirm_id', '')
    session_key = action_value.get('session_key', '')
    choice = action_value.get('choice', '')
    if not all([confirm_id, session_key, choice]):
        logger.warning("[feishu-commands] Incomplete slash_confirm data: %s", action_value)
        return

    result_msg = None
    try:
        result_msg = await resolve(session_key, confirm_id, choice)
        logger.info(
            "[feishu-commands] Slash confirm %s/%s → %s",
            session_key, confirm_id, choice,
        )
    except Exception as exc:
        logger.error("[feishu-commands] Slash confirm resolution failed: %s", exc)
        result_msg = f"❌ Error resolving confirmation: {exc}"

    # Send the handler's result back to the user
    if result_msg and chat_id:
        try:
            token = _get_tenant_token()
            _send_feishu_text(chat_id, result_msg, token)
            logger.info(
                "[feishu-commands] Sent slash-confirm result to %s: %r",
                chat_id, result_msg[:100],
            )
        except Exception as exc:
            logger.error(
                "[feishu-commands] Failed to send slash-confirm result: %s", exc,
            )
    elif result_msg and not chat_id:
        logger.warning(
            "[feishu-commands] No chat_id available, cannot deliver result: %r",
            result_msg[:100],
        )


def _make_send_result(success: bool, error: str, message_id: str = '') -> object:
    """Create a lightweight SendResult-like object."""
    return type('SendResult', (), {
        'success': success,
        'error': error,
        'message_id': message_id,
    })()


def _make_p2_card_response() -> object | None:
    """Return a P2CardActionTriggerResponse (or None if import fails)."""
    try:
        from lark_oapi.event.callback.model.p2_card_action_trigger import (
            P2CardActionTriggerResponse,
        )
        return P2CardActionTriggerResponse()
    except ImportError:
        return None


# ── pre_gateway_dispatch hook ──────────────────────────────────────────

def _hook_pre_gateway_dispatch(*, event, **_kw) -> None | dict:
    """Intercept /card button clickbacks and rewrite to the target command."""
    text = (event.text or "").strip()
    m = _CARD_BUTTON_RE.match(text)
    if not m:
        return None
    try:
        payload = json.loads(m.group("json"))
    except json.JSONDecodeError:
        logger.warning("[feishu-commands] Failed to parse card button payload: %r", text)
        return None

    # Slash-confirm callbacks handled by _on_card_action_trigger patch
    if payload.get("hermes_action") == "slash_confirm":
        return {"action": "skip", "reason": "handled by slash_confirm card action handler"}

    clicked: str | None = payload.get("hermes_clicked") or payload.get("command")
    if not clicked:
        logger.warning("[feishu-commands] Card button payload missing hermes_clicked: %r", payload)
        return None
    if not clicked.startswith("/"):
        clicked = "/" + clicked.lstrip()

    logger.info(
        "[feishu-commands] Rewriting card button click %r → %r",
        text, clicked,
    )
    return {"action": "rewrite", "text": clicked}


# ── Feishu API helpers ─────────────────────────────────────────────────

def _get_tenant_token() -> str:
    """Get a tenant_access_token from Feishu auth API."""
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID or FEISHU_APP_SECRET not set")

    data = json.dumps({
        "app_id": app_id,
        "app_secret": app_secret,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    token = result.get("tenant_access_token", "")
    if not token:
        raise RuntimeError(f"Failed to get tenant token: {result}")
    return token


def _get_current_chat_id() -> str:
    """Read the current chat ID from env (set by Feishu gateway)."""
    return os.environ.get("FEISHU_HOME_CHANNEL", "") or \
           os.environ.get("CURRENT_CHAT_ID", "")


def _send_feishu_text(chat_id: str, text: str, token: str) -> dict:
    """Send a plain text message to a Feishu chat (via REST API)."""
    body = json.dumps({
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _send_feishu_card(chat_id: str, card_json: dict) -> dict:
    """Send an interactive card to a Feishu chat."""
    token = _get_tenant_token()
    body = json.dumps({
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card_json, ensure_ascii=False),
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Tool handler ───────────────────────────────────────────────────────

def _handle_show_buttons(args: dict, **kw) -> str:
    """Send a Feishu interactive card with clickable command buttons."""
    title = str(args.get("title", "Commands"))
    prompt = str(args.get("prompt", ""))
    chat_id = str(args.get("chat_id", "") or _get_current_chat_id())

    raw_buttons = args.get("buttons", [])
    if not raw_buttons:
        return json.dumps({"success": False, "error": "No buttons provided"})

    if not chat_id:
        return json.dumps({
            "success": False,
            "error": "Chat ID not found. Set chat_id parameter or FEISHU_HOME_CHANNEL env."
        })

    elements = []
    if prompt:
        elements.append({"tag": "markdown", "content": prompt})

    button_rows = []
    for i, btn in enumerate(raw_buttons):
        label = str(btn.get("label", f"Button {i+1}"))
        command = str(btn.get("command", ""))
        btn_type = str(btn.get("type", "default"))
        button_rows.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": label},
            "type": "primary" if btn_type == "primary" else "danger" if btn_type == "danger" else "default",
            "value": {"hermes_clicked": command},
        })

    elements.append({"tag": "action", "actions": button_rows})

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"content": title, "tag": "plain_text"},
            "template": "blue",
        },
        "elements": elements,
    }

    try:
        result = _send_feishu_card(chat_id, card)
        code = result.get("code", -1)
        if code != 0:
            return json.dumps({
                "success": False,
                "error": f"Feishu API error (code={code}): {result.get('msg', '')}",
                "raw": result,
            }, ensure_ascii=False)
        return json.dumps({
            "success": True,
            "message_id": result.get("data", {}).get("message_id", ""),
        })
    except Exception as exc:
        logger.error("feishu_show_buttons failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


SCHEMA = {
    "name": "feishu_show_buttons",
    "description": "Send a Feishu interactive card with clickable buttons. Each button maps to a command. The user clicks instead of typing.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Card header title (default: 'Commands')",
            },
            "prompt": {
                "type": "string",
                "description": "Optional markdown text above the buttons",
            },
            "chat_id": {
                "type": "string",
                "description": "Optional Feishu chat_id. Auto-detected from env if omitted.",
            },
            "buttons": {
                "type": "array",
                "description": "List of buttons. Each: {label, command, type?}",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "Button text"},
                        "command": {"type": "string", "description": "Slash command to run when clicked, e.g. /model"},
                        "type": {"type": "string", "enum": ["default", "primary", "danger"], "description": "Button style (default: 'default')"},
                    },
                    "required": ["label", "command"],
                },
            },
        },
        "required": ["buttons"],
    },
}


def register(ctx) -> None:
    """Register plugin tools and hooks."""
    _patch_feishu_adapter()
    ctx.register_hook("pre_gateway_dispatch", _hook_pre_gateway_dispatch)
    ctx.register_tool(
        name="feishu_show_buttons",
        toolset="messaging",
        schema=SCHEMA,
        handler=_handle_show_buttons,
        requires_env=["FEISHU_APP_ID", "FEISHU_APP_SECRET"],
        description="Send a Feishu interactive card with clickable command buttons.",
        emoji="🔘",
    )
