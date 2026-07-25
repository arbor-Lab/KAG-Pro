"""Document loader: supports .txt and .pdf files."""

import re
from pathlib import Path

from pypdf import PdfReader

from kag_pro.core.types import Document  # re-export for backward compat


class DocumentLoader:
    """Load documents from .txt and .pdf files in a directory."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    # Stage inference from filename prefix: 01-05=primary, 06-11=middle, 12-15=high, 16-18=university
    _STAGE_FROM_PREFIX = {}
    for i in range(1, 21):
        if i <= 5:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "primary"
        elif i <= 11:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "middle"
        else:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "high"

    # Generated-textbook filename convention (see frontend/generate_textbooks.py):
    # gen_{stage_code}_{subject_code}_{nn}.txt, e.g. gen_ele_mat_01.txt
    _GEN_FILE_PATTERN = re.compile(r"^gen_([a-z]{3})_([a-z]{3})_\d+")
    _GEN_STAGE_CODES = {"ele": "primary", "mid": "middle", "hig": "high"}
    _GEN_SUBJECT_CODES = {
        "mat": "math",
        "oly": "math",  # 小学奥数属于数学学科
        "phy": "physics",
        "che": "chemistry",
        "bio": "biology",
        "geo": "geography",
        "his": "history",
    }

    # Fallback stage inference from Chinese stage keywords in the filename
    _STAGE_KEYWORDS = {"小学": "primary", "初中": "middle", "高中": "high", "大学": "university"}

    _SUBJECT_KEYWORDS = {
        "math": ["数学", "代数", "几何", "函数", "方程", "分数", "小数", "三角形", "四则", "面积", "周长", "概率", "统计", "导数", "微积分", "数列", "排列", "奥数"],
        "physics": ["物理", "力学", "牛顿", "重力", "压强", "浮力", "电磁", "电场", "磁场", "电路", "欧姆", "声", "光", "物态", "熔化", "蒸发", "热", "运动", "力"],
        "chemistry": ["化学", "反应", "配平", "方程式", "元素", "酸碱", "平衡", "勒夏特列", "电离", "pH"],
        "biology": ["生物", "细胞", "光合", "呼吸", "遗传", "基因", "免疫", "传染病"],
        "chinese": ["语文", "拼音", "识字", "阅读", "写作", "古诗", "文言"],
        "english": ["英语", "语法", "词汇", "完形", "阅读"],
        "geography": ["地理", "气候", "地形", "人口", "资源"],
        "history": ["历史", "古代", "近代", "战争", "革命"],
        "cs": ["数据结构", "算法", "复杂度", "操作系统", "进程", "内存", "排序"],
    }

    @classmethod
    def _parse_gen_filename(cls, filename: str) -> tuple[str | None, str | None]:
        """Parse the gen_{stage}_{subject}_{nn} convention; (None, None) if unmatched."""
        match = cls._GEN_FILE_PATTERN.match(filename)
        if not match:
            return None, None
        stage = cls._GEN_STAGE_CODES.get(match.group(1))
        subject = cls._GEN_SUBJECT_CODES.get(match.group(2))
        return stage, subject

    @classmethod
    def _infer_subject(cls, filename: str, text: str) -> str:
        _, gen_subject = cls._parse_gen_filename(filename)
        if gen_subject:
            return gen_subject
        combined = filename + text[:200]
        for subject, keywords in cls._SUBJECT_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return subject
        return "general"

    @classmethod
    def _infer_stage(cls, filename: str) -> str:
        gen_stage, _ = cls._parse_gen_filename(filename)
        if gen_stage:
            return gen_stage
        prefix = filename[:2]
        if prefix in cls._STAGE_FROM_PREFIX:
            return cls._STAGE_FROM_PREFIX[prefix]
        for keyword, stage in cls._STAGE_KEYWORDS.items():
            if keyword in filename:
                return stage
        return "unknown"

    def load(self, infer_stage: bool = True) -> list[Document]:
        """Load all supported files from the directory."""
        documents: list[Document] = []

        for filepath in sorted(self.directory.rglob("*")):
            if not filepath.is_file():
                continue

            suffix = filepath.suffix.lower()
            if suffix == ".txt":
                docs = self._load_txt(filepath)
            elif suffix == ".pdf":
                docs = self._load_pdf(filepath)
            elif suffix == ".md":
                docs = self._load_txt(filepath)
            else:
                continue

            if infer_stage:
                stage = self._infer_stage(filepath.name)
                for doc in docs:
                    doc.metadata["stage"] = stage
                    doc.metadata["subject"] = self._infer_subject(filepath.name, doc.text)

            documents.extend(docs)

        return documents

    def _load_txt(self, filepath: Path) -> list[Document]:
        text = filepath.read_text(encoding="utf-8")
        doc = Document(
            text=text,
            metadata={
                "source": str(filepath.name),
                "path": str(filepath),
                "type": "text",
            },
        )
        return [doc]

    def _load_pdf(self, filepath: Path) -> list[Document]:
        reader = PdfReader(str(filepath))
        documents: list[Document] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                doc = Document(
                    text=text.strip(),
                    metadata={
                        "source": str(filepath.name),
                        "path": str(filepath),
                        "type": "pdf",
                        "page": i + 1,
                    },
                )
                documents.append(doc)
        return documents
