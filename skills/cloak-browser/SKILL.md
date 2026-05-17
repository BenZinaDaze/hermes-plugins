---
name: cloak-browser
description: 使用 CloakBrowser 插件进行 stealth 浏览器自动化 — 绕过 bot 检测、CF、reCAPTCHA
---

# CloakBrowser 使用指南

## 何时使用

当需要打开网页、抓取内容、自动化操作、绕过 Cloudflare/reCAPTCHA 时，优先使用 cloak_browser 插件（已覆盖默认 browser_* 工具）。

## 启动方式

通过 `browser_navigate(url)` 自动启动。首次使用会自动下载 Chrome 二进制（约 200MB）。

## 工作流程

1. **打开页面** — `browser_navigate(url="https://example.com")`
   - 返回快照 + 交互元素列表（含 ref ID `@e1`, `@e2`...）
2. **查看元素** — `browser_snapshot(full=True)` 获取完整文本
3. **交互操作**
   - 点击：`browser_click(ref="@e2")`
   - 输入：`browser_type(ref="@e1", text="搜索内容")`
   - 滚动：`browser_scroll(direction="down")`
   - 键盘：`browser_press(key="Enter")`
4. **截图** — `browser_vision(question="页面上有什么")`
   - 返回 `screenshot_path`，用 `MEDIA:` 发送到平台
5. **关闭** — `browser_close()` 释放资源

## 注意事项

- 截图用 `vision_analyze` 看图，不要重复调用 `browser_vision` 截图
- 每个会话 ID 独立管理浏览器实例
- 完成后务必 `browser_close()`
- 插件注册在 gateway 层面，子 agent 需通过 `delegate_task(toolsets=['browser'])` 使用
