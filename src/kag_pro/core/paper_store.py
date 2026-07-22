"""Server-side paper persistence — JSON file storage in data/papers/."""

import json
import uuid
from datetime import datetime
from pathlib import Path


class PaperStore:
    """CRUD for saved exam papers stored as JSON files."""

    def __init__(self, store_dir: str | None = None):
        if store_dir is None:
            store_dir = str(
                Path(__file__).resolve().parent.parent / "data" / "papers"
            )
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, paper: dict) -> dict:
        """Save a paper dict. If it has no id, one is generated.
        Returns the saved paper dict with id."""
        paper = dict(paper)  # shallow copy
        if "id" not in paper or not paper["id"]:
            paper["id"] = uuid.uuid4().hex[:12]
        paper.setdefault("created_at", datetime.now().isoformat())

        filepath = self._dir / f"{paper['id']}.json"
        filepath.write_text(
            json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return paper

    def list_all(self) -> list[dict]:
        """Return summary list of all saved papers."""
        papers = []
        for fpath in sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                papers.append({
                    "id": data.get("id", fpath.stem),
                    "title": data.get("title", "未命名试卷"),
                    "stage": data.get("stage", ""),
                    "subject": data.get("subject", ""),
                    "difficulty": data.get("difficulty", ""),
                    "count": data.get("count", 0),
                    "created_at": data.get("created_at", ""),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return papers

    def get(self, paper_id: str) -> dict | None:
        """Get full paper data by id."""
        filepath = self._dir / f"{paper_id}.json"
        if not filepath.exists():
            return None
        return json.loads(filepath.read_text(encoding="utf-8"))

    def delete(self, paper_id: str) -> bool:
        """Delete a saved paper. Returns True if deleted."""
        filepath = self._dir / f"{paper_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False
