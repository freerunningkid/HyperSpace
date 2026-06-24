# 贡献指南

感谢你对 HyperSpace 的关注！欢迎提交 Issue、PR 或参与讨论。

## 开发环境

```bash
git clone https://github.com/freerunningkid/HyperSpace.git
cd HyperSpace
pip install -e ".[dev]"
cp .env.example .env   # 编辑填入你的 API Key
```

## 运行测试

```bash
pytest tests/ -v        # 225 个单元测试, 零网络依赖
```

## 代码规范

- Python 3.10+，类型注解使用 `from __future__ import annotations`
- 异步统一用 `asyncio` + `httpx`
- 所有 API Key 从 `.env` 读取，严禁硬编码
- 新增功能必须有单元测试

## 提交 PR 前

1. `pytest tests/ -v` 全部通过
2. 新功能有对应测试覆盖
3. 不修改 `hyperspace/experimental/` 目录

## 架构

参见 [docs/architecture.md](docs/architecture.md)
