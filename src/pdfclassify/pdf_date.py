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

# Short + long formats including day-month-year and short-year
DATE_REGEXES = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # e.g. 17/05/2025 or 17-05-25
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",  # e.g. 2025-05-17
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{2,4}\b",  # e.g. 17 May 25
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",  # e.g. 17. Mai 2025
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",  # e.g. 17 de mayo de 2025
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",  # e.g. 17 mai. 2025
    r"(?:0?[1-9]|1[0-2])[/-]20\d{2}",  # Month/Year (05/2025) → filtered later
]


def get_minimum_parts(pdf_file: Path) -> list[str]:
    """Read /minimum_parts from .meta.json if present, else default to day,month,year."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                meta = json.load(f)
            return meta.get("/minimum_parts", ["day", "month", "year"])
        except (json.JSONDecodeError, OSError):
            return ["day", "month", "year"]
    return ["day", "month", "year"]


def get_preferred_contexts(pdf_file: Path) -> list[str]:
    """Read /preferred_context from sidecar if present."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as meta_file:
                meta = json.load(meta_file)
            return meta.get("/preferred_context", [])
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def has_required_parts(date_str: str, minimum_parts: list[str]) -> bool:
    """Ensure the original date string explicitly contains all required parts."""
    checks = {
        "day": bool(re.search(r"\b([0-2]?\d|3[01])\b", date_str)),
        "month": bool(re.search(r"\b(0?[1-9]|1[0-2]|[a-zA-Zéêäöüßçñ]+)\b", date_str)),
        "year": bool(re.search(r"\b\d{4}\b", date_str)),
    }
    return all(checks[p] for p in minimum_parts)


def find_all_dates(
    text: str, languages: list[str], minimum_parts: list[str]
) -> list[tuple[datetime, str]]:
    """Return list of (datetime, matched text) for all valid dates."""
    found = set()
    results: list[tuple[datetime, str]] = []
    settings = {"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"}

    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in found:
                continue
            parsed = parse(match, languages=languages, settings=settings)
            if not parsed or parsed.year < 2020:
                continue
            # ✅ enforce explicit parts
            if not has_required_parts(match, minimum_parts):
                continue
            found.add(match)
            results.append((parsed, match.strip()))
    return results


def date_from_context(
    text: str, contexts: list[str], languages: list[str], minimum_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    """Find first date where a context keyword precedes it on the same line."""
    settings = {"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"}
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
                        raw = match.group()
                        parsed = parse(raw, languages=languages, settings=settings)
                        if (
                            parsed
                            and parsed.year >= 2020
                            and has_required_parts(raw, minimum_parts)
                        ):
                            return parsed, raw.strip()
    return None


def format_with_template(date_obj: datetime, template: Optional[str]) -> str:
    """Replace YYYY, MM, DD placeholders in template or default YYYYMMDD."""
    if template:
        return (
            template.replace("YYYY", f"{date_obj.year:04d}")
            .replace("MM", f"{date_obj.month:02d}")
            .replace("DD", f"{date_obj.day:02d}")
        )
    return f"{date_obj.year:04d}{date_obj.month:02d}{date_obj.day:02d}"


def main() -> None:
    """Parse arguments, extract dates, and print result or list."""
    parser = argparse.ArgumentParser(description="Extract the nth date from a PDF.")
    parser.add_argument("pdf_file", type=Path, help="Path to the PDF file.")
    parser.add_argument("-n", "--nth", type=int, default=1, help="Which date to extract (1-based).")
    parser.add_argument("-t", "--template", type=str, help="Template like 'invoice_YYYYMMDD'.")
    parser.add_argument("-c", "--convert", action="store_true", help="Use filename as template.")
    parser.add_argument("--list", action="store_true", help="List all matched dates.")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {get_version()}")

    args = parser.parse_args()
    languages = ["en", "fr", "de", "es"]
    text = extract_text_from_pdf(args.pdf_file)
    minimum_parts = get_minimum_parts(args.pdf_file)

    # Try context-aware extraction
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
