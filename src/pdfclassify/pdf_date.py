#!/usr/bin/env python3
"""
Extract the nth date from a PDF file and return it in a formatted string.
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

DATE_REGEXES = [
    r"(?:0?[1-9]|1[0-2])[/-]20\d{2}",  # month/year only
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]+\s+\d{2,4}\b",
    r"\b\d{1,2}\.\s*[a-zA-Zéêäöüßçñ]+\s+\d{4}\b",
    r"\b\d{1,2}\s+de\s+[a-zA-Zéêäöüßçñ]+\s+de\s+\d{4}\b",
    r"\b\d{1,2}\s+[a-zA-Zéêäöüßçñ]{3,}\.?\s+\d{4}\b",
]


def load_minimum_parts(pdf_file: Path) -> list[str]:
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                return json.load(f).get("minimum_parts", ["day", "month", "year"])
        except json.JSONDecodeError:
            pass
    return ["day", "month", "year"]


def get_preferred_contexts(pdf_file: Path) -> list[str]:
    meta_path = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                return json.load(f).get("/preferred_context", [])
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def meets_minimum_parts(parsed: datetime, raw: str, min_parts: list[str]) -> bool:
    raw_norm = raw.strip().lower()
    is_month_year = bool(re.fullmatch(r"(0?[1-9]|1[0-2])[/-]20\d{2}", raw_norm))

    has_day = not is_month_year and (
        re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", raw_norm)
        or re.search(r"\d{1,2}\s+[a-z]", raw_norm)
    )
    has_month = parsed.month is not None
    has_year = parsed.year >= 2020

    if min_parts == ["month", "year"] and has_day:
        return False
    if "day" in min_parts and not has_day:
        return False
    if "month" in min_parts and not has_month:
        return False
    if "year" in min_parts and not has_year:
        return False
    return True


def parse_month_year(raw: str) -> Optional[datetime]:
    m = re.fullmatch(r"(0?[1-9]|1[0-2])[/-](20\d{2})", raw.strip())
    if m:
        return datetime(int(m.group(2)), int(m.group(1)), 1)
    return None


def find_all_dates(
    text: str, languages: list[str], min_parts: list[str]
) -> list[tuple[datetime, str]]:
    results, seen = [], set()
    for pattern in DATE_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match in seen:
                continue
            parsed = parse_month_year(match) or parse(
                match,
                languages=languages,
                settings={"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"},
            )
            if parsed and parsed.year >= 2020 and meets_minimum_parts(parsed, match, min_parts):
                seen.add(match)
                results.append((parsed, match.strip()))
    return results


def date_from_context(
    text: str, contexts: list[str], languages: list[str], min_parts: list[str]
) -> Optional[tuple[datetime, str]]:
    for line in text.splitlines():
        ll = line.lower()
        for ctx in [c.lower() for c in contexts]:
            pos = ll.find(ctx)
            if pos == -1:
                continue
            for pattern in DATE_REGEXES:
                for m in re.finditer(pattern, line, flags=re.IGNORECASE):
                    if m.start() > pos:
                        parsed = parse_month_year(m.group()) or parse(
                            m.group(),
                            languages=languages,
                            settings={"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"},
                        )
                        if (
                            parsed
                            and parsed.year >= 2020
                            and meets_minimum_parts(parsed, m.group(), min_parts)
                        ):
                            return parsed, m.group().strip()
    return None


def format_with_template(dt: datetime, template: Optional[str]) -> str:
    if template:
        return (
            template.replace("YYYY", f"{dt.year:04d}")
            .replace("MM", f"{dt.month:02d}")
            .replace("DD", f"{dt.day:02d}")
        )
    return f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"


def main() -> None:
    p = argparse.ArgumentParser(description="Extract the nth date from a PDF and apply formatting.")
    p.add_argument("pdf_file", type=Path)
    p.add_argument("-n", "--nth", type=int, default=1)
    p.add_argument("-t", "--template", type=str)
    p.add_argument("-c", "--convert", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {get_version()}")
    a = p.parse_args()

    min_parts = load_minimum_parts(a.pdf_file)
    preferred = get_preferred_contexts(a.pdf_file)
    langs = ["en", "fr", "de", "es"]

    # ✅ Prefer sample_text from meta or env (for tests)
    text = os.getenv("PDFDATE_FAKE_TEXT")
    if not text:
        meta_path = a.pdf_file.with_suffix(a.pdf_file.suffix + ".meta.json")
        if meta_path.exists():
            try:
                meta = json.load(open(meta_path, encoding="utf-8"))
                text = meta.get("sample_text", "")
            except json.JSONDecodeError:
                text = ""
    if not text:
        try:
            text = extract_text_from_pdf(a.pdf_file)
        except Exception:
            text = ""

    # Context-aware first
    if preferred:
        r = date_from_context(text, preferred, langs, min_parts)
        if r:
            print(format_with_template(r[0], a.pdf_file.name if a.convert else a.template))
            return

    dates = find_all_dates(text, langs, min_parts)
    if a.list:
        (
            print(
                "\n".join(f"{i+1}: {d.date()} (from '{raw}')" for i, (d, raw) in enumerate(dates))
            )
            if dates
            else print("No dates found in the document.")
        )
        return

    if 0 < a.nth <= len(dates):
        print(
            format_with_template(dates[a.nth - 1][0], a.pdf_file.name if a.convert else a.template)
        )
    else:
        print(f"Could not find {a.nth} date(s) in the document.")


if __name__ == "__main__":
    main()
