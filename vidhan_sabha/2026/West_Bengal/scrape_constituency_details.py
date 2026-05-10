#!/usr/bin/env python3
"""
Scrape detailed constituency results from ECI website.

Fetches individual constituency pages to get vote counts for all candidates.
Uses Selenium for JavaScript rendering, falls back to requests/urllib.

Usage:
    python3 scrape_constituency_details.py
    python3 scrape_constituency_details.py --output results_detailed.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from html.parser import HTMLParser
from io import StringIO

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
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


def fetch_html_selenium(url: str, retries: int = 3) -> str | None:
    """Fetch HTML using Selenium."""
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

            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1)

            return driver.page_source
        except Exception as exc:
            print(f"    [attempt {attempt}/{retries}] {exc}")
            if attempt < retries:
                time.sleep(2)
        finally:
            if driver:
                driver.quit()
    return None


def fetch_html_requests(url: str, retries: int = 3) -> str | None:
    """Fetch HTML using requests."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            print(f"    [attempt {attempt}/{retries}] {exc}")
            if attempt < retries:
                time.sleep(2)
    return None


def parse_html_bs4(html: str) -> list[list[str]] | None:
    """Extract table from HTML using BeautifulSoup."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        # Find the largest table (usually the candidate results table)
        best_table = None
        max_rows = 0
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) > max_rows:
                max_rows = len(rows)
                best_table = table

        if not best_table:
            return None

        result_rows = []
        for row in best_table.find_all("tr"):
            cells = [cell.get_text(separator=" ", strip=True) for cell in row.find_all(["td", "th"])]
            if cells:
                result_rows.append(cells)

        return result_rows if result_rows else None
    except Exception as e:
        print(f"    BS4 parsing error: {e}")
        return None


class TableParser(HTMLParser):
    """Parse HTML tables without BeautifulSoup."""
    def __init__(self):
        super().__init__()
        self.tables = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cur_table = []
        self._cur_row = []
        self._buf = StringIO()

    def handle_starttag(self, tag: str, attrs):
        if tag == "table":
            self._in_table = True
            self._cur_table = []
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._cur_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._buf = StringIO()

    def handle_endtag(self, tag: str):
        if tag == "table" and self._in_table:
            if self._cur_table:
                self.tables.append(self._cur_table)
            self._in_table = False
        elif tag == "tr" and self._in_table:
            if self._cur_row:
                self._cur_table.append(self._cur_row)
            self._in_row = False
        elif tag in ("td", "th") and self._in_row:
            self._cur_row.append(" ".join(self._buf.getvalue().split()))
            self._in_cell = False

    def handle_data(self, data: str):
        if self._in_cell:
            self._buf.write(data)


def parse_html_stdlib(html: str) -> list[list[str]] | None:
    """Extract table from HTML using stdlib HTMLParser."""
    try:
        parser = TableParser()
        parser.feed(html)
        if parser.tables:
            # Return the largest table
            return max(parser.tables, key=len)
    except Exception as e:
        print(f"    Stdlib parsing error: {e}")
    return None


def extract_candidates_from_table(rows: list[list[str]]) -> list[dict]:
    """Extract candidate data from table rows."""
    candidates = []

    # Skip header rows and find where candidate data starts
    for row in rows:
        if not row or len(row) < 3:
            continue

        # Skip header/summary rows
        if any(skip in str(row[0]).lower() for skip in ["candidate", "total", "valid", "invalid"]):
            continue

        # Try to find candidate name and votes
        # Typical row: [Sl, Candidate Name, Party, Votes, ...]
        try:
            # Row format is usually: index, name, party, votes, percentage, status
            if len(row) >= 3:
                candidate_name = row[1].strip() if len(row) > 1 else ""
                party = row[2].strip() if len(row) > 2 else ""
                votes_str = row[3].strip() if len(row) > 3 else ""

                # Validate candidate name (should be meaningful)
                if candidate_name and len(candidate_name) > 2:
                    try:
                        votes = int(votes_str.replace(",", "")) if votes_str else 0
                        candidates.append({
                            "candidate_name": candidate_name,
                            "party": party,
                            "votes": votes
                        })
                    except ValueError:
                        pass
        except Exception:
            pass

    return candidates


def scrape_constituency(constituency_no: str, constituency_name: str, retries: int = 3) -> dict:
    """Scrape detailed results for a single constituency."""
    # Try different URL patterns
    url_patterns = [
        f"{BASE_URL}/Constitutency{constituency_no}.htm",
        f"{BASE_URL}/Constituency{constituency_no}.htm",
        f"{BASE_URL}/constituency{constituency_no}.htm",
        f"{BASE_URL}/constquery.htm?ac={constituency_no}",
    ]

    html = None
    used_url = None

    for url in url_patterns:
        print(f"  Trying: {url}")
        # Always try Selenium first for better JS rendering and anti-bot bypass
        if USE_SELENIUM:
            html = fetch_html_selenium(url, retries)
        elif USE_BS4:
            html = fetch_html_requests(url, retries)
        else:
            print(f"    Selenium not available. Please install: pip install selenium webdriver-manager")

        if html:
            used_url = url
            break

    if not html:
        print(f"  Failed to fetch HTML")
        return {
            "constituency_no": constituency_no,
            "constituency_name": constituency_name,
            "candidates": [],
            "status": "fetch_failed"
        }

    # Parse HTML
    if USE_BS4:
        rows = parse_html_bs4(html)
    else:
        rows = parse_html_stdlib(html)

    if not rows:
        print(f"  No table found")
        return {
            "constituency_no": constituency_no,
            "constituency_name": constituency_name,
            "candidates": [],
            "status": "parse_failed"
        }

    candidates = extract_candidates_from_table(rows)
    print(f"  Found {len(candidates)} candidates")

    return {
        "constituency_no": constituency_no,
        "constituency_name": constituency_name,
        "candidates": candidates,
        "status": "success",
        "url": used_url
    }


def load_parsed_results(csv_file: str = "eci_results_parsed.csv") -> list[dict]:
    """Load parsed summary results."""
    results = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            results = list(reader)
    except FileNotFoundError:
        print(f"Error: {csv_file} not found. Run parse_eci_results.py first.")
        sys.exit(1)
    return results


def save_results(data: list[dict], output_file: str, format: str = 'json'):
    """Save detailed results to file."""
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    if format == 'json':
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {output_file}")
    elif format == 'csv':
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Constituency No',
                'Constituency Name',
                'Candidate Name',
                'Party',
                'Votes',
                'Status'
            ])

            for item in data:
                const_no = item.get('constituency_no', '')
                const_name = item.get('constituency_name', '')
                status = item.get('status', '')

                if item.get('candidates'):
                    for cand in item['candidates']:
                        writer.writerow([
                            const_no,
                            const_name,
                            cand.get('candidate_name', ''),
                            cand.get('party', ''),
                            cand.get('votes', ''),
                            status
                        ])
                else:
                    writer.writerow([const_no, const_name, '', '', '', status])

        print(f"\nResults saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Scrape detailed constituency results from ECI website")
    parser.add_argument('--output', default='eci_constituency_details.json', help='Output file path')
    parser.add_argument('--csv', action='store_true', help='Save as CSV instead of JSON')
    parser.add_argument('--input', default='eci_results_parsed.csv', help='Input parsed results CSV')
    parser.add_argument('--limit', type=int, help='Limit scraping to first N constituencies')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between requests (seconds)')
    parser.add_argument('--retries', type=int, default=3, help='Retries per URL')

    args = parser.parse_args()

    if USE_SELENIUM:
        print("Using Selenium (browser automation)\n")
    elif USE_BS4:
        print("Using requests + BeautifulSoup4\n")
    else:
        print("Using stdlib urllib + HTMLParser\n")

    # Load constituency list
    parsed_results = load_parsed_results(args.input)
    print(f"Loaded {len(parsed_results)} constituencies\n")

    if args.limit:
        parsed_results = parsed_results[:args.limit]
        print(f"Limiting to {len(parsed_results)} constituencies\n")

    # Scrape details
    all_results = []
    for idx, result in enumerate(parsed_results, 1):
        const_no = result['constituency_no']
        const_name = result['constituency']

        print(f"[{idx}/{len(parsed_results)}] {const_name} (No. {const_no})")
        detail = scrape_constituency(const_no, const_name, args.retries)
        all_results.append(detail)

        if idx < len(parsed_results):
            time.sleep(args.delay)

    # Save results
    output_file = args.output
    if args.csv:
        output_file = output_file.replace('.json', '.csv')
        save_results(all_results, output_file, 'csv')
    else:
        save_results(all_results, output_file, 'json')

    # Print summary
    successful = sum(1 for r in all_results if r.get('status') == 'success')
    total_candidates = sum(len(r.get('candidates', [])) for r in all_results)
    print(f"\nSummary:")
    print(f"  Successful: {successful}/{len(all_results)}")
    print(f"  Total candidates: {total_candidates}")


if __name__ == '__main__':
    main()
