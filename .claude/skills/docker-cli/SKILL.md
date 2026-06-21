---
name: docker-cli
description: Docker 容器管理 — 运行/管理容器和镜像
last_used: 2026-06-11
---
# docker-cli — Docker 容器 CLI

> 基于 Docker v29.5.2，在 PATH 中可用。

## 常用命令

```powershell
docker ps                     # 运行中的容器
docker ps -a                  # 所有容器
docker images                 # 本地镜像
docker pull <image>           # 拉取镜像
docker run <image>            # 运行容器
docker stop <id>              # 停止
docker rm <id>                # 删除
docker compose up -d          # 启动 compose 服务
docker logs <id>              # 查看日志
docker exec -it <id> sh       # 进入容器
```

## 注意事项
- 需要 Docker Desktop 后台运行
- 轻量任务可用 podman 替代（语法兼容，不需要桌面端）
