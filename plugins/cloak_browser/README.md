# CloakBrowser 插件使用说明

## 简介

`cloak_browser` 是一个基于 [CloakBrowser](https://cloakbrowser.dev/) 的 stealth 浏览器自动化插件，用 C++ 源码级别的指纹修复替代了默认的 Playwright。

核心优势：
- **绕过 Cloudflare / reCAPTCHA / 各种 bot 检测**
- 使用实际修补过的 Chromium 二进制文件
- 覆盖了 9 个 `browser_*` 工具，替换默认实现

## 启用方式

在 `~/.hermes/config.yaml` 的 `plugins.enabled` 列表中添加 `cloak_browser`：

```yaml
plugins:
  enabled:
    - feishu_commands
    - feishu_format_check
    - cloak_browser
```

然后重启 gateway 生效。

## 提供的工具

| 工具 | 作用 |
|------|------|
| `browser_navigate(url)` | 打开 URL，返回页面快照 |
| `browser_snapshot(full=False)` | 获取当前页面快照 |
| `browser_click(ref)` | 点击元素（通过 ref ID） |
| `browser_type(ref, text)` | 在输入框输入文本 |
| `browser_scroll(direction)` | 滚动页面 |
| `browser_back()` | 返回上一页 |
| `browser_press(key)` | 键盘按键 |
| `browser_vision(question)` | 截图 |
| `browser_close()` | 关闭浏览器会话 |

## Ref ID 系统

`browser_navigate` 或 `browser_snapshot` 返回的快照中可交互元素有 `@eN` 类型的 ref ID：

```
Title: 百度一下，你就知道
Interactive elements:
  [@e1] <input> [placeholder="搜索"] >
  [@e2] <button> "百度一下" >
```

- `browser_click(ref="@e2")` — 点击按钮
- `browser_type(ref="@e1", text="天气")` — 输入文本

## 截图

`browser_vision(question="页面内容是什么")` 截图后返回路径，Hermes 用 `MEDIA:` 发送。

## 注意事项

- 首次启动会下载 Chrome 二进制（~200MB，缓存到 `~/.cloakbrowser/`）
- 每个会话 ID 独立管理浏览器实例
- 使用完调用 `browser_close()` 释放资源

## 调试记录

### v1.1 — 工具注册顺序修复

**问题：** 插件注册的 9 个 browser 工具在 gateway 启动后不可见，只有 `browser_close` 可用。

**根因：** 插件 `register()` 在 gateway 启动时先执行，注册了所有工具。但 `discover_builtin_tools()` 在第一个请求到来时（`model_tools` lazy import）才运行，用 `check_browser_requirements`（返回 False）覆盖了插件注册的 ToolEntry。

**修复：** `register()` 开头主动 `import model_tools`，强制 `discover_builtin_tools()` 先完成，插件再注册，确保 `_check_cloak_requirements` 是最终有效的 check_fn。