"""SitemapWatch — Flask application entry point."""

import logging
from flask import Flask, flash, redirect, render_template, request, url_for

from apscheduler.schedulers.background import BackgroundScheduler

from database import (
    add_snapshot,
    add_tracked_site,
    delete_tracked_site,
    get_all_tracked_sites,
    get_changes_for_site,
    get_latest_snapshot,
    get_total_changes_count,
    get_tracked_site,
    get_tracked_site_by_domain,
    init_db,
)
from monitor import check_all_sites, check_site
from sitemap import discover_sitemaps, fetch_urls_from_sitemaps, normalize_domain

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = "sitemapwatch-dev-secret-key"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def dashboard():
    """Main dashboard — list all tracked sites."""
    sites = get_all_tracked_sites()

    # Enrich each site with its latest snapshot URL count and total changes
    for site in sites:
        snapshot = get_latest_snapshot(site["id"])
        site["page_count"] = snapshot["url_count"] if snapshot else 0
        site["total_changes"] = get_total_changes_count(site["id"])

    return render_template("dashboard.html", sites=sites)


@app.route("/track", methods=["POST"])
def track():
    """Add a new site to track."""
    raw_url = request.form.get("url", "").strip()

    if not raw_url:
        flash("Please enter a URL.", "error")
        return redirect(url_for("dashboard"))

    # Normalize the domain
    try:
        domain = normalize_domain(raw_url)
    except Exception:
        flash("Please enter a valid URL.", "error")
        return redirect(url_for("dashboard"))

    if not domain or "." not in domain:
        flash("Please enter a valid URL.", "error")
        return redirect(url_for("dashboard"))

    # Check for duplicates
    existing = get_tracked_site_by_domain(domain)
    if existing:
        flash(f"'{domain}' is already being tracked.", "info")
        return redirect(url_for("dashboard"))

    # Discover sitemaps
    logger.info("Discovering sitemaps for %s...", domain)
    sitemap_urls = discover_sitemaps(domain)

    if not sitemap_urls:
        flash(
            f"No sitemap found for '{domain}'. The site may not publish one.",
            "error",
        )
        return redirect(url_for("dashboard"))

    logger.info("Found %d sitemap(s) for %s: %s", len(sitemap_urls), domain, sitemap_urls)

    # Add the site
    site_id = add_tracked_site(domain, sitemap_urls)

    # Take the initial snapshot
    urls = fetch_urls_from_sitemaps(sitemap_urls)
    if urls:
        add_snapshot(site_id, urls)
        flash(
            f"Now tracking {domain} — {len(urls)} pages found across {len(sitemap_urls)} sitemap(s).",
            "success",
        )
    else:
        flash(
            f"Tracking {domain}, but the sitemap(s) returned no URLs. Will retry on next check.",
            "warning",
        )

    return redirect(url_for("dashboard"))


@app.route("/check/<int:site_id>", methods=["POST"])
def check_now(site_id: int):
    """Trigger a manual check for a tracked site."""
    site = get_tracked_site(site_id)
    if site is None:
        flash("Site not found.", "error")
        return redirect(url_for("dashboard"))

    result = check_site(site)

    if result["error"]:
        flash(f"Error checking {site['domain']}: {result['error']}", "error")
    elif result["changed"]:
        added = len(result["added"])
        removed = len(result["removed"])
        parts = []
        if added:
            parts.append(f"{added} new page{'s' if added != 1 else ''}")
        if removed:
            parts.append(f"{removed} removed page{'s' if removed != 1 else ''}")
        flash(f"{site['domain']}: {', '.join(parts)} detected!", "success")
    else:
        flash(f"{site['domain']}: No changes detected.", "info")

    return redirect(url_for("dashboard"))


@app.route("/site/<int:site_id>")
def site_detail(site_id: int):
    """View change history for a specific tracked site."""
    site = get_tracked_site(site_id)
    if site is None:
        flash("Site not found.", "error")
        return redirect(url_for("dashboard"))

    snapshot = get_latest_snapshot(site_id)
    site["page_count"] = snapshot["url_count"] if snapshot else 0

    changes = get_changes_for_site(site_id)

    return render_template("site_detail.html", site=site, changes=changes)


@app.route("/remove/<int:site_id>", methods=["POST"])
def remove(site_id: int):
    """Remove a site from tracking."""
    site = get_tracked_site(site_id)
    if site is None:
        flash("Site not found.", "error")
        return redirect(url_for("dashboard"))

    domain = site["domain"]
    delete_tracked_site(site_id)
    flash(f"Stopped tracking {domain}. All history has been deleted.", "info")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


def start_scheduler():
    """Start the background scheduler for periodic sitemap checks."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_check,
        "interval",
        hours=6,
        id="sitemap_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started — checking every 6 hours.")


def scheduled_check():
    """Scheduled job: check all tracked sites."""
    logger.info("Running scheduled sitemap check...")
    results = check_all_sites()
    for r in results:
        if r.get("changed"):
            logger.info(
                "Changes detected for %s: +%d / -%d",
                r["domain"],
                len(r["added"]),
                len(r["removed"]),
            )
        elif r.get("error"):
            logger.warning("Error checking %s: %s", r["domain"], r["error"])
        else:
            logger.info("No changes for %s", r["domain"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    start_scheduler()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
