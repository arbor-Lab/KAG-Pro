"""MCP Server module — exposes KAG-Pro capabilities as MCP tools."""

from kag_pro.mcp_server.server import TOOLS, KAGProMCPServer

__all__ = ["KAGProMCPServer", "TOOLS"]
