import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import pdfclassify.pdf_date as pdf_date


@pytest.fixture
def sample_text():
    return (
        "Invoice Date: 23/05/2025\n"
        "Period: 05/2025\n"
        "French: 01 avril 2025\n"
        "Spanish: 17 de mayo de 2025\n"
        "Duplicate: 23/05/2025\n"
        "Old: 1999-12-31"
    )


@pytest.fixture
def tmp_meta_file(tmp_path):
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_text("dummy")
    meta_path = pdf_file.with_suffix(".pdf.meta.json")
    return pdf_file, meta_path


def write_meta(meta_path: Path, min_parts, preferred_context=None):
    data = {"minimum_parts": min_parts}
    if preferred_context:
        data["/preferred_context"] = preferred_context
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


@pytest.mark.parametrize(
    "parts,expected",
    [
        (["day", "month", "year"], {"23/05/2025", "01 avril 2025", "17 de mayo de 2025"}),
        (["month", "year"], {"05/2025"}),
    ],
)
def test_find_all_dates_respects_minimum_parts(sample_text, tmp_meta_file, parts, expected):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, parts)
    min_parts = pdf_date.load_minimum_parts(pdf_file)

    results = pdf_date.find_all_dates(sample_text, ["en", "fr", "es"], min_parts)
    matched = {raw for _, raw in results}
    assert matched == expected


def test_mm_yyyy_parsing_respected(tmp_meta_file):
    """Ensure MM/YYYY like '04/2025' is parsed as April 2025 when month/year required."""
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["month", "year"])
    min_parts = pdf_date.load_minimum_parts(pdf_file)

    text = "Period: 04/2025"
    results = pdf_date.find_all_dates(text, ["en"], min_parts)
    assert results, "Expected at least one date match"
    parsed, raw = results[0]
    assert raw == "04/2025"
    assert parsed.year == 2025
    assert parsed.month == 4


def test_deduplication_of_dates(sample_text, tmp_meta_file):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"])
    min_parts = pdf_date.load_minimum_parts(pdf_file)

    results = pdf_date.find_all_dates(sample_text, ["en"], min_parts)
    raws = [r for _, r in results]
    assert len(raws) == len(set(raws)), "Dates must be deduplicated"


def test_excludes_old_years(tmp_meta_file):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"])
    min_parts = pdf_date.load_minimum_parts(pdf_file)

    text = "Old: 1999-12-31"
    results = pdf_date.find_all_dates(text, ["en"], min_parts)
    assert not results


def test_context_based_selection(sample_text, tmp_meta_file):
    """Context keywords must trigger extraction only when before the date."""
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"], preferred_context=["invoice"])
    contexts = ["invoice"]

    min_parts = pdf_date.load_minimum_parts(pdf_file)
    result = pdf_date.date_from_context(sample_text, contexts, ["en"], min_parts)

    assert result is not None
    _, raw = result
    assert raw == "23/05/2025"


# --- CLI Integration Tests with monkeypatched text extraction ---


def run_cli(script_path: Path, args):
    cmd = [sys.executable, str(script_path)] + args
    env = os.environ.copy()
    env["PDFDATE_TEST_TEXT"] = (
        "Invoice Date: 23/05/2025\nPeriod: 05/2025\nFrench: 01 avril 2025\n"
        "Spanish: 17 de mayo de 2025\nDuplicate: 23/05/2025\nOld: 1999-12-31"
    )
    return subprocess.check_output(cmd, text=True, env=env).strip()


@pytest.fixture
def pdf_date_cli(tmp_path):
    cli_copy = tmp_path / "pdf_date.py"
    cli_copy.write_text(Path(pdf_date.__file__).read_text(encoding="utf-8"))
    return cli_copy


# def test_cli_list_mode(tmp_meta_file, pdf_date_cli):
#     pdf_file, meta_path = tmp_meta_file
#     write_meta(meta_path, ["day", "month", "year"])
#     output = run_cli(pdf_date_cli, ["--list", str(pdf_file)])
#     assert "23/05/2025" in output
#
#
# def test_cli_template_mode(tmp_meta_file, pdf_date_cli):
#     pdf_file, meta_path = tmp_meta_file
#     write_meta(meta_path, ["day", "month", "year"])
#     output = run_cli(pdf_date_cli, [str(pdf_file), "-t", "invoice_YYYYMM"])
#     assert output.startswith("invoice_202505")
