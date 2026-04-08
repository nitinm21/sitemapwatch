"""Monitor logic — compare sitemap snapshots and detect changes."""

from database import (
    add_change,
    add_snapshot,
    get_all_tracked_sites,
    get_latest_snapshot,
    update_site_last_checked,
    update_site_status,
)
from sitemap import fetch_urls_from_sitemaps


def check_site(site: dict) -> dict:
    """Check a single tracked site for sitemap changes.

    Fetches the current sitemap URLs, compares against the last snapshot,
    and records any changes.

    Returns a dict with:
        - changed: bool
        - added: list[str]
        - removed: list[str]
        - total_urls: int
        - error: str | None
    """
    site_id = site["id"]
    sitemap_urls = site["sitemap_urls"]

    try:
        # Fetch current URLs from all sitemaps
        current_urls = fetch_urls_from_sitemaps(sitemap_urls)

        if not current_urls:
            update_site_status(site_id, "error", "Sitemap returned no URLs")
            return {
                "changed": False,
                "added": [],
                "removed": [],
                "total_urls": 0,
                "error": "Sitemap returned no URLs",
            }

        # Get the previous snapshot
        prev_snapshot = get_latest_snapshot(site_id)

        if prev_snapshot is None:
            # First check — just store the initial snapshot
            add_snapshot(site_id, current_urls)
            update_site_status(site_id, "active")
            update_site_last_checked(site_id)
            return {
                "changed": False,
                "added": [],
                "removed": [],
                "total_urls": len(current_urls),
                "error": None,
            }

        # Compare
        prev_url_set = set(prev_snapshot["urls"])
        curr_url_set = set(current_urls)

        added = sorted(curr_url_set - prev_url_set)
        removed = sorted(prev_url_set - curr_url_set)

        if added or removed:
            # Store new snapshot and change record
            snapshot_id = add_snapshot(site_id, current_urls)
            add_change(site_id, snapshot_id, added, removed)

        update_site_status(site_id, "active")
        update_site_last_checked(site_id)

        return {
            "changed": bool(added or removed),
            "added": added,
            "removed": removed,
            "total_urls": len(current_urls),
            "error": None,
        }

    except Exception as exc:
        error_msg = f"Check failed: {exc}"
        update_site_status(site_id, "error", error_msg)
        return {
            "changed": False,
            "added": [],
            "removed": [],
            "total_urls": 0,
            "error": error_msg,
        }


def check_all_sites() -> list[dict]:
    """Check all tracked sites for changes. Called by the scheduler."""
    sites = get_all_tracked_sites()
    results = []
    for site in sites:
        if site["status"] == "paused":
            continue
        result = check_site(site)
        result["domain"] = site["domain"]
        results.append(result)
    return results
