#!/usr/bin/env python3
"""Find correct URL patterns for constituency detail pages."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
import re

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
        return html, driver
    except Exception as e:
        print(f"Error: {e}")
        if driver:
            driver.quit()
        return None, None

# Fetch main results page
url = "https://results.eci.gov.in/ResultAcGenMay2026/statewiseS251.htm"
print(f"Fetching main page: {url}\n")
html, driver = fetch_page(url)

if html:
    with open("main_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved main page ({len(html)} bytes)")

    # Look for links to constituency pages
    print("\nSearching for constituency links...")
    links = re.findall(r'href=["\']([^"\']*)["\']', html)
    constituency_links = [l for l in links if any(x in l.lower() for x in ['constituency', 'constquery', 'const', 'ac='])]

    print(f"Found {len(constituency_links)} potential constituency links:")
    for link in list(set(constituency_links))[:10]:
        print(f"  {link}")

    # Look for data attributes
    data_attrs = re.findall(r'data-\w+="[^"]*"', html)
    print(f"\nData attributes found: {len(set(data_attrs))}")
    for attr in list(set(data_attrs))[:5]:
        print(f"  {attr}")

    # Look for onclick handlers
    onclick_calls = re.findall(r'onclick=["\']([^"\']+)["\']', html)
    print(f"\nOnclick handlers found: {len(set(onclick_calls))}")
    for call in list(set(onclick_calls))[:5]:
        print(f"  {call}")

    # Check if page uses JavaScript for navigation
    if "fetch(" in html or "XMLHttpRequest" in html or "ajax" in html.lower():
        print("\nPage appears to use AJAX/JavaScript for loading data")

    if driver:
        # Try to find a link to first constituency
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            print(f"\nTotal <a> tags found: {len(links)}")

            for link in links[:20]:
                href = link.get_attribute("href")
                text = link.text.strip()
                if href and text and len(text) > 2:
                    print(f"  {text}: {href}")
        except Exception as e:
            print(f"Error finding links: {e}")

        driver.quit()
