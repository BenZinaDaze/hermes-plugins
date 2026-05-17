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

所有运行时操作优先走 mihomo API（:9999），避免编辑文件。
持久化配置（路由模式等）走菜单管道，不用 sed。

**API 基础地址**: `http://127.0.0.1:9999`（ShellCrash 改写为 9999，空 secret）

---

## 一、服务管理

```bash
# 启动
systemctl start shellcrash.service
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

---

## 二、运行时状态检查

```bash
# 进程和端口
ps aux | grep CrashCore | grep -v grep
ss -tlnp | grep CrashCore

# 当前运行时模式
curl -s 'http://127.0.0.1:9999/configs' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Mode:', d.get('mode'))
print('TUN:', d.get('tun',{}).get('enable'))
print('Mixed port:', d.get('mixed-port'))
print('Log level:', d.get('log-level'))
"

# 查看 external-controller API 地址
cat /tmp/ShellCrash/config.yaml | grep external-controller
```

---

## 三、菜单速查

进入菜单：`bash /etc/ShellCrash/menu.sh`

- **启动/停止核心**: 菜单 1
- **功能设置 路由模式**: 菜单 2 1（TUN/Tproxy/纯净）
- **功能设置 DNS 设置**: 菜单 2 2
- **管理配置文件 在线获取**: 菜单 6 2（更新订阅）
- **管理配置文件 切换**: 菜单 6 1（切换本地配置）
- **工具与优化 测试菜单**: 菜单 8 1
- **高级功能 调试输出**: 菜单 9 7

**非交互式管道**（自动执行）：

```bash
# 切换到 TUN 模式
printf '2\n1\n2\n0\n0\n' | bash /etc/ShellCrash/menu.sh

# 更新订阅
printf '6\n2\n<订阅URL>\n1\n0\n0\n' | bash /etc/ShellCrash/menu.sh

# 重启核心
printf '1\n1\n0\n0\n' | bash /etc/ShellCrash/menu.sh
```

注意：菜单选项编号可能随服务状态变化。推荐用 printf 时多跟 0 确保退出子菜单。

---

## 四、切换路由模式（无 API，走菜单管道）

路由模式（TUN/Tproxy/纯净）是 ShellCrash 层配置，无 API 接口。使用菜单管道代替 sed：

```bash
# 切 TUN 模式（mihomo 内核推荐）
printf '2\n1\n2\n0\n0\n' | bash /etc/ShellCrash/menu.sh
systemctl restart shellcrash.service

# 切 Tproxy 模式（仅 sing-box）
printf '2\n1\n3\n0\n0\n' | bash /etc/ShellCrash/menu.sh
systemctl restart shellcrash.service

# 切纯净模式
printf '2\n1\n1\n0\n0\n' | bash /etc/ShellCrash/menu.sh
systemctl restart shellcrash.service
```

**验证**：

```bash
# 看运行时 TUN 状态
curl -s 'http://127.0.0.1:9999/configs' | python3 -c "import sys,json;d=json.load(sys.stdin);print('TUN:',d.get('tun',{}).get('enable'))"

# TUN 设备检查
ip link show utun 2>/dev/null && echo 'TUN OK' || echo 'No TUN'

# 查看持久化配置
cat /etc/ShellCrash/configs/ShellCrash.cfg | grep redir_mod
```

---

## 五、DNS（通过 API 运行时切换）

所有 DNS 操作通过 `PATCH /configs` 在运行时生效，无需重启。

### 切到 fake-ip（推荐，避免 DNS 污染）

```bash
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"dns":{"enable":true,"enhanced-mode":"fake-ip","nameserver":["https://doh.pub/dns-query","https://223.5.5.5/dns-query"]}}'
```

### 切到 redir-host

```bash
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"dns":{"enable":true,"enhanced-mode":"redir-host","nameserver":["https://doh.pub/dns-query","https://223.5.5.5/dns-query"]}}'
```

### 修改 fake-ip-filter（避免所有域名绕过 fake-ip）

```bash
# 覆盖 fake-ip-filter（清掉 '+.*'、保留合理的本地域名）
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"dns":{"fake-ip-filter":["*.lan","*.local","*.localhost","*.home.arpa"]}}'
```

### 验证效果

```bash
# fake-ip 应返回 28.x.x.x
dig +short google.com @127.0.0.1 -p 1053

# 查看 DNS 运行时配置
curl -s 'http://127.0.0.1:9999/configs' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Mode:', d.get('mode'))
"
```

注意：API 修改的是运行时 DNS，重启后被 ShellCrash 的 `clash_modify.sh` 覆盖。如需持久化，需配合更改 ShellCrash.cfg 中 dns_mod 的值。

---

## 六、代理组切换（API）

所有切换通过 mihomo API，`store-selected: true` 保证订阅更新后选择保留。

### 切换代理组

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

### URL 编码

```python
python3 -c "import urllib.parse; print(urllib.parse.quote('🇬 谷歌服务'))"
```

### 查看所有 Selector 组的当前选择

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
curl -s -X PUT 'http://127.0.0.1:9999/proxies/%F0%9F%91%89%20%E6%89%8B%E5%8A%A8%E9%80%89%E6%8B%A9' \
  -H 'Content-Type: application/json' \
  -d '{"name":"🇺🇸 DMIT xtls-reality"}'
```

---

## 七、节点测速

### 一键测所有手动选择节点

```bash
python3 -c "
import json, urllib.request, urllib.parse

base = 'http://127.0.0.1:9999'
proxies = json.load(urllib.request.urlopen(f'{base}/proxies'))
manual = proxies['👉 手动选择']['all']

for name in manual:
    if name not in proxies:
        continue
    encoded = urllib.parse.quote(name, safe='')
    url = f'{base}/proxies/{encoded}/delay?url=https://cp.cloudflare.com/generate_204&timeout=5000'
    try:
        resp = json.load(urllib.request.urlopen(url, timeout=10))
        delay = resp.get('delay', 'TIMEOUT')
    except:
        delay = 'TIMEOUT'
    status = '✅' if isinstance(delay, int) and delay < 500 else '⚠️' if isinstance(delay, int) else '❌'
    print(f'{status} {name:40s} {str(delay):>6}ms')
"
```

### 测单个节点

```bash
curl -s "http://127.0.0.1:9999/proxies/$(python3 -c "import urllib.parse; print(urllib.parse.quote('🇺🇸 DMIT xtls-reality'))")/delay?url=https://cp.cloudflare.com/generate_204&timeout=5000"
```

---

## 八、连通性测试

```bash
# 透明代理测试（自动走规则）
for url in 'https://www.bing.com' 'https://www.google.com' 'https://www.baidu.com' 'https://www.youtube.com'; do
  echo "=== $url ==="
  curl -s -o /dev/null -w 'HTTP %{http_code} | %{time_total}s\n' --max-time 10 --connect-timeout 10 "$url" 2>&1
done

# 显式代理端口（绕过透明代理，直接验证节点）
curl -s -o /dev/null -w 'HTTP %{http_code} | %{time_total}s\n' -x http://127.0.0.1:7890 --max-time 10 https://www.google.com

# 切到全局模式验证节点
curl -s -X PATCH 'http://127.0.0.1:9999/configs' -H 'Content-Type: application/json' -d '{"mode":"global"}'
curl -s -o /dev/null -w '%{http_code} %{time_total}s' --max-time 10 https://www.google.com
curl -s -X PATCH 'http://127.0.0.1:9999/configs' -H 'Content-Type: application/json' -d '{"mode":"rule"}'
```

---

## 九、订阅管理

### 更新订阅

```bash
printf '6\n2\n<订阅URL>\n1\n0\n0\n' | bash /etc/ShellCrash/menu.sh
systemctl restart shellcrash.service
```

### 查看提供商和节点

```bash
curl -s 'http://127.0.0.1:9999/providers/proxies' | python3 -c "
import sys, json
d = json.load(sys.stdin)
for n, prov in d.get('providers', {}).items():
    print(f'--- {n} ({len(prov.get(\"proxies\",[]))} nodes) ---')
    for p in prov.get('proxies', []):
        print(f'  {p[\"name\"]}')
"
```

### 查看运行配置信息

```bash
cat /tmp/ShellCrash/config.yaml | wc -l
cat /tmp/ShellCrash/config.yaml | grep -E '^(mode|port|external-controller|log-level):'
```

---

## 十、日志与诊断

```bash
# systemd 日志
journalctl -u shellcrash.service -n 50 --no-pager
journalctl -u shellcrash.service -f  # 实时跟踪

# 启动日志
cat /tmp/ShellCrash/start.log 2>/dev/null | tail -30

# 开启调试日志（API，无需重启）
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"log-level":"debug"}'

# 恢复 info 级别
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"log-level":"info"}'

# 实时流量监控
curl -s -N 'http://127.0.0.1:9999/traffic' | head -c 2000
```

---

## 十一、API 端点速查

| 操作 | API | 方法 |
|------|-----|------|
| 查看运行时配置 | /configs | GET |
| 修改运行时配置 | /configs | PATCH |
| 改运行模式 (rule/global/direct) | /configs `{"mode":"..."}` | PATCH |
| 改 DNS | /configs `{"dns":{...}}` | PATCH |
| 改日志级别 | /configs `{"log-level":"..."}` | PATCH |
| 切换代理组 | /proxies/ENCODED_GROUP | PUT |
| 测节点延迟 | /proxies/ENCODED/delay | GET |
| 查看所有代理/组 | /proxies | GET |
| 查看提供商 | /providers/proxies | GET |
| 查看规则 | /rules | GET |
| 查看版本 | /version | GET |
| 流量实时 | /traffic | GET (stream) |
| 查看内存 | /memory | GET |

---

## 十二、常见问题速查

### Google 不通 — 三步定位

```bash
# 1. 显式代理测试（验证节点）
curl -s -o /dev/null -w '%{http_code} %{time_total}s' -x http://127.0.0.1:7890 https://www.google.com

# 2. 透明代理测试
curl -s -o /dev/null -w '%{http_code} %{time_total}s' https://www.google.com

# 3. 其他 Google 服务（区分 IP 封禁和配置问题）
curl -s -o /dev/null -w '%{http_code} %{time_total}s' https://fonts.googleapis.com
```

| 显式代理 | 透明代理 | 其他 Google | 结论 |
|----------|----------|-------------|------|
| ✅ 200 | ✅ 200 | ✅ | 正常 |
| ❌ 000 | ❌ 000 | ✅ | **节点 IP 被谷歌 CDN 阻止**，换节点 |
| ❌ 000 | ❌ 000 | ❌ | **节点/代理连接问题** |
| ✅ 200 | ❌ 000 | ✅/❌ | **Tproxy+mihomo 问题** 切 TUN |
| ✅ 200 | ❌ 000 | 显式也 ok | **DNS 污染** 切 fake-ip |

**修复命令**（全部通过 API，不编辑文件）：

```bash
# 1. DNS 切 fake-ip（运行时）
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"dns":{"enhanced-mode":"fake-ip"}}'

# 2. 谷歌服务切到代理组
curl -s -X PUT 'http://127.0.0.1:9999/proxies/%F0%9F%87%A8%20%E8%B0%B7%E6%AD%8C%E6%9C%8D%E5%8A%A1' \
  -H 'Content-Type: application/json' \
  -d '{"name":"🚀 节点选择"}'

# 3. 切换到全局模式绕过规则问题
curl -s -X PATCH 'http://127.0.0.1:9999/configs' \
  -H 'Content-Type: application/json' \
  -d '{"mode":"global"}'
```

---

## 十三、文件路径

- `/etc/ShellCrash/configs/ShellCrash.cfg` — ShellCrash 设置（持久化）
- `/etc/ShellCrash/menu.sh` — 管理菜单
- `/etc/ShellCrash/start.sh` — 核心启停
- `/tmp/ShellCrash/config.yaml` — 运行时配置（CrashCore 实际加载的）
- `/tmp/ShellCrash/CrashCore` — 运行中的二进制
- `/etc/ShellCrash/starts/clash_modify.sh` — 启动时改写 DNS 的钩子
- `/etc/ShellCrash/yamls/` — 存储的本地配置
- `/etc/ShellCrash/ruleset-d/` — 规则集文件