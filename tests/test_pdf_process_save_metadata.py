"""Unit tests for the PdfProcess class, focusing on metadata handling
and error detection for invalid PDFs."""

from pathlib import Path

import pytest

from pdfclassify._util import MyException
from pdfclassify.pdf_metadata_manager import PDFMetadataManager
from pdfclassify.pdf_process import PdfProcess


def test_metadata_written_for_valid_pdf(valid_pdf_file: Path) -> None:
    """Ensure metadata is saved correctly to a valid PDF."""
    _ = PdfProcess(str(valid_pdf_file))
    manager = PDFMetadataManager(valid_pdf_file)

    assert manager.read_custom_field("original_filename") == "blank.pdf"
    assert manager.read_custom_field("original_date") is not None


def test_invalid_pdf_raises_exception(invalid_pdf_file: Path) -> None:
    """Ensure a corrupt PDF raises a proper MyException."""
    with pytest.raises(MyException) as exc_info:
        PdfProcess(str(invalid_pdf_file))

    assert "Invalid PDF file" in str(exc_info.value)
    assert exc_info.value.exit_code == 2
