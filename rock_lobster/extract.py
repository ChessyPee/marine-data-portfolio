"""
Step 1: EXTRACT
Scrapes the "Landed Catch by Month" tables from the Fishing Tasmania Rock
Lobster Catch Updates page. This page publishes one HTML table per quota
year (2007/08 through the current season), each with its own quirks:
different column sets, kg vs tonnes across different eras, stray unicode
whitespace characters, and the occasional typo (e.g. "393..07").

We deliberately do NOT try to fix any of that here -- extract.py's only job
is to pull every table off the page faithfully into one raw, long-format
CSV. All interpretation and cleaning happens in clean.py. Keeping these
steps separate means you always have an untouched copy of what the source
actually said, which matters if anyone ever asks "where did this number
come from".

Run:
    python extract.py
Output:
    data/raw/rock_lobster_catch_raw.csv
"""

import csv
import datetime as dt
import re
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = (
    "https://fishing.tas.gov.au/commercial-fishing/commercial-fisheries/"
    "rock-lobster-fishery/rock-lobster-catch-updates"
)
OUT_PATH = Path(__file__).parent / "data" / "raw" / "rock_lobster_catch_raw.csv"

# Matches header cells like:
#   "Quota year 2026/27 TAC 1050.70 tonnes"
#   "Quota Year 2007/08 TAC 1523.5 tonnes plus"
QUOTA_HEADER_RE = re.compile(
    r"Quota\s*[Yy]ear\s*(\d{4}/\d{2}).*?TAC\s*([\d,]+\.?\d*)\s*tonnes", re.IGNORECASE
)


def clean_text(cell) -> str:
    """Strip zero-width spaces / non-breaking spaces that riddle this page,
    then collapse ordinary whitespace."""
    text = cell.get_text() if hasattr(cell, "get_text") else str(cell)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("​", "").replace("\xa0", " ")
    text = text.replace("*", "")  # stray markdown-style bold markers on some rows
    return re.sub(r"\s+", " ", text).strip()


def get_html(local_file: str | None = None) -> str:
    """Fetch the live page, unless a local HTML file is given (used for
    testing offline, or if you've saved a copy of the page yourself)."""
    if local_file:
        return Path(local_file).read_text(encoding="utf-8")
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text


def fetch_tables(html: str) -> list[list[list[str]]]:
    soup = BeautifulSoup(html, "lxml")

    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row = [clean_text(c) for c in cells]
            if any(row):
                rows.append(row)
        if rows:
            tables.append(rows)
    return tables


def parse_table(rows: list[list[str]], scraped_at: str) -> list[dict]:
    """One table = one quota year. First row is the header; last row (or a
    row starting with TOTAL) is a season total, not a monthly observation --
    we keep it, tagged separately, so clean.py can use it as a cross-check."""
    header = rows[0]
    match = QUOTA_HEADER_RE.search(header[0])
    if not match:
        return []  # not a catch table (skip nav/other tables on the page)

    quota_year = match.group(1)
    tac_tonnes_raw = match.group(2).replace(",", "")

    # Work out what units the catch column is in from the header wording
    catch_col_header = header[1] if len(header) > 1 else ""
    unit = "kg" if "kg" in catch_col_header.lower() else "tonnes"

    has_uncaught_col = len(header) >= 4

    records = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        label = row[0]
        is_total = "TOTAL" in label.upper()

        record = {
            "quota_year": quota_year,
            "tac_tonnes_raw": tac_tonnes_raw,
            "row_label": label,
            "is_total_row": is_total,
            "catch_raw": row[1] if len(row) > 1 else "",
            "catch_unit_raw": unit,
            "uncaught_raw": row[2] if has_uncaught_col and len(row) > 2 else "",
            "pct_tac_taken_raw": row[3] if has_uncaught_col and len(row) > 3
            else (row[2] if not has_uncaught_col and len(row) > 2 else ""),
            "source_url": URL,
            "scraped_at": scraped_at,
        }
        records.append(record)
    return records


def main():
    import sys

    local_file = sys.argv[1] if len(sys.argv) > 1 else None
    scraped_at = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    html = get_html(local_file)
    tables = fetch_tables(html)

    all_records = []
    for rows in tables:
        all_records.extend(parse_table(rows, scraped_at))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "quota_year", "tac_tonnes_raw", "row_label", "is_total_row",
        "catch_raw", "catch_unit_raw", "uncaught_raw", "pct_tac_taken_raw",
        "source_url", "scraped_at",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"Extracted {len(all_records)} rows from {len(tables)} tables -> {OUT_PATH}")
    n_quota_years = len({r["quota_year"] for r in all_records})
    print(f"Covers {n_quota_years} quota years.")


if __name__ == "__main__":
    main()
