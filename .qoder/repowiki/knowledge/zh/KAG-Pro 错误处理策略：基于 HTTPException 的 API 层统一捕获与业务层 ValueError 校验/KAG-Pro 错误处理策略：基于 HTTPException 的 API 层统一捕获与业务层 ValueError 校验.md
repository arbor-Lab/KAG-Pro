---
kind: error_handling
name: KAG-Pro 错误处理策略：基于 HTTPException 的 API 层统一捕获与业务层 ValueError 校验
category: error_handling
scope:
    - '**'
source_files:
    - frontend/server.py
    - src/kag_pro/kg/graph.py
    - src/kag_pro/diagnosis/classifier.py
    - src/kag_pro/core/pipeline.py
    - src/kag_pro/core/favorite_store.py
    - src/kag_pro/core/paper_store.py
    - src/kag_pro/core/paper_generator.py
    - src/kag_pro/data/external/SC-Ques-main/models/base_model.py
---

## 1. 采用的系统/方法
- 前端 FastAPI 服务使用 fastapi.HTTPException 作为统一的 HTTP 错误返回载体，所有路由通过 try/except Exception 包裹，将内部异常转换为 500 响应。
- 核心库（src/kag_pro）未定义自定义异常类型，主要依赖 Python 内置异常（ValueError、NotImplementedError、ImportError、json.JSONDecodeError），在关键边界处显式 raise。
- 诊断模块以规则分类加 LLM 兜底的方式处理错误，不抛异常而是返回默认分类结果，体现容错优先的设计。
- 外部 SC-Ques 子项目沿用上游代码风格，大量使用 raise NotImplementedError / raise ImportError 等标准异常。

## 2. 关键文件与位置
- frontend/server.py：FastAPI 路由层，集中 try/except 并统一 HTTPException(status_code=500, detail=str(e))；对 404 场景手动 raise HTTPException(404)。
- src/kag_pro/kg/graph.py：知识图谱实体/关系合法性校验，使用 ValueError 拒绝非法 relation type 或不存在实体。
- src/kag_pro/diagnosis/classifier.py：错题分类器，遇到无法匹配的情况回退到 concept_confusion，不抛出异常。
- src/kag_pro/core/pipeline.py：RAGPipeline 主流程，对外暴露 dict 结果，内部错误由下游组件自行处理；recommend_exercises 在未初始化 KG 时直接返回含 error 字段的字典而非抛异常。
- src/kag_pro/data/external/SC-Ques-main/models/base_model.py、hf_base.py：上游模型基类，广泛使用 raise NotImplementedError / raise ImportError。
- src/kag_pro/core/favorite_store.py、paper_store.py、paper_generator.py：JSON 持久化层，用 try/except (json.JSONDecodeError, KeyError) 做容错读取。

## 3. 架构与约定
- 分层职责清晰：API 层只负责把异常包装成 HTTP 响应，不关心具体错误语义；领域层通过内置异常表达参数/状态错误，或通过返回值中的特殊字段表达可恢复的业务失败。
- 无全局异常中间件：FastAPI 未注册自定义 exception handler，所有异常均由各路由函数内 try/except 捕获后 raise HTTPException。
- 诊断路径静默失败：_detect_diagnosis 中 _call_llm 调用被 except Exception: pass 吞掉，降级为普通问答，避免 LLM 不可用时阻断整个请求。
- 知识图谱强约束：KnowledgeGraph.add_relation 对 relation 白名单和实体存在性进行严格校验，违反即抛 ValueError，由上层决定是否捕获。

## 4. 开发者应遵循的规则
- API 层：每个路由函数必须用 try/except Exception as e 包裹，并将未知异常转为 HTTPException(status_code=500, detail=str(e))；业务性缺失应主动 raise HTTPException(404, ...)。
- 领域层：仅对真正的参数/状态非法使用内置异常，不要自定义异常类；对于可恢复的非致命错误，优先返回包含 error 字段的 dict。
- 诊断/LLM 调用：对可能失败的 LLM 调用采用 try/except 并给出合理降级逻辑，禁止让异常冒泡到 API 层导致 500。
- JSON 持久化：读取外部 JSON 时使用 try/except (json.JSONDecodeError, KeyError) 做容错，保证存储层健壮性。
- 上游代码：SC-Ques 子目录属于第三方/示例代码，保持其原有异常风格即可，无需强行改写。