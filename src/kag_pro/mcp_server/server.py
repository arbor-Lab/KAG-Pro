"""MCP Server — exposes KAG-Pro education capabilities as MCP tools.

Implements the Model Context Protocol (MCP) over stdio transport,
allowing Qoder agents and other MCP-compatible clients to call
KAG-Pro's query, diagnosis, recommendation, and paper generation
capabilities as programmatic tools.

Run with: python -m kag_pro.mcp_server.server
"""

import json
import sys
import traceback
from typing import Any

from kag_pro.core.bootstrap import create_default_registry
from kag_pro.core.event_bus import EventBus
from kag_pro.orchestration.orchestrator import EducationOrchestrator

# === Tool Definitions ===

TOOLS = [
    {
        "name": "kag_pro_query",
        "description": (
            "智能问答：对学生问题进行学段检测、知识检索（KG增强）、LLM生成答案、可选事实验证。"
            "适用于学科知识提问、解题思路、概念解释等场景。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "学生的问题"},
                "verify": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否进行事实一致性验证",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "kag_pro_diagnose",
        "description": (
            "错题诊断：分析学生的错误答案，识别错误类型和知识点，"
            "生成个性化反馈和补救内容。适用于学生做错题后的诊断分析。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "原题"},
                "student_answer": {"type": "string", "description": "学生的错误答案"},
                "correct_answer": {"type": "string", "description": "正确答案"},
                "stage": {
                    "type": "string",
                    "description": "学段（可选）：primary/middle/high",
                },
            },
            "required": ["question", "student_answer", "correct_answer"],
        },
    },
    {
        "name": "kag_pro_recommend",
        "description": (
            "个性化推荐：基于累积的错题历史，利用知识图谱分析薄弱知识点，"
            "生成针对性练习题和学习路径。需要在 diagnose 之后调用。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "default": 3,
                    "description": "推荐练习题数量",
                },
            },
        },
    },
    {
        "name": "kag_pro_exercises",
        "description": "生成练习题：根据错题分类结果，即时生成同类型练习题（难度递进）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "student_answer": {"type": "string"},
                "correct_answer": {"type": "string"},
            },
            "required": ["question", "student_answer", "correct_answer"],
        },
    },
    {
        "name": "kag_pro_generate_paper",
        "description": (
            "自动出卷：按学段、学科、知识点、难度、题型生成试卷。"
            "返回JSON格式试卷，包含题目、答案和解析。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "description": "小学/初中/高中"},
                "subject": {"type": "string", "description": "数学/物理/化学等"},
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "知识点列表",
                },
                "count": {"type": "integer", "default": 5, "description": "题目数量"},
                "difficulty": {
                    "type": "string",
                    "default": "中等",
                    "description": "基础/中等/提高/混合",
                },
                "question_types": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                    },
                    "description": "题型分配（可选）",
                },
            },
            "required": ["stage", "subject", "topics"],
        },
    },
    {
        "name": "kag_pro_index_documents",
        "description": "索引文档：将指定目录下的教材文件（.txt/.pdf/.md）加载到向量知识库。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "教材文件目录路径"},
            },
            "required": ["directory"],
        },
    },
    {
        "name": "kag_pro_get_knowledge_tree",
        "description": "获取知识树：返回按学段和学科组织的知识点结构，用于出卷和导航。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kag_pro_kg_search",
        "description": (
            "知识图谱查询：搜索知识图谱中的实体，获取前置知识和常见错误。"
            "适用于理解知识依赖关系和易错点。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "kag_pro_health",
        "description": "健康检查：返回系统状态和已索引文档数量。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # === Multimodal VQA Tools ===
    {
        "name": "kag_pro_upload_image",
        "description": (
            "上传教育相关图像（数学图表、物理示意图、化学分子结构、生物细胞图等）"
            "到知识库，支持后续的多模态检索和视觉问答。"
            "支持格式：PNG、JPG、JPEG。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "本地图像文件路径",
                },
                "description": {
                    "type": "string",
                    "default": "",
                    "description": "图像描述（可选）",
                },
                "metadata": {
                    "type": "object",
                    "description": "元数据（可选），如学科、学段、知识点等",
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "kag_pro_vqa",
        "description": (
            "视觉问答（VQA）：基于已上传图像进行多模态问答。"
            "自动分析图像内容（OCR文字、公式、图表），结合用户问题生成解答。"
            "适用于数学函数图像分析、物理受力图解读、化学结构识别等场景。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_id": {
                    "type": "string",
                    "description": "图像 ID（由 upload_image 返回）",
                },
                "question": {
                    "type": "string",
                    "description": "针对图像的问题",
                },
                "generate_answer": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否调用 LLM 生成完整答案",
                },
            },
            "required": ["image_id", "question"],
        },
    },
    {
        "name": "kag_pro_search_similar_images",
        "description": (
            "搜索与指定图像相似的图像资源。使用 CLIP 模型的图像嵌入进行相似度匹配。"
            "可用于查找相关的教学图片、历史题目等视觉资源。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "参考图像路径",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "返回相似图像数量",
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "kag_pro_list_images",
        "description": (
            "列出所有已上传到知识库的图像及其元数据。"
            "返回图像 ID、文件名、上传时间等信息。"
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class KAGProMCPServer:
    """MCP server wrapping EducationOrchestrator capabilities as tools."""

    def __init__(self, use_kg: bool = True):
        registry = create_default_registry(use_kg=use_kg)
        bus = EventBus()
        self._orchestrator = EducationOrchestrator(registry, bus)
        self._indexed = False
        self._multimodal_pipeline = None  # Lazy-loaded

    def _get_multimodal_pipeline(self):
        """Get or create multimodal pipeline."""
        if self._multimodal_pipeline is None:
            try:
                from kag_pro.core.multimodal_pipeline import create_multimodal_pipeline
                self._multimodal_pipeline = create_multimodal_pipeline(
                    use_clip=True,
                    clip_model="ViT-B/32",
                )
                print("Multimodal pipeline initialized")
            except ImportError as e:
                print(f"Multimodal dependencies not available: {e}")
                self._multimodal_pipeline = None
        return self._multimodal_pipeline

    def list_tools(self) -> list[dict]:
        """Return the list of available MCP tools."""
        return TOOLS

    def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """Handle a tool call and return the result."""
        try:
            return self._dispatch(tool_name, arguments)
        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    def _dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Route tool calls to the appropriate orchestrator method."""
        if tool_name == "kag_pro_query":
            result = self._orchestrator.query(
                question=arguments["question"],
                verify=arguments.get("verify", False),
            )
            return result.to_dict()

        elif tool_name == "kag_pro_diagnose":
            result = self._orchestrator.diagnose(
                question=arguments["question"],
                student_answer=arguments["student_answer"],
                correct_answer=arguments["correct_answer"],
                stage=arguments.get("stage"),
            )
            return result.to_dict()

        elif tool_name == "kag_pro_recommend":
            return self._orchestrator.recommend(
                count=arguments.get("count", 3),
            )

        elif tool_name == "kag_pro_exercises":
            return self._orchestrator.exercises(
                question=arguments["question"],
                student_answer=arguments["student_answer"],
                correct_answer=arguments["correct_answer"],
            )

        elif tool_name == "kag_pro_generate_paper":
            return self._orchestrator.generate_paper(
                stage=arguments["stage"],
                subject=arguments["subject"],
                topics=arguments["topics"],
                count=arguments.get("count", 5),
                difficulty=arguments.get("difficulty", "中等"),
                question_types=arguments.get("question_types"),
            )

        elif tool_name == "kag_pro_index_documents":
            count = self._orchestrator.index_documents(arguments["directory"])
            self._indexed = True
            return {"indexed": count, "directory": arguments["directory"]}

        elif tool_name == "kag_pro_get_knowledge_tree":
            from kag_pro.core.paper_generator import KnowledgeTreeExtractor
            tree = KnowledgeTreeExtractor()
            return tree.get_tree()

        elif tool_name == "kag_pro_kg_search":
            if self._orchestrator.registry.has("knowledge-graph"):
                kg = self._orchestrator.registry.resolve("knowledge-graph")
                entities = kg.search_entities(arguments["query"])
                results = []
                for e in entities[:10]:
                    prereqs = kg.get_prerequisites(e["id"])
                    mistakes = kg.get_common_mistakes(e["id"])
                    results.append({
                        "entity": e,
                        "prerequisites": [p["name"] for p in prereqs],
                        "common_mistakes": [m["name"] for m in mistakes],
                    })
                return {"results": results}
            return {"error": "Knowledge graph not initialized"}

        elif tool_name == "kag_pro_health":
            return {
                "status": "ok",
                "document_count": self._orchestrator.document_count,
                "services": self._orchestrator.registry.list_services(),
                "error_history_count": len(self._orchestrator.error_history),
            }

        # === Multimodal VQA Tools ===
        elif tool_name == "kag_pro_upload_image":
            pipeline = self._get_multimodal_pipeline()
            if pipeline is None:
                return {
                    "error": "Multimodal dependencies not available. Install with: pip install kag-pro[multimodal]"
                }

            try:
                image_id = pipeline.upload_image(
                    image_path=arguments["image_path"],
                    description=arguments.get("description", ""),
                    metadata=arguments.get("metadata"),
                )
                return {
                    "success": True,
                    "image_id": image_id,
                    "message": f"Image uploaded: {image_id}",
                }
            except Exception as e:
                return {"error": f"Failed to upload image: {str(e)}"}

        elif tool_name == "kag_pro_vqa":
            pipeline = self._get_multimodal_pipeline()
            if pipeline is None:
                return {
                    "error": "Multimodal dependencies not available"
                }

            try:
                result = pipeline.visual_question_answering(
                    image_path=arguments["image_path"],
                    question=arguments["question"],
                    generate_answer=arguments.get("generate_answer", True),
                )
                return result.__dict__ if hasattr(result, '__dict__') else str(result)
            except Exception as e:
                return {"error": f"VQA failed: {str(e)}"}

        elif tool_name == "kag_pro_search_similar_images":
            pipeline = self._get_multimodal_pipeline()
            if pipeline is None:
                return {
                    "error": "Multimodal dependencies not available"
                }

            try:
                results = pipeline.search_similar_images(
                    reference_image=arguments["image_path"],
                    top_k=arguments.get("top_k", 5),
                )
                return {"images": results}
            except Exception as e:
                return {"error": f"Image search failed: {str(e)}"}

        elif tool_name == "kag_pro_list_images":
            # For now, return a placeholder since we'd need to access the uploads directory
            # In a full implementation, we'd query the vector store for all image IDs
            return {
                "images": [],
                "message": "Image listing not yet fully implemented in MCP server"
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}


# === MCP Protocol Implementation (stdio transport) ===

def _read_message() -> dict | None:
    """Read a single JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _write_message(msg: dict) -> None:
    """Write a JSON-RPC message to stdout."""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _make_response(msg_id: str | int | None, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _make_error(msg_id: str | int | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve_stdio(server: KAGProMCPServer) -> None:
    """Run the MCP server on stdio transport (JSON-RPC over stdin/stdout)."""
    while True:
        msg = _read_message()
        if msg is None:
            break

        msg_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            _write_message(_make_response(msg_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "kag-pro-edu", "version": "0.2.0"},
                "capabilities": {"tools": {}},
            }))

        elif method == "notifications/initialized":
            pass  # No response needed for notifications

        elif method == "tools/list":
            _write_message(_make_response(msg_id, {"tools": server.list_tools()}))

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = server.handle_tool_call(tool_name, arguments)
            _write_message(_make_response(msg_id, {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2),
                }],
            }))

        elif method == "ping":
            _write_message(_make_response(msg_id, {}))

        else:
            if msg_id is not None:
                _write_message(_make_error(msg_id, -32601, f"Method not found: {method}"))


def main():
    """Entry point for running the MCP server."""
    server = KAGProMCPServer(use_kg=True)
    serve_stdio(server)


if __name__ == "__main__":
    main()
