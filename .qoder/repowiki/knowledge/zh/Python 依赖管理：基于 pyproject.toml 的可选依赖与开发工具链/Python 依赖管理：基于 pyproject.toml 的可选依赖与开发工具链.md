---
kind: dependency_management
name: Python 依赖管理：基于 pyproject.toml 的可选依赖与开发工具链
category: dependency_management
scope:
    - '**'
source_files:
    - pyproject.toml
    - Makefile
    - src/kag_pro.egg-info/requires.txt
    - .env.example
---

## 1. 使用的系统与方案
- 包构建系统：setuptools（build-backend = setuptools.build_meta），通过 `pyproject.toml` 声明式配置。
- 依赖声明：集中定义在根目录 `pyproject.toml` 的 `[project]` 和 `[project.optional-dependencies]` 中，使用 PEP 621 标准格式。
- 安装方式：通过 `pip install -e .` 以可编辑模式安装本地包；提供 Makefile 快捷目标 `install`、`install-dev`、`install-all`。
- 可选依赖分组：按功能域拆分为 `local-embed`（本地 embedding）、`faiss`（向量检索后端）、`dev`（测试/覆盖率）以及聚合组 `all`。
- 无锁文件：仓库未包含 `requirements.txt`、`poetry.lock`、`uv.lock` 等锁定文件，也未见 vendoring 策略。
- 私有源/代理：未发现 `.env` 之外的 pip 镜像或私有注册表配置，仅通过环境变量注入 API Key（如 OpenAI、DashScope）。

## 2. 关键文件与位置
- `pyproject.toml`：项目元数据、运行时依赖、可选依赖、pytest 配置、包发现规则的统一入口。
- `Makefile`：封装常用安装、测试、清理命令，作为开发者日常交互面。
- `src/kag_pro.egg-info/requires.txt`：由 setuptools 自动生成的依赖解析结果，反映当前已安装的可选依赖集合。
- `.env.example`：示例环境变量模板，用于注入第三方服务凭据（OpenAI/DashScope 等）。

## 3. 架构与约定
- 依赖分层：核心运行依赖（LLM SDK、向量数据库、分词器、PDF 解析、dotenv）放在 `dependencies`；体积大或可选的后端（sentence-transformers、faiss-cpu）放入 optional-dependencies，避免默认安装膨胀。
- 聚合依赖：`[all]` 组合所有可选组，方便一键安装完整环境。
- 包发现：`tool.setuptools.packages.find.where = ["src"]`，遵循 src-layout 组织源码，便于隔离测试与生产代码。
- 测试集成：`tool.pytest.ini_options` 指定 testpaths 与 pythonpath，使 pytest 可直接从仓库根运行。
- 版本约束风格：统一采用 `>=X.Y` 宽松下限约束，不锁定上限，便于生态演进但可能带来兼容风险。

## 4. 开发者应遵守的规则
- 新增依赖必须写入 `pyproject.toml` 对应分组，禁止在业务代码中硬编码版本号或通过 `importlib.metadata` 动态拉取。
- 对体积较大或非必需的功能（如本地 embedding、FAISS）放入 `optional-dependencies`，并通过 Makefile 提供对应的安装目标。
- 如需固定版本以保证 CI 稳定，应在仓库根增加 `requirements.in` / `requirements.txt` 或由脚本生成 lock 文件，并纳入版本控制。
- 第三方服务凭据一律通过环境变量注入，参考 `.env.example`，不要将密钥写死到代码或配置文件中。
- 修改依赖后建议执行 `make install-dev` 或 `pip install -e ".[all]"` 重新安装，确保 egg-info 与虚拟环境一致。