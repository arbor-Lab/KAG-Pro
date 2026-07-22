---
name: paper
description: KAG-Pro自动出卷 — 按学段、学科、知识点、难度生成试卷
---

调用 `kag_pro_generate_paper` MCP 工具生成试卷。

用法: `/paper <学段> <学科> <知识点1,知识点2,...> [数量] [难度]`

示例: `/paper 高中 数学 导数与极值,定积分 5 混合`

工具会生成JSON格式试卷，包含题目、答案、解析和难度标注。
