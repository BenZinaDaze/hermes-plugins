---
name: shellcrash-operations
title: ShellCrash 日常运维操作
description: ShellCrash 日常操作命令速查 — 开关服务、切换模式、代理组切换、测速、查状态
triggers:
  - shellcrash restart
  - shellcrash status
  - shellcrash 操作
  - clash 切换
  - shellcrash switch node
  - shellcrash tproxy tun
category: devops
tags:
  - shellcrash
  - clash
  - mihomo
  - proxy
  - ops
---

# ShellCrash 日常运维操作

## 一、服务管理

```bash
# 启动
systemctl start shellcrash.service
# 或
bash /etc/ShellCrash/start.sh start

# 停止
systemctl stop shellcrash.service

# 重启（必须先提问用户是否允许）
systemctl restart shellcrash.service

# 开机自启
systemctl enable shellcrash.service

# 查看状态
systemctl status shellcrash.service --no-pager -l
```

## 二、运行时状态检查

```bash
# 进程和端口
ps aux | grep CrashCore | grep -v grep
ss -tlnp | grep CrashCore

# 当前模式
cat /etc/ShellCrash/configs/ShellCrash.cfg | grep -E '^(redir_mod|dns_mod)='

# 当前配置（订阅生成的运行时配置）
cat /tmp/ShellCrash/config.yaml head -n 80  # 看 mode / port / external-controller

# 查看 external-controller API 地址
cat /tmp/ShellCrash/config.yaml | grep external-controller
```

**API 基础地址**: `http://127.0.0.1:9999`（ShellCrash 改写为 9999，空 secret）

## 三、菜单速查

进入菜单：`bash /etc/ShellCrash/menu.sh`

| 功能 | 菜单路径 | 说明 |
|------|----------|------|
| 启动/停止核心 | 1 | 启动/停止 CrashCore |
| 功能设置 → 路由模式 | 2 → 1 | 切 TUN/Tproxy/纯净 |
| 功能设置 → DNS 设置 | 2 → 2 | 改 DNS 上游/模式 |
| 管理配置文件 → 在线获取 | 6 → 2 | 更新订阅 |
| 管理配置文件 → 切换 | 6 → 1 | 切换本地配置 |
| 工具与优化 → 测试菜单 | 8 → 1 | 测试连通性 |
| 高级功能 → 调试输出 | 9 → 7 | 开/关调试日志 |

**非交互式管道**（自动执行）：

```bash
# 切换到 TUN 模式
printf '2\n1\n2\n0\n0\n' | bash /etc/ShellCrash/menu.sh

# 更新订阅
printf '6\n2\n<订阅URL>\n1\n0\n0\n' | bash /etc/ShellCrash/menu.sh

# 重启核心
printf '1\n1\n0\n0\n' | bash /etc/ShellCrash/menu.sh
```

> 注意：菜单选项编号可能随服务状态变化（运行/停止时选项 4 含义不同）。推荐用 `printf` 时多跟几个 `0` 确保退出子菜单。

## 四、切换路由模式

### 修改配置文件（推荐，避免菜单交互）

```bash
# 切到 TUN 模式（mihomo 内核推荐）
sed -i 's/redir_mod=.*/redir_mod=Tun模式/' /etc/ShellCrash/configs/ShellCrash.cfg

# 切到 Tproxy 模式（仅 sing-box 内核推荐）
sed -i 's/redir_mod=.*/redir_mod=Tproxy模式/' /etc/ShellCrash/configs/ShellCrash.cfg

# 切回纯净模式（只开代理端口，不做透明代理）
sed -i 's/redir_mod=.*/redir_mod=纯净模式/' /etc/ShellCrash/configs/ShellCrash.cfg

# 重启生效
systemctl restart shellcrash.service
```

### 验证模式生效

```bash
cat /etc/ShellCrash/configs/ShellCrash.cfg | grep redir_mod
# 输出示例: redir_mod=Tun模式

# TUN 模式检查
ip link show utun 2>/dev/null && echo 'TUN interface OK' || echo 'No TUN'
```

## 五、DNS 模式切换

```bash
# 切到 fake-ip（推荐 — 避免 DNS 污染）
sed -i 's/dns_mod=.*/dns_mod=fake-ip/' /etc/ShellCrash/configs/ShellCrash.cfg

# 切到 redir_host
sed -i 's/dns_mod=.*/dns_mod=redir_host/' /etc/ShellCrash/configs/ShellCrash.cfg

# 重启生效
systemctl restart shellcrash.service

# 验证 fake-ip 生效（应返回 28.x.x.x 而非真实 IP）
dig +short google.com @127.0.0.1 -p 1053
```

> **注意**：`dns_mod=redir_host` 时，ShellCrash 的 `clash_modify.sh` 会在 `fake-ip-filter` 中注入 `'+.*'`，匹配所有域名 → 所有域名绕过 fake-ip 走国内 DNS → Google 等外站被污染。**切到 `fake-ip` 解决。**

## 六、代理组切换（API）

所有切换通过 mihomo 外部 API，`store-selected: true` 保证订阅更新后选择依然保留。

### 切换代理组（最常用）

```bash
# 🇬 谷歌服务 → 🚀 节点选择
curl -s -X PUT 'http://127.0.0.1:9999/proxies/%F0%9F%87%A8%20%E8%B0%B7%E6%AD%8C%E6%9C%8D%E5%8A%A1' \
  -H 'Content-Type: application/json' \
  -d '{"name":"🚀 节点选择"}'

# 🚀 节点选择 → 👉 手动选择
curl -s -X PUT 'http://127.0.0.1:9999/proxies/%F0%9F%9A%80%20%E8%8A%82%E7%82%B9%E9%80%89%E6%8B%A9' \
  -H 'Content-Type: application/json' \
  -d '{"name":"👉 手动选择"}'

# 🐟 漏网之鱼 → DIRECT
curl -s -X PUT 'http://127.0.0.1:9999/proxies/%F0%9F%90%9F%20%E6%BC%8F%E7%BD%91%E4%B9%8B%E9%B1%BC' \
  -H 'Content-Type: application/json' \
  -d '{"name":"DIRECT"}'
```

### URL 编码助手

```python
# 获取中文/Emoji 组名的 URL 编码
python3 -c "import urllib.parse; print(urllib.parse.quote('🇬 谷歌服务'))"
# → %F0%9F%87%A8%20%E8%B0%B7%E6%AD%8C%E6%9C%8D%E5%8A%A1
```

### 查看当前选择

```bash
curl -s 'http://127.0.0.1:9999/proxies' | python3 -c "
import sys, json
d = json.load(sys.stdin)
for name, g in d.get('proxies', {}).items():
    if g.get('type') == 'Selector':
        print(f'{name}: {g.get(\"now\")}')
"
```

### 列出组内所有节点

```bash
curl -s 'http://127.0.0.1:9999/proxies' | python3 -c "
import sys, json
d = json.load(sys.stdin)
manual = d['proxies']['👉 手动选择']
for i, p in enumerate(manual['all'], 1):
    print(f'{i:2d}. {p}')
"
```

### 选具体节点

```bash
# 在 👉 手动选择 中选一个节点
curl -s -X PUT 'http://127.0.0.1:9999/proxies/%F0%9F%91%89%20%E6%89%8B%E5%8A%A8%E9%80%89%E6%8B%A9' \
  -H 'Content-Type: application/json' \
  -d '{"name":"🇺🇸 DMIT xtls-reality"}'
```

### 错误处理

- `{"message":"Selector update error: proxy not exist"}` — 选中的是子组名（如