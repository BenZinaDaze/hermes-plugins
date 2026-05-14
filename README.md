# Hermes Plugins

收集 Hermes Agent 的插件和技能。

## 文件结构

```
hermes-plugins/
├── README.md
├── scripts/
│   └── install-feishu-buttons.sh
├── plugins/
│   └── feishu_commands/
│       ├── __init__.py
│       └── plugin.yaml
└── skills/
    └── feishu-buttons/
        └── SKILL.md
```

## 插件列表

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

## 添加新插件

1. 在 `plugins/` 下创建新目录
2. 放入 `__init__.py` 和 `plugin.yaml`
3. 在 `skills/` 下创建对应的 skill 文档（可选）
4. 更新本 README

## License
MIT
