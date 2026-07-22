---
kind: external_dependency
name: ChromaDB 向量数据库
slug: chromadb
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### ChromaDB 向量数据库
- **角色定位**: 本地持久化的向量存储后端，用于存储教材文本的嵌入向量
- **集成方式**: 使用 `chromadb.PersistentClient` 进行本地文件持久化，默认路径 `data/chroma_db`
- **集合配置**: 集合名为 `kagpro_education`，使用余弦相似度 (`hnsw:space: cosine`) 计算向量距离
- **数据格式**: 存储包含文本内容、元数据（学段、学科等）和嵌入向量的完整文档
- **查询特性**: 支持基于阈值的相似度过滤和学段/学科的加权重排序
- **约束**: 本地部署模式，无网络依赖，数据完全存储在本地文件系统