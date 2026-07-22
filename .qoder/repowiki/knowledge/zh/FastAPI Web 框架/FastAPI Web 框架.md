---
kind: external_dependency
name: FastAPI Web 框架
slug: fastapi
category: external_dependency
category_hints:
    - vendor_identity
scope:
    - '**'
---

### FastAPI Web 框架
- **角色定位**: 项目的 RESTful API 服务器框架，提供前端交互接口
- **核心端点**: `/api/query`（智能问答）、`/api/diagnose`（错题诊断）、`/api/exercises`（练习生成）、`/api/generate-paper`（自动出卷）、`/api/favorites`（收藏管理）
- **请求处理**: 使用 Pydantic 模型进行请求/响应数据验证和序列化
- **静态文件**: 提供单页 HTML 前端界面，ChatGPT 风格的用户交互界面