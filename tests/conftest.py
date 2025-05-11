"""Unit tests for verifying the restore_original_state behavior in PdfProcess."""

from pathlib import Path

import pytest
from pypdf import PdfWriter


def create_blank_pdf(path: Path) -> None:
    """Utility to create a blank PDF file."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


@pytest.fixture(name="valid_pdf_file")
def valid_pdf_fixture(tmp_path: Path) -> Path:
    """Return a valid PDF for metadata testing."""
    pdf_path = tmp_path / "blank.pdf"
    create_blank_pdf(pdf_path)
    return pdf_path


@pytest.fixture(name="invalid_pdf_file")
def invalid_pdf_fixture(tmp_path: Path) -> Path:
    """Create a deliberately invalid/corrupt PDF file."""
    invalid_path = tmp_path / "invalid.pdf"
    with open(invalid_path, "wb") as f:
        f.write(b"\x00\x00\x00\x01B")
    return invalid_path
