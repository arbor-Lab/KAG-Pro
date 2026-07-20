"""Document loader: supports .txt and .pdf files."""

from pathlib import Path
from typing import List

from pypdf import PdfReader


class Document:
    """A single document with text content and metadata."""

    def __init__(self, text: str, metadata: dict | None = None):
        self.text = text
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        src = self.metadata.get("source", "unknown")
        return f"Document(source={src!r}, chars={len(self.text)})"


class DocumentLoader:
    """Load documents from .txt and .pdf files in a directory."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    # Stage inference from filename prefix: 01-05=primary, 06-11=middle, 12-15=high, 16-18=university
    _STAGE_FROM_PREFIX = {}
    for i in range(1, 19):
        if i <= 5:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "primary"
        elif i <= 11:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "middle"
        elif i <= 15:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "high"
        else:
            _STAGE_FROM_PREFIX[str(i).zfill(2)] = "university"

    @classmethod
    def _infer_stage(cls, filename: str) -> str:
        prefix = filename[:2]
        return cls._STAGE_FROM_PREFIX.get(prefix, "unknown")

    def load(self, infer_stage: bool = True) -> List[Document]:
        """Load all supported files from the directory."""
        documents: List[Document] = []

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

            documents.extend(docs)

        return documents

    def _load_txt(self, filepath: Path) -> List[Document]:
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

    def _load_pdf(self, filepath: Path) -> List[Document]:
        reader = PdfReader(str(filepath))
        documents: List[Document] = []
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
