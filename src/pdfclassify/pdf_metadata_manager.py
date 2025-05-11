"""Module for managing PDF custom metadata with date retention."""

import os
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject


def _format_pdf_date(dt_str: str) -> str:
    if dt_str.startswith("D:") and len(dt_str) >= 16:
        # Already PDF-style format: return as-is to avoid corruption
        return dt_str
    # Assume ISO format and convert
    dt = datetime.fromisoformat(dt_str)
    return f"D:{dt.strftime('%Y%m%d%H%M%S')}"


@dataclass
class MyMetadata:
    """My custom metadata for PDF files."""

    classification: Optional[str] = None
    original_file_name: Optional[str] = None
    original_date: Optional[str] = None


class PDFMetadataManager:
    """Manage custom metadata fields in PDF files while preserving timestamps."""

    def __init__(self, input_path: Path) -> None:
        self.input_path = input_path
        self.reader = PdfReader(input_path)
        self.mod_date = self.reader.metadata.get("/ModDate")
        self._original_stat = os.stat(input_path)

    def _load_metadata(self) -> dict:
        return PdfReader(self.input_path).metadata or {}

    def print_metadata(self) -> None:
        """Print the metadata of the PDF in a visually enhanced format."""
        bold = "\033[1m"
        reset = "\033[0m"
        dim = "\033[2m"
        cyan = "\033[36m"

        metadata = MyMetadata(
            classification=self.read_custom_field("/Classification"),
            original_file_name=self.read_custom_field("/Original_Filename"),
            original_date=self.read_custom_field("/Original_Date"),
        )

        print(f"{bold}Custom metadata for {self.input_path}:{reset}")
        print("-" * 40)

        max_len = max(len(f.name) for f in fields(metadata))
        for field in fields(metadata):
            name = f"{bold}{field.name:<{max_len}}{reset}"
            value = getattr(metadata, field.name)
            display = str(value) if value is not None else f"{dim}–{reset}"
            print(f"{cyan}{name}{reset} : {display}")

    def read_custom_field(self, field_name: str) -> Optional[str]:
        """
        Read a custom metadata field from the PDF.

        Args:
            field_name (str): The name of the metadata field (e.g., "/Classification").

        Returns:
            Optional[str]: The value of the field, or None if not found.
        """
        return self._load_metadata().get(field_name)

    def write_custom_field(
        self,
        field_name: str,
        value: str,
        output_path: Optional[Path] = None,
        overwrite: bool = True,
    ) -> bool:
        """
        Write or update a custom metadata field in the PDF.

        Args:
            field_name (str): The name of the metadata field.
            value (str): The value to assign to the field.
            output_path (Optional[Path]): Path to save the updated PDF. Overwrites original if None.
            overwrite (bool): If False, do not overwrite field if it already exists.
        """
        current_metadata = self._load_metadata()
        if not overwrite and field_name in current_metadata:
            return False
        save_path = output_path or self.input_path
        self._update_metadata({field_name: value}, save_path, override=False)
        return True

    def delete_custom_field(self, field_name: str, output_path: Optional[Path] = None) -> None:
        """
        Delete a custom metadata field from the PDF.

        Args:
            field_name (str): The name of the field to delete.
            output_path (Optional[Path]): Path to save the updated PDF. Overwrites original if None.
        """
        current_metadata = self._load_metadata()
        if field_name not in current_metadata:
            return
        updated_metadata = current_metadata.copy()
        updated_metadata.pop(field_name, None)
        save_path = output_path or self.input_path
        self._update_metadata(updated_metadata, save_path, override=True)

    def _update_metadata(
        self, new_data: dict[str, str], save_path: Path, override: bool = False
    ) -> None:
        writer = PdfWriter()
        reader = PdfReader(self.input_path)  # Re-read to avoid stale state
        writer.append_pages_from_reader(reader)

        metadata = {}
        if not override:
            existing_metadata = reader.metadata or {}
            metadata.update(
                {
                    NameObject(k): TextStringObject(str(v))
                    for k, v in existing_metadata.items()
                    if isinstance(k, str) and v is not None
                }
            )

        for k, v in new_data.items():
            metadata[NameObject(k)] = TextStringObject(str(v))

        if self.mod_date:
            metadata[NameObject("/ModDate")] = TextStringObject(_format_pdf_date(self.mod_date))

        writer.add_metadata(metadata)

        with open(save_path, "wb") as f:
            writer.write(f)

        os.utime(save_path, (self._original_stat.st_atime, self._original_stat.st_mtime))
