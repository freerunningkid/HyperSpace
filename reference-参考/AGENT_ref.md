# AGENT.md 参考速查

## 执行闭环

| 做了什么 | 之后必须 | 否则就是 |
|---------|---------|---------|
| 改了代码 | 跑验证（测试/编译/诊断） | 没验证 = 没做完 |
| 跑了命令 | 读输出，确认 exit code | 没看输出 = 白跑 |
| 声称"修好了" | 复现原错误场景确认已不在 | 没复现 = 猜测 |
| 写了文件 | 重新读文件确认内容正确 | 没确认 = 可能写错位置 |

## 工作区路径

| 项目 | 路径 |
|------|------|
| ZCode 工作区 | `D:\Agent-ZCode` |
| ZCode 程序 | `D:\ZCode` |
| Reasonix 主工作区 | `D:\Reasonix` |
| 默认安装路径 | `D:\临时` |

### Reasonix 参考资源

| 资源 | 位置 |
|------|------|
| 技术知识库 | `D:\Reasonix\knowledge-知识库\` |
| 参考文档 | `D:\Reasonix\reference-参考\` |
| 工程项目黄页 | `D:\Reasonix\reference-参考\GitHub_Top_Projects_Guide.md` |
| 成长指南 | `D:\Reasonix\reference-参考\Reasonix成长指南-从优秀到卓越.md` |
| OCR 识别脚本 | `D:\Reasonix\scripts\lib\ocr.py` |
| Token/Key 文件目录 | `D:\Reasonix\scripts\lib\*token*.json`、`D:\Reasonix\scripts\lib\*_key*.json` |
| 学习资料 | `D:\Reasonix\learning-学习\` |

## 知识索引

Reasonix 记忆系统位于 `D:\Reasonix\memory/`：

| 文件 | 内容 |
|------|------|
| `profiles/preferences.md` | 沟通风格、编码习惯、TTS |
| `knowledge/domain.md` | 技术经验和踩坑记录 |
| `lessons/errors.md` | 错误分类与教训 |
| `decisions/decisions.md` | 架构决策与否决方案 |

需要相关技术知识时优先读取这些文件。

## 外部资源

项目黄页（500 个 20K+ Star 开源项目分类索引）：
`D:\Reasonix\reference-参考\GitHub_Top_Projects_Guide.md`
遇到困难时优先搜索此文件找现成方案。

## 笔记命名规范

`<类别>-<描述>-<YYYYMMDD_HHMMSS>.md`
前缀：账号-/工作-/技术-/笔记-/参考-/便签-
