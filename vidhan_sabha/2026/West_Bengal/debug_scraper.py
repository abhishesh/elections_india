#!/usr/bin/env python3
"""Debug scraper - fetch and save HTML for inspection."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time

def fetch_page(url):
    driver = None
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)

        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)

        html = driver.page_source
        return html
    finally:
        if driver:
            driver.quit()

# Test first constituency
url = "https://results.eci.gov.in/ResultAcGenMay2026/Constitutency12.htm"
print(f"Fetching: {url}")
html = fetch_page(url)

# Save for inspection
with open("debug_output.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Saved to debug_output.html ({len(html)} bytes)")

# Check what tables exist
from html.parser import HTMLParser

class TableFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = 0
        self.in_table = False
        self.rows = 0
        self.in_row = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
            self.tables += 1
            print(f"Found table {self.tables}")
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.rows += 1

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
            print(f"  Total rows in table: {self.rows}")
            self.rows = 0

parser = TableFinder()
parser.feed(html)
print(f"\nTotal tables found: {parser.tables}")

# Check for specific content
if "candidate" in html.lower():
    print("Found 'candidate' in HTML")
if "Candidate" in html:
    print("Found 'Candidate' in HTML")
if "votes" in html.lower():
    print("Found 'votes' in HTML")
