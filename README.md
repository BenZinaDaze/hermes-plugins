# Hermes Plugins

收集 Hermes Agent 的插件和技能。

## 文件结构

```
hermes-plugins/
├── README.md
├── scripts/
│   └── install-feishu-buttons.sh
├── plugins/
│   ├── feishu_commands/      — 飞书按钮卡片
│   ├── cloak_browser/        — 隐身浏览器自动化
│   └── feishu_format_check/  — 飞书格式净化
└── skills/
    ├── feishu-buttons/                   — 飞书按钮卡片技能
    ├── cloak-browser/                    — CloakBrowser 使用指南
    └── devops/shellcrash-operations/     — ShellCrash 日常运维
```

## 插件列表

---

### feishu_commands — 飞书按钮卡片

用飞书交互卡片按钮代替斜杠命令打字，点击即发送。

**安装：**

```bash
# 一键安装（替换 YOUR_USER 为你的 GitHub 用户名）
bash <(curl -sSL https://raw.githubusercontent.com/YOUR_USER/hermes-plugins/main/scripts/install-feishu-buttons.sh) YOUR_USER/hermes-plugins
```

**手动安装：**

```bash
mkdir -p ~/.hermes/plugins/feishu_commands
cp plugins/feishu_commands/* ~/.hermes/plugins/feishu_commands/
```

然后在 `~/.hermes/config.yaml` 中启用：

```yaml
plugins:
  enabled:
    - feishu_commands
```

重启网关：

```bash
hermes gateway restart
```

**使用：**

AI 助手调用 `feishu_show_buttons` 工具发送卡片，用户点击按钮即可执行命令。

**工作原理：**

1. 用户点击按钮 → 飞书通过 WebSocket 发送 card_action_trigger
2. 网关路由为合成命令 `/card button {...}`
3. 插件 hook 拦截，通过 REST API 将命令作为真实文本消息发回会话
4. 网关正常处理并回复

---

### cloak_browser — 隐身浏览器自动化

基于 [CloakBrowser](https://github.com/nousresearch/cloak-browser) 的隐身浏览器插件，绕过 Cloudflare、reCAPTCHA 等 bot 检测。

**安装：**

```bash
mkdir -p ~/.hermes/plugins/cloak_browser
cp plugins/cloak_browser/* ~/.hermes/plugins/cloak_browser/
```

在 `~/.hermes/config.yaml` 中启用：

```yaml
plugins:
  enabled:
    - cloak_browser
```

重启网关：

```bash
hermes gateway restart
```

依赖：需要在环境变量或 `.env` 中配置 CloakBrowser API key（`CLOAK_BROWSER_API_KEY`）。

---

### feishu_format_check — 飞书格式净化

自动移除飞书消息中的表格、标题、分割线等不支持的富文本格式，确保输出兼容飞书渲染。

**安装：**

```bash
mkdir -p ~/.hermes/plugins/feishu_format_check
cp plugins/feishu_format_check/* ~/.hermes/plugins/feishu_format_check/
```

在 `~/.hermes/config.yaml` 中启用：

```yaml
plugins:
  enabled:
    - feishu_format_check
```

重启网关：

```bash
hermes gateway restart
```

---

## 技能列表

### feishu-buttons

配合 feishu_commands 插件使用的技能文档，定义飞书按钮卡片的用法和注意事项。

### cloak-browser

CloakBrowser 技能文档，涵盖浏览器导航、点击、截图等操作的最佳实践。

### shellcrash-operations

ShellCrash 日常运维命令速查：服务管理、模式切换、API 代理组切换、节点测速、故障诊断。

---

## 添加新插件/技能

1. `plugins/` 下创建插件目录（`__init__.py` + `plugin.yaml`）
2. `skills/` 下创建对应技能文档（`SKILL.md`）
3. 更新本 README
4. 提交并推送

## License

MIT
