"""Favorite store — JSON persistence for favorite items (papers, questions, diagnoses)."""

import json
import uuid
from datetime import datetime
from pathlib import Path


class FavoriteStore:
    """CRUD for favorited items: papers, chat Q&A, and error diagnoses."""

    def __init__(self, store_dir: str | None = None):
        if store_dir is None:
            store_dir = str(
                Path(__file__).resolve().parent.parent / "data" / "favorites"
            )
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, item: dict) -> dict:
        """Save a favorite item. Required fields: type, content.
        Optional: subject, knowledge_point, stage, title.
        Returns the saved item dict with id."""
        item = dict(item)
        if "id" not in item or not item["id"]:
            item["id"] = uuid.uuid4().hex[:12]
        item.setdefault("created_at", datetime.now().isoformat())

        filepath = self._dir / f"{item['id']}.json"
        filepath.write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return item

    def list_all(
        self,
        fav_type: str | None = None,
        subject: str | None = None,
        knowledge_point: str | None = None,
    ) -> list[dict]:
        """List favorites, optionally filtered by type, subject, knowledge_point."""
        items = []
        for fpath in sorted(
            self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                continue

            if fav_type and data.get("type") != fav_type:
                continue
            if subject and subject not in (data.get("subject") or ""):
                continue
            if knowledge_point and knowledge_point not in (data.get("knowledge_point") or ""):
                continue

            items.append({
                "id": data.get("id", fpath.stem),
                "type": data.get("type", ""),
                "title": data.get("title", ""),
                "subject": data.get("subject", ""),
                "stage": data.get("stage", ""),
                "knowledge_point": data.get("knowledge_point", ""),
                "created_at": data.get("created_at", ""),
            })
        return items

    def get(self, item_id: str) -> dict | None:
        """Get full favorite item by id."""
        filepath = self._dir / f"{item_id}.json"
        if not filepath.exists():
            return None
        return json.loads(filepath.read_text(encoding="utf-8"))

    def delete(self, item_id: str) -> bool:
        """Delete a favorite item. Returns True if deleted."""
        filepath = self._dir / f"{item_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False
