---
name: knowledge-explore
description: 知识图谱探索技能。搜索教育知识图谱中的实体，查看知识点的前置依赖、包含关系和常见错误。当需要理解知识结构、规划教学路径、查找关联知识点时触发。可配合genui生成图谱可视化。
---

# KAG-Pro 知识图谱探索

## 使用场景
- 理解知识点之间的前置依赖关系
- 查找某知识点的常见错误
- 规划教学路径和学习顺序
- 探索知识点之间的关联

## 工作流程
1. 调用 `kag_pro_kg_search` MCP 工具，传入搜索关键词
2. 工具在知识图谱中搜索匹配实体
3. 对每个实体返回：实体信息、前置知识列表、常见错误列表
4. 知识图谱覆盖高中数学、物理、化学主要知识点

## 知识图谱关系类型
- **prerequisite**: A 是 B 的前置知识（学B之前需先掌握A）
- **contains**: A 包含 B（B是A的子知识点）
- **related_to**: A 与 B 相关联
- **common_mistake**: A 的常见错误是 B

## Qoder 技能集成

### genui 集成
搜索结果可使用 genui 的 `show_widget` 工具渲染：
- 实体-关系图（节点=知识点，边=关系类型）
- 前置知识依赖链可视化
- 常见错误提示卡片

## 示例
调用：kag_pro_kg_search(query="导数")
返回：{"results":[{"entity":{"name":"导数","type":"concept"}, "prerequisites":["函数","极限"], "common_mistakes":["导数零点≠极值点"]}]}
