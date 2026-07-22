---
kind: logging_system
name: 日志系统：未实现结构化日志，仅使用 print 调试输出
category: logging_system
scope:
    - '**'
---

经全面检索代码库，未发现任何 Python logging 框架的使用（无 `import logging`、`getLogger`、`basicConfig`、`setLevel`、`addHandler` 等调用），也没有独立的日志配置模块或 log/ 目录。项目中的“日志”行为全部由裸 `print()` 语句承担，主要出现在以下位置：
- `frontend/generate_textbooks.py`：教材生成脚本的进度与错误打印
- `Makefile` 中嵌入的 Python 片段：问答结果展示
- `notebooks/00_rag_prototype.ipynb`：原型探索过程中的交互式输出
- 前端 `index.html` 中的浏览器端 `prt()` 函数用于页面打印

这些 `print` 调用没有统一的格式规范、级别划分或输出目标控制，属于临时调试式输出，不具备生产级日志能力（无法按级别过滤、无法写入文件/远程服务、无法附加结构化字段）。因此本仓库不存在可识别的“logging_system”。