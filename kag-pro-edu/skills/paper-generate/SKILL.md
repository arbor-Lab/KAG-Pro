---
name: paper-generate
description: 自动出卷技能。按学段、学科、知识点、难度、题型生成完整试卷。当需要生成练习卷、测试卷、模拟卷时触发。返回JSON格式试卷含题目、答案和解析。
---

# KAG-Pro 自动出卷

## 使用场景
- 教师需要快速生成练习卷或测试卷
- 需要按特定知识点和难度出题
- 需要选择题/填空题/简答题等题型组合

## 工作流程
1. 调用 `kag_pro_get_knowledge_tree` 获取可用知识点结构（可选）
2. 调用 `kag_pro_generate_paper` MCP 工具，传入学段、学科、知识点、数量、难度
3. 工具自动完成：LLM生成 → JSON解析 → 格式校验
4. 返回完整试卷JSON，包含题目、答案、解析、难度标注

## 参数说明
- stage: 小学/初中/高中
- subject: 数学/物理/化学/生物/地理/历史
- topics: 知识点列表（如 ["导数与极值", "定积分"]）
- count: 题目数量（默认5）
- difficulty: 基础/中等/提高/混合
- question_types: 题型分配（如 [{"type":"选择题","count":3},{"type":"填空题","count":2}]）

## 输出规范
- 选择题必须包含ABCD四个选项
- 填空题答案完整
- 简答题答案要点清晰
- 每题附带详细解析

## 示例
调用：kag_pro_generate_paper(stage="高中", subject="数学", topics=["导数与极值"], count=5, difficulty="混合")
返回：{"title":"高中数学练习卷 - 导数与极值", "questions":[{"id":1,"type":"选择题","question":"...","answer":"B","analysis":"...","difficulty":"基础"}]}
