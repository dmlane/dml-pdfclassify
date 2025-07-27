#!/usr/bin/env python3
"""
Extract the nth date from a PDF file and return it in a formatted string.

Usage:
  pdf_date.py file.pdf
  pdf_date.py file.pdf -n 2
  pdf_date.py file.pdf -t invoice_YYYYMM
  pdf_date.py file.pdf -c
  pdf_date.py file.pdf --list
  pdf_date.py file.pdf --version
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from dateparser import parse

from pdfclassify._util import extract_text_from_pdf
from pdfclassify.argument_handler import get_version

DATE_REGEXES = [
    r"(?:0?[1-9]|1[0-2])[/-]20\d{2}",  # MM/YYYY
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # DD/MM/YYYY or MM/DD/YY
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",  # YYYY-MM-DD
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",  # 17 May 2025
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",  # 17. Mai 2025
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",  # 17 de mayo de 2025
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",  # 17 mai. 2025
]


def get_preferred_contexts(pdf_file: Path) -> list[str]:
    """Read /preferred_context from sidecar if available."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if not meta_path.exists():
        return []
    try:
        with meta_path.open("r", encoding="utf-8") as meta_file:
            meta = json.load(meta_file)
        return meta.get("/preferred_context", [])
    except (json.JSONDecodeError, TypeError):
        return []


def get_minimum_parts(pdf_file: Path) -> list[str]:
    """Read /minimum_parts from sidecar if available, otherwise return default."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if not meta_path.exists():
        return ["day", "month", "year"]
    try:
        with meta_path.open("r", encoding="utf-8") as meta_file:
            meta = json.load(meta_file)
        return meta.get("/minimum_parts", ["day", "month", "year"])
    except (json.JSONDecodeError, TypeError):
        return ["day", "month", "year"]


def has_required_parts(date_str: str, minimum_parts: list[str]) -> bool:
    """Return True if the date string contains all required parts."""
    checks = {
        "day": re.search(r"\b\d{1,2}\b", date_str) is not None,
        "month": re.search(r"\b(0?[1-9]|1[0-2]|[a-zA-Zéêäöüßçñ]+)\b", date_str) is not None,
        "year": re.search(r"\b\d{4}\b", date_str) is not None,
    }
    return all(checks[p] for p in minimum_parts)


def find_all_dates(text: str, minimum_parts: list[str]) -> list[tuple[datetime, str]]:
    """Return a list of (datetime, matched_string) for all
    detected dates that match minimum_parts."""
    found = set()
    results: list[tuple[datetime, str]] = []

    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in found:
                continue
            if not has_required_parts(match, minimum_parts):
                continue
            parsed = parse(
                match,
                languages=["en", "fr", "de", "es"],
                settings={
                    "PREFER_DAY_OF_MONTH": "first",
                    "DATE_ORDER": "DMY",
                },
            )
            if parsed and parsed.year >= 2020:
                found.add(match)
                results.append((parsed, match.strip()))

    return results


def date_from_context(
    text: str, contexts: list[str], minimum_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    """Try to locate a date where the context keyword appears before the date."""
    lowered_contexts = [c.lower() for c in contexts]

    for line in text.splitlines():
        line_lower = line.lower()
        for ctx in lowered_contexts:
            if ctx not in line_lower:
                continue
            for pattern in DATE_REGEXES:
                for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                    if not has_required_parts(match.group(), minimum_parts):
                        continue
                    parsed = parse(
                        match.group(),
                        languages=["en", "fr", "de", "es"],
                        settings={
                            "PREFER_DAY_OF_MONTH": "first",
                            "DATE_ORDER": "DMY",
                        },
                    )
                    if parsed and parsed.year >= 2020:
                        return parsed, match.group().strip()
    return None


def format_with_template(date_obj: datetime, template: Optional[str]) -> str:
    """Replace YYYY, MM, DD placeholders in template or return YYYYMMDD."""
    if template:
        return (
            template.replace("YYYY", f"{date_obj.year:04d}")
            .replace("MM", f"{date_obj.month:02d}")
            .replace("DD", f"{date_obj.day:02d}")
        )
    return f"{date_obj.year:04d}{date_obj.month:02d}{date_obj.day:02d}"


def main() -> None:
    """Parse args, extract dates, and print result or list."""
    parser = argparse.ArgumentParser(
        description="Extract the nth date from a PDF and apply formatting."
    )
    parser.add_argument("pdf_file", type=Path, help="Path to the PDF file.")
    parser.add_argument("-n", "--nth", type=int, default=1, help="Which date to extract (1-based).")
    parser.add_argument("-t", "--template", type=str, help="Template like 'invoice_YYYYMMDD'.")
    parser.add_argument("-c", "--convert", action="store_true", help="Use filename as template.")
    parser.add_argument("--list", action="store_true", help="List all matched dates and exit.")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {get_version()}")

    args = parser.parse_args()

    text = extract_text_from_pdf(args.pdf_file)
    minimum_parts = get_minimum_parts(args.pdf_file)

    # Try context-aware extraction
    preferred_contexts = get_preferred_contexts(args.pdf_file)
    if preferred_contexts:
        result = date_from_context(text, preferred_contexts, minimum_parts)
        if result:
            date_obj, _ = result
            template = args.pdf_file.name if args.convert else args.template
            print(format_with_template(date_obj, template))
            return

    # Fallback: generic extraction
    dates = find_all_dates(text, minimum_parts)

    if args.list:
        if dates:
            for idx, (dt, raw) in enumerate(dates, start=1):
                print(f"{idx}: {dt.date()} (from '{raw}')")
        else:
            print("No dates found in the document.")
        return

    if 0 < args.nth <= len(dates):
        date_obj, _ = dates[args.nth - 1]
        template = args.pdf_file.name if args.convert else args.template
        print(format_with_template(date_obj, template))
    else:
        print(f"Could not find {args.nth} date(s) in the document.")


if __name__ == "__main__":
    main()
