"""
SQLite History Database for OCR Capture Records.
Stores raw text, formatted outputs, thumbnail, timestamp, and tags.
Provides search, filter, and export methods.
"""

import sqlite3
import json
import base64
import io
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from PIL import Image
from src.config import DB_PATH


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ocr_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    engine      TEXT NOT NULL,
    raw_text    TEXT NOT NULL,
    markdown_text TEXT DEFAULT '',
    tsv_text    TEXT DEFAULT '',
    json_data   TEXT DEFAULT '',
    thumbnail   TEXT DEFAULT '',
    tags        TEXT DEFAULT '',
    bbox_x1     INTEGER DEFAULT 0,
    bbox_y1     INTEGER DEFAULT 0,
    bbox_x2     INTEGER DEFAULT 0,
    bbox_y2     INTEGER DEFAULT 0,
    elapsed_ms  REAL DEFAULT 0,
    confidence  REAL DEFAULT 0
);
"""


class HistoryRecord:
    def __init__(self, row: tuple):
        (self.id, self.timestamp, self.engine, self.raw_text,
         self.markdown_text, self.tsv_text, self.json_data, self.thumbnail,
         self.tags, self.bbox_x1, self.bbox_y1, self.bbox_x2, self.bbox_y2,
         self.elapsed_ms, self.confidence) = row

    @property
    def tags_list(self) -> List[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def preview_text(self) -> str:
        return (self.raw_text[:120] + "…") if len(self.raw_text) > 120 else self.raw_text

    @property
    def thumbnail_image(self) -> Optional[Image.Image]:
        if not self.thumbnail:
            return None
        try:
            img_bytes = base64.b64decode(self.thumbnail)
            return Image.open(io.BytesIO(img_bytes))
        except Exception:
            return None


class HistoryDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()

    @staticmethod
    def _encode_thumbnail(pil_img: Image.Image, max_size: int = 200) -> str:
        """Encodes PIL image as base64 JPEG thumbnail string."""
        try:
            thumb = pil_img.copy()
            thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            thumb.convert("RGB").save(buf, format="JPEG", quality=70)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            return ""

    def save(self, engine: str, raw_text: str, markdown_text: str = "",
             tsv_text: str = "", json_data: str = "", capture_image: Optional[Image.Image] = None,
             bbox: tuple = (0, 0, 0, 0), elapsed_ms: float = 0.0,
             confidence: float = 0.0, tags: str = "") -> int:
        """Saves a new OCR capture record. Returns new record ID."""
        thumbnail = self._encode_thumbnail(capture_image) if capture_image else ""
        timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
        x1, y1, x2, y2 = bbox

        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO ocr_history
                   (timestamp, engine, raw_text, markdown_text, tsv_text, json_data,
                    thumbnail, tags, bbox_x1, bbox_y1, bbox_x2, bbox_y2, elapsed_ms, confidence)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (timestamp, engine, raw_text, markdown_text, tsv_text, json_data,
                 thumbnail, tags, x1, y1, x2, y2, elapsed_ms, confidence)
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent(self, limit: int = 50) -> List[dict]:
        """Returns most recent capture records."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, timestamp, engine, raw_text, thumbnail, elapsed_ms, confidence
                   FROM ocr_history ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 100) -> List[dict]:
        """Full-text search in raw_text and tags fields."""
        q = f"%{query}%"
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, timestamp, engine, raw_text, thumbnail, elapsed_ms, confidence
                   FROM ocr_history
                   WHERE raw_text LIKE ? OR tags LIKE ?
                   ORDER BY id DESC LIMIT ?""", (q, q, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[dict]:
        """Returns full record by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM ocr_history WHERE id=?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete(self, record_id: int):
        """Deletes a single record by ID."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM ocr_history WHERE id=?", (record_id,))
            conn.commit()

    def clear_all(self):
        """Deletes all records. Use with caution."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM ocr_history")
            conn.commit()

    def get_count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM ocr_history").fetchone()[0]
