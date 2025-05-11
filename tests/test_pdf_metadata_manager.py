"""Tests for the PDFMetadataManager class."""

# pylint: disable=redefined-outer-name

import os
import time
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

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


def test_timestamps_are_preserved(valid_pdf_file: Path) -> None:
    """Ensure file modification times are preserved after update."""
    original_stat = os.stat(valid_pdf_file)
    original_mtime = original_stat.st_mtime

    time.sleep(1)  # Ensure filesystem time delta

    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/Classification", "timestamp-test")

    new_stat = os.stat(valid_pdf_file)
    assert new_stat.st_mtime == original_mtime


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


def test_mod_date_preserved_format(valid_pdf_file: Path) -> None:
    """Ensure that /ModDate is preserved and formatted properly."""
    # Manually write a PDF with a ModDate field
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/ModDate": "D:20240508120000"})
    with open(valid_pdf_file, "wb") as f:
        writer.write(f)

    # Confirm the ModDate was written
    reader = PdfReader(valid_pdf_file)
    assert reader.metadata.get("/ModDate") == "D:20240508120000"

    # Now use your manager and trigger a write action
    manager = PDFMetadataManager(valid_pdf_file)
    manager.write_custom_field("/TestField", "Value")

    # Confirm the ModDate still exists after the update
    mod_date = manager.read_custom_field("/ModDate")
    assert mod_date is not None
    assert mod_date.startswith("D:")


def test_write_custom_field_return_value(valid_pdf_file: Path) -> None:
    """Ensure write_custom_field returns True on write and False when skipped."""
    manager = PDFMetadataManager(valid_pdf_file)
    assert manager.write_custom_field("/Foo", "bar") is True
    assert manager.write_custom_field("/Foo", "baz", overwrite=False) is False
