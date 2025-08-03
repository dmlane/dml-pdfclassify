# pylint: disable=redefined-outer-name, too-few-public-methods
"""Test PdfProcess sidecar metadata preservation and retrieval."""

import os
from datetime import datetime
from pathlib import Path

import pytest
from fpdf import FPDF

from pdfclassify.pdf_metadata_manager import PDFMetadataManager


@pytest.fixture
def dummy_pdf(tmp_path: Path) -> Path:
    """Create a dummy PDF with known timestamp and name."""
    pdf_path = tmp_path / "original_name.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Dummy content", ln=True)
    pdf.output(str(pdf_path))

    # Set known mod time
    mod_time = datetime(2022, 1, 1, 12, 0, 0).timestamp()
    os.utime(pdf_path, (mod_time, mod_time))
    return pdf_path


def test_sidecar_original_metadata(dummy_pdf: Path, tmp_path: Path) -> None:
    """
    Ensure original name and timestamp are correctly stored in the sidecar and retrievable,
    even after renaming and touching the file.
    """
    original_name = dummy_pdf.name
    original_mod_time = dummy_pdf.stat().st_mtime
    iso_date = datetime.fromtimestamp(original_mod_time).isoformat()

    # Write original metadata
    manager = PDFMetadataManager(dummy_pdf)
    manager.write_custom_field("original_filename", original_name)
    manager.write_custom_field("original_date", iso_date)

    # Rename PDF and sidecar together
    renamed_path = tmp_path / "renamed.pdf"
    manager.rename_with_sidecar(renamed_path)

    # Modify timestamp after rename
    os.utime(renamed_path, None)

    # Reload manager from renamed path and verify metadata
    manager = PDFMetadataManager(renamed_path)
    assert manager.read_custom_field("original_filename") == "original_name.pdf"
    assert manager.read_custom_field("original_date") == iso_date
    assert manager.verify_pdf_hash() is True
