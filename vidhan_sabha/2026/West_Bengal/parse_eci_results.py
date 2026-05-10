#!/usr/bin/env python3
"""
Parse ECI results CSV and extract constituency-wise candidate vote information.
"""

import csv
import json
import re
from pathlib import Path

def clean_text(text):
    """Remove extra whitespace and clean up text."""
    if not text:
        return ""
    # Remove the 'i Party Wise State Trends...' noise
    text = re.sub(r'i Party Wise State Trends.*$', '', text)
    return text.strip()

def is_candidate_name(text):
    """Check if text looks like a candidate name (uppercase words)."""
    if not text or len(text) < 3:
        return False
    # Candidate names are typically uppercase with spaces
    return text.isupper() and len(text.split()) >= 2

def parse_eci_results(csv_file):
    """
    Parse ECI results CSV and extract meaningful constituency data.
    Returns a list of constituencies with their candidates.
    """
    results = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    for row_idx, row in enumerate(all_rows):
        if len(row) < 8:
            continue

        # Skip metadata and noise rows
        if not row[0] or 'source' in row[0].lower() or 'Status Known' in row[0]:
            continue

        # Look for constituency data: should have URL, name, number
        if 'http' not in row[0]:
            continue

        try:
            constituency_name = row[1].strip() if len(row) > 1 else ""
            constituency_no = row[2].strip() if len(row) > 2 else ""

            # Validate this is a constituency row
            if not constituency_name or 'Constituency' in constituency_name:
                continue

            if not constituency_no or not constituency_no.isdigit():
                continue

            # Extract candidate data
            leading_candidate = clean_text(row[3]) if len(row) > 3 else ""
            leading_party = clean_text(row[4]) if len(row) > 4 else ""

            trailing_candidate = ""
            trailing_party = ""

            # Find trailing candidate by looking for uppercase name pattern
            for j in range(10, min(len(row), 25)):
                text = clean_text(row[j])
                if is_candidate_name(text):
                    trailing_candidate = text
                    if j + 1 < len(row):
                        trailing_party = clean_text(row[j + 1])
                    break

            # Find margin and round/status from the end
            margin = ""
            round_info = ""
            status = ""

            for j in range(len(row) - 1, max(len(row) - 10, 0), -1):
                text = row[j].strip()
                if 'Declared' in text or 'Counting' in text or 'Uncontested' in text:
                    status = text
                elif '/' in text and all(c.isdigit() or c == '/' for c in text):
                    round_info = text
                elif text.isdigit() and len(text) > 2 and not margin:
                    margin = text

            if constituency_name and leading_candidate:
                results.append({
                    'constituency': constituency_name,
                    'constituency_no': constituency_no,
                    'leading_candidate': leading_candidate,
                    'leading_party': leading_party,
                    'trailing_candidate': trailing_candidate,
                    'trailing_party': trailing_party,
                    'margin': margin,
                    'round': round_info,
                    'status': status
                })
        except Exception as e:
            continue

    return results

def save_results(results, output_format='csv'):
    """Save parsed results to file in specified format."""
    if output_format == 'csv':
        output_file = 'eci_results_parsed.csv'
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'constituency', 'constituency_no',
                'leading_candidate', 'leading_party',
                'trailing_candidate', 'trailing_party',
                'margin', 'round', 'status'
            ])
            writer.writeheader()
            writer.writerows(results)

    elif output_format == 'json':
        output_file = 'eci_results_parsed.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_file}")
    return output_file

if __name__ == '__main__':
    csv_file = 'eci_results.csv'

    print("Parsing ECI results CSV...")
    results = parse_eci_results(csv_file)

    print(f"Found {len(results)} constituencies\n")

    # Print first few results
    print("Sample results:")
    for result in results[:5]:
        print(f"\nConstituency: {result['constituency']} (No. {result['constituency_no']})")
        print(f"  Leading: {result['leading_candidate']} ({result['leading_party']})")
        print(f"  Trailing: {result['trailing_candidate']} ({result['trailing_party']})")
        print(f"  Margin: {result['margin']} votes")
        print(f"  Round: {result['round']}")
        print(f"  Status: {result['status']}")

    # Save to both formats
    save_results(results, 'csv')
    save_results(results, 'json')
