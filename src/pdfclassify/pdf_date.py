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
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from dateparser import parse

from pdfclassify._util import extract_text_from_pdf
from pdfclassify.argument_handler import get_version

# Patterns: MM/YYYY, DD/MM/YYYY, YYYY-MM-DD, etc.
DATE_REGEXES = [
    r"(?:0?[1-9]|1[0-2])[/-]20\d{2}",  # month/year only e.g. "06/2025"
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # day/month/year
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",  # ISO style
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{2,4}\b",  # 17 May 2025
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",  # 17. Mai 2025
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",  # 17 de mayo de 2025
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",  # 17 mai. 2025
]


def load_minimum_parts(pdf_file: Path) -> list[str]:
    """Read /minimum_parts from sidecar JSON or default to ['day','month','year']."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                meta = json.load(f)
            return meta.get("/minimum_parts", ["day", "month", "year"])
        except json.JSONDecodeError:
            pass
    return ["day", "month", "year"]


def get_preferred_contexts(pdf_file: Path) -> list[str]:
    """Read .meta.json and return Preferred_Context list, or empty list."""
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if not meta_path.exists():
        return []
    try:
        with meta_path.open("r", encoding="utf-8") as meta_file:
            meta = json.load(meta_file)
        return meta.get("/preferred_context", [])
    except (json.JSONDecodeError, TypeError):
        return []


def meets_minimum_parts(parsed: datetime, raw: str, min_parts: list[str]) -> bool:
    """Ensure a detected date satisfies required parts (day/month/year)."""
    raw_norm = raw.strip().lower()
    is_month_year_only = bool(re.fullmatch(r"(0?[1-9]|1[0-2])[/-]20\d{2}", raw_norm))

    has_day = not is_month_year_only and (
        bool(re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", raw_norm))
        or bool(re.search(r"\b\d{1,2}\s+[a-z]", raw_norm))
    )

    has_month = parsed.month is not None
    has_year = parsed.year is not None and parsed.year >= 2020

    # 🔹 Exclude full dates if only month/year is requested
    if min_parts == ["month", "year"] and has_day:
        return False

    if "day" in min_parts and not has_day:
        return False
    if "month" in min_parts and not has_month:
        return False
    if "year" in min_parts and not has_year:
        return False
    return True


def find_all_dates(
    text: str, languages: list[str], min_parts: list[str]
) -> list[tuple[datetime, str]]:
    """Return list of (datetime, matched_string) that meet /minimum_parts."""
    found = set()
    results: list[tuple[datetime, str]] = []

    settings = {"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"}

    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in found:
                continue
            parsed = parse(match, languages=languages, settings=settings)  # type: ignore[arg-type]
            if parsed and parsed.year >= 2020 and meets_minimum_parts(parsed, match, min_parts):
                found.add(match)
                results.append((parsed, match.strip()))
    return results


def date_from_context(
    text: str, contexts: list[str], languages: list[str], min_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    """Find date where context keyword precedes it in the same line."""
    lowered_contexts = [c.lower() for c in contexts]
    settings = {"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"}

    for line in text.splitlines():
        line_lower = line.lower()
        for ctx in lowered_contexts:
            ctx_index = line_lower.find(ctx)
            if ctx_index == -1:
                continue
            for pattern in DATE_REGEXES:
                for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                    if match.start() > ctx_index:
                        parsed = parse(match.group(), languages=languages, settings=settings)
                        if (
                            parsed
                            and parsed.year >= 2020
                            and meets_minimum_parts(parsed, match.group(), min_parts)
                        ):
                            return parsed, match.group().strip()
    return None


def format_with_template(date_obj: datetime, template: Optional[str]) -> str:
    """Replace YYYY, MM, DD placeholders in the template or return YYYYMMDD."""
    if template:
        return (
            template.replace("YYYY", f"{date_obj.year:04d}")
            .replace("MM", f"{date_obj.month:02d}")
            .replace("DD", f"{date_obj.day:02d}")
        )
    return f"{date_obj.year:04d}{date_obj.month:02d}{date_obj.day:02d}"


def main() -> None:  # CLI entry
    parser = argparse.ArgumentParser(
        description="Extract the nth date from a PDF and apply formatting."
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
    min_parts = load_minimum_parts(args.pdf_file)
    preferred_contexts = get_preferred_contexts(args.pdf_file)

    # ✅ For testing: bypass PDF parsing if env var is set
    fake_text = os.getenv("PDFDATE_FAKE_TEXT")
    if fake_text:
        text = fake_text
    else:
        text = extract_text_from_pdf(args.pdf_file)

    # Context-aware extraction
    if preferred_contexts:
        result = date_from_context(text, preferred_contexts, languages, min_parts)
        if result:
            date_obj, _ = result
            template = args.pdf_file.name if args.convert else args.template
            print(format_with_template(date_obj, template))
            return

    # Generic extraction
    dates = find_all_dates(text, languages, min_parts)

    if args.list:
        if dates:
            for idx, (dt, raw) in enumerate(dates, 1):
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
