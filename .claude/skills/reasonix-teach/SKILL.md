---
name: teach
description: 教小金东新技能：基于最近发展区+检索练习+间隔重复，用于一造备考和技术学习
---

# teach — 教小金东新技能或概念

> 来源: [mattpocock/skills](https://github.com/mattpocock/skills) (133k ⭐)
> 适配: Reasonix Code

## 核心原则

三层学透：**知识 → 技能 → 智慧**

- **知识**：从高质量资源抓，不靠我记忆瞎编
- **技能**：通过交互式课程 + quiz + 即时反馈掌握
- **智慧**：去社区真刀真枪用出来

## 执行流程

### Step 1：确定 Mission

如果 `MISSION.md` 不存在或未填充，先问用户为什么要学这个。没有 Mission 的学习是散的。

### Step 2：加载教学工作区

学习状态存在 `learning-学习/<主题>/` 目录下：
- `MISSION.md` — 学习目标
- `reference/` — 速查表、算法、口诀
- `RESOURCES.md` — 高质量外部资源索引
- `learning-records/` — 学习记录（非显而易见的洞察）
- `lessons/` — 单课 HTML 输出
- `NOTES.md` — 用户偏好笔记

### Step 3：评估最近发展区

读 learning-records → 判断当前水平 → 教"刚好够难"的内容

### Step 4：设计课程

- 短课时（一次教一个知识点）
- 包含检索练习（不直接给答案）
- 间隔重复（不同时间复习）
- 混合出题（技能练习时）

### Step 5：课后写学习记录

每次课后写一条 learning-record，记录非显而易见的洞察。

## 约束

- ❌ 不要依赖自己的参数知识——先去 RESOURCES.md 找高质量来源
- ❌ 不要一次教太多——工作记忆很小
- ❌ 不要跳过 retrieval practice——流畅≠记住
- ✅ 用 quiz 和反馈环巩固技能
- ✅ 每课链接到 reference 和外部资源
