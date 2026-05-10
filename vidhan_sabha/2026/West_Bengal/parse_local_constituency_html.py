#!/usr/bin/env python3
"""
Parse locally saved ECI constituency HTML files.

When you manually save constituency detail pages from the browser,
this script extracts all candidate names and vote counts.

Usage:
    1. Visit: https://results.eci.gov.in/ResultAcGenMay2026/statewiseS251.htm
    2. Click a constituency to view detailed results
    3. Right-click → Save Page As → Save to 'html_pages/' folder
    4. Run: python3 parse_local_constituency_html.py

Files will be saved as:
    - eci_detailed.csv
    - eci_detailed.json
"""

import os
import json
import csv
from pathlib import Path
from html.parser import HTMLParser


class CandidateTableParser(HTMLParser):
    """Extract candidate data from ECI HTML tables."""

    def __init__(self):
        super().__init__()
        self.candidates = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.cell_buffer = []
        self.table_count = 0
        self.row_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
            self.table_count += 1
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.row_count += 1
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.cell_buffer = []

    def handle_data(self, data):
        if self.in_cell:
            text = data.strip()
            if text:
                self.cell_buffer.append(text)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_row:
            cell_text = " ".join(self.cell_buffer)
            self.current_row.append(cell_text)
            self.in_cell = False
        elif tag == "tr" and self.in_table:
            if self.current_row:
                self._process_row(self.current_row)
            self.in_row = False
        elif tag == "table" and self.in_table:
            self.in_table = False

    def _process_row(self, row):
        """Extract candidate data from a table row."""
        if len(row) < 3:
            return

        # Skip header rows
        headers = ["candidate", "party", "votes", "electors", "percentage", "sl", "no."]
        first_cell = row[0].lower()
        if any(h in first_cell for h in headers):
            return

        # Skip total/summary rows
        if any(word in first_cell.lower() for word in ["total", "valid", "invalid", "polled", "rejected"]):
            return

        # Try to extract candidate data
        try:
            # Common pattern: Index | Name | Party | Votes | ...
            if len(row) >= 4:
                # Get candidate name and party
                candidate_name = None
                party = None
                votes = None

                # Try different column arrangements
                if row[0].isdigit() or row[0].replace(".", "").isdigit():
                    # Format: Index, Name, Party, Votes, ...
                    candidate_name = row[1] if len(row) > 1 else None
                    party = row[2] if len(row) > 2 else None
                    votes_str = row[3] if len(row) > 3 else None
                else:
                    # Format: Name, Party, Votes, ...
                    candidate_name = row[0]
                    party = row[1] if len(row) > 1 else None
                    votes_str = row[2] if len(row) > 2 else None

                # Validate and parse votes
                if candidate_name and votes_str:
                    # Clean up votes string and convert to int
                    votes_str = votes_str.replace(",", "").strip()
                    try:
                        votes = int(votes_str)
                        if candidate_name and len(candidate_name) > 2:
                            self.candidates.append({
                                "candidate": candidate_name,
                                "party": party or "",
                                "votes": votes
                            })
                    except ValueError:
                        pass
        except Exception as e:
            pass

    def get_candidates(self):
        """Return extracted candidates."""
        return self.candidates


def parse_html_file(filepath):
    """Parse a single HTML file and extract candidates."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()

        parser = CandidateTableParser()
        parser.feed(html)

        candidates = parser.get_candidates()
        return {
            "filepath": str(filepath),
            "candidates": candidates,
            "success": len(candidates) > 0
        }
    except Exception as e:
        return {
            "filepath": str(filepath),
            "candidates": [],
            "success": False,
            "error": str(e)
        }


def extract_constituency_info(filepath):
    """Try to extract constituency name from filename."""
    # Try to match: constituency_{number}_{name}.html
    filename = Path(filepath).stem
    parts = filename.split('_')

    if len(parts) >= 3 and parts[0].lower() == 'constituency':
        try:
            const_no = parts[1]
            const_name = '_'.join(parts[2:]).replace('_', ' ')
            return const_no, const_name
        except:
            pass

    # Fallback: just use filename
    return None, filename


def main():
    html_dir = Path("html_pages")

    if not html_dir.exists():
        print(f"HTML directory not found: {html_dir}")
        print("\nTo use this parser:")
        print("1. Visit: https://results.eci.gov.in/ResultAcGenMay2026/statewiseS251.htm")
        print("2. Click on a constituency name")
        print("3. Right-click → Save Page As")
        print("4. Create a folder 'html_pages' and save pages there")
        print("5. Run this script again")
        return

    html_files = list(html_dir.glob("*.html")) + list(html_dir.glob("*.htm"))

    if not html_files:
        print(f"No HTML files found in {html_dir}")
        return

    print(f"Found {len(html_files)} HTML files\n")

    # Parse all files
    all_results = []
    successful = 0

    for idx, filepath in enumerate(html_files, 1):
        print(f"[{idx}/{len(html_files)}] Parsing {filepath.name}...", end=" ")

        result = parse_html_file(filepath)
        const_no, const_name = extract_constituency_info(filepath)

        if result["success"]:
            successful += 1
            print(f"✓ Found {len(result['candidates'])} candidates")
            all_results.append({
                "constituency_no": const_no,
                "constituency_name": const_name,
                "candidates": result["candidates"]
            })
        else:
            print("✗ No candidates found")

    print(f"\nSuccessfully parsed: {successful}/{len(html_files)} files")
    print(f"Total candidates found: {sum(len(r['candidates']) for r in all_results)}\n")

    # Save results
    # JSON format
    json_file = "eci_detailed.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"Saved to {json_file}")

    # CSV format
    csv_file = "eci_detailed.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Constituency No",
            "Constituency Name",
            "Candidate Name",
            "Party",
            "Votes"
        ])

        for result in all_results:
            const_no = result.get("constituency_no", "")
            const_name = result.get("constituency_name", "")

            for cand in result.get("candidates", []):
                writer.writerow([
                    const_no,
                    const_name,
                    cand.get("candidate", ""),
                    cand.get("party", ""),
                    cand.get("votes", "")
                ])

    print(f"Saved to {csv_file}")

    # Show samples
    if all_results:
        print("\nSample results:")
        for result in all_results[:2]:
            print(f"\n{result['constituency_name']} ({result['constituency_no']}):")
            for cand in result['candidates'][:3]:
                votes = f"{cand['votes']:,}" if isinstance(cand['votes'], int) else cand['votes']
                print(f"  {cand['candidate']} ({cand['party']}) - {votes} votes")


if __name__ == "__main__":
    main()
