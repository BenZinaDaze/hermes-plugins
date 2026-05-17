# shellcrash-operations 技能说明

## 针对项目

**ShellCrash (juewuy/ShellCrash)** — https://github.com/juewuy/ShellCrash

Linux 命令行下的代理客户端管理工具，底层使用 mihomo (Clash Meta) 内核。

## 适用场景

你已经在服务器上装好了 ShellCrash，日常需要：

- 重启/查看 ShellCrash 服务状态
- 切换路由模式（TUN / Tproxy / 纯净）
- 切换 DNS 模式（fake-ip / redir-host）
- 切换代理组（谷歌服务走代理 / 节点选择 / 手动选节点）
- 测节点延迟
- 更新订阅
- 查日志 / 排错（尤其 Google 不通时）

## 核心原则

1. **能走 mihomo API 的，不走文件** — `PATCH /configs` 运行时生效，无需重启
2. **无 API 的操作用菜单管道** — `printf` 模拟菜单输入，代替 sed
3. **不编辑 yaml 配置文件** — 订阅更新会覆盖文件编辑；用 `store-selected` API 持久化代理组选择

## API 基础

- 地址：`http://127.0.0.1:9999`（ShellCrash 改写，不是配置里的 9090）
- 认证：无（ShellCrash 设空 secret）
- 完整端点清单见 SKILL.md 第十一章

## 安装前提

安装 ShellCrash 请使用 `linux-proxy-setup` 技能。本技能仅包含运维操作，不包含安装步骤。

## 文件位置

| 文件 | 用途 |
|------|------|
| `/etc/ShellCrash/configs/ShellCrash.cfg` | 持久化设置（路由模式、DNS 模式） |
| `/etc/ShellCrash/menu.sh` | 管理菜单 |
| `/tmp/ShellCrash/config.yaml` | 运行时配置（mihomo 实际加载的） |
| `/etc/ShellCrash/starts/clash_modify.sh` | 启动时重写 DNS 的钩子 |
