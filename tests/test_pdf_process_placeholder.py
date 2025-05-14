# tests/test_pdf_process_placeholder.py
# pylint: disable=redefined-outer-name

"""Tests for placeholder-skipping and 2OCR queue logic in PdfProcess."""

import os
import subprocess

import pytest

import pdfclassify.pdf_process as pp_mod
from pdfclassify._util import MyException
from pdfclassify.argument_handler import ParsedArgs
from pdfclassify.pdf_process import PdfProcess
from pdfclassify.pdf_semantic_classifier import PDFSemanticClassifier

PDFMetadataManager = pp_mod.PDFMetadataManager


@pytest.fixture(autouse=True)
def save_meta_invocations(monkeypatch):
    """Stub out _save_metadata and count its invocations."""
    calls = {"count": 0}

    def fake_save_metadata(*_unused_args):
        calls["count"] += 1

    monkeypatch.setattr(PdfProcess, "_save_metadata", fake_save_metadata, raising=False)
    return calls


def test_skip_zero_length_placeholder(tmp_path, monkeypatch, save_meta_invocations):
    """
    GIVEN a zero-length file with the placeholder xattr
    WHEN PdfProcess is instantiated
    THEN it raises MyException and does not save metadata.
    """
    pdf = tmp_path / "stub.pdf"
    pdf.write_bytes(b"")

    monkeypatch.setattr(os, "listxattr", lambda _: ["com.apple.placeholder"], raising=False)
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: b"", raising=False)

    with pytest.raises(MyException):
        PdfProcess(str(pdf))

    assert save_meta_invocations["count"] == 0


def test_predict_empty_text_queues_for_2ocr(tmp_path, monkeypatch):
    """
    GIVEN a non-placeholder PDF and a classifier that raises empty-text
    WHEN predict() is called
    THEN the file is moved to a pdfclassify.2ocr subdirectory
    """
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")

    # No placeholder attribute
    monkeypatch.setattr(os, "listxattr", lambda _: [], raising=False)

    # Stub out PDFMetadataManager to avoid real PDF parsing
    class DummyPDFManager:
        """Dummy manager with no-op metadata methods."""

        def __init__(self, path):
            """Initialize dummy metadata manager."""

        def read_custom_field(self, _field):
            """Return None if no field found."""
            return None

        def write_custom_field(self, *args, **kwargs):
            """No-op method."""

        def print_metadata(self):
            """No-op method."""

    monkeypatch.setattr(pp_mod, "PDFMetadataManager", DummyPDFManager, raising=False)

    # Stub classifier to simulate empty-text error
    monkeypatch.setattr(PDFSemanticClassifier, "train", lambda self: None, raising=False)

    def fake_predict(self, pdf_path, confidence_threshold):
        raise ValueError("PDF text is empty.")

    monkeypatch.setattr(PDFSemanticClassifier, "predict", fake_predict, raising=False)

    parsed_args = ParsedArgs(
        input_file=str(pdf),
        training_data_path="unused",
        no_rename=False,
        output_path=str(tmp_path),
        info=False,
        verbose=False,
        restore_original=False,
    )

    proc = PdfProcess(str(pdf))
    proc.predict(parsed_args)

    queue_dir = tmp_path / "pdfclassify.2ocr"
    assert queue_dir.is_dir(), "2OCR queue directory should exist"

    moved = list(queue_dir.iterdir())
    assert len(moved) == 1, "One file should be queued for OCR"
    assert moved[0].name.startswith("empty"), "Queued file name should match original"
    assert not pdf.exists(), "Original file should be moved out"
