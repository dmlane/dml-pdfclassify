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

# Regex patterns for various date formats
DATE_REGEXES = [
    r"(?:0?[1-9]|1[0-2])[/-]20\d{2}",  # MM/YYYY
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # 17/05/2025
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",  # 2025-05-17
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{2,4}\b",  # 17 May 25
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",  # 17. Mai 2025
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",  # 17 de mayo de 2025
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",  # 17 mai. 2025
]


def get_preferred_contexts(pdf_file: Path) -> list[str]:
    """Read .meta.json and return /preferred_context list, or empty list."""
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
    """Read /minimum_parts from .meta.json or return ['day','month','year']."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if not meta_path.exists():
        return ["day", "month", "year"]
    try:
        with meta_path.open("r", encoding="utf-8") as meta_file:
            meta = json.load(meta_file)
        return meta.get("/minimum_parts", ["day", "month", "year"])
    except (json.JSONDecodeError, TypeError):
        return ["day", "month", "year"]


def has_required_parts(date_obj: datetime, minimum_parts: list[str]) -> bool:
    """Return True if the parsed date satisfies the minimum_parts constraint."""
    parts_present = {"year"}
    if date_obj.day != 1 or "day" in minimum_parts:
        parts_present.add("day")
    parts_present.add("month")
    return all(p in parts_present for p in minimum_parts)


def parse_date_string(date_str: str, minimum_parts: list[str]) -> Optional[datetime]:
    """Parse date string and return datetime if it meets minimum_parts requirements."""
    # Handle MM/YYYY specifically
    m = re.fullmatch(r"(0?[1-9]|1[0-2])[/-](20\d{2})", date_str)
    if m:
        month, year = m.groups()
        date_obj = datetime(int(year), int(month), 1)
        return date_obj if has_required_parts(date_obj, minimum_parts) else None

    # Generic parse
    settings = {"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"}
    parsed = parse(date_str, settings=settings)  # type: ignore[arg-type]
    if parsed and parsed.year >= 2020 and has_required_parts(parsed, minimum_parts):
        return parsed
    return None


def find_all_dates(
    text: str, languages: list[str], minimum_parts: list[str]
) -> list[tuple[datetime, str]]:
    """Return all (datetime, matched_string) dates that meet minimum_parts."""
    found = set()
    results = []
    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in found:
                continue
            parsed = parse_date_string(match, minimum_parts)
            if parsed:
                found.add(match)
                results.append((parsed, match.strip()))
    return results


def date_from_context(
    text: str, contexts: list[str], languages: list[str], minimum_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    """Find a date that appears after a context keyword in the same line."""

    lowered_contexts = [c.lower() for c in contexts]
    for line in text.splitlines():
        line_lower = line.lower()
        for ctx in lowered_contexts:
            ctx_index = line_lower.find(ctx)
            if ctx_index == -1:
                continue
            for pattern in DATE_REGEXES:
                for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                    if match.start() > ctx_index:
                        parsed = parse_date_string(match.group(), minimum_parts)
                        if parsed:
                            return parsed, match.group().strip()
    return None


def format_with_template(date_obj: datetime, template: Optional[str]) -> str:
    """Format output date with template or default YYYYMMDD."""
    if template:
        return (
            template.replace("YYYY", f"{date_obj.year:04d}")
            .replace("MM", f"{date_obj.month:02d}")
            .replace("DD", f"{date_obj.day:02d}")
        )
    return f"{date_obj.year:04d}{date_obj.month:02d}{date_obj.day:02d}"


def main() -> None:  # pylint: disable=too-many-branches
    """Parse arguments, extract dates, and print the result."""
    parser = argparse.ArgumentParser(
        description="Extract the nth date from a PDF and apply formatting.",
        epilog="Examples:\n"
        "  pdf_date.py file.pdf\n"
        "  pdf_date.py file.pdf -n 2\n"
        "  pdf_date.py file.pdf -t invoice_YYYYMM\n"
        "  pdf_date.py file.pdf -c\n"
        "  pdf_date.py file.pdf --list\n"
        "  pdf_date.py file.pdf --version",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("pdf_file", type=Path, help="Path to the PDF file.")
    parser.add_argument(
        "-n", "--nth", type=int, default=1, help="Which date to extract (1-based index)."
    )
    parser.add_argument("-t", "--template", type=str, help="Template like 'invoice_YYYYMMDD'.")
    parser.add_argument("-c", "--convert", action="store_true", help="Use filename as template.")
    parser.add_argument("--list", action="store_true", help="List all matched dates.")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {get_version()}")

    args = parser.parse_args()
    languages = ["en", "fr", "de", "es"]
    text = extract_text_from_pdf(args.pdf_file)

    # ✅ Load minimum_parts for selection
    minimum_parts = get_minimum_parts(args.pdf_file)

    # Try context-based extraction first
    preferred_contexts = get_preferred_contexts(args.pdf_file)
    if preferred_contexts:
        result = date_from_context(text, preferred_contexts, languages, minimum_parts)
        if result:
            date_obj, _ = result
            template = args.pdf_file.name if args.convert else args.template
            print(format_with_template(date_obj, template))
            return

    # Fallback: generic extraction
    dates = find_all_dates(text, languages, minimum_parts)

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
