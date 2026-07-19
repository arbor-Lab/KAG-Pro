# KAG-Pro: 面向全学段教育的知识增强生成智能问答框架

Knowledge-Augmented Generation for Education — 基于 RAG + 知识图谱的中国 K-12 与大学教育智能问答系统。

## 快速开始

### 1. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 运行原型验证

```bash
make run-prototype
```

或使用 Python:

```python
from kag_pro.core import RAGPipeline

pipeline = RAGPipeline()
pipeline.index_documents("src/kag_pro/data/textbooks")
result = pipeline.query("什么是分数？")
print(result["answer"])
```

## 项目结构

```
KAG-Pro/
├── src/kag_pro/core/     # RAG 核心管线
│   ├── loader.py          # 文档加载（txt/pdf）
│   ├── splitter.py        # 中文语义切分
│   ├── embedder.py        # 向量嵌入生成
│   ├── vector_store.py    # ChromaDB 向量存储
│   ├── retriever.py       # 检索策略
│   ├── generator.py       # LLM 答案生成
│   └── pipeline.py        # 管线编排
├── tests/                 # 测试
├── notebooks/             # 实验 Notebook
└── data/                  # 运行时数据
```

## 运行测试

```bash
make install-dev
make test
```

## 技术栈

- **LLM**: OpenAI GPT-4o / DashScope Qwen
- **嵌入**: text-embedding-3-small
- **向量库**: ChromaDB
- **文本切分**: LangChain RecursiveCharacterTextSplitter + 中文语义切分
- **分词**: jieba
