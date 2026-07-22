# KAG-Pro 教育智能助手

面向中国 K-12 全学段教育的知识增强大语言模型智能问答框架。

## 功能概述

- **智能问答**：基于知识图谱增强的 RAG 检索，回答学科知识问题
- **错题诊断**：分析学生错误答案，识别错误类型，生成个性化反馈
- **个性化推荐**：利用知识图谱分析薄弱知识点，生成针对性练习和学习路径
- **自动出卷**：按学段、学科、知识点、难度自动生成试卷
- **知识图谱探索**：查询知识点的前置依赖和常见错误

## 架构

系统采用双层可插拔架构：
- **底层**：Python 库通过 Protocol 接口 + PluginRegistry + EventBus 实现模块解耦
- **上层**：通过 MCP Server 暴露为 Qoder 可调用工具，配合 SKILL.md 技能指引

## 包含组件

- 6 个技能 (skills/)：rag-query, error-diagnose, exercise-recommend, paper-generate, system-evaluate, knowledge-explore
- 4 个命令 (commands/)：/query, /diagnose, /recommend, /paper
- 1 个子 Agent (agents/)：edu-tutor 教育辅导助手
- 1 个 MCP Server：kag-pro-edu 工具服务

## 环境变量

- `OPENAI_API_KEY`：OpenAI 兼容 API 密钥
- `LLM_MODEL`：LLM 模型名（默认 gpt-4o）
- `EMBEDDING_MODEL`：嵌入模型名（默认 text-embedding-3-small）

## Qoder 技能集成

本插件可与以下 Qoder 内置技能协同工作：
- **chrome-devtools**：前端界面测试和 API 响应调试
- **genui**：生成交互式练习题组件和知识图谱可视化
- **schedule**：创建间隔复习定时任务
- **browser-use**：从教育网站获取内容扩展知识库
