"""
Har bir suhbat juftligi uchun alohida SQLite: message_dbs/dm.<kichik_id>_<katta_id>.sqlite3
Qatorlar: matn, rasm/fayl, tahrir, yumshoq o‘chirish (deleted_at).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from django.conf import settings

DM_DIR_NAME = "message_dbs"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_EXT = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".txt",
    ".zip",
    ".webm",
    ".ogg",
    ".mp3",
    ".m4a",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def pair_ids(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    a, b = int(user_a_id), int(user_b_id)
    if a == b:
        raise ValueError("pair must be two distinct users")
    return (a, b) if a < b else (b, a)


def pair_db_path(low_id: int, high_id: int) -> str:
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    db_dir = os.path.join(base_dir, DM_DIR_NAME)
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, f"dm.{int(low_id)}_{int(high_id)}.sqlite3")


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _existing_columns(conn: sqlite3.Connection) -> set[str]:
    return {str(r[1]) for r in conn.execute("PRAGMA table_info(dm_message)").fetchall()}


def _migrate_columns(conn: sqlite3.Connection) -> None:
    cols = _existing_columns(conn)
    specs: list[tuple[str, str]] = [
        ("deleted_at", "TEXT"),
        ("edited_at", "TEXT"),
        ("msg_type", "TEXT DEFAULT 'text'"),
        ("file_relpath", "TEXT"),
        ("orig_filename", "TEXT"),
        ("reply_to_id", "INTEGER"),
    ]
    for name, decl in specs:
        if name not in cols:
            conn.execute(f"ALTER TABLE dm_message ADD COLUMN {name} {decl}")


def ensure_pair_schema(low_id: int, high_id: int) -> str:
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS dm_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_dm_message_created ON dm_message(created_at);
            """
        )
        _migrate_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dm_read_state (
                user_id INTEGER NOT NULL PRIMARY KEY,
                last_read_message_id INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dm_hidden_message (
                user_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, message_id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _safe_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_EXT else ""


def _save_upload(
    low_id: int, high_id: int, uploaded, *, as_voice: bool = False
) -> tuple[str, str, str]:
    """(msg_type, file_relpath, orig_filename) yoki ValueError."""
    if not uploaded or not getattr(uploaded, "name", None):
        raise ValueError("no file")
    if uploaded.size and uploaded.size > MAX_UPLOAD_BYTES:
        raise ValueError("file too large")
    ext = _safe_ext(uploaded.name)
    if not ext:
        raise ValueError("unsupported file type")
    media_root = Path(str(settings.MEDIA_ROOT))
    rel_dir = f"dm/{int(low_id)}_{int(high_id)}"
    dest_dir = media_root / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}{ext}"
    rel_path = f"{rel_dir}/{name}"
    full = media_root / rel_path
    with full.open("wb") as out:
        for chunk in uploaded.chunks():
            out.write(chunk)
    voice_exts = {".webm", ".ogg", ".mp3", ".m4a"}
    if as_voice and ext in voice_exts:
        msg_type = "voice"
    elif ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        msg_type = "image"
    else:
        msg_type = "file"
    orig = Path(uploaded.name).name[:200]
    return msg_type, rel_path.replace("\\", "/"), orig


def _row_dict(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["id"] = int(d["id"])
    d["sender_id"] = int(d["sender_id"])
    d["body"] = d["body"] or ""
    d["msg_type"] = (d.get("msg_type") or "text") or "text"
    d["file_relpath"] = d.get("file_relpath") or ""
    d["orig_filename"] = d.get("orig_filename") or ""
    d["deleted_at"] = d.get("deleted_at") or ""
    d["edited_at"] = d.get("edited_at") or ""
    rt = d.get("reply_to_id")
    d["reply_to_id"] = int(rt) if rt is not None else None
    return d


def get_message(low_id: int, high_id: int, message_id: int) -> Optional[dict[str, Any]]:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        row = conn.execute(
            """
            SELECT id, sender_id, body, created_at, deleted_at, edited_at,
                   msg_type, file_relpath, orig_filename, reply_to_id
            FROM dm_message WHERE id = ?
            """,
            (int(message_id),),
        ).fetchone()
        return _row_dict(row) if row else None
    finally:
        conn.close()


def fetch_messages_by_ids(low_id: int, high_id: int, ids: set[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        qmarks = ",".join("?" * len(ids))
        rows = conn.execute(
            f"""
            SELECT id, sender_id, body, created_at, deleted_at, edited_at,
                   msg_type, file_relpath, orig_filename, reply_to_id
            FROM dm_message WHERE id IN ({qmarks})
            """,
            tuple(int(x) for x in ids),
        ).fetchall()
        return {int(r["id"]): _row_dict(r) for r in rows}
    finally:
        conn.close()


def short_quote_preview(row: dict[str, Any]) -> str:
    p = preview_for_message_row(row)
    return (p[:76] + "…") if len(p) > 76 else p


def attach_reply_previews(low_id: int, high_id: int, msgs: list[dict[str, Any]]) -> None:
    need: set[int] = set()
    for m in msgs:
        rid = m.get("reply_to_id")
        if rid:
            need.add(int(rid))
    parents = fetch_messages_by_ids(low_id, high_id, need)
    for m in msgs:
        rid = m.get("reply_to_id")
        if not rid:
            m["reply_quote"] = None
            continue
        pr = parents.get(int(rid))
        if not pr:
            m["reply_quote"] = None
            continue
        m["reply_quote"] = {
            "sender_id": int(pr["sender_id"]),
            "preview": short_quote_preview(pr),
            "deleted": bool(pr.get("deleted_at")),
        }


def mark_thread_read(low_id: int, high_id: int, reader_id: int) -> None:
    """O‘qilganlik: foydalanuvchi oxirgi xabargacha ko‘rdi."""
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM dm_message").fetchone()
        max_id = int(row[0] or 0)
        conn.execute(
            """
            INSERT INTO dm_read_state (user_id, last_read_message_id) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_read_message_id = excluded.last_read_message_id
            """,
            (int(reader_id), max_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_read_cursor(low_id: int, high_id: int, user_id: int) -> int:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT last_read_message_id FROM dm_read_state WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def insert_message(
    low_id: int,
    high_id: int,
    *,
    sender_id: int,
    body: str = "",
    uploaded=None,
    as_voice: bool = False,
    reply_to_id: Optional[int] = None,
) -> int:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    b = (body or "").strip()
    msg_type = "text"
    file_relpath: Optional[str] = None
    orig_filename: Optional[str] = None
    if uploaded:
        msg_type, file_relpath, orig_filename = _save_upload(
            low_id, high_id, uploaded, as_voice=as_voice
        )
    if not b and not file_relpath:
        raise ValueError("empty message")
    if len(b) > 4000:
        b = b[:4000]
    rt: Optional[int] = None
    if reply_to_id:
        parent = get_message(low_id, high_id, int(reply_to_id))
        if parent:
            rt = int(parent["id"])
    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            INSERT INTO dm_message (sender_id, body, created_at, msg_type, file_relpath, orig_filename, reply_to_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(sender_id),
                b,
                _now_iso(),
                msg_type,
                file_relpath or "",
                orig_filename or "",
                rt,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def insert_existing_message(
    low_id: int,
    high_id: int,
    *,
    sender_id: int,
    body: str,
    msg_type: str,
    file_relpath: str = "",
    orig_filename: str = "",
    reply_to_id: Optional[int] = None,
) -> int:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    b = (body or "").strip()
    mt = (msg_type or "text").strip() or "text"
    fr = (file_relpath or "").strip()
    of = (orig_filename or "").strip()
    if mt not in {"text", "image", "file", "voice"}:
        mt = "text"
    if len(b) > 4000:
        b = b[:4000]
    if not b and not fr:
        raise ValueError("empty message")
    rt: Optional[int] = None
    if reply_to_id:
        parent = get_message(low_id, high_id, int(reply_to_id))
        if parent:
            rt = int(parent["id"])
    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            INSERT INTO dm_message (sender_id, body, created_at, msg_type, file_relpath, orig_filename, reply_to_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(sender_id),
                b,
                _now_iso(),
                mt,
                fr,
                of[:200],
                rt,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def hide_message_for_user(
    low_id: int, high_id: int, *, viewer_id: int, message_id: int
) -> bool:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        conn.execute(
            """
            INSERT INTO dm_hidden_message (user_id, message_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, message_id) DO UPDATE SET created_at = excluded.created_at
            """,
            (int(viewer_id), int(message_id), _now_iso()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def _visible_messages_query() -> str:
    # deleted_at bo‘lsa umuman ko‘rsatmaymiz; hidden bo‘lsa faqat shu user uchun ko‘rsatmaymiz
    return """
        SELECT m.id, m.sender_id, m.body, m.created_at, m.deleted_at, m.edited_at,
               m.msg_type, m.file_relpath, m.orig_filename, m.reply_to_id
        FROM dm_message m
        LEFT JOIN dm_hidden_message h
          ON h.message_id = m.id AND h.user_id = ?
        WHERE (m.deleted_at IS NULL OR m.deleted_at = '')
          AND h.message_id IS NULL
    """


def list_visible_messages(
    low_id: int,
    high_id: int,
    *,
    viewer_id: int,
    limit: int = 200,
    before_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        if before_id:
            rows = conn.execute(
                _visible_messages_query()
                + """
                AND m.id < ?
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (int(viewer_id), int(before_id), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                _visible_messages_query()
                + """
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (int(viewer_id), int(limit)),
            ).fetchall()
        out = [_row_dict(r) for r in rows]
        out.reverse()
        return out
    finally:
        conn.close()


def list_visible_messages_after(
    low_id: int,
    high_id: int,
    *,
    viewer_id: int,
    after_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if after_id <= 0:
        return []
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        rows = conn.execute(
            _visible_messages_query()
            + """
            AND m.id > ?
            ORDER BY m.id ASC
            LIMIT ?
            """,
            (int(viewer_id), int(after_id), int(limit)),
        ).fetchall()
        return [_row_dict(r) for r in rows]
    finally:
        conn.close()

def edit_message(
    low_id: int, high_id: int, *, message_id: int, sender_id: int, new_body: str
) -> bool:
    ensure_pair_schema(low_id, high_id)
    nb = (new_body or "").strip()
    if not nb:
        raise ValueError("empty body")
    if len(nb) > 4000:
        nb = nb[:4000]
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            UPDATE dm_message
            SET body = ?, edited_at = ?
            WHERE id = ? AND sender_id = ? AND (deleted_at IS NULL OR deleted_at = '')
            """,
            (nb, _now_iso(), int(message_id), int(sender_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def soft_delete_message(low_id: int, high_id: int, *, message_id: int, sender_id: int) -> bool:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            UPDATE dm_message
            SET deleted_at = ?
            WHERE id = ? AND sender_id = ? AND (deleted_at IS NULL OR deleted_at = '')
            """,
            (_now_iso(), int(message_id), int(sender_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_messages(
    low_id: int, high_id: int, *, limit: int = 200, before_id: Optional[int] = None
) -> list[dict[str, Any]]:
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        if before_id:
            rows = conn.execute(
                """
                SELECT id, sender_id, body, created_at, deleted_at, edited_at,
                       msg_type, file_relpath, orig_filename, reply_to_id
                FROM dm_message
                WHERE id < ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(before_id), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, sender_id, body, created_at, deleted_at, edited_at,
                       msg_type, file_relpath, orig_filename, reply_to_id
                FROM dm_message
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        out = [_row_dict(r) for r in rows]
        out.reverse()
        return out
    finally:
        conn.close()


def list_messages_after(
    low_id: int, high_id: int, *, after_id: int, limit: int = 100
) -> list[dict[str, Any]]:
    """Polling: faqat yangi xabarlar (after_id > 0)."""
    if after_id <= 0:
        return []
    ensure_pair_schema(low_id, high_id)
    path = pair_db_path(low_id, high_id)
    conn = _connect(path)
    try:
        rows = conn.execute(
            """
            SELECT id, sender_id, body, created_at, deleted_at, edited_at,
                   msg_type, file_relpath, orig_filename, reply_to_id
            FROM dm_message
            WHERE id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (int(after_id), int(limit)),
        ).fetchall()
        return [_row_dict(r) for r in rows]
    finally:
        conn.close()


def preview_for_message_row(row: dict[str, Any]) -> str:
    if row.get("deleted_at"):
        return "Xabar o‘chirildi"
    mt = row.get("msg_type") or "text"
    if mt == "image":
        t = (row.get("body") or "").strip()
        return f"📷 {t}" if t else "📷 Rasm"
    if mt == "file":
        name = (row.get("orig_filename") or "fayl").strip()
        t = (row.get("body") or "").strip()
        base = f"📎 {name}"
        return f"{base}: {t}" if t else base
    if mt == "voice":
        return "🎤 Ovozli xabar"
    return ((row.get("body") or "").replace("\n", " ").strip() or "Xabar")[:120]
