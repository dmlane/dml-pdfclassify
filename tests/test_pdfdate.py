"""Tests for pdf_date.py date extraction, filtering, and CLI behavior."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pdf_date as pdf_date
import pytest


# ─────────────────────────────────────────────
# Helper to write sidecar metadata with minimum_parts
# ─────────────────────────────────────────────
def write_meta(meta_path: Path, minimum_parts, preferred_context=None):
    data = {
        "/minimum_parts": minimum_parts,
    }
    if preferred_context:
        data["/preferred_context"] = preferred_context
    meta_path.write_text(json.dumps(data), encoding="utf-8")


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────
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
    pdf_file.write_bytes(b"%PDF-1.4\n%Fake PDF content")
    meta_file = pdf_file.with_suffix(".pdf.meta.json")
    return pdf_file, meta_file


@pytest.fixture
def pdf_date_cli(tmp_path):
    """Copy the pdf_date.py file to a temp directory so subprocess can run it."""
    cli_path = tmp_path / "pdf_date.py"
    cli_path.write_text(Path(pdf_date.__file__).read_text(), encoding="utf-8")
    return cli_path


# ─────────────────────────────────────────────
# Parametrized tests for minimum_parts filtering
# ─────────────────────────────────────────────
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


def test_deduplication_of_dates(sample_text, tmp_meta_file):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"])
    min_parts = pdf_date.load_minimum_parts(pdf_file)

    results = pdf_date.find_all_dates(sample_text, ["en"], min_parts)
    matched = [raw for _, raw in results]
    assert matched.count("23/05/2025") == 1


def test_excludes_old_years(sample_text, tmp_meta_file):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"])
    min_parts = pdf_date.load_minimum_parts(pdf_file)

    results = pdf_date.find_all_dates(sample_text, ["en"], min_parts)
    assert all(date.year >= 2020 for date, _ in results)


def test_context_based_selection(sample_text, tmp_meta_file):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"], preferred_context=["invoice"])
    contexts = ["invoice"]

    min_parts = pdf_date.load_minimum_parts(pdf_file)
    result = pdf_date.date_from_context(sample_text, contexts, ["en"], min_parts)

    assert result is not None
    _, raw = result
    assert raw == "23/05/2025"


# ─────────────────────────────────────────────
# Helpers to run CLI in subprocess
# ─────────────────────────────────────────────
def run_cli(cli_path, args):
    """Run the CLI in a subprocess and return stdout."""
    cmd = [sys.executable, str(cli_path)] + [str(a) for a in args]
    env = os.environ.copy()
    # propagate fake text if set
    if "PDFDATE_FAKE_TEXT" in os.environ:
        env["PDFDATE_FAKE_TEXT"] = os.environ["PDFDATE_FAKE_TEXT"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.stdout.strip()


# ─────────────────────────────────────────────
# CLI tests (with fake text via environment)
# ─────────────────────────────────────────────
def test_cli_list_mode(sample_text, tmp_meta_file, pdf_date_cli, monkeypatch):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"])

    # ✅ Use environment variable for fake text
    monkeypatch.setenv("PDFDATE_FAKE_TEXT", sample_text)

    output = run_cli(pdf_date_cli, ["--list", str(pdf_file)])
    assert "23/05/2025" in output


def test_cli_template_mode(sample_text, tmp_meta_file, pdf_date_cli, monkeypatch):
    pdf_file, meta_path = tmp_meta_file
    write_meta(meta_path, ["day", "month", "year"])

    # ✅ Use environment variable for fake text
    monkeypatch.setenv("PDFDATE_FAKE_TEXT", sample_text)

    output = run_cli(pdf_date_cli, [str(pdf_file), "-t", "invoice_YYYYMM"])
    assert output.startswith("invoice_202505")
