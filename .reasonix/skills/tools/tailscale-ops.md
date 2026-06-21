---
name: tailscale-ops
description: Tailscale 组网运维：状态检查/设备管理/ACL规则/故障排查。
last_used: never
---
# tailscale-ops — Tailscale 运维技能

> 管理 Tailscale 虚拟组网，实现跨设备安全访问。

## 设备信息

| 设备 | Tailscale IP | 用途 |
|------|-------------|------|
| **办公 PC** | `<TAILSCALE_IP_OFFICE>` | 日常开发/Reasonix 主环境 |
| **家用 PC** | `<TAILSCALE_IP_HOME>` | 备用/大模型推理 |
| **手机 (Termux)** | 动态 | SSH 远程办公 PC |

## 常用命令

### 状态检查
```bash
# 查看 Tailscale 状态
tailscale status

# 查看本机 IP
tailscale ip

# 查看服务状态
tailscale status --json | python -m json.tool
```

### 设备管理
```bash
# 列出所有在线设备
tailscale status --online

# 查看设备详情
tailscale status <device-name>

# 重启 Tailscale
net stop tailscale && net start tailscale
# 或
Restart-Service tailscaled
```

### SSH 远程连接
```bash
# 从手机 SSH 到办公 PC
ssh kid@<TAILSCALE_IP_OFFICE>

# 从手机 SSH 到家用 PC
ssh kid@<TAILSCALE_IP_HOME>
```

### 故障排查
```bash
# 检查 Tailscale 服务
Get-Service tailscale*

# 查看日志
Get-EventLog -LogName Application -Source Tailscale -Newest 20

# 重置 DNS
ipconfig /flushdns
```

## 与 Claude Code 手机远程集成

```bash
# 手机端 (Termux)
termux-wake-lock          # 防止后台断连
ssh kid@<TAILSCALE_IP_OFFICE>    # 连接办公 PC
cd D:\Reasonix           # 进入工作目录
claude                    # 启动 Claude Code

# 用完释放
termux-wake-unlock
```

## 防火墙规则

```powershell
# 检查 Tailscale 防火墙规则
netsh advfirewall firewall show rule name=all | Select-String Tailscale

# Tailscale 通常自动管理防火墙，无需手动配置
```

## 注意事项

- Tailscale IP 可能变化，建议使用 device name 而非 IP
- 手机 Termux 需设置电池优化为"无限制"
- SSH 连接需确保 Windows SSH Server 服务已启动
- 跨网络访问时，确保两台设备都在同一 Tailnet 中
