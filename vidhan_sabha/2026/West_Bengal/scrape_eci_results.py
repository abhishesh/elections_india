"""
ECI Election Results Scraper for West Bengal Vidhan Sabha 2026.

Fetches HTML from ECI result pages and converts table data to CSV.

Uses Selenium (browser automation) by default to handle JavaScript and
anti-bot measures. Falls back to requests + BeautifulSoup4, then stdlib
urllib + HTMLParser if dependencies aren't available.

Usage:
    uv run scrape_eci_results.py

Local-file fallback:
    uv run scrape_eci_results.py --local-dir html_pages
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.request
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service

    USE_SELENIUM = True
except ImportError:
    USE_SELENIUM = False

try:
    import requests
    from bs4 import BeautifulSoup

    USE_BS4 = True
except ImportError:
    requests = None
    BeautifulSoup = None
    USE_BS4 = False


BASE_URL = "https://results.eci.gov.in/ResultAcGenMay2026"
REFERER = f"{BASE_URL}/index.htm"
STATE_CODE = "S25"
DEFAULT_OUTPUT_CSV = Path(__file__).resolve().parent / "eci_results.csv"

URLS = [f"{BASE_URL}/statewise{STATE_CODE}{i}.htm" for i in range(1, 16)]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": REFERER,
    "Connection": "keep-alive",
}


def fetch_html_selenium(url: str, retries: int) -> str | None:
    """Fetch HTML using Selenium to handle JavaScript and anti-bot measures."""
    for attempt in range(1, retries + 1):
        driver = None
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={HEADERS['User-Agent']}")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(url)

            WebDriverWait(driver, 30).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            html = driver.page_source
            return html
        except Exception as exc:
            print(f"  [attempt {attempt}/{retries}] {exc}")
            if attempt < retries:
                time.sleep(2)
        finally:
            if driver:
                driver.quit()
    return None


def fetch_html_requests(session: requests.Session, url: str, retries: int) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception as exc:
            print(f"  [attempt {attempt}/{retries}] {exc}")
            if attempt < retries:
                time.sleep(2)
    return None


def fetch_html_stdlib(url: str, retries: int) -> str | None:
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                for encoding in ("utf-8", "latin-1", "windows-1252"):
                    try:
                        return raw.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("latin-1", errors="replace")
        except Exception as exc:
            print(f"  [attempt {attempt}/{retries}] {exc}")
            if attempt < retries:
                time.sleep(2)
    return None


def parse_tables_bs4(html: str) -> list[list[list[str]]]:
    """Return tables as list-of-tables; each table is list-of-rows."""
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for row in table.find_all("tr"):
            cells = [
                cell.get_text(separator=" ", strip=True)
                for cell in row.find_all(["td", "th"])
            ]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cur_tbl: list[list[str]] = []
        self._cur_row: list[str] = []
        self._buf = StringIO()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._cur_tbl = []
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._cur_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._buf = StringIO()

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._cur_tbl:
                self.tables.append(self._cur_tbl)
            self._in_table = False
        elif tag == "tr" and self._in_table:
            if self._cur_row:
                self._cur_tbl.append(self._cur_row)
            self._in_row = False
        elif tag in ("td", "th") and self._in_row:
            self._cur_row.append(" ".join(self._buf.getvalue().split()))
            self._in_cell = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._buf.write(data)

    def handle_entityref(self, name: str) -> None:
        if self._in_cell:
            self._buf.write(
                {"amp": "&", "nbsp": " ", "lt": "<", "gt": ">", "quot": '"'}.get(
                    name, ""
                )
            )

    def handle_charref(self, name: str) -> None:
        if self._in_cell:
            try:
                codepoint = int(name[1:], 16) if name.startswith("x") else int(name)
                self._buf.write(chr(codepoint))
            except ValueError:
                pass


def parse_tables_stdlib(html: str) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.tables


def extract_best_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    """Return the table with the most rows, which is usually the results table."""
    if not tables:
        return None
    return max(tables, key=len)


def normalize_rows(rows: list[list[str]], max_cols: int) -> list[list[str]]:
    return [(row + [""] * max_cols)[:max_cols] for row in rows]


def parse_html(html: str) -> list[list[str]] | None:
    tables = parse_tables_bs4(html) if USE_BS4 else parse_tables_stdlib(html)
    return extract_best_table(tables)


def write_rows(rows: list[list[str]], output_csv: Path) -> None:
    max_cols = max(len(row) for row in rows)
    normalized = normalize_rows(rows, max_cols)
    header = ["source"] + [f"col_{i}" for i in range(max_cols - 1)]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(normalized)

    print(f"\nDone. {len(normalized)} rows written to '{output_csv}'")


def scrape_remote(output_csv: Path, retries: int, delay: float) -> int:
    method = "Selenium"
    if USE_SELENIUM:
        print("Using Selenium (browser automation)\n")
    elif USE_BS4:
        print("Using requests + BeautifulSoup4\n")
        method = "requests + BeautifulSoup4"
    else:
        print("Using stdlib urllib + HTMLParser\n")
        method = "stdlib urllib + HTMLParser"

    session = None
    if not USE_SELENIUM and USE_BS4:
        session = requests.Session()
        try:
            session.get(
                REFERER,
                headers={**HEADERS, "Referer": "https://results.eci.gov.in/"},
                timeout=15,
            )
            print("Warm-up request to index page done.\n")
            time.sleep(1)
        except Exception as exc:
            print(f"Warm-up failed (non-fatal): {exc}\n")

    all_rows: list[list[str]] = []
    for idx, url in enumerate(URLS, 1):
        page_id = url.split(f"statewise{STATE_CODE}")[-1].replace(".htm", "")
        print(f"[{idx:02d}/{len(URLS)}] Fetching page {page_id}: {url}")

        if USE_SELENIUM:
            html = fetch_html_selenium(url, retries)
        elif session:
            html = fetch_html_requests(session, url, retries)
        else:
            html = fetch_html_stdlib(url, retries)

        if html is None:
            print("  Failed. Skipping.\n")
            continue

        tables = parse_tables_bs4(html) if USE_BS4 else parse_tables_stdlib(html)
        best = extract_best_table(tables)
        if best is None:
            print("  No tables found on page.\n")
            continue

        col_count = max(len(row) for row in best)
        print(
            f"  {len(tables)} table(s) found; using largest "
            f"({len(best)} rows, {col_count} cols)."
        )
        all_rows.extend([[url] + row for row in best])
        time.sleep(delay)

    if not all_rows:
        print("\nNo data collected.")
        if USE_SELENIUM:
            print(
                """
Selenium failed to retrieve data. Possible causes:
  1. ChromeDriver not available or Chrome not installed
  2. Network issues or site blocking.

Fallback option:
  - Save pages manually in your browser into an html_pages directory, then run:
      python scrape_eci_results.py --local-dir html_pages
"""
            )
        else:
            print(
                """
results.eci.gov.in may be blocking automated requests.

Options:
  1. Save pages manually in your browser into an html_pages directory, then run:
       python scrape_eci_results.py --local-dir html_pages
  2. Install Selenium: uv add selenium webdriver-manager
"""
            )
        return 1

    write_rows(all_rows, output_csv)
    return 0


def parse_local(html_dir: Path, output_csv: Path) -> int:
    if not html_dir.exists():
        print(f"Local HTML directory not found: {html_dir}")
        return 1

    all_rows: list[list[str]] = []
    for path in sorted(html_dir.glob("*.htm")):
        html = path.read_text(encoding="latin-1", errors="replace")
        best = parse_html(html)
        if best:
            all_rows.extend([[str(path)] + row for row in best])

    if not all_rows:
        print(f"No table rows found in {html_dir}")
        return 1

    write_rows(all_rows, output_csv)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape or parse West Bengal Vidhan Sabha 2026 ECI result tables."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"CSV output path. Defaults to {DEFAULT_OUTPUT_CSV}.",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        help=(
            "Parse locally saved .htm files instead of fetching from "
            "results.eci.gov.in."
        ),
    )
    parser.add_argument("--retries", type=int, default=3, help="Fetch retries per URL.")
    parser.add_argument("--delay", type=float, default=0.75, help="Delay between requests.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.local_dir:
        return parse_local(args.local_dir, args.output)
    return scrape_remote(args.output, args.retries, args.delay)


if __name__ == "__main__":
    sys.exit(main())
