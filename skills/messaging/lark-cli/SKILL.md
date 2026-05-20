---
name: lark-cli
description: "飞书文档操作通过 lark-cli 完成（创建/读取/更新/删除），替代裸调 Feishu API。安装、认证、常用命令速查、身份选择策略。"
version: 1.0.0
author: hermes-agent
platforms: [linux, macos]
prerequisites:
  commands: [lark-cli]
---

# Lark-CLI — 飞书文档操作 CLI

## 概述

当用户需要操作飞书文档（创建、读取、更新、删除）时，优先使用 `lark-cli` 而不是直接调 Feishu Open API。lark-cli 处理了 markdown 转换、分块上传、认证刷新等细节。

**安装方式：** `npm install -g @larksuite/cli`
**当前版本：** v1.0.34
**路径：** `/root/.hermes/node/bin/lark-cli`

## 认证流程

### 首次配置

1. **绑定 Hermes 凭据：**
   ```
   lark-cli config bind --source hermes --identity user-default
   ```
   - `--identity bot-only` — 只能操作机器人资源（安全）
   - `--identity user-default` — 能以用户身份操作个人资源
   - 需要用户确认后才执行

2. **设备授权登录（两步）：**
   ```
   # 第一步：获取 verification_url，发给用户
   lark-cli auth login --no-wait --json --recommend
   # 输出中拿到 verification_url，让用户在浏览器中打开完成授权
   
   # 第二步：用户确认授权后，用 device_code 完成
   lark-cli auth login --device-code <device_code>
   ```

### 认证验证

```
lark-cli auth status --verify
```

### 认证有效期

- user token: 2 小时过期，自动刷新
- refresh token: 7 天有效（截止日期见 `refreshExpiresAt`）
- 过期后需重新走设备授权流程

## 身份选择策略

| 场景 | 用谁的身份 (`--as`) | 原因 |
|------|-------------------|------|
| 创建文档 | `--as user` | 用户拥有默认编辑权限 |
| 读取/更新用户创建的文档 | `--as user` | 用户身份操作个人资源 |
| 读取/更新机器人创建的文档 | `--as bot` | 机器人创建的文档用户无权限 |
| 删除机器人创建的文档 | `--as bot` | 机器人创建者才有删除权限 |
| 不确定时 | 先 `--as user`，403 换 `--as bot` | 安全降级 |

## 文档操作命令（v2 API）

### 创建文档

```
cat content.md | lark-cli docs +create \
  --title "文档标题" \
  --content - \
  --doc-format markdown \
  --as user \
  --api-version v2
```

- 标题必填
- markdown 内容从 stdin 传入（不支持绝对路径）
- 返回 `document_id` 和 `url`

### 读取文档内容

```
lark-cli docs +fetch \
  --doc "https://www.feishu.cn/docx/<doc_id>" \
  --as user \
  --api-version v2 \
  --doc-format markdown \
  --format pretty
```

- `--doc-format markdown --format pretty` 输出 markdown 文本（v2 会正确渲染代码块）
- `--doc-format xml` 输出 XML 格式（含 block 结构）
- `--scope outline` 只看标题大纲
- `--revision-id <N>` 读取指定版本

### 更新文档

```
cat content.md | lark-cli docs +update \
  --doc "https://www.feishu.cn/docx/<doc_id>" \
  --command overwrite \
  --content - \
  --doc-format markdown \
  --as user \
  --api-version v2
```

- `--command overwrite` — 完全替换内容
- `--command append` — 追加到末尾
- `--content -` — 内容从 stdin 传入
- `--doc-format markdown` — 内容为 markdown 格式
- `--revision-id -1`（默认）— 基于最新版本编辑

### 删除文档

```
lark-cli drive +delete \
  --file-token <doc_id> \
  --type docx \
  --as user \
  --yes
```

- 需要确认身份权限（机器人创建的要 `--as bot`）
- `--type` 可选：docx, doc, sheet, slides, bitable, folder 等

## 文档 URL 格式

- 机器人创建：`https://bytedance.feishu.cn/docx/<doc_id>`
- 用户创建：`https://www.feishu.cn/docx/<doc_id>`
- 两种 URL 在 lark-cli 中都能解析，不用区分

## 注意事项 / Pitfalls

1. **markdown 内容传入：** `--content` 不支持绝对路径。用 stdin：`cat file.md | lark-cli ... --content -`

2. **v2 API 必须显式指定：** 所有 `docs` 命令记得加 `--api-version v2`，否则默认 v1（有 deprecation 警告且代码块渲染有问题）。

3. **并发限制：** 飞书文档 API 每秒 3 QPS（单应用），单文档每秒 3 次并发编辑。批量操作需加延迟。

4. **`--as bot` vs `--as user`：** 文档由谁创建，就用谁的身份操作。不确定时先 user 再 bot。如果 user 403 则换 bot。

5. **v2 +update 没有 `--new-title`：** v1 支持 `--new-title` 同时改标题，v2 不支持。需要改标题的话，用 `lark-cli api` 单独调接口。
