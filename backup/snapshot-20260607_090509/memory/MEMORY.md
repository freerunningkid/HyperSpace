# Memory

- [App Execution Alias 必须用 VBScript ShellExecute](app-execution-alias-vbs-launcher.md) — App Execution Alias (0字节 wt.exe) 需用 VBScript ShellExecute 启动
- [Claude Code 原生二进制恢复步骤](claude-code-binary-restore.md) — claude.exe 占位脚本替换为 230MB 原生二进制的完整流程
- [右键菜单先查参考再改](context-menu-fix-by-reference.md) — 右键菜单修复前先查同类参考，照着抄不要发明
- [context menu icon needs 0 suffix](context-menu-icon-needs-0-suffix.md) — 注册表 Icon 值必须加 ,0 后缀指定资源索引
- [context menu no flash pattern](context-menu-no-flash-pattern.md) — 右键菜单无闪烁启动模式：cmd /c start /B
- [右键菜单命令直接写 wt.exe 即可](context-menu-wt-direct.md) — 右键菜单启动 wt.exe 直接注册表写，不需 start/B 或 VBS
- [idm first for downloads](idm-first-for-downloads.md) — 下载任务优先用 IDM skill，不要用 curl/wget 徒劳试 30 轮。2026-06-04 安装 OpenCode 的教训。
- [Ollama Proxy 解决 VS Code 响应过长](ollama-proxy-vscode-response-too-long.md) — Ollama Proxy + qwen3.5:copilot 解决 VS Code "Response too long"
- [Windows Python GBK 编码修复](python-windows-gbk-encoding.md) — Windows Python 控制台 GBK 编码报错修复
- [Ctrl+C 复制 / Esc 打断键盘修改](reasonix-keyboard-ctrlfix.md) — Ctrl+C always copies in Reasonix, Esc interrupts
- [注册表：HKCU 无需管理员](registry-hkcu-vs-hkcr.md) — HKCU 路径无需管理员添加右键菜单注册表项
- [Shift 组合键失效排查指南](shift-keys-troubleshoot.md) — Shift 组合键失效的三大根因：粘滞键、输入法中英文切换、语言栏热键冲突
