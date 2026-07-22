---
name: system-evaluate
description: 系统评估技能。对RAG系统输出质量进行多维度评估（Accuracy/BLEU/BERTScore/Faithfulness），支持消融实验和统计显著性检验。当需要评估系统性能、对比系统变体时触发。
---

# KAG-Pro 系统评估

## 使用场景
- 评估 RAG 系统的回答质量
- 对比不同系统变体（纯LLM vs RAG vs KG增强RAG）
- 进行消融实验和统计显著性检验

## 评估指标
- **Accuracy**: 参考答案 n-gram 在生成答案中的覆盖率
- **BLEU**: 基于 jieba 分词的 BLEU 分数
- **BERTScore**: 基于嵌入余弦相似度的语义匹配度
- **Faithfulness**: 生成答案与检索来源的最大相似度

## 工作流程
1. 准备测试数据集：每条包含 question 和 reference（标准答案）
2. 调用 `kag_pro_query` 对每个问题生成答案
3. 对比生成答案与参考答案，计算各指标
4. 支持配对 t 检验和 Wilcoxon 符号秩检验

## 统计检验
- **paired_ttest**: 配对 t 检验，适用于正态分布数据
- **wilcoxon_test**: Wilcoxon 符号秩检验，适用于小样本或非正态分布
- 两者都报告 p 值、效应量（Cohen's d）和显著性判定

## 消融实验
支持以下系统变体对比：
- full: 完整系统（RAG + KG + 诊断）
- pure_llm: 纯 LLM 基线
- 通过移除组件评估各模块贡献
