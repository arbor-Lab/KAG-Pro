# AGENTS.md — KAG-Pro Agent 入口

## 项目定位

KAG-Pro 是面向 K-12 全学科的知识增强生成（Knowledge-Augmented Generation）智能问答框架。
核心管线 `RAGPipeline` 串联文档加载、中文语义分块、向量检索（ChromaDB + BGE）、知识图谱增强重排、LLM 答案生成与事实校验；
副管线提供错题诊断、知识追踪与个性化练习推荐。FastAPI 服务对外暴露聊天、出题、收藏等 REST API。

## 目录职责

| 路径 | 职责 | 关键文件 |
|------|------|----------|
| `src/kag_pro/core/` | RAG 核心管线 | `pipeline.py`（编排入口）、`retriever.py`、`generator.py`、`verifier.py` |
| `src/kag_pro/diagnosis/` | 错题诊断与推荐 | `classifier.py`、`diagnoser.py`、`knowledge_tracing.py`、`recommender.py` |
| `src/kag_pro/kg/` | 教育知识图谱 | `graph.py`、`kg_retriever.py`、`auto_extractor.py` |
| `src/kag_pro/stage/` | 学段识别 | `detector.py`（LLM + 关键词双路） |
| `src/kag_pro/datasets/` | 外部数据集与教材生成 | `loader.py`、`textbook_generator.py` |
| `src/kag_pro/evaluation/` | 评测指标 | `metrics.py`（BLEU / BERTScore / t-test） |
| `frontend/` | Web 服务与单页界面 | `server.py`（FastAPI）、`index.html` |
| `tests/` | pytest 测试套件 | `test_pipeline.py`、`test_retriever.py`、`test_stage.py` 等 |
| `src/kag_pro/data/textbooks/` | 249 篇教材语料 | 只读数据，勿修改 |
| `data/chroma_db/` | ChromaDB 持久化 | 已在 `.gitignore`，勿提交 |

## 常用命令

```bash
make install-dev    # 安装开发依赖（pytest + ruff + pre-commit）
make install-all    # 安装全部依赖（含 server / local-embed / faiss）
make lint           # ruff 静态检查（src/ + tests/）
make test           # pytest 测试套件
make test-cov       # 带覆盖率的测试
make check          # lint + test 合并执行
make run-prototype  # RAG 原型演示（索引教材 + 批量问答）
make clean          # 清理 ChromaDB 与缓存
```

## 编辑后校验指引（必须执行）

**任何对 `src/` 或 `tests/` 的代码编辑后，必须依次执行以下校验，并报告退出码与关键输出。**

### 1. 静态检查 — `make lint`

```bash
make lint
```

- 退出码 `0` = 通过；非零 = 存在 lint 错误，必须修复后重跑。
- ruff 规则配置在 `pyproject.toml` 的 `[tool.ruff.lint]` 段。
- 修复时可使用 `ruff check <file> --fix --unsafe-fixes`，但须人工复核自动修改。

### 2. 单元测试 — `make test`

```bash
make test
```

- 退出码 `0` = 全部通过；非零 = 存在失败用例。
- 测试配置在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 段（`testpaths=tests`, `pythonpath=src`）。
- 部分测试依赖 `OPENAI_API_KEY` 环境变量（见 `tests/test_pipeline.py` 的 `@pytest.mark.skipif`），无 key 时相关用例自动跳过。

### 3. 合并检查 — `make check`

在声明任务完成前，运行 `make check`（等价于 `make lint && make test`），确认两项均通过。

### 校验事件报告格式

每次校验执行后，在回复中记录：

```
make lint → 退出码 0（All checks passed!）
make test → 退出码 0（62 passed）
```

或失败时：

```
make lint → 退出码 1（Found N errors）
make test → 退出码 1（N failed, M passed）
```

此格式使后续有界审查可从会话中提取规范化校验事件。

## 高风险区

| 风险 | 说明 | 约束 |
|------|------|------|
| **向量库状态** | `data/chroma_db/` 是可变二进制状态，已在 `.gitignore` 但历史提交可能仍跟踪 | 勿手动提交 `chroma.sqlite3`；若已跟踪执行 `git rm --cached` |
| **API 密钥** | `.env` 含 `OPENAI_API_KEY` / `DASHSCOPE_API_KEY`，已在 `.gitignore` | 勿将密钥硬编码或提交；仅引用环境变量 |
| **直接提交 main** | 无 CI / 分支保护，工作直接落在 `main` | 优先在分支上工作；提交前执行 `make check` |
| **教材语料** | `src/kag_pro/data/textbooks/` 为只读语料 | 勿修改已有教材文件；新教材通过 `textbook_generator.py` 生成 |
| **外部数据集** | `src/kag_pro/data/external/` 含 SC-Ques、Math23K 等 | 大文件已在 `.gitignore`；勿提交原始数据集 |

## 受影响检查映射

| 修改区域 | 必须运行 | 理由 |
|----------|----------|------|
| `src/kag_pro/core/*.py` | `make lint && make test` | 核心管线逻辑变更影响检索与生成 |
| `src/kag_pro/diagnosis/*.py` | `make lint && make test` | 诊断逻辑变更影响错题分类与推荐 |
| `src/kag_pro/kg/*.py` | `make lint` | 知识图谱模块无专门测试，至少保证 lint 通过 |
| `src/kag_pro/stage/*.py` | `make lint && make test` | 学段检测有 `test_stage.py` 覆盖 |
| `frontend/server.py` | `make lint` | API 路由变更需 lint；手动验证 `/api/health` |
| `tests/*.py` | `make test` | 测试自身变更需确认可运行 |
| `pyproject.toml` | `make lint && make test` | 依赖或配置变更影响全部校验路由 |
| `Makefile` | `make lint && make test` | 命令定义变更需验证路由仍可用 |
