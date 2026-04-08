"""SQLite database initialization and helper functions for SitemapWatch."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "sitemapwatch.db"


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize the database schema."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tracked_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL UNIQUE,
            sitemap_urls TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            last_checked TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            urls TEXT NOT NULL DEFAULT '[]',
            url_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (site_id) REFERENCES tracked_sites(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            snapshot_id INTEGER NOT NULL,
            added_urls TEXT NOT NULL DEFAULT '[]',
            removed_urls TEXT NOT NULL DEFAULT '[]',
            added_count INTEGER NOT NULL DEFAULT 0,
            removed_count INTEGER NOT NULL DEFAULT 0,
            detected_at TEXT NOT NULL,
            FOREIGN KEY (site_id) REFERENCES tracked_sites(id) ON DELETE CASCADE,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tracked Sites
# ---------------------------------------------------------------------------


def add_tracked_site(domain: str, sitemap_urls: list[str]) -> int:
    """Insert a new tracked site. Returns the new row id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO tracked_sites (domain, sitemap_urls, created_at, status) VALUES (?, ?, ?, 'active')",
        (domain, json.dumps(sitemap_urls), now_iso()),
    )
    conn.commit()
    site_id = cursor.lastrowid
    conn.close()
    return site_id


def get_tracked_site(site_id: int) -> dict | None:
    """Return a single tracked site by id, or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM tracked_sites WHERE id = ?", (site_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def get_tracked_site_by_domain(domain: str) -> dict | None:
    """Return a tracked site by domain, or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM tracked_sites WHERE domain = ?", (domain,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def get_all_tracked_sites() -> list[dict]:
    """Return all tracked sites."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM tracked_sites ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_site_status(site_id: int, status: str, error_message: str | None = None) -> None:
    """Update a site's status and optional error message."""
    conn = get_db()
    conn.execute(
        "UPDATE tracked_sites SET status = ?, error_message = ?, last_checked = ? WHERE id = ?",
        (status, error_message, now_iso(), site_id),
    )
    conn.commit()
    conn.close()


def update_site_last_checked(site_id: int) -> None:
    """Update the last_checked timestamp for a site."""
    conn = get_db()
    conn.execute(
        "UPDATE tracked_sites SET last_checked = ? WHERE id = ?",
        (now_iso(), site_id),
    )
    conn.commit()
    conn.close()


def delete_tracked_site(site_id: int) -> None:
    """Delete a tracked site and all its snapshots/changes (cascade)."""
    conn = get_db()
    conn.execute("DELETE FROM tracked_sites WHERE id = ?", (site_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def add_snapshot(site_id: int, urls: list[str]) -> int:
    """Insert a new snapshot. Returns the new row id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO snapshots (site_id, urls, url_count, created_at) VALUES (?, ?, ?, ?)",
        (site_id, json.dumps(urls), len(urls), now_iso()),
    )
    conn.commit()
    snapshot_id = cursor.lastrowid
    conn.close()
    return snapshot_id


def get_latest_snapshot(site_id: int) -> dict | None:
    """Return the most recent snapshot for a site, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM snapshots WHERE site_id = ? ORDER BY created_at DESC LIMIT 1",
        (site_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------


def add_change(
    site_id: int,
    snapshot_id: int,
    added_urls: list[str],
    removed_urls: list[str],
) -> int:
    """Insert a new change record. Returns the new row id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO changes (site_id, snapshot_id, added_urls, removed_urls, added_count, removed_count, detected_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            site_id,
            snapshot_id,
            json.dumps(added_urls),
            json.dumps(removed_urls),
            len(added_urls),
            len(removed_urls),
            now_iso(),
        ),
    )
    conn.commit()
    change_id = cursor.lastrowid
    conn.close()
    return change_id


def get_changes_for_site(site_id: int) -> list[dict]:
    """Return all change records for a site, most recent first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM changes WHERE site_id = ? ORDER BY detected_at DESC",
        (site_id,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_total_changes_count(site_id: int) -> int:
    """Return the total number of change records for a site."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM changes WHERE site_id = ?", (site_id,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict, parsing JSON fields."""
    d = dict(row)
    for key in ("sitemap_urls", "urls", "added_urls", "removed_urls"):
        if key in d and isinstance(d[key], str):
            d[key] = json.loads(d[key])
    return d
