# tests/test_pdf_process_placeholder.py
# pylint: disable=redefined-outer-name

"""Tests for placeholder-skipping logic in PdfProcess.__init__."""

import os
import subprocess

import pytest

from pdfclassify._util import MyException
from pdfclassify.pdf_process import PdfProcess


@pytest.fixture(autouse=True)
def save_meta_invocations(monkeypatch):
    """Stub out _save_metadata and count its invocations."""
    calls = {"count": 0}

    def fake_save_metadata(*_unused_args):
        """Increment call count instead of saving metadata."""
        calls["count"] += 1

    # Patch PdfProcess._save_metadata; ignore if not present
    monkeypatch.setattr(PdfProcess, "_save_metadata", fake_save_metadata, raising=False)
    return calls


def test_skip_zero_length_placeholder(tmp_path, monkeypatch, save_meta_invocations):
    """
    GIVEN a zero-length file with the placeholder xattr
    WHEN PdfProcess is instantiated
    THEN it raises MyException and does not save metadata.
    """
    pdf_file = tmp_path / "stub.pdf"
    pdf_file.write_bytes(b"")

    # Simulate placeholder attribute
    monkeypatch.setattr(os, "listxattr", lambda _: ["com.apple.placeholder"], raising=False)
    # Stub subprocess fallback
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: b"", raising=False)

    with pytest.raises(MyException):
        PdfProcess(str(pdf_file))

    # Ensure metadata save was never called
    assert save_meta_invocations["count"] == 0


def test_process_non_placeholder(tmp_path, monkeypatch, save_meta_invocations):
    """
    GIVEN a non-zero PDF file without placeholder xattr
    WHEN PdfProcess is instantiated
    THEN it constructs successfully and calls _save_metadata once.
    """
    pdf_file = tmp_path / "real.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%EOF")

    # No placeholder attribute
    monkeypatch.setattr(os, "listxattr", lambda _: [], raising=False)
    # Stub subprocess fallback
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: b"", raising=False)

    instance = PdfProcess(str(pdf_file))

    assert isinstance(instance, PdfProcess)
    assert save_meta_invocations["count"] == 1
