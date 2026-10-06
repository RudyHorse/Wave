import sqlite3
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
DB_PATH = os.path.join(DB_DIR, 'seismic.db')
os.makedirs(DB_DIR, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER,
            trace_count INTEGER,
            samples_per_trace INTEGER,
            sample_rate REAL,
            min_amplitude REAL,
            max_amplitude REAL,
            ffid_min INTEGER, ffid_max INTEGER,
            shot_min INTEGER, shot_max INTEGER,
            cdp_min INTEGER, cdp_max INTEGER,
            offset_min INTEGER, offset_max INTEGER,
            inline_min INTEGER, inline_max INTEGER,
            xline_min INTEGER, xline_max INTEGER,
            chan_min INTEGER, chan_max INTEGER,
            is_processed INTEGER DEFAULT 0,
            source_file_id TEXT,
            processing_desc TEXT,
            file_hash TEXT,
            created_at TEXT NOT NULL
        )
    """)
    try:
        conn.execute("ALTER TABLE files ADD COLUMN file_hash TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE files ADD COLUMN chan_min INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE files ADD COLUMN chan_max INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def save_file_meta(file_id: str, meta: Dict[str, Any]) -> bool:
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO files (
                id, name, file_path, file_size,
                trace_count, samples_per_trace, sample_rate,
                min_amplitude, max_amplitude,
                ffid_min, ffid_max, shot_min, shot_max,
                cdp_min, cdp_max, offset_min, offset_max,
                inline_min, inline_max, xline_min, xline_max,
                chan_min, chan_max,
                is_processed, source_file_id, processing_desc, file_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id, meta.get('file_name', ''), meta.get('file_path', ''), meta.get('file_size', 0),
            meta.get('trace_count', 0), meta.get('samples_per_trace', 0), meta.get('sample_rate', 0.0),
            meta.get('min_amplitude', 0.0), meta.get('max_amplitude', 0.0),
            meta.get('ffid_min', 0), meta.get('ffid_max', 0),
            meta.get('shot_min', 0), meta.get('shot_max', 0),
            meta.get('cdp_min', 0), meta.get('cdp_max', 0),
            meta.get('offset_min', 0), meta.get('offset_max', 0),
            meta.get('inline_min', 0), meta.get('inline_max', 0),
            meta.get('xline_min', 0), meta.get('xline_max', 0),
            meta.get('chan_min', 0), meta.get('chan_max', 0),
            1 if meta.get('is_processed', False) else 0,
            meta.get('source_file_id'),
            meta.get('processing_desc'),
            meta.get('file_hash'),
            meta.get('created_at', datetime.now().isoformat()),
        ))
        conn.commit()
        return True
    finally:
        conn.close()


def list_files() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM files ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_file_meta(file_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_file_meta(file_id: str) -> bool:
    conn = get_conn()
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    deleted = conn.total_changes > 0
    conn.commit()
    conn.close()
    return deleted


def find_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE file_hash = ?", (file_hash,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_files(query: str = '') -> List[Dict[str, Any]]:
    conn = get_conn()
    if query:
        rows = conn.execute(
            "SELECT * FROM files WHERE name LIKE ? ORDER BY created_at DESC",
            (f'%{query}%',)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM files ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_db()
