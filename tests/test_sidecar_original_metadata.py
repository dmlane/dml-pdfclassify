"""Tests for the PDFMetadataManager class using sidecar metadata."""

# pylint: disable=redefined-outer-name

import json
from pathlib import Path

import pytest

from pdfclassify.pdf_metadata_manager import PDFMetadataManager


def test_write_and_read_custom_metadata(valid_pdf_file: Path) -> None:
    """Test writing and reading a custom metadata field."""
    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Classification", "invoice")
    assert manager.read_custom_field("/Classification") == "invoice"


def test_write_metadata_without_overwrite(valid_pdf_file: Path) -> None:
    """Test that write_custom_field respects overwrite=False."""
    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Classification", "initial")
    manager.write_custom_field("/Classification", "new", overwrite=False)
    assert manager.read_custom_field("/Classification") == "initial"


def test_delete_custom_metadata(valid_pdf_file: Path) -> None:
    """Test deleting a custom metadata field."""
    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Original_Filename", "original.pdf")
    manager.delete_custom_field("/Original_Filename")
    assert manager.read_custom_field("/Original_Filename") is None


def test_pdf_file_not_modified(valid_pdf_file: Path) -> None:
    """Ensure PDF file content is not modified when writing metadata."""
    original_content = valid_pdf_file.read_bytes()

    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Classification", "unchanged-test")

    assert valid_pdf_file.read_bytes() == original_content


def test_print_metadata_smoke(valid_pdf_file: Path, capsys: pytest.CaptureFixture) -> None:
    """Smoke test for print_metadata output formatting."""
    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Classification", "invoice")
    manager.write_custom_field("/Original_Filename", "test.pdf")
    manager.write_custom_field("/Original_Date", "2024-12-01")
    manager.print_metadata()
    captured = capsys.readouterr()
    assert "custom metadata for" in captured.out.lower()
    assert "classification" in captured.out.lower()
    assert "invoice" in captured.out.lower()


def test_write_custom_field_return_value(valid_pdf_file: Path) -> None:
    """Ensure write_custom_field returns True on write and False when skipped."""
    manager = PDFMetadataManager(valid_pdf_file)
    assert manager.write_custom_field("/Foo", "bar") is True
    assert manager.write_custom_field("/Foo", "baz", overwrite=False) is False


def test_sidecar_file_content(valid_pdf_file: Path) -> None:
    """Ensure sidecar file contains expected JSON structure."""
    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Classification", "invoice")

    sidecar_path = valid_pdf_file.with_suffix(valid_pdf_file.suffix + ".meta.json")
    assert sidecar_path.exists()

    with sidecar_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("/Classification") == "invoice"
