---
name: podman-cli
description: Podman 容器运行时 — Docker 替代，开源无守护进程
last_used: 2026-06-11
---
# podman-cli — 容器管理 CLI

> 基于 Podman v5.8.2（Docker 兼容开源替代）。
> 路径: `D:\软件\Podman\podman.exe`

## 常用命令

```powershell
D:\软件\Podman\podman.exe ps              # 查看运行中的容器
D:\软件\Podman\podman.exe ps -a           # 所有容器
D:\软件\Podman\podman.exe images          # 查看镜像
D:\软件\Podman\podman.exe pull <image>    # 拉取镜像
D:\软件\Podman\podman.exe run <image>     # 运行容器
D:\软件\Podman\podman.exe stop <id>       # 停止容器
D:\软件\Podman\podman.exe rm <id>         # 删除容器
```

## 注意事项
- 与 docker CLI 命令兼容：`podman ps` = `docker ps`
- 不需要 Docker Desktop，无守护进程，更轻量
