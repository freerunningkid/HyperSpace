# 2B 灵魂层 — 记忆

> 技术经验、纠错教训、架构决策、模式观察。evolve 自动维护。

## 技术经验
- voice_server.py 路径必须用相对路径
- Reasonix run_command 不支持 & && 链式操作
- 中文路径引号异常 → 用 python -c 绕过
- DeepSeek V4 Anthropic 端点：https://api.deepseek.com/anthropic
- DeepSeek 自动前缀缓存，头部稳定即可享受 93%+ 命中率

## ZCode 架构
- Electron 应用，Chrome_WidgetWin_1 窗口类
- 配置分层：v2/config.json（UI）+ cli/config.json（CLI）
- 聊天存 SQLite → message + part 表
- UI 自动化：pywinauto UIA 零成本读控件文本

## 对话桥 v1.0
- 三层防线：UIA → OmniParser → 文件桥
- 文件协议：inbox/outbox 覆盖写
- 发后焦点恢复，去重：sent_log.txt
- Enter 不可靠 → AHK + pywinauto 点发送

## 决策记录
- D-001: 工作区从 AgentWork 迁移至 Reasonix
- D-009: ZCode DeepSeek V4 + 多 Agent 桥接
- D-010: UI 操控优先底层，视觉仅辅助
