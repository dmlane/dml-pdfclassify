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

            # try Python API first
            try:
                xattrs = os.listxattr(self.pdf_file)
            except (AttributeError, NotImplementedError):
                # fallback: xattr lists only names when no -l flag is given
                raw = subprocess.check_output(
                    ["xattr", str(self.pdf_file)], stderr=subprocess.DEVNULL
                )
                # decode loosely to avoid errors
                names = raw.decode("utf-8", errors="ignore").splitlines()
                xattrs = names

            if size == 0 and "com.apple.placeholder" in xattrs:
                raise MyException(f"Skipping zero-length placeholder PDF: {pdf_path}", 4)
        except OSError:
            # e.g. permission error — ignore and let later code handle
            pass

        # proceed with the existing metadata save
        try:
            self._save_metadata()
        except PdfReadError as e:
            raise MyException(f"Invalid PDF file: {e}", 2) from e

    def display_info(self) -> None:
        """Display metadata and info about the file"""
        pdf_manager = PDFMetadataManager(self.pdf_file)
        pdf_manager.print_metadata()

    def _save_metadata(self) -> None:
        """Save details about the file in custom metadata fields."""
        try:
            pdf_manager = PDFMetadataManager(self.pdf_file)
            mod_time = os.path.getmtime(self.pdf_file)
            mod_date_str = datetime.fromtimestamp(mod_time).isoformat()

            existing = {
                "/Original_Filename": pdf_manager.read_custom_field("/Original_Filename"),
                "/Original_Date": pdf_manager.read_custom_field("/Original_Date"),
            }

            if existing["/Original_Filename"] is None:
                pdf_manager.write_custom_field("/Original_Filename", self.pdf_file.name)

            if existing["/Original_Date"] is None:
                pdf_manager.write_custom_field("/Original_Date", mod_date_str)

        except PdfReadError as e:
            raise MyException(f"Invalid PDF file: {e}", 2) from e
        except Exception as e:
            raise MyException(f"Unexpected error during metadata save: {e}", 3) from e

    def restore_original_state(self) -> None:
        """Restore the original file name and timestamp from custom metadata"""
        pdf_manager = PDFMetadataManager(self.pdf_file)
        original_file_name = pdf_manager.read_custom_field("/Original_Filename")
        original_date = pdf_manager.read_custom_field("/Original_Date")
        if original_file_name is not None:
            new_file_name = Path(original_file_name).name
            new_path = self.pdf_file.parent / new_file_name
            self.pdf_file.rename(new_path)
            self.pdf_file = new_path

        if original_date is not None:
            mod_time = datetime.fromisoformat(original_date).timestamp()
            os.utime(self.pdf_file, (mod_time, mod_time))

    def predict(self, args: ParsedArgs) -> None:
        """Predict the label of the pdf using the trained classifier"""
        pdf_manager = PDFMetadataManager(self.pdf_file)
        classifier = PDFSemanticClassifier(data_dir=args.training_data_path)
        classifier.train()
        label = classifier.predict(
            pdf_path=str(self.pdf_file),
            confidence_threshold=CONFIG.confidence_threshold,
        )
        print(
            f"Predicted label: {label.label} with confidence "
            + f"{label.confidence:.2f} Success={label.success}%"
        )
        if label.success:
            # Update custom metadata with the predicted label
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
        """
        Perform actions based on the classification result.

        - If prediction.success is True:
            - Rename the file to "<label>.pdf" and move it to output_path.
            - Append a counter if the target file exists.

        - If prediction.success is False:
            - Keep original filename.
            - Move it to a "pdfclassify.rejects" subdirectory.
            - Append a counter if the file already exists.
            - Output filename extension is always ".pdf".

        Args:
            file_name (Path): Path to the original PDF file.
            prediction (Classification): The result of the classification.
            rename (bool): Whether to rename the file based on prediction.
            output_path (Path, optional): Directory to move renamed file if successful.

        Returns:
            Path: The final path the file was moved to, or None if not renamed.
        """
        if not rename:
            return None

        suffix = ".pdf"
        original_stem = file_name.stem  # Always start from the original name

        if prediction.success:
            base_dir = output_path if output_path else file_name.parent
            new_stem = prediction.label
        else:
            base_dir = file_name.parent / "pdfclassify.rejects"
            new_stem = original_stem

        base_dir.mkdir(parents=True, exist_ok=True)

        new_path = base_dir / f"{new_stem}{suffix}"
        counter = 1
        while new_path.exists():
            new_path = base_dir / f"{new_stem}_{counter}{suffix}"
            counter += 1

        shutil.move(str(file_name), new_path)
        return new_path
