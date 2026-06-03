# Superpowers 插件

Superpowers 是一个 Claude Code 增强插件，安装后 AI 会自动获得一套完整的工作流技能——从需求分析、方案设计、代码编写到测试验证，全程自主完成。

你只需要描述想做什么，剩下的交给 AI。

## 安装

在 Claude Code 终端中依次运行以下两条命令：

```bash
# 1. 注册插件市场
/plugin marketplace add obra/superpowers-marketplace

# 2. 从市场安装 Superpowers
/plugin install superpowers@superpowers-marketplace
```

安装完成后重启 Claude Code 即可生效。

## 使用方式

启动一个新的 Claude Code 对话，然后输入：

```
/brainstorming 描述你想做的事情
```

例如：

```
/brainstorming 用 React 做一个待办事项应用，支持添加、删除、标记完成
```

接下来你只需要坐好，跟着 AI 的引导走。Superpowers 会自动：

1. **分析需求** — 和你确认功能细节和技术选型
2. **制定计划** — 拆分任务，设计实现方案
3. **编写代码** — 逐步实现每个功能模块
4. **测试验证** — 运行测试确保代码正确
5. **代码审查** — 自动检查代码质量

整个过程中 AI 会在关键节点询问你的意见，你只需要回答即可。

## 了解更多

- [Superpowers GitHub 仓库](https://github.com/obra/superpowers) — 完整文档和源码
- [实际使用演示](https://blog.fsck.com/blog/2025/superpowers/superpowers-demo.txt) — 一个用 Superpowers 从零构建 Todo App 的完整对话记录
