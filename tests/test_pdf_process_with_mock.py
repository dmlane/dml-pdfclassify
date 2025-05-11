# pylint: disable=redefined-outer-name, too-few-public-methods
"""Test PdfProcess.predict() with mocked PDFSemanticClassifier."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fpdf import FPDF

from pdfclassify.argument_handler import ParsedArgs
from pdfclassify.pdf_process import PdfProcess


@pytest.fixture
def temp_pdf(tmp_path: Path) -> Path:
    """Create a dummy PDF file."""
    pdf_path = tmp_path / "mocked_test.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Test PDF content", ln=True)
    pdf.output(str(pdf_path))
    return pdf_path


@pytest.fixture
def parsed_args(tmp_path: Path) -> ParsedArgs:
    """Mocked ParsedArgs input."""
    return ParsedArgs(
        verbose=False,
        training_data_path="tests/testresources/labeled_training_data",
        output_path=str(tmp_path / "out"),
        no_rename=False,
        restore_original=False,
        info=False,
        input_file="mocked_test.pdf",
    )


@patch("pdfclassify.pdf_process.PDFSemanticClassifier")
def test_predict_success_with_mock(mock_classifier_class, temp_pdf, parsed_args):
    """Mock classifier returns successful prediction, file should be moved/renamed."""
    mock_classifier = MagicMock()
    mock_classifier.train.return_value = None
    mock_classifier.predict.return_value = type(
        "MockResult", (), {"success": True, "label": "invoice", "confidence": 0.92}
    )()

    mock_classifier_class.return_value = mock_classifier

    process = PdfProcess(str(temp_pdf))
    process.predict(parsed_args)

    moved_files = list(Path(parsed_args.output_path).glob("invoice*.pdf"))
    assert moved_files, "Expected a renamed 'invoice*.pdf' file in the output directory."


@patch("pdfclassify.pdf_process.PDFSemanticClassifier")
def test_predict_failure_with_mock(mock_classifier_class, temp_pdf, parsed_args):
    """Mock classifier returns failed prediction, file should be moved to rejects."""
    mock_classifier = MagicMock()
    mock_classifier.train.return_value = None
    mock_classifier.predict.return_value = type(
        "MockResult", (), {"success": False, "label": "unknown", "confidence": 0.2}
    )()

    mock_classifier_class.return_value = mock_classifier

    process = PdfProcess(str(temp_pdf))
    process.predict(parsed_args)

    rejects_dir = temp_pdf.parent / "pdfclassify.rejects"
    moved_files = list(rejects_dir.glob("mocked_test*.pdf"))
    assert moved_files, "Expected file moved to pdfclassify.rejects with original name."
