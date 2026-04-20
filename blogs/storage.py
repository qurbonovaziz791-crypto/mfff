from __future__ import annotations

import glob
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from django.conf import settings


DB_DIR_NAME = "user_dbs"


def _safe_username(username: str) -> str:
    """
    File nomi uchun xavfsiz variant.
    Eslatma: bu username'ni o'zgartirmaydi (faqat db filename uchun).
    """
    username = (username or "").strip()
    if not username:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9._-]", "_", username)


def user_db_path(user_id: int) -> str:
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    db_dir = os.path.join(base_dir, DB_DIR_NAME)
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, f"db.{int(user_id)}.sqlite3")


def legacy_user_db_path(username: str) -> str:
    """
    Eski format (username asosida) db path.
    Migratsiya uchun kerak.
    """
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    db_dir = os.path.join(base_dir, DB_DIR_NAME)
    os.makedirs(db_dir, exist_ok=True)
    safe = _safe_username(username)
    return os.path.join(db_dir, f"db.{safe}.sqlite3")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            hashtag TEXT NULL,
            mood TEXT NOT NULL,
            is_public INTEGER NOT NULL DEFAULT 0,
            parent_id INTEGER NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_is_public ON posts(is_public);")

    cols = _table_columns(conn, "posts")
    if "visibility" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN visibility INTEGER NOT NULL DEFAULT 3")
        conn.execute("UPDATE posts SET visibility = 3 WHERE is_public = 1")
        conn.execute("UPDATE posts SET visibility = 0 WHERE is_public = 0")
    if "is_draft" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN is_draft INTEGER NOT NULL DEFAULT 0")


# visibility: 0=faqat men, 1=havola (unlisted), 2=kuzatuvchilar, 3=hammaga
VIS_PRIVATE = 0
VIS_UNLISTED = 1
VIS_FOLLOWERS = 2
VIS_PUBLIC = 3


def _sync_is_public_from_visibility(visibility: int) -> int:
    return 1 if visibility == VIS_PUBLIC else 0


def _row_to_post_dict(r: sqlite3.Row) -> dict[str, Any]:
    created_at = _parse_dt(r["created_at"])
    vis = int(r["visibility"]) if "visibility" in r.keys() and r["visibility"] is not None else (
        VIS_PUBLIC if int(r["is_public"]) == 1 else VIS_PRIVATE
    )
    draft = int(r["is_draft"]) if "is_draft" in r.keys() and r["is_draft"] is not None else 0
    return {
        "id": int(r["id"]),
        "title": r["title"],
        "body": r["body"],
        "hashtag": r["hashtag"] or "",
        "mood": r["mood"],
        "is_public": bool(int(r["is_public"])),
        "visibility": vis,
        "is_draft": bool(draft),
        "parent_id": r["parent_id"],
        "created_at": created_at,
    }


def _merge_legacy_into_new(*, legacy_path: str, new_path: str) -> None:
    """
    Agar ikkala DB ham mavjud bo'lsa, legacy'dagi postlarni new'ga ko'chiradi.
    """
    legacy_conn = _connect(legacy_path)
    new_conn = _connect(new_path)
    try:
        _ensure_schema(new_conn)
        # Legacy schema bo'lmasa ham, yiqilmasin
        try:
            rows = legacy_conn.execute(
                "SELECT title, body, hashtag, mood, is_public, parent_id, created_at, updated_at FROM posts"
            ).fetchall()
        except Exception:
            rows = []

        if rows:
            new_conn.executemany(
                """
                INSERT INTO posts (title, body, hashtag, mood, is_public, parent_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["title"],
                        r["body"],
                        r["hashtag"],
                        r["mood"],
                        r["is_public"],
                        r["parent_id"],
                        r["created_at"],
                        r["updated_at"],
                    )
                    for r in rows
                ],
            )
            new_conn.commit()
    finally:
        legacy_conn.close()
        new_conn.close()


def init_user_db(user_id: int, username: Optional[str] = None) -> str:
    """
    Har bir user uchun alohida sqlite fayl va posts jadvalini yaratadi.
    Idempotent: mavjud bo'lsa, o'zgartirmaydi.
    """
    new_path = user_db_path(user_id)

    # --- Legacy -> New migratsiya ---
    if username:
        legacy_path = legacy_user_db_path(username)
        if os.path.exists(legacy_path) and not os.path.exists(new_path):
            # Eng oddiy migratsiya: rename
            os.replace(legacy_path, new_path)
        elif os.path.exists(legacy_path) and os.path.exists(new_path):
            # Ikkalasi ham bor bo'lsa: merge + legacy'ni backupga ko'chirish
            _merge_legacy_into_new(legacy_path=legacy_path, new_path=new_path)
            os.replace(legacy_path, legacy_path + ".bak")

    conn = _connect(new_path)
    try:
        _ensure_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return new_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_post(
    *,
    user_id: int,
    username: Optional[str] = None,
    title: str,
    body: str,
    mood: str,
    hashtag: Optional[str] = None,
    parent_id: Optional[int] = None,
    is_public: bool = False,
    visibility: Optional[int] = None,
    is_draft: bool = False,
) -> int:
    init_user_db(user_id, username=username)
    path = user_db_path(user_id)
    now = _now_iso()
    vis = int(visibility) if visibility is not None else (VIS_PUBLIC if is_public else VIS_PRIVATE)
    ip = _sync_is_public_from_visibility(vis)
    draft = 1 if is_draft else 0
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        cur = conn.execute(
            """
            INSERT INTO posts (title, body, hashtag, mood, is_public, parent_id, created_at, updated_at, visibility, is_draft)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, body, hashtag, mood, ip, parent_id, now, now, vis, draft),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def delete_post(*, user_id: int, username: Optional[str] = None, post_id: int) -> None:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        conn.execute("DELETE FROM posts WHERE id = ?", (int(post_id),))
        conn.commit()
    finally:
        conn.close()


def toggle_post_public(*, user_id: int, username: Optional[str] = None, post_id: int) -> None:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        row = conn.execute("SELECT is_public, visibility FROM posts WHERE id = ?", (int(post_id),)).fetchone()
        if not row:
            return
        vis = int(row["visibility"]) if "visibility" in row.keys() else VIS_PRIVATE
        if int(row["is_public"]) == 1 or vis == VIS_PUBLIC:
            new_vis = VIS_PRIVATE
        else:
            new_vis = VIS_PUBLIC
        ip = _sync_is_public_from_visibility(new_vis)
        conn.execute(
            "UPDATE posts SET is_public = ?, visibility = ?, updated_at = ? WHERE id = ?",
            (ip, new_vis, _now_iso(), int(post_id)),
        )
        conn.commit()
    finally:
        conn.close()


def update_post(
    *,
    user_id: int,
    username: Optional[str] = None,
    post_id: int,
    title: str,
    body: str,
    mood: str,
    hashtag: Optional[str] = None,
    visibility: int = VIS_PRIVATE,
    is_draft: bool = False,
) -> None:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        ip = _sync_is_public_from_visibility(int(visibility))
        conn.execute(
            """
            UPDATE posts SET title = ?, body = ?, hashtag = ?, mood = ?, is_public = ?, visibility = ?, is_draft = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, body, hashtag, mood, ip, int(visibility), 1 if is_draft else 0, _now_iso(), int(post_id)),
        )
        conn.commit()
    finally:
        conn.close()


def get_post(*, user_id: int, username: Optional[str] = None, post_id: int) -> Optional[dict[str, Any]]:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        r = conn.execute(
            """
            SELECT id, title, body, hashtag, mood, is_public, parent_id, created_at, updated_at, visibility, is_draft
            FROM posts WHERE id = ? AND parent_id IS NULL
            """,
            (int(post_id),),
        ).fetchone()
        if not r:
            return None
        return _row_to_post_dict(r)
    finally:
        conn.close()


def post_visible_to_viewer(
    post: dict[str, Any],
    *,
    is_owner: bool,
    viewer_is_yaqin: bool,
) -> bool:
    if is_owner:
        return True
    if post.get("is_draft"):
        return False
    v = int(post.get("visibility", VIS_PRIVATE))
    if v == VIS_PUBLIC:
        return True
    if v == VIS_FOLLOWERS and viewer_is_yaqin:
        return True
    if v == VIS_UNLISTED:
        return True
    return False


def post_visible_on_profile_timeline(
    post: dict[str, Any],
    *,
    is_owner: bool,
    viewer_is_yaqin: bool,
) -> bool:
    if is_owner:
        return True
    if post.get("is_draft"):
        return False
    v = int(post.get("visibility", VIS_PRIVATE))
    if v == VIS_PUBLIC:
        return True
    if v == VIS_FOLLOWERS and viewer_is_yaqin:
        return True
    return False


def _parse_dt(value: str) -> datetime:
    # created_at UTC isoformat yoziladi; agar parse bo'lmasa, hozirgi vaqt.
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def list_posts(
    *,
    user_id: int,
    username: Optional[str] = None,
    is_owner: bool,
    query: Optional[str] = None,
    date_filter: Optional[str] = None,  # YYYY-MM-DD
    tag: Optional[str] = None,
    viewer_is_yaqin: bool = False,
    include_drafts: bool = True,
    feed_author_username: Optional[str] = None,
) -> list[dict[str, Any]]:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        clauses: list[str] = ["parent_id IS NULL"]
        params: list[Any] = []

        if not is_owner:
            clauses.append("is_draft = 0")
            clauses.append(
                "("
                "visibility = ? OR (visibility = ? AND ? = 1)"
                ")"
            )
            params.extend([VIS_PUBLIC, VIS_FOLLOWERS, 1 if viewer_is_yaqin else 0])

        if is_owner and not include_drafts:
            clauses.append("is_draft = 0")

        if query:
            q = f"%{query.strip()}%"
            clauses.append("(title LIKE ? OR body LIKE ? OR hashtag LIKE ?)")
            params.extend([q, q, q])

        if date_filter:
            clauses.append("substr(created_at, 1, 10) = ?")
            params.append(date_filter.strip())

        if tag:
            t = tag.strip().lstrip("#").lower()
            if t:
                clauses.append("(lower(hashtag) = ? OR lower(hashtag) = ?)")
                params.extend([f"#{t}", t])

        where_sql = " AND ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT id, title, body, hashtag, mood, is_public, parent_id, created_at, updated_at, visibility, is_draft
            FROM posts
            WHERE {where_sql}
            ORDER BY created_at DESC
            """,
            params,
        ).fetchall()

        out = [_row_to_post_dict(r) for r in rows]
        uname = (feed_author_username or username or "").strip()
        for d in out:
            d["author_id"] = int(user_id)
            if uname:
                d["author_username"] = uname
        return out
    finally:
        conn.close()


def list_feed_posts_from_yaqin_author(
    *,
    author_id: int,
    author_username: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Yaqin foydalanuvchining lentaga tushadigan postlari (draftsiz, ildiz postlar).
    Ko‘rinish: ommaviy yoki «faqat yaqinlarim» — bu yerda tomoshabin yaqin deb hisoblanadi.
    """
    return list_posts(
        user_id=author_id,
        username=author_username,
        is_owner=False,
        viewer_is_yaqin=True,
        include_drafts=False,
        feed_author_username=author_username,
    )


def calendar_day_counts(
    *,
    user_id: int,
    username: Optional[str] = None,
    year: int,
    month: int,
) -> dict[int, int]:
    """Oy ichida har kun uchun xotiralar soni (draftsiz)."""
    init_user_db(user_id, username=username)
    prefix = f"{int(year)}-{int(month):02d}"
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT CAST(substr(created_at, 9, 2) AS INTEGER) AS d, COUNT(*) AS c
            FROM posts
            WHERE parent_id IS NULL AND is_draft = 0 AND substr(created_at, 1, 7) = ?
            GROUP BY d
            """,
            (prefix,),
        ).fetchall()
        return {int(r["d"]): int(r["c"]) for r in rows if r["d"] is not None}
    finally:
        conn.close()


def available_years(*, user_id: int, username: Optional[str] = None) -> list[int]:
    """Foydalanuvchida mavjud (draftsiz) yillar ro'yxati."""
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT DISTINCT substr(created_at, 1, 4) AS y
            FROM posts
            WHERE parent_id IS NULL AND is_draft = 0
            ORDER BY y DESC
            """
        ).fetchall()
        out: list[int] = []
        for r in rows:
            y = str(r["y"] or "").strip()
            if not y:
                continue
            try:
                out.append(int(y))
            except ValueError:
                continue
        return out
    finally:
        conn.close()


def user_mood_stats_in_range(
    *,
    user_id: int,
    username: Optional[str] = None,
    date_from: str,
    date_to: str,
) -> tuple[int, dict[str, int]]:
    """
    Foydalanuvchining xotiralari (draftsiz) uchun [date_from, date_to] oralig'i.
    Sanalar YYYY-MM-DD, created_at prefiksi bilan solishtiriladi.
    """
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        where = (
            "parent_id IS NULL AND is_draft = 0 "
            "AND substr(created_at, 1, 10) >= ? AND substr(created_at, 1, 10) <= ?"
        )
        params = (date_from.strip(), date_to.strip())
        total_row = conn.execute(
            f"SELECT COUNT(*) AS n FROM posts WHERE {where}",
            params,
        ).fetchone()
        total = int(total_row["n"] or 0)
        rows = conn.execute(
            f"""
            SELECT mood, COUNT(*) AS c FROM posts
            WHERE {where}
            GROUP BY mood ORDER BY c DESC
            """,
            params,
        ).fetchall()
        by_mood = {str(r["mood"]): int(r["c"]) for r in rows}
        return total, by_mood
    finally:
        conn.close()


def user_writing_streak_days(*, user_id: int, username: Optional[str] = None) -> int:
    """
    Bugundan boshlab orqaga ketma-ket necha kunda kamida bitta xotira bor.
    Bugun yozilmagan bo'lsa, streak 0.
    """
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT DISTINCT substr(created_at, 1, 10) AS d
            FROM posts
            WHERE parent_id IS NULL AND is_draft = 0
            """
        ).fetchall()
        dates = {str(r["d"]) for r in rows if r["d"]}
        d = date.today()
        streak = 0
        while d.isoformat() in dates:
            streak += 1
            d -= timedelta(days=1)
        return streak
    finally:
        conn.close()


def user_hashtag_top(
    *,
    user_id: int,
    username: Optional[str] = None,
    limit: int = 5,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[tuple[str, int]]:
    """Eng ko'p ishlatilgan hashtaglar (draftsiz)."""
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        clauses = [
            "parent_id IS NULL",
            "is_draft = 0",
            "hashtag IS NOT NULL",
            "trim(hashtag) != ''",
        ]
        params: list[Any] = []
        if date_from:
            clauses.append("substr(created_at, 1, 10) >= ?")
            params.append(date_from.strip())
        if date_to:
            clauses.append("substr(created_at, 1, 10) <= ?")
            params.append(date_to.strip())
        where_sql = " AND ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT hashtag, COUNT(*) AS c FROM posts
            WHERE {where_sql}
            GROUP BY hashtag ORDER BY c DESC LIMIT ?
            """,
            (*params, int(limit)),
        ).fetchall()
        return [(str(r["hashtag"]), int(r["c"])) for r in rows]
    finally:
        conn.close()


def global_public_mood_stats(*, days: Optional[int] = None) -> tuple[int, dict[str, int]]:
    """
    Barcha foydalanuvchilarning faqat hammaga ochiq (visibility=PUBLIC) xotiralari
    bo'yicha kayfiyatlar yig'indisi. days berilsa — oxirgi N kun.
    """
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    db_dir = os.path.join(base_dir, DB_DIR_NAME)
    if not os.path.isdir(db_dir):
        return 0, {}

    from datetime import date, timedelta

    since: Optional[str] = None
    if days is not None and int(days) > 0:
        since = (date.today() - timedelta(days=int(days) - 1)).isoformat()

    agg: dict[str, int] = {}
    total = 0
    pattern = os.path.join(db_dir, "db.*.sqlite3")
    for path in glob.glob(pattern):
        conn = _connect(path)
        try:
            _ensure_schema(conn)
            if since:
                where = (
                    "parent_id IS NULL AND is_draft = 0 AND visibility = ? "
                    "AND substr(created_at, 1, 10) >= ?"
                )
                params = (VIS_PUBLIC, since)
            else:
                where = "parent_id IS NULL AND is_draft = 0 AND visibility = ?"
                params = (VIS_PUBLIC,)
            rows = conn.execute(
                f"SELECT mood, COUNT(*) AS c FROM posts WHERE {where} GROUP BY mood",
                params,
            ).fetchall()
            for r in rows:
                k = str(r["mood"])
                c = int(r["c"])
                agg[k] = agg.get(k, 0) + c
                total += c
        except Exception:
            continue
        finally:
            conn.close()
    return total, agg


def posts_on_month_day(
    *,
    user_id: int,
    username: Optional[str] = None,
    month: int,
    day: int,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Har yilgi bir xil sana (MM-DD) bo'yicha postlar (draftsiz)."""
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    mmdd = f"{int(month):02d}-{int(day):02d}"
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT id, title, body, hashtag, mood, is_public, parent_id, created_at, updated_at, visibility, is_draft
            FROM posts
            WHERE parent_id IS NULL AND is_draft = 0 AND substr(created_at, 6, 5) = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (mmdd, int(limit)),
        ).fetchall()
        out = [_row_to_post_dict(r) for r in rows]
        uname = (username or "").strip()
        for dct in out:
            dct["author_id"] = int(user_id)
            if uname:
                dct["author_username"] = uname
        return out
    finally:
        conn.close()


def recap_for_year(
    *,
    user_id: int,
    username: Optional[str] = None,
    year: int,
) -> dict[str, Any]:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        y = str(int(year))
        total = conn.execute(
            """
            SELECT COUNT(*) FROM posts
            WHERE parent_id IS NULL AND is_draft = 0 AND substr(created_at, 1, 4) = ?
            """,
            (y,),
        ).fetchone()[0]
        mood_rows = conn.execute(
            """
            SELECT mood, COUNT(*) AS c FROM posts
            WHERE parent_id IS NULL AND is_draft = 0 AND substr(created_at, 1, 4) = ?
            GROUP BY mood
            """,
            (y,),
        ).fetchall()
        by_mood = {str(r["mood"]): int(r["c"]) for r in mood_rows}
        hashtag_row = conn.execute(
            """
            SELECT hashtag, COUNT(*) AS c FROM posts
            WHERE parent_id IS NULL AND is_draft = 0 AND substr(created_at, 1, 4) = ?
              AND hashtag IS NOT NULL AND trim(hashtag) != ''
            GROUP BY hashtag ORDER BY c DESC LIMIT 1
            """,
            (y,),
        ).fetchone()
        top_tag = hashtag_row["hashtag"] if hashtag_row and hashtag_row["hashtag"] else None
        return {"year": int(year), "total": int(total), "by_mood": by_mood, "top_hashtag": top_tag}
    finally:
        conn.close()


def export_posts_text_lines(
    *,
    user_id: int,
    username: Optional[str] = None,
    year: Optional[int] = None,
) -> list[str]:
    init_user_db(user_id, username=username)
    conn = _connect(user_db_path(user_id))
    try:
        _ensure_schema(conn)
        clauses = ["parent_id IS NULL", "is_draft = 0"]
        params: list[Any] = []
        if year is not None:
            clauses.append("substr(created_at, 1, 4) = ?")
            params.append(str(int(year)))
        where_sql = " AND ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT title, body, hashtag, mood, created_at FROM posts
            WHERE {where_sql}
            ORDER BY created_at ASC
            """,
            params,
        ).fetchall()
        lines: list[str] = []
        for r in rows:
            lines.append(f"--- {r['created_at'][:19]} | {mood_label(r['mood'])}")
            lines.append(r["title"])
            lines.append(r["body"])
            if r["hashtag"]:
                lines.append(r["hashtag"])
            lines.append("")
        return lines
    finally:
        conn.close()


def search_hashtag_global(tag: str) -> list[dict[str, Any]]:
    """Barcha ochiq xotiralar orasidan hashtag bo'yicha (profile sqlite fayllari)."""
    t = tag.strip().lstrip("#").lower()
    if not t:
        return []
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    db_dir = os.path.join(base_dir, DB_DIR_NAME)
    if not os.path.isdir(db_dir):
        return []
    out: list[dict[str, Any]] = []
    pattern = os.path.join(db_dir, "db.*.sqlite3")
    for path in glob.glob(pattern):
        base = os.path.basename(path)
        m = re.match(r"^db\.(\d+)\.sqlite3$", base)
        if not m:
            continue
        uid = int(m.group(1))
        conn = _connect(path)
        try:
            _ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT id, title, body, hashtag, mood, is_public, parent_id, created_at, updated_at, visibility, is_draft
                FROM posts
                WHERE parent_id IS NULL AND is_draft = 0 AND visibility = ?
                  AND (lower(hashtag) = ? OR lower(hashtag) = ?)
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (VIS_PUBLIC, f"#{t}", t),
            ).fetchall()
            for r in rows:
                d = _row_to_post_dict(r)
                d["author_id"] = uid
                out.append(d)
        except Exception:
            continue
        finally:
            conn.close()
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out[:80]


# Eski SQLite postlar (happy, dream, …) uchun — admin `Kayfiyat` jadvali asosiy manba.
LEGACY_MOOD_LABELS: dict[str, str] = {
    "happy": "😊 Yaxshi",
    "sad": "😔 Ma’yus",
    "energy": "⚡ Energiya",
    "work": "🛠️ Ish bilan band",
    "dream": "☁️ Xayolparast",
}


def mood_label(mood_key: str) -> str:
    if not mood_key:
        return ""
    s = str(mood_key).strip()
    from blogs.models import Kayfiyat

    k = Kayfiyat.objects.filter(slug=s).first()
    if k:
        em = (k.emoji or "").strip()
        nm = (k.name or "").strip()
        if em and nm:
            return f"{em} {nm}"
        return nm or em or s
    return LEGACY_MOOD_LABELS.get(s, s)

