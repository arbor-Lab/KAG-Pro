# KAG-Pro

面向 K-12 中小学教育的知识增强生成智能问答框架

结合 RAG 检索增强、知识图谱和错题诊断，覆盖小学、初中、高中全学科，为大模型提供权威教材知识上下文，降低幻觉，提升准确率。

## 能力概览

| 能力 | 说明 |
|---|---|
| 智能问答 | 249 篇教材、113K 字、12 学科全覆盖，LLM 驱动学段自动识别 |
| 知识图谱 | 42 实体 + 37 关系，向量 + 图遍历混合重排序 |
| 错题诊断 | 17 种错误类型识别，知识点映射，个性化反馈 |
| 练习推荐 | 三层难度递增练习题生成，点击按钮即出 |
| 本地嵌入 | BGE-large-zh 本地运行，零 API 调用 |
| DeepSeek 驱动 | LLM 生成使用 DeepSeek，支持 OpenAI 兼容协议 |

## 项目规模

| 维度 | 数值 |
|---|---|
| 教材 | 249 篇、113K 字、12 学科 |
| 知识图谱 | 42 实体、37 关系 |
| 错误类型 | 17 种 |
| Python 模块 | 51 个 |
| 测试用例 | 22 个 |

## 快速开始

```bash
git clone https://github.com/arbor-Lab/KAG-Pro.git
cd KAG-Pro
pip install -e ".[all]"
cp .env.example .env   # 填入 DeepSeek API Key
python frontend/server.py   # 启动 Chat 界面
```

## 架构

```
学生提问 → 阶段识别(LLM) → 学科过滤 → 向量检索(BGE+ChromaDB) → KG增强 → 重排序 → 答案生成(DeepSeek) → 事实校验
                                                                       ↓
                                                               错题诊断 → 知识回顾 → [相似题目练习]
```

## 项目结构

```
KAG-Pro/
├── frontend/                   # ChatGPT 风格 Web 界面
│   ├── server.py               #   FastAPI 后端
│   └── index.html              #   单页前端
├── src/kag_pro/
│   ├── core/                   # RAG 核心管线
│   │   ├── loader.py           #   文档加载 (txt/pdf) + 学段/学科推断
│   │   ├── splitter.py         #   中文语义切分
│   │   ├── embedder.py         #   BGE 本地嵌入
│   │   ├── vector_store.py     #   ChromaDB + 学段/学科过滤
│   │   ├── retriever.py        #   检索策略
│   │   ├── generator.py        #   LLM 生成 + 格式化
│   │   ├── verifier.py         #   事实一致性校验
│   │   └── pipeline.py         #   管线编排
│   ├── diagnosis/              # 错题诊断
│   │   ├── classifier.py       #   17 种错误类型
│   │   ├── diagnoser.py        #   诊断引擎 + 反馈生成
│   │   ├── recommender.py      #   个性化推荐
│   │   └── knowledge_tracing.py #  BKT + DKT 知识追踪
│   ├── kg/                     # 知识图谱
│   │   ├── graph.py            #   图存储与遍历
│   │   ├── extractor.py        #   实体关系构建
│   │   ├── kg_retriever.py     #   KG 增强检索 + 重排序
│   │   └── auto_extractor.py   #   自动实体抽取
│   ├── stage/                  # 阶段感知
│   │   └── detector.py         #   LLM 知识模块分析
│   ├── datasets/               # 外部数据集加载
│   │   ├── loader.py           #   Math23K / SC-Ques / 智慧学伴
│   │   └── textbook_generator.py # 278 知识点自动生成
│   ├── evaluation/             # 评价体系
│   │   └── metrics.py          #   BLEU / BERTScore / t-test / 消融实验
│   └── data/
│       ├── textbooks/          #   249 篇教材
│       └── curriculum_standards.txt
└── tests/                      # 22 个测试用例
```

## 技术栈

| 组件 | 选型 |
|---|---|
| LLM | DeepSeek V4 Pro |
| 嵌入 | BAAI/bge-large-zh-v1.5 (本地) |
| 向量库 | ChromaDB |
| 知识图谱 | 自研轻量图引擎 |
| 后端 | FastAPI + uvicorn |
| 前端 | 单页 HTML (ChatGPT 风格) |

## 外部数据集

详见 [DATA_MANIFEST.md](DATA_MANIFEST.md)

| 数据集 | 数量 | 学科 |
|---|---|---|
| Math23K | 22K | 数学 |
| SC-Ques | 289K | 英语 |
| 智慧学伴 K-12 | 314K | 7 科 |

## 许可

MIT
