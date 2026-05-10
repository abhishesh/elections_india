# ECI West Bengal 2026 Results - Scraping & Parsing Guide

## Summary Data (✅ Complete)

The initial scrape successfully extracted summary-level results showing the leading and trailing candidates for all 293 constituencies with vote margins.

**Files:**
- `eci_results.csv` - Raw scraped HTML table data
- `eci_results_parsed.csv` - Cleaned summary results (constituency, candidates, margins)
- `eci_results_parsed.json` - Same data in JSON format

**Contains:**
- Constituency name & number
- Leading candidate name & party
- Trailing candidate name & party  
- Vote margin (difference between 1st and 2nd place)
- Counting round info
- Result status

## Detailed Candidate Data (⚠️ Limited by Anti-Bot Protection)

The ECI website (`results.eci.gov.in`) has strong Cloudflare protection that blocks automated scraping attempts. URLs like `https://results.eci.gov.in/ResultAcGenMay2026/Constituency12.htm` return 403 Access Denied errors to non-browser clients.

### Option 1: Manual Browser Export (Recommended)

1. **Visit the ECI website:**
   ```
   https://results.eci.gov.in/ResultAcGenMay2026/statewiseS251.htm
   ```

2. **Click on a constituency** to view detailed results

3. **Save the HTML page:**
   - Right-click → Save Page As
   - Save to a folder like `html_pages/`
   - Naming convention: `constituency_12_ALIPURDUARS.html`

4. **Run the local parser:**
   ```bash
   python3 scrape_constituency_details.py --input eci_results_parsed.csv --local-dir html_pages
   ```

### Option 2: Browser Developer Tools (One-Off Export)

For a single or few constituencies:

1. Open DevTools (F12 → Network tab)
2. Visit the constituency detail page
3. Look for AJAX/XHR requests that fetch the data
4. Copy the response JSON if available
5. Parse using the provided scripts

### Option 3: Use Existing Data

If you only need summary-level analysis (which candidates won/lost, vote margins), the parsed CSV files contain all necessary information:

```bash
# View summary results
head -20 eci_results_parsed.csv

# Analyze results
python3 -c "
import json
with open('eci_results_parsed.json') as f:
    data = json.load(f)
    bjp = sum(1 for r in data if 'Bharatiya Janata' in r['leading_party'])
    aitc = sum(1 for r in data if 'Trinamool' in r['leading_party'])
    print(f'BJP wins: {bjp}, AITC wins: {aitc}')
"
```

## Scraping Scripts

### `scrape_eci_results.py` - Summary Scraper
Fetches the main results page with all 293 constituencies in a summary table.

```bash
uv run scrape_eci_results.py  # Outputs to eci_results.csv
```

### `parse_eci_results.py` - Parser & Cleaner  
Converts raw CSV to clean constituency-candidate format.

```bash
python3 parse_eci_results.py  # Outputs JSON and CSV
```

### `scrape_constituency_details.py` - Detail Scraper
Attempts to fetch individual constituency pages (limited by anti-bot measures).

```bash
# From local HTML files
python3 scrape_constituency_details.py \
  --input eci_results_parsed.csv \
  --local-dir html_pages \
  --output eci_detailed.json

# Command-line options
python3 scrape_constituency_details.py --help
```

## Data Structure

### Summary CSV Format
```
constituency,constituency_no,leading_candidate,leading_party,trailing_candidate,trailing_party,margin,round,status
ALIPURDUARS,12,PARITOSH DAS,Bharatiya Janata Party,SUMAN KANJILAL,All India Trinamool Congress,70420,24/24,Result Declared
```

### Detailed JSON Format (if scraped)
```json
{
  "constituency_no": "12",
  "constituency_name": "ALIPURDUARS",
  "status": "success",
  "candidates": [
    {
      "candidate_name": "PARITOSH DAS",
      "party": "Bharatiya Janata Party",
      "votes": 123456
    },
    {
      "candidate_name": "SUMAN KANJILAL",
      "party": "All India Trinamool Congress",
      "votes": 53036
    }
  ]
}
```

## Anti-Bot Protection Notes

The ECI website uses Cloudflare WAF (Web Application Firewall) which:
- ✅ Allows normal browser traffic
- ❌ Blocks requests from standard HTTP clients (urllib, requests)
- ⚠️ Sometimes blocks Selenium/headless browsers

If you encounter 403 errors when scraping, try:
1. Adding more realistic delays between requests
2. Rotating user agents
3. Using a residential VPN
4. Falling back to manual browser export

## Alternative Data Sources

If you need complete candidate vote data, consider:
- Official ECI downloadable reports (if available)
- State Election Commission of West Bengal
- News media APIs (if available)
- Wikipedia election articles
