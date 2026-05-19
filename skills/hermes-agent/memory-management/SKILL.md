---
name: memory-management
title: Memory Management
description: Manage Hermes Agent's persistent memory — review, consolidate, and prune entries to stay within the 2,200-char limit.
category: hermes-agent
---

# Memory Management

Hermes Agent has two persistent memory stores injected into the system prompt at session start:

| Store | Purpose | Limit |
|-------|---------|-------|
| `memory` | Agent's personal notes — environment facts, conventions, learned quirks | 2,200 chars |
| `user` | User profile — preferences, communication style, expectations | 1,375 chars |

**Memory never auto-cleans.** No TTL, no LRU, no scheduled eviction. When full, the `memory` tool returns an error and you must manually remove/replace entries.

## When to Review

- **>80% full** — consolidate before adding anything new
- **Any "Memory at X/2,200 chars" error** — triggered by attempting to add an entry that won't fit
- **After any session that saved 3+ entries** — check if older entries became redundant

## Decision Rules: Keep vs Remove

### Remove (过时条件)

| Type | Example |
|------|---------|
| **已封入 skill 的** | "Before pushing repos, verify README — encoded in github-repo-management skill" → skill 已接管，记忆里多余 |
| **一次性创建记录** | "Created shellcrash-operations skill" → 技能已存在，不需要记"我创建了它" |
| **已被其他条目覆盖** | "Feishu card button fix (prefix handling)" + "Gateway restart deadlock" → 后者已覆盖前者 |
| **任务进度/TODO** | "Phase 2 done, PR #42 merged" → 用 session_search 回溯，不占 memory |
| **临时调试信息** | 一次性错误分析、临时文件路径、会话内的摸索过程 |

### Keep (保留优先级)

1. **用户偏好**（最高优先级）— venv 路径偏好、回复风格要求、权限确认方式
2. **环境事实** — OS 版本、工具安装路径、项目结构
3. **持久性工作流知识** — 网关重启死锁、插件备份要求（未列入 skill 的）

## Consolidation Techniques

### 1. Merge related entries

多个同类事实合并为一条：

```
User prefers venv: /root/.hermes/hermes-agent/.venv/bin/python. Gateway restart: use systemctl, not --replace.
```

### 2. Shorten verbose entries

`Created references/platform-toolset-debugging.md under hermes-agent skill — debugging guide for why tools appear/disappear...` → `platform-toolset-debugging.md exists in hermes-agent skill — tool visibility debugging`

### 3. Replace + Remove pattern

1. `memory(action="replace", target="memory", old_text="...", content="shorter merged version")`
2. `memory(action="remove", target="memory", old_text="covered entry's unique substring")`

## Proactive Prevention

- **Prune after each major project phase** — before memory hits 80%
- **Before pushing a new skill to GitHub** — check if any memory entry is now covered by the skill
- **When user corrects your behavior** — the correction replaces, not appends. Remove the old preference entry first if it exists.
- **Don't save task progress** — session_search can retrieve past session context. Memory is for durable facts that survive weeks.

## Pitfalls

- `old_text` must be a **unique substring** matching exactly one entry — if it matches multiple entries, the tool returns an error asking for a more specific match
- Removing an entry that doesn't exist returns an error but doesn't corrupt other entries
- Memory changes are written to disk immediately but only appear in the system prompt **next session** — the current session still sees the old snapshot
- `user` store (1,375 chars) has a tighter limit than `memory` (2,200 chars) — profile entries need to be even more compact
