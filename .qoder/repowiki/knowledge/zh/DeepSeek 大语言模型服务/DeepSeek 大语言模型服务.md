---
kind: external_dependency
name: DeepSeek 大语言模型服务
slug: deepseek
category: external_dependency
category_hints:
    - vendor_identity
    - auth_protocol
scope:
    - '**'
---

### DeepSeek 大语言模型服务
- **角色定位**: 项目主要的 LLM 生成引擎，通过 OpenAI 兼容 API 协议调用
- **集成方式**: 使用 `openai` SDK 的 `OpenAI` 客户端，配置 `base_url=https://api.deepseek.com/v1` 和 `OPENAI_API_KEY`
- **默认模型**: `deepseek-v4-pro`，可通过环境变量 `LLM_MODEL` 切换
- **备用方案**: 支持阿里云 DashScope (Qwen 系列) 作为备用 LLM 提供商，通过 `DASHSCOPE_API_KEY` 配置
- **认证协议**: 采用 OpenAI 兼容的 API Key 认证机制，所有 LLM 调用统一通过 OpenAI SDK 接口
- **验证**: 需参考官方文档确认具体的模型名称、API 参数和速率限制