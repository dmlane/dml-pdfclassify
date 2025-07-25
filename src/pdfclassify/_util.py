"""Utility classes and functions"""

import argparse
import logging
import textwrap
from pathlib import Path

from pdfminer.high_level import extract_text

from pdfclassify.config import PDFClassifyConfig

logging.getLogger("pdfminer").setLevel(logging.ERROR)
# Load config once only and make it available throughout the application
CONFIG = PDFClassifyConfig()


class MyException(Exception):
    """Custom exception with exit code for controlled termination."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class RawFormatter(argparse.HelpFormatter):
    """Help formatter to split the text on newlines and indent each line"""

    def _fill_text(self, text, width, indent):
        """Split the text on newlines and indent each line"""
        return "\n".join(
            [
                textwrap.fill(line, width)
                for line in textwrap.indent(textwrap.dedent(text), indent).splitlines()
            ]
        )


# in _util.py


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text using pdfminer.six (better layout/text coverage)."""
    try:
        return extract_text(str(pdf_path)) or ""
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"⚠️ PDF text extraction failed: {e}")
        return ""
