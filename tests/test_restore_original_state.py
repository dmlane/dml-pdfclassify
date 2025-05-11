# pylint: disable=redefined-outer-name, too-few-public-methods
"""Test PdfProcess.restore_original_state()."""

import os
from datetime import datetime
from pathlib import Path

import pytest
from fpdf import FPDF

from pdfclassify.pdf_process import PdfProcess


@pytest.fixture
def dummy_pdf(tmp_path: Path) -> Path:
    """Create a dummy PDF with known timestamp."""
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


def test_restore_original_state(valid_pdf_file: Path, tmp_path: Path) -> None:
    """Ensure PdfProcess can restore the original name and timestamp."""
    process = PdfProcess(str(valid_pdf_file))
    original_name = valid_pdf_file.name
    original_mod_time = os.path.getmtime(valid_pdf_file)

    # Move and rename file
    new_path = tmp_path / "renamed.pdf"
    valid_pdf_file.rename(new_path)
    assert new_path.name != original_name

    # Change timestamp
    os.utime(new_path, None)
    assert os.path.getmtime(new_path) != original_mod_time

    # Restore state
    process = PdfProcess(str(new_path))
    process.restore_original_state()

    restored_path = new_path.parent / original_name
    assert restored_path.exists()
    assert restored_path.name == original_name

    restored_mod_time = os.path.getmtime(restored_path)
    assert abs(restored_mod_time - original_mod_time) < 1
