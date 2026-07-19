"""Tests for ChineseTextSplitter."""

from kag_pro.core.loader import Document
from kag_pro.core.splitter import ChineseTextSplitter


class TestChineseTextSplitter:

    def test_single_short_document(self):
        splitter = ChineseTextSplitter(chunk_size=500, chunk_overlap=50)
        doc = Document(text="这是一段简短的测试文本。", metadata={"source": "test.txt"})
        chunks = splitter.split([doc])
        assert len(chunks) == 1
        assert chunks[0].metadata["source"] == "test.txt"

    def test_long_document_is_chunked(self):
        splitter = ChineseTextSplitter(chunk_size=100, chunk_overlap=20)
        long_text = "。".join([f"第{i}句话" for i in range(50)])
        doc = Document(text=long_text, metadata={"source": "long.txt"})
        chunks = splitter.split([doc])
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 200
            assert chunk.metadata["source"] == "long.txt"

    def test_chunk_size_constrained(self):
        splitter = ChineseTextSplitter(chunk_size=200, chunk_overlap=30)
        text = "测试内容。" * 100
        doc = Document(text=text, metadata={})
        chunks = splitter.split([doc])
        for chunk in chunks:
            assert len(chunk.text) < 400

    def test_section_detection(self):
        splitter = ChineseTextSplitter(chunk_size=500, chunk_overlap=50)
        text = "第一章 基础知识\n这是第一章的内容。\n第二章 进阶知识\n这是第二章的内容。\n"
        doc = Document(text=text, metadata={"source": "chapters.txt"})
        chunks = splitter.split([doc])
        assert len(chunks) >= 1
        sections = [c.metadata.get("section") for c in chunks if c.metadata.get("section")]
        assert len(sections) >= 1

    def test_empty_document_list(self):
        splitter = ChineseTextSplitter()
        chunks = splitter.split([])
        assert chunks == []

    def test_metadata_preserved(self):
        splitter = ChineseTextSplitter(chunk_size=500, chunk_overlap=50)
        doc = Document(
            text="知识点：三角形的内角和等于180度。证明方法如下。",
            metadata={"source": "triangle.txt", "grade": 3, "subject": "math"},
        )
        chunks = splitter.split([doc])
        for chunk in chunks:
            assert chunk.metadata["source"] == "triangle.txt"
            assert chunk.metadata["grade"] == 3
            assert chunk.metadata["subject"] == "math"
