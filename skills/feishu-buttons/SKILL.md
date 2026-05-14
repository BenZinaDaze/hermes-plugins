---
name: feishu-buttons
description: "Send Feishu interactive cards with clickable command buttons, and handle button click callbacks from the Feishu gateway."
---

# Feishu Button Cards Plugin

## Overview

The `feishu_commands` plugin registers the **`feishu_show_buttons`** tool, which sends interactive Feishu card messages with buttons the user can click instead of typing.

Full source reference in `references/plugin-source.md`.

Reference GitHub repo at `/root/hermes-plugins/` — structured for multiple plugins/skills under one roof:

```
hermes-plugins/
├── plugins/
│   └── feishu_commands/       # This plugin
└── skills/
    └── feishu-buttons/        # This skill
```

Add future plugins under `plugins/` and skills under `skills/` in the same repo.

## Plugin File Structure

The plugin lives at `~/.hermes/plugins/feishu_commands/` with two files:

```
feishu_commands/
├── plugin.yaml      # Plugin manifest (name, version, deps)
└── __init__.py      # Tool handler + API helpers + gateway hook
```

### `__init__.py` Anatomy

All imports (including `from __future__ import annotations`) must be at the **absolute top of the file**, before the docstring. Putting `from __future__ import annotations` after function definitions causes `SyntaxError` — the plugin will fail to load silently ("N found, N-1 enabled" in agent.log).

The `_hook_pre_gateway_dispatch` function **must be `async def`** — the gateway dispatcher awaits it. A sync `def` will fail at runtime.

### Gateway Hook — Button Click → Text Injection (critical)

**THE PROBLEM:** When the user clicks a Feishu card button, the gateway creates a synthetic `MessageEvent` with `message_id = card_action_token` (format `c-xxx`). When the agent tries to reply to this event, Feishu's API rejects it with error `99992354` — only `om_xxx` message IDs are valid for replies.

**THE FIX:** The plugin's `pre_gateway_dispatch` hook intercepts button clickbacks (matching regex `/card button {...}`) and does NOT use `rewrite` action. Instead:

1. It returns `{"action": "skip"}` — telling the gateway to drop the synthetic event entirely
2. Before skipping, it calls `_send_feishu_text()` via REST API to inject the command as a **real Feishu text message** into the chat
3. The gateway receives this text message normally with a valid `om_xxx` message_id and can reply successfully

### Gateway Restart

After adding/changing a plugin, check agent.log for successful loading:

```bash
grep 'Plugin discovery' ~/.hermes/logs/agent.log
# Expected: "13 found, 9 enabled" (9 = plugin enabled)
```

Restart via systemd (not `hermes gateway restart` which may not be available):

```bash
systemctl restart hermes-gateway
```

## Testing the Plugin

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
result = mod._send_feishu_card('oc_your_chat_id', card_json)
```

### Common Errors

- **Code 10014** — App Secret invalid. Verify FEISHU_APP_SECRET in .env matches Feishu dev console exactly.
- **Code 10003** — Invalid params. Check card JSON — button `value` must be a dict, not string.
- **Code 230001** — Permission denied. App needs `im:message:send_as_app` scope.
- **Code 99992354** — Invalid message_id. Card action tokens (`c-xxx`) cannot be reply targets. The plugin's `skip + inject` flow fixes this — confirm hook returns `{"action": "skip"}`, not `{"action": "rewrite"}`.
- **Plugin silent failure** — Check agent.log for "N found, N-1 enabled". The missing plugin likely has a SyntaxError.

## Sending Buttons

Call the tool **only when the user needs to confirm or execute a slash command action** — model switch, new session, approve/deny. Do NOT send buttons for every mention of a slash command in text; casual mentions and side comments should remain as text.

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

### Button Types

- `"default"` — neutral
- `"primary"` — blue/branded (main action)
- `"danger"` — red (destructive)

## Plugin Name

Directory must be `feishu_commands/` (underscore), **not** `feishu-commands/` (hyphen). Python modules cannot have hyphens in names.

```yaml
plugins:
  enabled:
    - feishu_commands
```

## Env Requirements

```
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_HOME_CHANNEL=oc_xxx   # optional, auto-detected if omitted
```
