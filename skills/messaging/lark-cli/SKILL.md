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

## 文档操作命令

### 创建文档

```
cat content.md | lark-cli docs +create \
  --title "文档标题" \
  --markdown - \
  --as user
```

- 标题必填
- markdown 内容从 stdin 传入（lark-cli 不支持绝对路径 `--markdown`）
- 返回 `doc_id` 和 `doc_url`

### 读取文档内容

```
lark-cli docs +fetch \
  --doc "https://www.feishu.cn/docx/<doc_id>" \
  --as user \
  --format pretty
```

- `--format pretty` 输出 markdown 文本
- `--format json` 输出原始 JSON（含 block 结构）
- 支持 `--scope outline` 只看标题大纲

### 更新文档

```
cat content.md | lark-cli docs +update \
  --doc "https://www.feishu.cn/docx/<doc_id>" \
  --mode overwrite \
  --markdown - \
  --new-title "新标题（可选）" \
  --as user
```

- `--mode overwrite` — 完全替换内容
- `--mode append` — 追加到末尾
- `--markdown -` — 内容从 stdin 传入
- 可选 `--new-title` 同时修改标题

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

1. **markdown 路径限制：** `--markdown` 不支持绝对路径（如 `/tmp/file.md`）。必须用相对路径或 stdin 传参：`cat file.md | lark-cli ... --markdown -`

2. **v1 API 已弃用：** lark-cli 的 `docs +create/+fetch/+update` 默认用 v1 API（输出 deprecation 警告）。但 v2 API 需要确认 skill 已更新。更新命令：
   ```
   lark-cli update
   ```

3. **markdown 代码块渲染差异：** lark-cli 的 markdown 转换 对 ```bash 代码块支持有限，注意检查最终文档的代码块是否渲染正确。

4. **并发限制：** 飞书文档 API 每秒 3 QPS（单应用），单文档每秒 3 次并发编辑。批量操作需加延迟。

5. **`--as bot` vs `--as user`：** 这是最常见的坑。文档由谁创建，就用谁的身份操作。不确定时先 user 再 bot。
