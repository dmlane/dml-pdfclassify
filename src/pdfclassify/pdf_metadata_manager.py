"""Module for managing PDF custom metadata with date retention."""

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter


@dataclass
class MyMetadata:
    """My custom metadata for PDF files."""

    classification: Optional[str] = None
    original_file_name: Optional[str] = None
    original_date: Optional[str] = None


class PDFMetadataManager:
    """Manage custom metadata fields in PDF files while preserving timestamps."""

    def __init__(self, input_path: Path) -> None:
        """
        Initialize the metadata manager with the path to a PDF file.

        Args:
            input_path (Path): Path to the PDF file.
        """
        self.input_path = input_path
        self.reader = PdfReader(input_path)
        self.mod_date = self.reader.metadata.get("/ModDate")
        self._original_stat = os.stat(input_path)

    def _load_metadata(self) -> dict:
        """Reload metadata from disk."""
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
    ) -> None:
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
            return

        save_path = output_path or self.input_path
        self._update_metadata({field_name: value}, save_path)

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
        self,
        new_data: dict[str, str],
        save_path: Path,
        override: bool = False,
    ) -> None:
        """
        Internal helper to write updated metadata and restore timestamps.

        Args:
            new_data (dict[str, str]): Fields to update (or full metadata if override=True).
            save_path (Path): Where to save the output file.
            override (bool): Whether to overwrite all metadata or just update fields.
        """
        writer = PdfWriter()
        writer.append_pages_from_reader(PdfReader(self.input_path))

        metadata = {} if override else self._load_metadata()
        metadata.update(new_data)

        if self.mod_date:
            metadata["/ModDate"] = self.mod_date

        writer.add_metadata(metadata)

        with open(save_path, mode="wb") as file_handle:
            writer.write(file_handle)

        os.utime(save_path, (self._original_stat.st_atime, self._original_stat.st_mtime))
