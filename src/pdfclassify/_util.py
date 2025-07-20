"""Utility classes and functions"""

import argparse
import textwrap
from pathlib import Path

from pypdf import PdfReader

from pdfclassify.config import PDFClassifyConfig

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


def extract_text_from_pdf(pdf_file: Path) -> str:
    """Extract all text from a PDF using pypdf."""
    reader = PdfReader(str(pdf_file))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
