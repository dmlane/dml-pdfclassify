"""Module for managing sidecar metadata for PDFs using a JSON file."""

import hashlib
import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional, Union

import numpy as np
from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass
class MyMetadata:
    """Custom metadata for PDF sidecar files."""

    classification: Optional[str] = None
    original_file_name: Optional[str] = None
    original_date: Optional[str] = None
    confidence: Optional[float] = None
    sha256: Optional[str] = None
    preferred_context: Optional[list[str]] = None


class PDFMetadataManager:
    """
    Manage custom metadata for a PDF via a sidecar JSON file.

    Sidecar is stored as <filename>.meta.json alongside the PDF.
    """

    def __init__(self, input_path: Path) -> None:
        self.input_path = input_path
        self.sidecar_path = input_path.with_suffix(input_path.suffix + ".meta.json")

        try:
            PdfReader(str(input_path))
        except Exception as e:
            raise PdfReadError(f"Invalid PDF file: {input_path}") from e

    def _calculate_pdf_hash(self) -> str:
        """Calculate SHA-256 hash of the PDF file."""
        hasher = hashlib.sha256()
        with self.input_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _load_metadata(self) -> dict:
        if self.sidecar_path.exists():
            with self.sidecar_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_metadata(self, metadata: dict) -> None:
        """Save metadata to the sidecar file."""
        metadata["/sha256"] = self._calculate_pdf_hash()
        with self.sidecar_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def print_metadata(self) -> None:
        """Print the metadata in a visually enhanced format."""
        bold = "\033[1m"
        reset = "\033[0m"
        dim = "\033[2m"
        cyan = "\033[36m"

        metadata = self.get_structured_metadata()

        print(f"{bold}Custom metadata for {self.input_path.name}:{reset}")
        print("-" * 40)

        max_len = max(len(f.name) for f in fields(metadata))
        for field in fields(metadata):
            name = f"{bold}{field.name:<{max_len}}{reset}"
            value = getattr(metadata, field.name)
            display = str(value) if value is not None else f"{dim}–{reset}"
            print(f"{cyan}{name}{reset} : {display}")

    def get_structured_metadata(self) -> MyMetadata:
        """Load sidecar metadata into a structured dataclass."""
        data = self._load_metadata()
        return MyMetadata(**{f.name: data.get("/" + f.name.lower()) for f in fields(MyMetadata)})

    def read_custom_field(self, field_name: str) -> Optional[Union[str, float, int]]:
        """
        Read a custom field from the sidecar.

        Args:
            field_name (str): Field name (e.g., "/Classification")

        Returns:
            Optional[str]: The value, or None if missing
        """
        return self._load_metadata().get(field_name)

    def write_custom_field(
        self,
        field_name: str,
        value: str | float | int | list[str],
        overwrite: bool = True,
    ) -> bool:
        """
        Write or update a custom metadata field in the sidecar.

        Args:
            field_name (str): The name of the field (e.g., "/classification")
            value (str | float | int | list[str]): The value to set
            overwrite (bool): If False, will skip writing if field exists

        Returns:
            bool: True if written, False if skipped
        """
        metadata = self._load_metadata()
        if not overwrite and field_name in metadata:
            return False

        # Coerce value to JSON-safe types
        if isinstance(value, (np.floating, float)):
            value = float(value)
        elif isinstance(value, (np.integer, int)):
            value = int(value)
        elif isinstance(value, list):
            value = [str(v) for v in value]
        else:
            value = str(value)

        metadata[field_name.lower()] = value

        self._save_metadata(metadata)
        return True

    def delete_custom_field(self, field_name: str) -> None:
        """
        Delete a field from the sidecar metadata, if present.

        Args:
            field_name (str): The field name to delete
        """
        metadata = self._load_metadata()
        if field_name in metadata:
            metadata.pop(field_name)
            self._save_metadata(metadata)

    def rename_with_sidecar(self, new_name: str | Path) -> Path:
        """
        Rename or move the PDF and its sidecar file to match the new name.
        Raises an error if the sidecar's hash does not match the PDF.

        Args:
            new_name (str | Path): New file name or path (e.g., 'invoice.pdf' or
            '/new/path/invoice.pdf')

        Returns:
            Path: The new path to the renamed PDF
        """
        new_pdf_path = Path(new_name).with_suffix(".pdf")
        new_sidecar_path = new_pdf_path.with_suffix(new_pdf_path.suffix + ".meta.json")

        # Ensure target directory exists
        new_pdf_path.parent.mkdir(parents=True, exist_ok=True)

        # Check sidecar validity before renaming
        if self.sidecar_path.exists():
            if not self.verify_pdf_hash():
                raise ValueError(f"PDF hash does not match metadata in {self.sidecar_path}")
            self.sidecar_path.rename(new_sidecar_path)

        self.input_path.rename(new_pdf_path)

        # Update internal state
        self.input_path = new_pdf_path
        self.sidecar_path = new_sidecar_path
        return new_pdf_path

    def verify_pdf_hash(self) -> bool:
        """Verify that the current PDF matches the SHA-256 hash in the sidecar."""
        stored = self.read_custom_field("/sha256")
        if not stored:
            return False
        return stored == self._calculate_pdf_hash()
