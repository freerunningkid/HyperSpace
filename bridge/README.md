# ZCode ↔ Reasonix Bridge v1.0

三层防线之「文件兜底」——A2 (ZCode) 与 2B (Reasonix) 之间的文件 IPC。

## 整体架构

```
用户小金东 👑
    │
    ├──【主通道】聊天框 ────────────── 正常对话走这里
    │
    └──【保底通道】bridge/ 文件桥 ─── 异步/卡住时走这里
```

## 文件约定

| 文件 | 方向 | 方式 | 说明 |
|------|------|------|------|
| `inbox.txt` | A2 → 2B | 覆盖写 | A2 每次回复时同步写入，2B 直接读到最新内容 |
| `outbox.txt` | 2B → A2 | 覆盖写，读完清空 | 异步传指令，A2 处理完清空为空文件 |
| `stop.txt` | 手动 | 存在即停止 | 存在时 → 立即停止所有循环 |
| `state.json` | 自动 | 状态保持 | { round, last_msg_id, max_rounds } |
| `sent_log.txt` | 自动 | 追加 | AHK 发送去重记录 |

## 主通道：聊天框（AHK 辅助）

### 发消息到 ZCode
1. 记下当前窗口句柄（Reasonix）
2. AHK 激活 ZCode → 发送消息 → Enter
3. 立刻切回 Reasonix 窗口（0.5 秒内完成）

### 去重机制
每次发消息前查 `sent_log.txt`，已发过则跳过。

## 保底通道：文件桥

当聊天框卡住或需要异步通信时：

### outbox.txt（2B → A2）
- **写**：2B 覆盖写入指令
- **读**：A2 每次被调用时检查，读到内容即处理
- **清空**：A2 处理完后清空为空文件

### inbox.txt（A2 → 2B）
- **写**：A2 每次回复小金东时同步覆盖写入
- **读**：2B 直接读取，下次写入会覆盖

## 每次用户发消息时 — 先扫 ZCode（不可跳过）

每次用户说话时，第一件事不是回用户——是先查 ZCode：
1. pywinauto UIA 读取 ZCode 最新聊天文字
2. 如果有新回复 → 先告知用户，再回用户的话
3. 没新回复 → 正常回用户

用户插话不意味着 A2 没回复。

### 防呆机制
- stop.txt 存在 → 退出
- 连续空回复 3 次 → 暂停
- 轮次 ≥ max_rounds → 暂停，询问小金东
- 重复消息 → 跳过
- 没必要回的消息 → 不回（纯问候、单字、重复确认）

## 用法

```powershell
# 停止循环
New-Item D:\Reasonix\bridge\stop.txt -Force

# 查看最新回复
type D:\Reasonix\bridge\inbox.txt

# 发送回复（写入 outbox.txt，AHK 自动发出）
echo "回复内容" | Out-File D:\Reasonix\bridge\outbox.txt
```

## 协议历史

- **2026-06-17**：v1.0 定稿。由 2B 搭建基础桥，A2 加入文件直写能力，小金东批准三层防线方案
