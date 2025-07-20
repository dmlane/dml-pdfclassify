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
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dateparser import parse
from pypdf import PdfReader

from pdfclassify.argument_handler import get_version  # lazy import of version

# noinspection SpellCheckingInspection
DATE_REGEXES = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",
]


def extract_text_from_pdf(path: Path) -> str:
    """Extract all text from a PDF file."""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def find_all_dates(text: str, languages: list[str]) -> list[tuple[datetime, str]]:
    """
    Find and parse all explicit dates in the given text, in document order.
    Returns a list of (datetime, matched_string).
    """
    found = set()
    results: list[tuple[datetime, str]] = []
    settings: dict[str, Any] = {"PREFER_DAY_OF_MONTH": "first"}

    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in found:
                continue
            parsed = parse(match, languages=languages, settings=settings)  # type: ignore[arg-type]
            if parsed and parsed.year >= 2020:
                found.add(match)
                results.append((parsed, match.strip()))

    return results


def format_with_template(date_obj: datetime, template: str | None) -> str:
    """Replace YYYY, MM, DD placeholders in the template or return YYYYMMDD."""
    if template:
        return (
            template.replace("YYYY", f"{date_obj.year:04d}")
            .replace("MM", f"{date_obj.month:02d}")
            .replace("DD", f"{date_obj.day:02d}")
        )
    return f"{date_obj.year:04d}{date_obj.month:02d}{date_obj.day:02d}"


def main() -> None:
    """Parse arguments, extract dates, and print result or list."""
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
        "-n",
        "--nth",
        type=int,
        default=1,
        help="Which date to extract (1-based index). Default is 1.",
    )
    parser.add_argument(
        "-t", "--template", type=str, help="Template like 'invoice_YYYYMMDD'. Uses YYYY, MM, DD."
    )
    parser.add_argument(
        "-c",
        "--convert",
        action="store_true",
        help="Use filename (with extension) as template, interpolating date.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all matched dates (index, date, matched text) and exit.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
        help="Show program version and exit.",
    )

    args = parser.parse_args()
    languages = ["en", "fr", "de", "es"]
    text = extract_text_from_pdf(args.pdf_file)
    dates = find_all_dates(text, languages)

    if args.list:
        if dates:
            for idx, (dt, raw) in enumerate(dates, start=1):
                print(f"{idx}: {dt.date()} (from '{raw}')")
        else:
            print("No dates found in the document.")
        return

    if 0 < args.nth <= len(dates):
        date_obj, _ = dates[args.nth - 1]
        if args.convert:
            template = args.pdf_file.name
        elif args.template:
            template = args.template
        else:
            template = None
        print(format_with_template(date_obj, template))
    else:
        print(f"Could not find {args.nth} date(s) in the document.")


if __name__ == "__main__":
    main()
