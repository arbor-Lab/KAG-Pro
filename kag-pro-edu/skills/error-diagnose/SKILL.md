---
name: error-diagnose
description: 错题诊断技能。分析学生的错误答案，识别17种错误类型（漏根、符号错误、公式误用、受力分析错误等），生成个性化反馈。当学生提供错误答案并询问对错时触发。
---

# KAG-Pro 错题诊断

## 使用场景
- 学生做错题后想知道为什么错
- 学生提供自己的答案并询问对错
- 需要按学段适配的反馈风格（小学耐心有趣、初中发现思维漏洞、高中注重解题思路）

## 工作流程
1. 调用 `kag_pro_diagnose` MCP 工具，传入原题、学生答案、正确答案
2. 工具自动完成：错误分类 → 知识点定位 → 教材检索 → LLM生成反馈
3. 返回结果包含：错误类型、置信度、知识点、提示、补救内容、个性化反馈
4. 若错题历史达到2条以上，自动触发推荐生成练习题

## 错误类型覆盖
missing_root, discriminant_error, sign_error, calculation_error,
formula_misapplication, incomplete_factorization, distribution_error,
force_mass_confusion, equation_not_balanced, reaction_type_error,
circuit_analysis_error, force_analysis_error, chemical_formula_error,
equilibrium_error, trigonometric_error, concept_confusion, missing_condition

## 输出规范
- 反馈格式：错误分析（1-2句） + 知识回顾（2-3句）
- 不使用 Markdown 符号
- 语气温和，先指出错误再引导正确理解
- 总字数150-250字

## 示例
学生答错一元二次方程，漏了一个根。
调用：kag_pro_diagnose(question="x²-5x+6=0", student_answer="x=2", correct_answer="x=2或x=3")
返回：error_type="missing_root", knowledge_point="一元二次方程求根", hint="开平方时注意正负号"
