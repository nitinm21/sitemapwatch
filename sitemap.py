"""Sitemap discovery, fetching, and parsing logic for SitemapWatch."""

import re
from urllib.parse import urljoin, urlparse

import requests
from lxml import etree

# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 15

# Common sitemap paths to try
COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
]

# XML namespaces used in sitemaps
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# User-Agent header to identify ourselves
HEADERS = {
    "User-Agent": "SitemapWatch/1.0 (sitemap monitor)",
}


def normalize_domain(raw_input: str) -> str:
    """Normalize user input to a clean domain string.

    Accepts formats like:
      - competitor.com
      - https://competitor.com
      - https://competitor.com/some/path
      - competitor.com/sitemap.xml

    Returns: 'competitor.com' (just the domain, no scheme or path).
    """
    raw_input = raw_input.strip()

    # Add scheme if missing so urlparse works correctly
    if not raw_input.startswith(("http://", "https://")):
        raw_input = "https://" + raw_input

    parsed = urlparse(raw_input)
    domain = parsed.netloc or parsed.path.split("/")[0]

    # Strip www. prefix for consistency
    if domain.startswith("www."):
        domain = domain[4:]

    return domain.lower()


def base_url(domain: str) -> str:
    """Return the HTTPS base URL for a domain."""
    return f"https://{domain}"


def discover_sitemaps(domain: str) -> list[str]:
    """Discover all sitemap URLs for a domain.

    Strategy:
    1. Check /robots.txt for Sitemap: directives
    2. Try common sitemap paths
    3. Follow sitemap index files recursively

    Returns a list of leaf sitemap URLs (not indexes).
    """
    root = base_url(domain)
    candidate_urls: set[str] = set()

    # Step 1: Check robots.txt
    try:
        resp = requests.get(
            urljoin(root, "/robots.txt"),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                match = re.match(r"^\s*Sitemap:\s*(.+)", line, re.IGNORECASE)
                if match:
                    candidate_urls.add(match.group(1).strip())
    except requests.RequestException:
        pass  # robots.txt not available — continue with defaults

    # Step 2: Add common paths
    for path in COMMON_SITEMAP_PATHS:
        candidate_urls.add(urljoin(root, path))

    # Step 3: Resolve candidates — follow sitemap indexes recursively
    leaf_sitemaps: list[str] = []
    visited: set[str] = set()

    def resolve(url: str) -> None:
        if url in visited:
            return
        visited.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return

            content_type = resp.headers.get("Content-Type", "")
            # Some servers return text/html for missing pages
            if "html" in content_type and "xml" not in content_type:
                return

            root_el = etree.fromstring(resp.content)
            tag = _strip_ns(root_el.tag)

            if tag == "sitemapindex":
                # This is a sitemap index — follow child sitemaps
                for sitemap_el in root_el.findall("sm:sitemap/sm:loc", SITEMAP_NS):
                    child_url = sitemap_el.text.strip() if sitemap_el.text else None
                    if child_url:
                        resolve(child_url)
            elif tag == "urlset":
                # This is a leaf sitemap
                leaf_sitemaps.append(url)
        except (requests.RequestException, etree.XMLSyntaxError):
            pass  # Skip unreachable or malformed sitemaps

    for url in candidate_urls:
        resolve(url)

    return leaf_sitemaps


def fetch_urls_from_sitemaps(sitemap_urls: list[str]) -> list[str]:
    """Fetch and parse all URLs from a list of sitemap URLs.

    Returns a sorted, deduplicated list of page URLs.
    """
    all_urls: set[str] = set()

    for sitemap_url in sitemap_urls:
        try:
            resp = requests.get(
                sitemap_url, headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
            if resp.status_code != 200:
                continue

            root_el = etree.fromstring(resp.content)
            tag = _strip_ns(root_el.tag)

            if tag == "urlset":
                for loc_el in root_el.findall("sm:url/sm:loc", SITEMAP_NS):
                    url = loc_el.text.strip() if loc_el.text else None
                    if url:
                        all_urls.add(url)
            elif tag == "sitemapindex":
                # Shouldn't happen if discover_sitemaps resolved properly,
                # but handle gracefully by recursing
                child_urls = []
                for sitemap_el in root_el.findall("sm:sitemap/sm:loc", SITEMAP_NS):
                    child_url = sitemap_el.text.strip() if sitemap_el.text else None
                    if child_url:
                        child_urls.append(child_url)
                if child_urls:
                    all_urls.update(fetch_urls_from_sitemaps(child_urls))
        except (requests.RequestException, etree.XMLSyntaxError):
            continue  # Skip this sitemap, try others

    return sorted(all_urls)


def _strip_ns(tag: str) -> str:
    """Strip the XML namespace from a tag name.

    '{http://...}urlset' -> 'urlset'
    """
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag
