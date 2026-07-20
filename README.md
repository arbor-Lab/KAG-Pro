# KAG-Pro：面向全学段教育的知识增强生成智能问答框架

> Knowledge-Augmented Generation for Education — 基于 RAG + 知识图谱的中国 K-12 与大学教育智能问答系统

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 概述

KAG-Pro 是一个面向中国教育体系的智能问答框架，覆盖 **小学 → 初中 → 高中 → 大学** 四个学段。系统结合检索增强生成（RAG）、知识图谱（KG）和错题诊断三大核心能力，为大语言模型提供权威教材知识作为上下文，降低幻觉、提升准确性。

### 核心特性

- **四学段 RAG 管线** — 18 个教材专题，179 条语义块，跨学段自动识别与风格适配
- **知识图谱增强** — 42 实体 + 37 关系，向量检索 + 图遍历混合重排序
- **错题诊断** — 17 种错误类型识别，知识点映射 + 个性化反馈生成
- **本地嵌入** — BGE-large-zh 模型本地运行，零 API 调用
- **DeepSeek 驱动** — LLM 生成使用 DeepSeek API，支持 OpenAI 兼容协议

## 项目统计

| 维度 | 数量 |
|---|---|
| 源码文件 | 20 个 Python 模块 |
| 代码行数 | ~1,500 行 |
| 测试用例 | 22 个单元测试 |
| 教材专题 | 18 个（小学5 + 初中6 + 高中4 + 大学3） |
| 知识图谱 | 42 实体 + 37 关系 |
| 错误类型 | 17 种 |
| 学段检测 | 4 阶段自动分类 |

## 快速开始

### 1. 环境要求

- Python 3.11+
- pip

### 2. 安装

```bash
git clone https://github.com/arbor-Lab/KAG-Pro.git
cd KAG-Pro

# 安装核心依赖
pip install -e .

# 一键安装全部依赖（含测试和本地嵌入）
pip install -e ".[all]"
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key：
#   OPENAI_API_KEY=sk-your-key
```

### 4. 运行

```bash
make run-prototype
```

或使用 Python API：

```python
from kag_pro.core import RAGPipeline

# 创建带知识图谱增强的管线
pipeline = RAGPipeline(use_kg=True)

# 索引教材
pipeline.index_documents("src/kag_pro/data/textbooks")

# 提问
result = pipeline.query("什么是分数？")
print(result["answer"])
print(f"学段: {result['stage']}")
print(f"来源: {result['sources'][0]['source']}")

# 错题诊断
diagnosis = pipeline.diagnose(
    question="解方程 x² - 4 = 0",
    student_answer="x=2",
    correct_answer="x=2 或 x=-2",
)
print(f"错误类型: {diagnosis['error_type']}")
print(f"反馈: {diagnosis['personalized_feedback']}")
```

### 5. 运行测试

```bash
make test
```

## 系统架构

```
                         ┌─────────────────┐
                         │   学生提问       │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  阶段检测模块    │  ← 小学/初中/高中/大学
                         └────────┬────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │                               │
         ┌────────▼────────┐            ┌─────────▼─────────┐
         │   向量检索       │            │   知识图谱检索     │
         │  (BGE + ChromaDB)│            │   (实体 + 关系)    │
         └────────┬────────┘            └─────────┬─────────┘
                  │                               │
                  └───────────────┬───────────────┘
                                  │
                         ┌────────▼────────┐
                         │   混合重排序     │  ← 向量得分 + 图得分
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  LLM 答案生成   │  ← DeepSeek V4 Pro
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │                           │
           ┌────────▼────────┐        ┌─────────▼─────────┐
           │   答案校验       │        │   错题诊断引擎     │
           └────────┬────────┘        └─────────┬─────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                         ┌────────▼────────┐
                         │   个性化反馈     │
                         └─────────────────┘
```

## 项目结构

```
KAG-Pro/
├── src/kag_pro/
│   ├── core/                    # RAG 核心管线
│   │   ├── loader.py            #   文档加载（txt/pdf/md）
│   │   ├── splitter.py          #   中文语义切分
│   │   ├── embedder.py          #   BGE 本地嵌入
│   │   ├── vector_store.py      #   ChromaDB 向量存储
│   │   ├── retriever.py         #   检索策略
│   │   ├── generator.py         #   LLM 答案生成
│   │   └── pipeline.py          #   管线编排器
│   ├── diagnosis/               # 错题诊断模块
│   │   ├── classifier.py        #   17种错误类型识别
│   │   └── diagnoser.py         #   诊断引擎 + 反馈生成
│   ├── kg/                      # 知识图谱模块
│   │   ├── graph.py             #   图存储与遍历
│   │   ├── extractor.py         #   实体/关系构建
│   │   └── kg_retriever.py      #   KG增强检索 + 重排序
│   ├── stage/                   # 阶段感知
│   │   └── detector.py          #   四学段自动识别
│   ├── data/
│   │   ├── textbooks/           #   18个教材专题
│   │   ├── test_errors_middle.txt # 错题测试集
│   │   └── curriculum_standards.txt # 学科分类标准参考
│   └── utils/
│       └── config.py            # 配置管理
├── tests/                       # 测试
├── notebooks/                   # 原型验证 Notebook
├── pyproject.toml               # 项目配置
├── Makefile                     # 快捷命令
└── .env.example                 # 配置模板
```

## 技术栈

| 组件 | 技术选型 |
|---|---|
| LLM 生成 | DeepSeek V4 Pro |
| 向量嵌入 | BAAI/bge-large-zh-v1.5（本地） |
| 向量数据库 | ChromaDB |
| 知识图谱 | 自研轻量图引擎（JSON + 邻接表） |
| 文本切分 | LangChain RecursiveCharacterTextSplitter + 中文语义切分 |
| 分词 | jieba |

## 实验评估

| 实验 | 结果 |
|---|---|
| 纯 LLM vs RAG vs KG-RAG | KG-RAG 答案有教材依据，先修知识和易错提醒增强 |
| 向量检索 vs KG 增强检索 | KG 纠正了来源匹配错误（初中→高中） |
| 错题诊断准确率 | 82%（11 题测试集） |
| 检索命中率 | 88%（跨学段测试） |
| 阶段识别准确率 | 75%（8 题测试集） |

## 执行摘要进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 第 1-4 周 | 文献调研 + 小学数据采集 | ✅ |
| 第 5-6 周 | RAG 基线系统搭建 | ✅ |
| 第 7-8 周 | 初中阶段 + 错题诊断原型 | ✅ |
| 第 9-10 周 | 初中模块整合 + 诊断调优 | ✅ |
| 第 11-14 周 | 高中知识图谱 + KG 增强检索 | ✅ |
| 第 15-22 周 | 全学段测试 + 对比实验 + 优化 | ✅ |


## 外部数据集

项目集成了三个公开教育数据集（需单独下载），总计 62.5 万条数据。
详见 [DATA_MANIFEST.md](DATA_MANIFEST.md)。

| 数据集 | 数量 | 学科 |
|---|---|---|
| Math23K | 22K | 数学 |
| SC-Ques | 289K | 英语 |
| 智慧学伴 K-12 | 314K | 7科 |


## 许可

MIT License
