# SitemapWatch — Product Requirements Document

## 1. Overview

**SitemapWatch** is a web application that monitors competitors' sitemaps for changes. Users enter a website URL, and the app automatically discovers its sitemap, takes a snapshot, and periodically checks for new or removed pages — surfacing competitive intelligence before it's publicly announced.

### Core Insight

Every website publishes a `sitemap.xml` that lists all its pages. When companies add new product pages, pricing tiers, integration pages, or landing pages, those URLs appear in the sitemap **before** any public announcement. By monitoring sitemaps, you get early signal on:

- New product launches (e.g., `/products/enterprise-plan`)
- Partnership announcements (e.g., `/integrations/salesforce`)
- Pricing changes (e.g., new pricing tier URLs)
- Campaign landing pages before they go live
- Hiring signals (e.g., new career/team pages)
- Content strategy shifts (e.g., new blog categories)

---

## 2. User Flow

```
1. User visits the SitemapWatch homepage
2. User enters a competitor's website URL (e.g., "competitor.com")
3. User clicks "Track"
4. Backend discovers the sitemap, parses all URLs, stores the initial snapshot
5. User sees a confirmation: "Now tracking competitor.com — 347 pages found"
6. Background scheduler re-checks the sitemap periodically
7. User returns to the dashboard to see tracked sites and any changes detected
8. User clicks into a tracked site to see the full change history (new/removed URLs with timestamps)
```

---

## 3. Tech Stack

| Layer        | Technology                     | Rationale                                      |
|--------------|--------------------------------|------------------------------------------------|
| **Backend**  | Python 3.11+ / Flask           | Simple, user-familiar, great XML parsing libs  |
| **Frontend** | HTML / CSS / JavaScript (Jinja2 templates) | No build step, minimal complexity for MVP |
| **Database** | SQLite                         | Zero config, single-file, perfect for MVP      |
| **Scheduler**| APScheduler (BackgroundScheduler) | In-process, no external dependencies        |
| **HTTP**     | `requests` + `lxml`            | Robust sitemap fetching and XML parsing        |

### Why This Stack

- **No build tools, no npm, no bundler** — just Python and a browser.
- SQLite runs in-process — no database server to manage.
- APScheduler runs inside the Flask process — no separate worker or cron to configure.
- Everything runs with a single command: `python app.py`.

---

## 4. Features — MVP Scope

### 4.1 Add a Site to Track

- **Input**: A text field accepting a domain or full URL (e.g., `competitor.com`, `https://competitor.com`, `https://competitor.com/sitemap.xml`).
- **Normalization**: The app normalizes the input to a base domain (strip paths, ensure `https://`).
- **Validation**: Basic URL validation. Reject obviously invalid inputs.
- **Duplicate check**: If the site is already being tracked, show a message instead of adding it again.

### 4.2 Sitemap Discovery

The app attempts to find sitemaps in this order:

1. **Check `/robots.txt`** for `Sitemap:` directives.
2. **Try `/sitemap.xml`** at the root domain.
3. **Try common alternatives**: `/sitemap_index.xml`, `/sitemap/sitemap.xml`.
4. **Follow sitemap index files**: If a sitemap is a `<sitemapindex>`, recursively fetch all referenced `<sitemap>` entries.

If no sitemap is found after all attempts, display an error: *"No sitemap found for this domain. The site may not publish one."*

### 4.3 Initial Snapshot

Once a sitemap is discovered:

- Parse all `<url><loc>` entries from all discovered sitemaps.
- Store every URL with its `<lastmod>` timestamp (if available).
- Record the snapshot timestamp.
- Display to the user: *"Now tracking [domain] — [N] pages found."*

### 4.4 Periodic Monitoring

- **Default check frequency**: Every 6 hours.
- A background scheduler (APScheduler) runs inside the Flask app process.
- On each check:
  1. Re-fetch and re-parse all sitemaps for the tracked domain.
  2. Compare the current URL set against the last snapshot.
  3. Identify **added URLs** (new pages) and **removed URLs** (deleted pages).
  4. If there are changes, store a new snapshot and a change record.
  5. If no changes, update the "last checked" timestamp only.

### 4.5 Manual "Check Now"

- Each tracked site has a "Check Now" button on the dashboard.
- Triggers an immediate re-check outside the scheduled cycle.
- Shows a loading state while checking, then displays results.

### 4.6 Dashboard

A simple dashboard showing all tracked sites:

| Column              | Description                                  |
|---------------------|----------------------------------------------|
| **Domain**          | The tracked website                          |
| **Pages Tracked**   | Total number of URLs in the latest snapshot   |
| **Last Checked**    | Timestamp of the most recent check           |
| **Changes**         | Count of total changes detected (all time)   |
| **Status**          | Active / Error (e.g., sitemap unreachable)   |
| **Actions**         | "Check Now" button, "View Changes" link, "Remove" button |

### 4.7 Change Detail View

When a user clicks into a tracked site:

- Show the site's full change history, grouped by check date.
- Each entry shows:
  - **Date/time** of the check
  - **Added URLs** (highlighted in green) — with clickable links
  - **Removed URLs** (highlighted in red) — with the URL text shown
- Most recent changes appear at the top.
- Show the total URL count at each snapshot for context.

### 4.8 Remove a Tracked Site

- "Remove" button on the dashboard.
- Confirmation prompt: *"Stop tracking [domain]? This will delete all history."*
- Deletes all snapshots and change records for that domain.

---

## 5. Data Model (SQLite)

### `tracked_sites`

| Column          | Type      | Description                              |
|-----------------|-----------|------------------------------------------|
| `id`            | INTEGER PK| Auto-increment                           |
| `domain`        | TEXT      | Normalized domain (e.g., `competitor.com`)|
| `sitemap_urls`  | TEXT (JSON)| List of discovered sitemap URLs          |
| `created_at`    | DATETIME  | When tracking started                    |
| `last_checked`  | DATETIME  | Last successful check timestamp          |
| `status`        | TEXT      | `active`, `error`, `paused`              |
| `error_message` | TEXT      | Last error message (if status=error)     |

### `snapshots`

| Column          | Type      | Description                              |
|-----------------|-----------|------------------------------------------|
| `id`            | INTEGER PK| Auto-increment                           |
| `site_id`       | INTEGER FK| References `tracked_sites.id`            |
| `urls`          | TEXT (JSON)| Full list of URLs in this snapshot        |
| `url_count`     | INTEGER   | Total number of URLs                     |
| `created_at`    | DATETIME  | When this snapshot was taken              |

### `changes`

| Column          | Type      | Description                              |
|-----------------|-----------|------------------------------------------|
| `id`            | INTEGER PK| Auto-increment                           |
| `site_id`       | INTEGER FK| References `tracked_sites.id`            |
| `snapshot_id`   | INTEGER FK| References `snapshots.id`                |
| `added_urls`    | TEXT (JSON)| List of newly added URLs                 |
| `removed_urls`  | TEXT (JSON)| List of removed URLs                     |
| `added_count`   | INTEGER   | Number of added URLs                     |
| `removed_count` | INTEGER   | Number of removed URLs                   |
| `detected_at`   | DATETIME  | When the change was detected             |

---

## 6. API Endpoints

| Method | Endpoint                    | Description                                |
|--------|-----------------------------|--------------------------------------------|
| GET    | `/`                         | Dashboard — list all tracked sites         |
| POST   | `/track`                    | Add a new site to track                    |
| POST   | `/check/<site_id>`          | Trigger a manual check for a site          |
| GET    | `/site/<site_id>`           | View change history for a specific site    |
| POST   | `/remove/<site_id>`         | Remove a site from tracking                |

All endpoints return HTML (server-rendered via Jinja2). No separate API/SPA.

---

## 7. UI Design

### Style

- **Minimal and clean** — no heavy framework, no complex layout.
- Light background with a dark accent color.
- Monospace font for URLs to aid readability.
- Responsive but desktop-first (this is a power-user tool).

### Pages

1. **Dashboard (`/`)**
   - Header with app name "SitemapWatch" and a brief tagline.
   - Input field + "Track" button at the top.
   - Table of tracked sites below.
   - Empty state: *"No sites tracked yet. Enter a URL above to get started."*

2. **Site Detail (`/site/<id>`)**
   - Site domain as the page title.
   - Summary stats: total pages, tracking since, last checked.
   - "Check Now" button.
   - Change history feed (reverse chronological).
   - Each change entry is a collapsible card showing added/removed URLs.

---

## 8. Error Handling

| Scenario                        | Behavior                                              |
|---------------------------------|-------------------------------------------------------|
| Invalid URL input               | Flash message: "Please enter a valid URL."            |
| No sitemap found                | Flash message: "No sitemap found for this domain."    |
| Sitemap fetch timeout (>15s)    | Mark site status as `error`, show message on dashboard|
| Malformed XML                   | Attempt best-effort parsing; if total failure, mark as error |
| Site already tracked            | Flash message: "This site is already being tracked."  |
| Network error during check      | Mark as `error`, retain last good snapshot, retry on next cycle |
| Sitemap behind auth/paywall     | Mark as `error`: "Sitemap is not publicly accessible."|

---

## 9. Non-Functional Requirements

| Requirement       | Target                                                  |
|-------------------|---------------------------------------------------------|
| **Concurrency**   | Support tracking 2-10 sites simultaneously (MVP)        |
| **Performance**   | Sitemap fetch + parse should complete within 30 seconds  |
| **Storage**       | SQLite — single file, no external DB server              |
| **Reliability**   | Graceful error handling; one failing site doesn't affect others |
| **Security**      | No authentication for MVP (single-user, local use)       |
| **Deployment**    | Runs locally with `python app.py`; optionally Docker     |

---

## 10. Project Structure

```
sitemapwatch/
├── app.py                  # Flask app entry point, routes, scheduler setup
├── database.py             # SQLite database initialization and helpers
├── sitemap.py              # Sitemap discovery, fetching, and parsing logic
├── monitor.py              # Diff logic — compare snapshots, detect changes
├── templates/
│   ├── base.html           # Base template with layout and styles
│   ├── dashboard.html      # Main dashboard page
│   └── site_detail.html    # Per-site change history page
├── static/
│   └── style.css           # Minimal custom styles
├── requirements.txt        # Python dependencies
├── README.md               # Setup and usage instructions
└── sitemapwatch.db          # SQLite database (auto-created at runtime)
```

---

## 11. Dependencies

```
flask>=3.0
requests>=2.31
lxml>=5.0
apscheduler>=3.10
```

---

## 12. Out of Scope (Future Features)

These are explicitly **not** part of the MVP but are planned for future iterations:

- **Email notifications** when changes are detected
- **Slack/webhook notifications**
- **AI-powered analysis** of detected changes (e.g., categorize new URLs as product/pricing/blog)
- **Pricing page monitoring** (separate from sitemap — monitor `/pricing` page content)
- **User accounts and authentication**
- **Hosted/cloud deployment** with multi-tenancy
- **Export** (CSV/JSON export of change history)
- **URL categorization** (auto-tag URLs by type: product, blog, docs, etc.)
- **Comparison view** across competitors (side-by-side timeline)

---

## 13. Success Criteria

The MVP is complete when:

1. A user can enter a website URL and click "Track."
2. The app discovers and parses the site's sitemap.
3. The initial snapshot is stored and the page count is displayed.
4. The background scheduler re-checks every 6 hours.
5. New and removed URLs are detected and displayed in the change history.
6. The user can manually trigger a "Check Now."
7. The user can remove a tracked site.
8. The app handles errors gracefully (no sitemap, network issues, etc.).
9. The entire app runs with a single command: `python app.py`.

---

## 14. Recommended Defaults Summary

These are the defaults chosen for all ambiguous decisions:

| Decision                  | Default                                                |
|---------------------------|--------------------------------------------------------|
| Tech stack                | Python/Flask + SQLite + Jinja2 templates               |
| Sitemap discovery         | Full recursive (robots.txt + common paths + index follow) |
| What counts as a change   | Both added AND removed URLs                            |
| Check frequency           | Every 6 hours                                          |
| Monitoring mechanism      | Background scheduler (APScheduler) + manual "Check Now"|
| Server model              | Always-on (single process)                             |
| Users                     | Single user, no auth                                   |
| Change display            | Chronological feed with added (green) / removed (red)  |
| History                   | Full history retained, timeline view                   |
| Dashboard                 | Simple table of all tracked sites                      |
| Design                    | Minimal, clean, light theme, monospace URLs             |
| Notifications             | Web UI only (no email/push for MVP)                    |
| Error handling             | Graceful — mark as error, show message, retry next cycle|
