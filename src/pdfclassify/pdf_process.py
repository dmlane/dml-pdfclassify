"""Manipulate the name and/or metadata of a pdf."""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from pypdf.errors import PdfReadError

from pdfclassify._util import CONFIG, MyException
from pdfclassify.argument_handler import ParsedArgs
from pdfclassify.pdf_metadata_manager import PDFMetadataManager
from pdfclassify.pdf_semantic_classifier import Classification, PDFSemanticClassifier


class PdfProcess:
    """Process a PDF file with the specified operations."""

    def __init__(self, pdf_path: str):
        self.pdf_file = Path(pdf_path)
        if not self.pdf_file.is_file():
            raise MyException(f"File {pdf_path} does not exist", 1)

        # ── skip zero-length iCloud placeholder PDFs ──
        try:
            size = self.pdf_file.stat().st_size
            try:
                xattrs = os.listxattr(self.pdf_file)
            except (AttributeError, NotImplementedError):
                raw = subprocess.check_output(
                    ["xattr", str(self.pdf_file)], stderr=subprocess.DEVNULL
                )
                xattrs = raw.decode("utf-8", errors="ignore").splitlines()
            if size == 0 and "com.apple.placeholder" in xattrs:
                raise MyException(f"Skipping zero-length placeholder PDF: {pdf_path}", 4)
        except OSError:
            pass

        try:
            self._save_metadata()
        except PdfReadError as e:
            raise MyException(f"Invalid PDF file: {e}", 2) from e

    def display_info(self) -> None:
        """Display metadata and info about the file"""
        PDFMetadataManager(self.pdf_file).print_metadata()

    def _save_metadata(self) -> None:
        """Save details about the file in custom metadata fields."""
        try:
            pdf_manager = PDFMetadataManager(self.pdf_file)
            mod_date = datetime.fromtimestamp(self.pdf_file.stat().st_mtime).isoformat()
            if pdf_manager.read_custom_field("/Original_Filename") is None:
                pdf_manager.write_custom_field("/Original_Filename", self.pdf_file.name)
            if pdf_manager.read_custom_field("/Original_Date") is None:
                pdf_manager.write_custom_field("/Original_Date", mod_date)
        except PdfReadError as e:
            raise MyException(f"Invalid PDF file: {e}", 2) from e
        except Exception as e:
            raise MyException(f"Unexpected error during metadata save: {e}", 3) from e

    def restore_original_state(self) -> None:
        """Restore the original file name and timestamp from custom metadata"""
        pdf_manager = PDFMetadataManager(self.pdf_file)
        orig_name = pdf_manager.read_custom_field("/Original_Filename")
        orig_date = pdf_manager.read_custom_field("/Original_Date")
        if orig_name:
            new_path = self.pdf_file.with_name(Path(orig_name).name)
            self.pdf_file.rename(new_path)
            self.pdf_file = new_path
        if orig_date:
            ts = datetime.fromisoformat(orig_date).timestamp()
            os.utime(self.pdf_file, (ts, ts))

    def predict(self, args: ParsedArgs) -> None:
        """Predict the label of the pdf using the trained classifier"""
        pdf_manager = PDFMetadataManager(self.pdf_file)
        classifier = PDFSemanticClassifier(data_dir=args.training_data_path)
        classifier.train()
        try:
            label = classifier.predict(
                pdf_path=str(self.pdf_file),
                confidence_threshold=CONFIG.confidence_threshold,
            )
        except ValueError as e:
            if "empty" in str(e).lower():
                print(f"⚠️ Skipping '{self.pdf_file.name}': PDF text is empty.")
                return
            raise
        print(
            f"Predicted label: {label.label} with confidence {label.confidence:.2f} "
            f"Success={label.success}%"
        )
        if label.success:
            pdf_manager.write_custom_field(
                field_name="/Classification", value=label.label, overwrite=True
            )
        new_path = self.take_action(
            file_name=self.pdf_file,
            prediction=label,
            rename=not args.no_rename,
            output_path=Path(args.output_path),
        )
        if new_path:
            print(f"File moved to: {new_path}")

    def take_action(
        self,
        file_name: Path,
        prediction: Classification,
        rename: bool = True,
        output_path: Path = None,
    ):
        """Perform actions based on the classification result."""
        if not rename:
            return None
        suffix = ".pdf"
        base_dir = output_path if prediction.success else file_name.parent / "pdfclassify.rejects"
        stem = prediction.label if prediction.success else file_name.stem
        base_dir.mkdir(parents=True, exist_ok=True)
        target = base_dir / f"{stem}{suffix}"
        count = 1
        while target.exists():
            target = base_dir / f"{stem}_{count}{suffix}"
            count += 1
        shutil.move(str(file_name), target)
        return target
