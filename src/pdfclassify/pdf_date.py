#!/usr/bin/env python3
"""
Extract the nth date from a PDF file and return it in a formatted string.

This script scans text (extracted from a PDF or provided via metadata/env)
for date-like strings using a set of regular expressions, parses them with
`dateparser`, filters by required parts (day/month/year), and outputs either
a formatted date or a list of matches.

Enhancements vs. the original:
- Supports month-name-first formats like "July 25, 2025 08:00:04 CEST".
- Detects the "day" component in month-name-first strings within
  `meets_minimum_parts`.
"""

from __future__ import annotations

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

# Precompiled patterns/constants
# Lowercase month name pattern for quick "day present?" checks.
_MONTH_NAME_SHORT = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"

# NOTE: Order matters. More specific patterns should come before generic ones.
DATE_REGEXES = [
    # Month-name first (e.g., "July 25, 2025", "July 25, 2025 08:00:04 CEST")
    (
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?(?:\s+[A-Z]{2,5})?)?\b"
    ),
    # Month abbreviation first (e.g., "Jul 25, 2025", "Sept 7, 2025 08:00 CEST")
    (
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?"
        r"\s+\d{1,2},?\s+\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?(?:\s+[A-Z]{2,5})?)?\b"
    ),
    # Month/year only (numeric, keep early so it’s found when allowed)
    r"(?:0?[1-9]|1[0-2])[/-]20\d{2}",
    # Common numeric variants
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # e.g., 25/07/2025 or 07-25-25
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",  # e.g., 2025-07-25
    # Day Monthname Year variants across languages
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{2,4}\b",  # e.g., 25 July 2025
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",  # e.g., 25. Juli 2025
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",  # e.g., 25 de julio de 2025
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",  # e.g., 25 sept. 2025
]


def load_minimum_parts(pdf_file: Path) -> list[str]:
    """
    Load the minimum required date parts for a given PDF.

    The companion sidecar JSON (same name + ".meta.json") can contain a
    "minimum_parts" array, e.g. ["day", "month", "year"] or ["month", "year"].

    Args:
        pdf_file: Path to the PDF file.

    Returns:
        A list of required parts. Defaults to ["day", "month", "year"].
    """
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as handle:
                return json.load(handle).get("minimum_parts", ["day", "month", "year"])
        except json.JSONDecodeError:
            # Fall back to default if JSON is invalid.
            pass
    return ["day", "month", "year"]


def get_preferred_contexts(pdf_file: Path) -> list[str]:
    """
    Load preferred context keywords to bias where dates are extracted.

    The sidecar JSON can contain a "/preferred_context" array. If present,
    the script first tries to find a date on the same line or the next line
    after any of these context strings.

    Args:
        pdf_file: Path to the PDF file.

    Returns:
        A list of context strings (case-insensitive comparisons are applied).
    """
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                contexts = data.get("/preferred_context", [])
                return contexts if isinstance(contexts, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def meets_minimum_parts(parsed: datetime, raw: str, min_parts: list[str]) -> bool:
    """
    Determine whether a parsed date and its raw text meet the required parts.

    This uses both the parsed datetime and light-weight regex checks against
    the raw match to infer whether a "day" token was present, including
    month-name-first patterns like "July 25, 2025".

    Args:
        parsed: The parsed datetime.
        raw: The raw matched string.
        min_parts: Required parts, e.g. ["day", "month", "year"] or ["month", "year"].

    Returns:
        True if the date meets the requirement, False otherwise.
    """
    raw_norm = raw.strip().lower()
    is_month_year = bool(re.fullmatch(r"(0?[1-9]|1[0-2])[/-]20\d{2}", raw_norm))

    # Detect presence of a day in multiple formats:
    # - numeric day first: "25/07/2025" or "25 July 2025"
    # - month-name first: "july 25, 2025" (abbrev/long forms)
    has_day = not is_month_year and (
        re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", raw_norm)  # 25/07/2025, 07-25-2025
        or re.search(r"\b\d{1,2}\s+[a-z]", raw_norm)  # 25 July 2025
        or re.search(rf"\b{_MONTH_NAME_SHORT}\.?\s+\d{{1,2}}\b", raw_norm)  # July 25, 2025
    )

    has_month = parsed.month is not None
    has_year = parsed.year >= 2020

    if min_parts == ["month", "year"] and has_day:
        # Caller explicitly wants month+year granularity; reject if a day was present.
        return False
    if "day" in min_parts and not has_day:
        return False
    if "month" in min_parts and not has_month:
        return False
    if "year" in min_parts and not has_year:
        return False
    return True


def parse_month_year(raw: str) -> Optional[datetime]:
    """
    Parse explicit numeric month/year (no day), e.g. '07/2025' or '7-2025'.

    Args:
        raw: The raw matched string.

    Returns:
        A datetime set to the first day of the month if matched, else None.
    """
    match = re.fullmatch(r"(0?[1-9]|1[0-2])[/-](20\d{2})", raw.strip())
    if match:
        return datetime(int(match.group(2)), int(match.group(1)), 1)
    return None


def find_all_dates(
    text: str, languages: list[str], min_parts: list[str]
) -> list[tuple[datetime, str]]:
    """
    Find all date-like matches in the text and return parsed results.

    Args:
        text: Input text to search.
        languages: Language hints for `dateparser.parse`.
        min_parts: Minimum required parts for a valid match.

    Returns:
        A list of (parsed_datetime, raw_string) tuples, in the order found.
    """
    results: list[tuple[datetime, str]] = []
    seen: set[str] = set()

    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in seen:
                continue

            parsed = parse_month_year(match) or parse(
                match,
                languages=languages,
                settings={
                    "PREFER_DAY_OF_MONTH": "first",
                    "DATE_ORDER": "DMY",
                },
            )
            if parsed and parsed.year >= 2020 and meets_minimum_parts(parsed, match, min_parts):
                seen.add(match)
                results.append((parsed, match.strip()))
    return results


def extract_first_valid_date(
    fragment: str, languages: list[str], min_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    """
    Return the first valid (datetime, raw) date found in a text fragment.

    Args:
        fragment: The line or small text block to scan.
        languages: Language hints for `dateparser.parse`.
        min_parts: Minimum required parts for a valid match.

    Returns:
        The first (datetime, raw) tuple that meets requirements, else None.
    """
    for pattern in DATE_REGEXES:
        for match in re.finditer(pattern, fragment, flags=re.IGNORECASE):
            raw = match.group()
            parsed = parse_month_year(raw) or parse(
                raw,
                languages=languages,
                settings={
                    "PREFER_DAY_OF_MONTH": "first",
                    "DATE_ORDER": "DMY",
                },
            )
            if parsed and parsed.year >= 2020 and meets_minimum_parts(parsed, raw, min_parts):
                return parsed, raw.strip()
    return None


def date_from_context(
    text: str, contexts: list[str], languages: list[str], min_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    """
    Find a date that appears on the same line as, or directly after, a context keyword.

    Args:
        text: Full text to scan.
        contexts: Context keywords to search for (case-insensitive).
        languages: Language hints for `dateparser.parse`.
        min_parts: Minimum required parts for a valid match.

    Returns:
        The first (datetime, raw) tuple near a context, else None.
    """
    lines = text.splitlines()
    lower_contexts = [c.lower() for c in contexts]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(ctx in line_lower for ctx in lower_contexts):
            # Check same line
            result = extract_first_valid_date(line, languages, min_parts)
            if result:
                return result
            # Check next line (if available)
            if i + 1 < len(lines):
                result = extract_first_valid_date(lines[i + 1], languages, min_parts)
                if result:
                    return result
    return None


def format_with_template(dt: datetime, template: Optional[str]) -> str:
    """
    Format a datetime using a simple YYYY/MM/DD templating scheme.

    Recognized tokens:
      - YYYY -> 4-digit year
      - MM   -> 2-digit month
      - DD   -> 2-digit day

    If no template is provided, defaults to YYYYMMDD.

    Args:
        dt: The datetime to format.
        template: The template string, or None for default.

    Returns:
        The formatted date string.
    """
    if template:
        return (
            template.replace("YYYY", f"{dt.year:04d}")
            .replace("MM", f"{dt.month:02d}")
            .replace("DD", f"{dt.day:02d}")
        )
    return f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"


def main() -> None:
    """CLI entrypoint to extract, list, or format dates from a PDF."""
    parser = argparse.ArgumentParser(
        description="Extract the nth date from a PDF and apply formatting."
    )
    parser.add_argument("pdf_file", type=Path)
    parser.add_argument("-n", "--nth", type=int, default=1)
    parser.add_argument("-t", "--template", type=str)
    parser.add_argument("-c", "--convert", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    args = parser.parse_args()

    min_parts = load_minimum_parts(args.pdf_file)
    preferred = get_preferred_contexts(args.pdf_file)
    langs = ["en", "fr", "de", "es"]

    # Prefer sample_text from meta or env (useful for tests)
    text = os.getenv("PDFDATE_FAKE_TEXT")
    if not text:
        meta_path = args.pdf_file.with_suffix(args.pdf_file.suffix + ".meta.json")
        if meta_path.exists():
            try:
                with meta_path.open("r", encoding="utf-8") as handle:
                    meta = json.load(handle)
                    text = meta.get("sample_text", "")
            except json.JSONDecodeError:
                text = ""
    if not text:
        try:
            text = extract_text_from_pdf(args.pdf_file)
        except Exception as exc:  # pylint: disable=broad-except
            # We deliberately swallow extraction errors and continue with empty text,
            # because callers often rely on --list behavior even when extraction fails.
            _ = exc  # satisfy pylint about unused variable
            text = ""

    # Context-aware first
    if preferred:
        ctx_result = date_from_context(text, preferred, langs, min_parts)
        if ctx_result:
            print(
                format_with_template(
                    ctx_result[0], args.pdf_file.name if args.convert else args.template
                )
            )
            return

    # Otherwise, collect all dates and proceed
    dates = find_all_dates(text, langs, min_parts)
    if args.list:
        if dates:
            print(
                "\n".join(f"{i+1}: {d.date()} (from '{raw}')" for i, (d, raw) in enumerate(dates))
            )
        else:
            print("No dates found in the document.")
        return

    if 0 < args.nth <= len(dates):
        print(
            format_with_template(
                dates[args.nth - 1][0], args.pdf_file.name if args.convert else args.template
            )
        )
    else:
        print(f"Could not find {args.nth} date(s) in the document.")


if __name__ == "__main__":
    main()
