# 记忆互读验证 — 2026-06-09

> 目标：确认 Reasonix 和 Claude Code 两边都能读取 D:\Reasonix\memory\

## 共享记忆目录

```
D:\Reasonix\memory\          ← Git 仓库根目录下的记忆库
├── MEMORY.md                ← 记忆索引
├── decisions/               ← 架构决策
├── knowledge/               ← 技术经验
├── lessons/                 ← 错误教训
├── meta/                    ← 健康/冲突/changelog
├── patterns/                ← 模式候选项
├── profiles/                ← 用户画像
└── skills/proposals/        ← Skill 提议
```

## 同步方式

- **传输**: Git (github.com/freerunningkid/KID-Reasonix202606020008)
- **频率**: 会话开始前 pull，会话结束后 push
- **冲突**: 写入 memory/meta/conflicts.md，不做自动合并

## 两边访问验证

### Reasonix 侧 ✅
- 直接读写 D:\Reasonix\memory\（本地文件系统）
- remember() 工具写入的是这个目录
- CLAUDE.md 里配置的 memory/ 路径指向此处

### Claude Code 侧
- AgentWork 工作区通过 Git clone 获取
- 需要配置 CLAUDE.md 或 rules 指向 memory/ 目录
- 建议：在 AgentWork 的 CLAUDE.md 中添加 memory 路径映射

## 待确认
- [ ] 那边的 2B 是否已在 AgentWork 中配置了 D:\Reasonix\memory\ 的读取路径
- [ ] Git sync 脚本是否需要更新（两边写同一个 repo，确保 commit 不冲突）