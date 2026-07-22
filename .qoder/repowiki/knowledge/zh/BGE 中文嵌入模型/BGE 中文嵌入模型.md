---
kind: external_dependency
name: BGE 中文嵌入模型
slug: bge-large-zh
category: external_dependency
category_hints:
    - vendor_identity
    - framework_behavior
scope:
    - '**'
---

### BGE 中文嵌入模型
- **角色定位**: 默认的本地文本向量化模型，用于将中文教育文本转换为向量表示
- **集成方式**: 通过 `sentence-transformers` 库加载，使用 `SentenceTransformer` 类进行推理
- **运行模式**: 支持两种模式 - 本地 BGE 模型（默认）或远程 OpenAI 兼容 API
- **模型选择**: 通过 `EMBEDDING_MODEL` 环境变量配置，以 `BAAI/` 或 `bge-` 开头的模型名自动启用本地模式
- **性能优化**: 批量嵌入时设置 `normalize_embeddings=True` 和 `show_progress_bar=False` 提升性能
- **备选方案**: 当模型名不以 `BAAI/` 开头时，降级为 OpenAI 兼容 API 调用