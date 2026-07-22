"""Chinese text splitter with semantic-aware chunking."""

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from kag_pro.core.types import Document


class ChineseTextSplitter:
    """Split Chinese educational text into semantic chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self._separators = [
            "\n\n", "\n", "。", "！", "？", "；", "，", " ", ""
        ]
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self._separators,
            keep_separator=True,
        )
        self._section_pattern = re.compile(
            r"(?:第[一二三四五六七八九十百千0-9]+[章节课]|(?:[一二三四五六七八九十]+|[0-9]+)[、.)）])"
        )

    def split(self, documents: list[Document]) -> list[Document]:
        chunks: list[Document] = []
        for doc in documents:
            doc_chunks = self._split_document(doc)
            chunks.extend(doc_chunks)
        return chunks

    def _split_document(self, doc: Document) -> list[Document]:
        chunks: list[Document] = []
        sections = self._split_by_sections(doc.text)
        for section_text, section_title in sections:
            base_meta = dict(doc.metadata)
            if section_title:
                base_meta["section"] = section_title
            langchain_docs = self._splitter.create_documents(
                texts=[section_text], metadatas=[base_meta]
            )
            for lc_doc in langchain_docs:
                chunk = Document(
                    text=lc_doc.page_content, metadata=dict(lc_doc.metadata)
                )
                chunks.append(chunk)
        return chunks

    def _split_by_sections(self, text: str) -> list[tuple]:
        lines = text.split("\n")
        sections = []
        current_lines = []
        current_title = None
        for line in lines:
            stripped = line.strip()
            if self._section_pattern.match(stripped):
                if current_lines:
                    sections.append(("\n".join(current_lines), current_title))
                current_lines = [line]
                current_title = stripped
            else:
                current_lines.append(line)
        if current_lines:
            sections.append(("\n".join(current_lines), current_title))
        if len(sections) <= 1:
            return [(text, None)]
        return [(t, title) for t, title in sections]
