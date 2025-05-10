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


def test_restore_original_state(dummy_pdf: Path, tmp_path: Path) -> None:
    """Ensure PdfProcess can restore the original name and timestamp."""
    # Instantiate to store metadata
    process = PdfProcess(str(dummy_pdf))
    original_name = dummy_pdf.name
    original_mod_time = os.path.getmtime(dummy_pdf)

    # Rename and move file manually
    new_path = tmp_path / "renamed.pdf"
    dummy_pdf.rename(new_path)

    # Confirm it changed
    assert new_path.name != original_name

    # Modify timestamp
    new_mod_time = datetime.now().timestamp()
    os.utime(new_path, (new_mod_time, new_mod_time))
    assert os.path.getmtime(new_path) != original_mod_time

    # Re-run process on moved file
    process = PdfProcess(str(new_path))
    process.restore_original_state()

    # Confirm restored path and name
    restored_path = new_path.parent / original_name
    assert restored_path.exists()
    assert restored_path.name == original_name

    # Confirm restored timestamp (allow slight rounding drift)
    restored_mod_time = os.path.getmtime(restored_path)
    assert abs(restored_mod_time - original_mod_time) < 1, "Timestamp not restored"
