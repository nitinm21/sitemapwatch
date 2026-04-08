# SitemapWatch

Monitor competitor websites by tracking changes to their sitemaps. Get early signal on new product launches, pricing changes, partnerships, and more — before they're publicly announced.

## How It Works

Every website publishes a `sitemap.xml` listing all its pages. When companies add new product pages, pricing tiers, or landing pages, those URLs appear in the sitemap **before** any public announcement. SitemapWatch monitors these sitemaps and alerts you to changes.

## Features

- **One-click tracking** — Enter a domain and click "Track"
- **Automatic sitemap discovery** — Checks `robots.txt`, common paths, and follows sitemap indexes
- **Change detection** — Identifies new and removed URLs
- **Background monitoring** — Checks every 6 hours automatically
- **Manual checks** — "Check Now" button for on-demand updates
- **Change history** — Full timeline of all detected changes

## Quick Start

### Prerequisites

- Python 3.11+

### Setup

```bash
# Clone the repo
git clone https://github.com/nitinm21/sitemapwatch.git
cd sitemapwatch

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

The app will be available at **http://localhost:5000**.

### Usage

1. Open http://localhost:5000 in your browser
2. Enter a competitor's website URL (e.g., `stripe.com`)
3. Click **Track**
4. The app discovers the sitemap, parses all URLs, and stores the initial snapshot
5. Come back later to see what's changed — or click **Check Now** for an immediate update

## Project Structure

```
sitemapwatch/
├── app.py              # Flask app — routes, scheduler, entry point
├── database.py         # SQLite database initialization and helpers
├── sitemap.py          # Sitemap discovery, fetching, and parsing
├── monitor.py          # Diff logic — compare snapshots, detect changes
├── templates/
│   ├── base.html       # Base template with layout and styles
│   ├── dashboard.html  # Main dashboard page
│   └── site_detail.html # Per-site change history page
├── static/
│   └── style.css       # Styles
├── requirements.txt    # Python dependencies
├── final_spec.md       # Full product requirements document
└── README.md           # This file
```

## Tech Stack

- **Backend**: Python / Flask
- **Database**: SQLite (zero config, auto-created)
- **Scheduler**: APScheduler (in-process background jobs)
- **Sitemap Parsing**: lxml + requests
- **Frontend**: Server-rendered HTML with Jinja2 templates

## Future Plans

- Email/Slack notifications on changes
- AI-powered analysis of detected changes
- Pricing page content monitoring
- URL categorization (product, blog, docs, etc.)
- Export to CSV/JSON

## License

MIT
