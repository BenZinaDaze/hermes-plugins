---
name: feishu-buttons
description: "Send Feishu interactive cards with clickable command buttons, and handle button click callbacks from the Feishu gateway."
---

# Feishu Button Cards Plugin

## Overview

The `feishu_commands` plugin registers the **`feishu_show_buttons`** tool, which sends interactive Feishu card messages with buttons the user can click instead of typing.

Full source reference in `references/plugin-source.md`.

## Plugin File Structure

The plugin lives at `~/.hermes/plugins/feishu_commands/` with two files:

```
feishu_commands/
├── plugin.yaml      # Plugin manifest (name, version, deps)
└── __init__.py      # Tool handler + API helpers + gateway hook
```

### `__init__.py` Anatomy

All imports (including `from __future__ import annotations`) must be at the **absolute top of the file**, before the docstring and before any code. Putting `from __future__ import annotations` after function definitions causes `SyntaxError`.

The `_hook_pre_gateway_dispatch` function **must be `async def`** — the gateway dispatcher awaits it. A sync `def` will fail at runtime.

### Gateway Hook — Button Click → Text Injection (critical)

**THE PROBLEM:** When the user clicks a Feishu card button, the gateway creates a synthetic `MessageEvent` with `message_id = card_action_token` (format `c-xxx`). When the agent tries to reply to this event, Feishu's API rejects it with error `99992354` — only `om_xxx` message IDs are valid targets for replies.

**THE FIX:** The plugin's `pre_gateway_dispatch` hook intercepts button clickbacks (matching regex `/card button {...}`) and does NOT use `rewrite` action. Instead:

1. It returns `{"action": "skip"}` — telling the gateway to drop the synthetic event entirely
2. Before skipping, it calls `_send_feishu_text()` via REST API to inject the command (`/model`, `/new`, etc.) as a **real Feishu text message** into the chat
3. The gateway receives this text message normally with a valid `om_xxx` message_id and can reply successfully

This approach avoids the reply-to-card-action-token bug entirely.

### Gateway Restart Required

After adding/changing a plugin in `config.yaml`, the gateway must be restarted:

```
systemctl restart hermes-gateway
```

Check `~/.hermes/logs/agent.log` for `Plugin discovery complete: N found, M enabled` to confirm the plugin loaded.

## Testing the Plugin

After making changes, verify the plugin loads and the API works:

```python
import sys, json, os, importlib.util

os.environ['FEISHU_APP_ID'] = '...'
os.environ['FEISHU_APP_SECRET'] = '...'

spec = importlib.util.spec_from_file_location(
    'feishu_commands',
    '/root/.hermes/plugins/feishu_commands/__init__.py'
)
mod = importlib.util.module_from_spec(spec)
sys.modules['feishu_commands'] = mod
spec.loader.exec_module(mod)

token = mod._get_tenant_token()  # raises on failure

result = mod._send_feishu_card(
    'oc_your_chat_id',
    {'config': {'wide_screen_mode': True}, 'header': ..., 'elements': [...]}
)
```

### Common Errors

- **Code 10014** — App Secret invalid. Verify FEISHU_APP_SECRET in .env matches Feishu dev console exactly (no truncation).
- **Code 10003** — Invalid params. Check card JSON structure — button `value` must be a dict, not a string.
- **Code 230001** — Permission denied. App needs `im:message:send_as_app` scope granted by tenant admin.
- **Code 99992354** — Invalid message_id in reply. Card action tokens (`c-xxx`) cannot be used as message_id for replies. The plugin handles this via the `skip + inject` flow — if you still see this error, confirm the hook returns `{"action": "skip"}` not `{"action": "rewrite"}`.

## Sending Buttons

Call the tool only when the user needs to confirm or execute a slash command action — NOT every mention of a slash command in text response.

```json
{
  "title": "Choose an action",
  "prompt": "What would you like to do?",
  "buttons": [
    {"label": "Switch Model", "command": "/model", "type": "primary"},
    {"label": "New Session", "command": "/new"},
    {"label": "Help", "command": "/help"}
  ]
}
```

**When to send buttons:** Model switch, new session, approve/deny, or any operation where clicking is smoother than typing.
**When NOT to send buttons:** Casual mentions, side comments, or explaining available commands.

## Button Styling

- `"default"` — neutral style
- `"primary"` — blue/branded (main action)
- `"danger"` — red (destructive actions)

## When Not to Use

- For simple quick replies without commands, just use text.
- For dangerous command approvals, the built-in approval card is already handled by the gateway automatically.
- For info-only responses that mention available commands in passing — use text, not buttons.

## Plugin Name

The plugin directory is `feishu_commands/` (underscore), not `feishu-commands/` (hyphen). Python modules cannot have hyphens in their names. Match this in `config.yaml`:

```yaml
plugins:
  enabled:
    - feishu_commands
```

## Env Requirements

```
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_HOME_CHANNEL=oc_xxx   # optional, for auto-detecting chat_id
```