---
name: idm-first-for-downloads
description: 下载任务优先用 IDM skill，不要用 curl/wget 徒劳试 30 轮。2026-06-04 安装 OpenCode 的教训。
metadata:
  type: feedback
---

**教训：** 2026-06-04 安装 OpenCode 时，IDM skill 路径已确认存在（`D:\软件\Internet Download Manager\IDM\IDMan.exe`），但我第一次调用后没坚持推进，转而用 curl/wget/PowerShell/BITS 等尝试了 30+ 轮，浪费大量时间。最后小金东自己用 IDM 几分钟就下完了。

**Why:** IDM 是国内 GitHub 下载的最佳方案，直连速度 1MB/min vs IDM 多线程可达几十 MB/min。skill 设计的目的就是避免这种低效探索。

**How to apply:** 任何文件下载任务（特别是 GitHub Release），第一选择始终是 IDM skill。确认 IDMan.exe 路径存在 → 构造 `/d /n /s /p` 命令 → `cmd.exe /c` 执行。不做其他尝试。
