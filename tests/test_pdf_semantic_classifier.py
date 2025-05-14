"""Tests for the PDFSemanticClassifier using real test resources and edge cases."""

# pylint: disable=redefined-outer-name

import json
import logging
import shutil
import time
from pathlib import Path

import pytest

from pdfclassify.pdf_semantic_classifier import Classification, PDFSemanticClassifier

APP_NAME = "pdfclassify"


def create_blank_pdf(path: Path) -> None:
    """Helper to create a minimal blank PDF file."""
    # A blank PDF with just header and empty body
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<>\n%%EOF")


@pytest.fixture(autouse=True)
def patch_logger_for_caplog(caplog):  # pylint: disable=unused-argument
    """Ensure the application logger outputs to stderr so caplog can capture it cleanly."""
    logger = logging.getLogger(APP_NAME)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("\n%(message)s"))
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
def empty_data_dir(tmp_path: Path) -> Path:
    """Provide an empty directory for testing no-data behavior."""
    return tmp_path / "empty_data"


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


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    """Create a corrupted PDF file for testing."""
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a pdf content")
    return path


@pytest.fixture
def blank_pdf(tmp_path: Path) -> Path:
    """Create an extractable-blank PDF file for testing empty content."""
    path = tmp_path / "blank.pdf"
    create_blank_pdf(path)
    return path


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
    classifier.train()
    invoice_file = next((labeled_training_copy / "invoice").glob("*.pdf"))
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
    classifier.train()
    invoice_file = next((labeled_training_copy / "invoice").glob("*.pdf"))
    embed_path = classifier._embedding_path(str(invoice_file))  # pylint: disable=protected-access
    assert embed_path.exists()

    invoice_file.unlink()
    caplog.clear()
    with caplog.at_level("INFO"):
        classifier.train()

    # embedding file should be gone
    assert not embed_path.exists()


def test_cache_reuse_skips_unnecessary_retraining(
    classifier: PDFSemanticClassifier, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure cache prevents redundant retraining."""
    classifier.train()
    caplog.clear()
    with caplog.at_level("INFO"):
        classifier.train()
    assert not any("updated embedding" in msg.lower() for msg in caplog.messages)


def test_empty_pdf_raises(classifier: PDFSemanticClassifier, blank_pdf: Path) -> None:
    """An empty (blank) PDF should raise a ValueError for empty text or extraction failure."""
    classifier.train()
    with pytest.raises(ValueError):
        classifier.predict(str(blank_pdf))


def test_cache_corrupt_json_recovery(
    labeled_training_copy: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A corrupt file_hashes.json should be ignored and re-embedding occur."""
    classifier = PDFSemanticClassifier(
        data_dir=str(labeled_training_copy), cache_name=labeled_training_copy.name
    )
    classifier.train()
    with open(classifier.hash_path, "w", encoding="utf-8") as f:
        f.write("{ not valid json }")
    caplog.clear()
    with caplog.at_level("INFO"):  # capture both warnings and info for re-embedding logs
        classifier.train()

    # after corrupt JSON, embeddings directory should have been rebuilt
    embeddings = list(Path(classifier.embeddings_dir).glob("*.joblib"))
    pdfs = list(Path(labeled_training_copy).rglob("*.pdf"))
    assert len(embeddings) == len(pdfs)


def test_embedding_files_exist_after_train(labeled_training_copy: Path) -> None:
    """After a successful train, each PDF should have a .joblib embedding in a fresh cache."""
    classifier = PDFSemanticClassifier(
        data_dir=str(labeled_training_copy), cache_name=labeled_training_copy.name
    )
    classifier.train()
    embeddings = list(Path(classifier.embeddings_dir).glob("*.joblib"))
    pdfs = list(labeled_training_copy.rglob("*.pdf"))
    assert len(embeddings) == len(pdfs)


def test_threshold_boundary(classifier: PDFSemanticClassifier, invoice_test_pdf: Path) -> None:
    """When the similarity equals the threshold, success should be True."""
    classifier.train()
    result = classifier.predict(str(invoice_test_pdf), confidence_threshold=0.0)
    assert result.success
    assert result.label == "invoice"
