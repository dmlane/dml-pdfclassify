"""Tests for the PDFSemanticClassifier using real test resources."""

# pylint: disable=redefined-outer-name

import json
import logging
import shutil
import time
from pathlib import Path

import pytest

from pdfclassify.pdf_semantic_classifier import Classification, PDFSemanticClassifier

APP_NAME = "pdfclassify"


@pytest.fixture(autouse=True)
def patch_logger_for_caplog(caplog):  # pylint: disable=unused-argument
    """Ensure the application logger outputs to stderr so caplog can capture it cleanly."""
    logger = logging.getLogger(APP_NAME)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("\n%(message)s"))  # prepend newline
    logger.addHandler(stream_handler)
    yield
    logger.removeHandler(stream_handler)


@pytest.fixture
def labeled_training_copy(tmp_path: Path) -> Path:
    """Copy labeled training data to a temporary directory."""
    source = Path(__file__).parent / "testresources" / "labeled_training_data"
    if not source.exists():
        pytest.skip("Labeled training data directory not found.")
    dest = tmp_path / "training_data"
    shutil.copytree(source, dest)
    return dest


@pytest.fixture
def classifier(labeled_training_copy: Path) -> PDFSemanticClassifier:
    """Return a classifier initialized with the copied training data."""
    return PDFSemanticClassifier(data_dir=str(labeled_training_copy))


@pytest.fixture
def invoice_test_pdf() -> Path:
    """Return the path to invoice_test.pdf."""
    return Path(__file__).parent / "testresources" / "invoice_test.pdf"


@pytest.fixture
def report_test_pdf() -> Path:
    """Return the path to report_test.pdf."""
    return Path(__file__).parent / "testresources" / "report_test.pdf"


@pytest.fixture
def unknown_test_pdf() -> Path:
    """Return the path to unknown_1.pdf."""
    return Path(__file__).parent / "testresources" / "unknown_1.pdf"


def test_train_and_predict_invoice(
    classifier: PDFSemanticClassifier, invoice_test_pdf: Path
) -> None:
    """Train and classify a known invoice document."""
    classifier.train()
    result = classifier.predict(str(invoice_test_pdf), confidence_threshold=0.1)
    assert result.success
    assert result.label == "invoice"


def test_train_and_predict_report(classifier: PDFSemanticClassifier, report_test_pdf: Path) -> None:
    """Train and classify a known report document."""
    classifier.train()
    result = classifier.predict(str(report_test_pdf), confidence_threshold=0.1)
    assert result.success
    assert result.label == "report"


def test_predict_unknown_fails(classifier: PDFSemanticClassifier, unknown_test_pdf: Path) -> None:
    """Test that an unknown document fails classification."""
    classifier.train()
    result = classifier.predict(str(unknown_test_pdf), confidence_threshold=0.95)
    assert isinstance(result, Classification)
    assert not result.success


def test_embedding_updated_on_file_change(
    classifier: PDFSemanticClassifier, labeled_training_copy: Path
) -> None:
    """Ensure modified training file updates its embedding."""
    training_dir = labeled_training_copy
    classifier.train()
    invoice_file = next((training_dir / "invoice").glob("*.pdf"))
    hash_path = classifier.hash_path

    with open(hash_path, encoding="utf-8") as f:
        before = json.load(f)

    time.sleep(1)
    invoice_file.write_text("Modified invoice text.", encoding="utf-8")

    classifier.train()
    with open(hash_path, encoding="utf-8") as f:
        after = json.load(f)

    assert before[str(invoice_file)] != after[str(invoice_file)]


def test_embedding_removed_on_file_delete(
    classifier: PDFSemanticClassifier, labeled_training_copy: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure deleted PDFs remove their embeddings."""
    training_dir = labeled_training_copy
    classifier.train()
    invoice_file = next((training_dir / "invoice").glob("*.pdf"))
    embed_path = classifier._embedding_path(str(invoice_file))  # pylint: disable=protected-access
    assert embed_path.exists()

    invoice_file.unlink()
    caplog.clear()
    with caplog.at_level("INFO"):
        classifier.train()

    assert not embed_path.exists()
    # assert any("removed:" in msg.lower() for msg in caplog.messages)
    assert any(
        "removed:" in m.lower() for m in caplog.messages
    ), "Expected 'Removed:' log not found."


def test_cache_reuse_skips_unnecessary_retraining(
    classifier: PDFSemanticClassifier, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure cache prevents redundant retraining."""
    classifier.train()

    with caplog.at_level("INFO"):
        classifier.train()

    assert not any("updated embedding" in msg.lower() for msg in caplog.messages)
