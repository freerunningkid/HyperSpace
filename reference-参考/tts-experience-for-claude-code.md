# TTS 语音输出 — 经验文档

> 给 ClaudeCode 的 TTS 集成指南。这个项目的 Agent（2B）需在每次回复结束时执行 TTS，
> 把自然语言朗读出来。以下是完整实现方案，不含任何新增需求，只记录已有事实。
>
> **状态:** 已在 `D:\Reasonix` 项目中稳定运行。Agent 强约束（CLAUDE.md TTS 铁律）保证不可跳过。

---

## 1. 架构概览

```
Agent 回复文本
  │
  ▼
speak.py（主入口，自动降级链）
  │
  ├─ ① Edge TTS streaming（ffplay 管道，首音 <500ms）   🥇
  ├─ ② Edge TTS save 模式（下载→ffplay/powershell 播放） 🥈
  └─ ③ SAPI5 本地合成（Xiaoxiao Natural / Huihui Desktop）🥉
```

- **不依赖外部服务**：Edge TTS 走微软在线语音，SAPI5 完全离线
- **语音:** 中文女声 Xiaoxiao（自然/明亮）
- **调用方式:** 纯 Python，一键调用

---

## 2. 核心脚本

### `speak.py` — 主引擎（D:\Reasonix\scripts\lib\speak.py）

```python
python speak.py "要朗读的文本"
python speak.py "要朗读的文本"    # 从 argv
echo "文本" | python speak.py    # 从 stdin
```

**关键行为：**

- `filter_text(text)` — 自动过滤代码块、URL、文件路径、hash 等，只留自然语言
- 如果过滤后为空（纯技术输出），不朗读
- 返回 exit code 0（成功）/ 1（全部失败）
- Agent 约束：每次回复最后一步必须调 `speak.py`，失败重试一次

### `voice_monitor.py` — 兜底方案（D:\Reasonix\scripts\mcp\voice_monitor.py）

```python
python voice_monitor.py                          # 监控最新会话
python voice_monitor.py --session <session-id>   # 监控指定会话
```

- 轮询 `.reasonix/sessions/` 下的 JSONL 文件
- 检测新 assistant 消息 → 自动调 `speak.py` 朗读
- 去重机制（content hash），不重复朗读
- 0.5 秒轮询间隔
- 作为 Agent 主动发言失败时的兜底层

---

## 3. 降级链详解

| 等级 | 引擎 | 优先顺序 | 延迟 | 网络要求 | 依赖 |
|------|------|---------|------|---------|------|
| 🥇 | Edge streaming | Windows 最高 | < 500ms | 需要 | `edge-tts` + `ffplay` |
| 🥈 | Edge save | 次高 | 2-5s | 需要 | `edge-tts` + `ffplay` 或 PowerShell |
| 🥉 | SAPI5 | 最低离线兜底 | 瞬时 | 无需 | `pywin32` |

`speak.py` 的 `speak()` 主入口自动按此链降级：
```python
if os.name == "nt":  # Windows 下 SAPI5 优先（响应更快）
    return speak_sapi5(text) or speak_edge_streaming(text) or speak_edge(text)
return speak_edge_streaming(text) or speak_edge(text) or speak_sapi5(text)  # 非 Windows
```

---

## 4. 依赖安装

```bash
# Edge TTS（流式 + 保存模式）
pip install edge-tts

# SAPI5 本地合成（Windows 专用）
pip install pywin32

# ffplay（流式播放器，需要从 ffmpeg 获取）
# 从 https://ffmpeg.org/download.html 下载
# 把 ffplay.exe 放到 PATH 中
```

---

## 5. 关键配置

### 5.1 语音
```python
VOICE = "zh-CN-XiaoxiaoNeural"  # 中文女声，明亮自然
```

### 5.2 Edge streaming 实现要点
```python
import edge_tts
communicate = edge_tts.Communicate(text, VOICE)

# ffplay stdin 管道 — 边下边播
proc = subprocess.Popen(
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-"],
    stdin=subprocess.PIPE,
)
for chunk in communicate.stream_sync():
    if chunk["type"] == "audio":
        proc.stdin.write(chunk["data"])
proc.stdin.close()
proc.wait(timeout=60)
```

### 5.3 SAPI5 实现要点
```python
import win32com.client
sp = win32com.client.Dispatch("SAPI.SpVoice")

# 优先 Xiaoxiao Natural（本地版）
for i in range(sp.GetVoices().Count):
    d = sp.GetVoices().Item(i).GetDescription().lower()
    if "xiaoxiao" in d and "natural" in d and "online" not in d:
        sp.Voice = sp.GetVoices().Item(i)
        break

sp.Speak(text, 0)  # 同步播放
```

---

## 6. Agent 集成规则

如果要在 Agent 中集成 TTS，需要：

1. **回复最后一步执行 TTS** — 不可跳过，优先级高于其他规则
2. **内容过滤** — 只朗读自然语言，过滤代码块、路径、URL
3. **失败重试** — `speak.py` 返回非零时自动重试一次
4. **兜底** — 可同时运行 `voice_monitor.py` 作为兜底

---

## 7. 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 无声音 | ffplay 未安装 | 安装 ffmpeg，确保 ffplay.exe 在 PATH |
| Edge 报错 | 网络不可达 | 自动降级到 SAPI5（无需操作） |
| SAPI5 报错 | `pywin32` 未安装 | `pip install pywin32` |
| 朗读技术内容 | `filter_text()` 遗漏 | 检查 filter_text 正则 |
| 重复朗读 | voice_monitor 冲突 | 确保只用一个 TTS 触发方式 |
| Agent 不朗读 | 约束未强制执行 | 参考 CLAUDE.md "TTS 铁律" |

---

## 8. 文件清单

| 文件 | 作用 |
|------|------|
| `scripts/lib/speak.py` | 主 TTS 引擎，降级链 |
| `scripts/mcp/voice_monitor.py` | 文件监控兜底 |
| `CLAUDE.md`（TTS 铁律节） | Agent 行为约束 |
