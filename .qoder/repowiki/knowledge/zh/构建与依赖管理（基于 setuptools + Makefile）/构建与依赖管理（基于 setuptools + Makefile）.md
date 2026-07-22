---
kind: build_system
name: 构建与依赖管理（基于 setuptools + Makefile）
category: build_system
scope:
    - '**'
source_files:
    - Makefile
    - pyproject.toml
---

本项目采用轻量级的 Python 包构建体系，核心由 pyproject.toml 声明式配置与顶层 Makefile 任务脚本组成，未引入 Docker、CI/CD 流水线或跨平台编译工具链。

1. 构建系统
- 使用 setuptools.build_meta 作为后端，通过 PEP 517/518 的 pyproject.toml 完成元数据、依赖与可选依赖声明。
- 包名 kag-pro，版本 0.1.0，要求 Python >=3.11，源码位于 src/kag_pro，由 [tool.setuptools.packages.find] where = ["src"] 自动发现。
- 无 setup.py、setup.cfg、tox.ini、Dockerfile、.github/workflows 等文件，也不存在自定义 build.sh / release.sh。

2. 依赖策略
- 运行时依赖集中在 openai、dashscope、chromadb、langchain-text-splitters、jieba、python-dotenv、pypdf。
- 可选依赖以 extras 形式提供：local-embed（本地 sentence-transformers）、faiss（faiss-cpu）、dev（pytest + pytest-cov），并通过 all 聚合。
- 开发环境通过 pip install -e ".[dev]" 安装可编辑模式 + 测试依赖；生产环境用 pip install -e .。

3. Makefile 任务约定
- install / install-dev / install-all：对应三种 pip 安装场景。
- test：运行 pytest tests/ -v；test-cov：在 test 基础上输出覆盖率报告。
- lint：调用 ruff check src/ tests/ 进行静态检查。
- clean：清理 data/chroma_db/*、__pycache__ 与 .pyc。
- run-prototype：内联 Python 脚本直接实例化 RAGPipeline 并对教材目录建索引并问答，用于快速验证。

4. 测试与代码质量
- 测试框架为 pytest，配置文件位于 pyproject.toml 中 [tool.pytest.ini_options]，指定 testpaths = ["tests"] 与 pythonpath = ["src"]。
- 代码风格检查使用 ruff，未见 flake8/black/mypy 等工具。

5. 发布与打包
- 当前仓库未包含任何发布脚本或 CI 触发器，也未见 dist/、build/ 产物。若需发布，可直接执行 python -m build（需额外安装 build 包）生成 wheel/sdist，再上传至 PyPI。

开发者应遵循的规则：
- 新增依赖时优先放入 dependencies 或对应的 optional-dependencies extras，避免在 Makefile 中硬编码 pip 参数。
- 新增测试用例后，通过 make test 或 make test-cov 统一执行，不要绕过 pytest 配置。
- 修改源码后如需重新加载，使用 make install-dev 保持可编辑模式。
- 清理工作区统一走 make clean，不要手动删除 __pycache__ 或 chroma 数据库。