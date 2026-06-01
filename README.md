# KID-Reasonix202606020008

Reasonix 全配置同步仓库 — 家里 ↔ 办公室无缝衔接。

## 办公室首次部署

```bat
git clone https://github.com/freerunningkid/KID-Reasonix202606020008.git
cd KID-Reasonix202606020008
setup.bat
```

## 日常同步

```bat
# 下班前（家里）
git add -A && git commit -m "sync" && git push

# 上班后（办公室）
git pull
setup.bat
```

反之亦然：办公室做完事 push，回家 pull。

## 包含内容

| 目录/文件 | 说明 |
| --- | --- |
| `config/reasonix/` | Reasonix 配置 + 会话历史 |
| `config/claude/` | Claude Code 全局记忆(CLAUDE.md)、settings、plans、projects、todos |
| `scripts/mcp/` | MCP 脚本（voice_monitor / voice_server） |
| `reasonix-voice.bat` | 语音启动脚本 |

## 注意事项

- 仓库已排除 `dist/`、`node.exe` 等 Reasonix 安装文件，办公室需先安装 Reasonix 本体
- 仓库为 **Private**，含 API key 等敏感信息，勿公开
