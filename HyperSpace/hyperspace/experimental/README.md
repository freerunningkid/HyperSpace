# ⚠ HyperSpace 实验性模块 — 法律警告

本目录 (`hyperspace/experimental/`) 下的代码用于个人学习浏览器自动化.

## ⚠️ 重要声明

1. **服务条款**: DeepSeek、Kimi 等聊天网页的服务条款禁止自动化/脚本访问.
   - DeepSeek ToS 第 3.5(3) 条明确禁止此行为.
2. **风险自负**: 使用本模块可能导致账号被封禁.
3. **仅个人学习**: 请勿用于商业用途或批量/并发请求.
4. **严格隔离**: 本模块:
   - 不接入 MCP 服务 (`hyperspace/server.py` **不**引用本模块)
   - 不写入 `.mcp.json`
   - 不纳入公开 release
5. **登录态**: 首次运行会打开浏览器窗口, 请手动扫码登录. 登录态会保存到 `data/` 目录.

## 使用

```bash
# 安装 Playwright (首次)
pip install playwright
python -m playwright install chromium

# 识图
python -m hyperspace.experimental.web_vision --image path/to/photo.jpg

# 通用对话（管道/参数皆可）
echo "你好，介绍一下你自己" | python -m hyperspace.experimental.web_probe --stdin
python -m hyperspace.experimental.web_probe "写一段冒泡排序"
```

## 文件说明

| 文件 | 用途 | 状态 |
|------|------|------|
| `session.py` | DeepSeek 会话管理 (共享登录态) | ✓ |
| `web_vision.py` | CLI: 传图片 → DeepSeek 网页端识图 | ✓ |
| `web_probe.py` | CLI: 通用文本对话 (支持参数/stdin) | ✓ |

---

*此模块不构成对任何厂商 ToS 的故意违反, 仅为个人学习 Playwright 自动化技术.*
