#!/usr/bin/env python3
"""
PDF Classification Verifier with:
- Progress counter (top)
- Status message (bottom)
- Skip reviewed files (unless --all)
- Vertical scroll, auto width scaling
- Review status (✅/❌)
- Undo & date renaming
- Keyboard shortcuts (works on macOS)
- --help for usage and shortcuts
- In-GUI Help button showing shortcuts
"""

import argparse
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

ACTIONS_STACK = []

# ========= Keyboard Shortcuts Help =========
SHORTCUTS = """
Keyboard Shortcuts:
  ← / →    : Previous / Next page
  C / Enter: Confirm current file
  R        : Reject current file
  U        : Undo last action
  N / Space: Next file
  D        : Change date in filename
  Q        : Quit
"""


class PDFReviewer(QWidget):
    DATE_PATTERN = re.compile(r"(.*_)(\d{4}(?:\d{2}(?:\d{2})?)?)\.pdf$", re.IGNORECASE)

    def __init__(self, folder: Path, review_all: bool):
        super().__init__()
        self.folder = folder
        self.review_all = review_all
        self.pdf_files = self._collect_pdfs()
        self.current_index = 0
        self.current_page = 0
        self.doc = None
        self.rendered_pixmap = None
        self._image_buffer = None

        self.setFocusPolicy(Qt.StrongFocus)
        self.setWindowTitle("PDF Classification Verifier")
        self.resize(900, 1000)

        # ========= Layout =========
        main_layout = QVBoxLayout()

        # Top progress label
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.progress_label)

        # Scrollable PDF display
        self.scroll_area = QScrollArea()
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.pdf_label)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # Bottom status line (moved here)
        self.status_line = QLabel("Ready")
        self.status_line.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_line)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.btn_prev_page = QPushButton("◀ Page")
        self.btn_next_page = QPushButton("Page ▶")
        self.btn_confirm = QPushButton("✅ Confirm")
        self.btn_reject = QPushButton("❌ Reject")
        self.btn_undo = QPushButton("↩ Undo")
        self.btn_change_date = QPushButton("📅 Change Date")
        self.btn_help = QPushButton("❔ Help")
        self.btn_next_file = QPushButton("Next ➡")

        for b in [
            self.btn_prev_page,
            self.btn_next_page,
            self.btn_confirm,
            self.btn_reject,
            self.btn_undo,
            self.btn_change_date,
            self.btn_help,
            self.btn_next_file,
        ]:
            btn_layout.addWidget(b)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

        # ========= Button Bindings =========
        self.btn_prev_page.clicked.connect(self.prev_page)
        self.btn_next_page.clicked.connect(self.next_page)
        self.btn_confirm.clicked.connect(lambda: self.set_status("confirmed"))
        self.btn_reject.clicked.connect(lambda: self.set_status("rejected"))
        self.btn_undo.clicked.connect(self.undo_action)
        self.btn_change_date.clicked.connect(self.change_date)
        self.btn_next_file.clicked.connect(self.next_file)
        self.btn_help.clicked.connect(self.show_shortcuts)

        # Load first PDF
        self.load_current_pdf()

    # ========= Collect PDFs =========
    def _collect_pdfs(self):
        pdfs = sorted(self.folder.glob("*.pdf"))
        return [p for p in pdfs if not self._has_review_status(p)] if not self.review_all else pdfs

    def _has_review_status(self, pdf_path: Path) -> bool:
        sidecar = pdf_path.with_name(f"{pdf_path.name}.meta.json")
        if sidecar.exists():
            try:
                return "review_status" in json.loads(sidecar.read_text())
            except json.JSONDecodeError:
                return False
        return False

    # ========= PDF Rendering =========
    def load_current_pdf(self):
        if self.current_index >= len(self.pdf_files):
            self.progress_label.setText("All PDFs reviewed ✅")
            self.status_line.setText("")
            self.pdf_label.clear()
            return
        pdf_path = self.get_current_pdf()
        self.doc = fitz.open(pdf_path)
        self.current_page = 0
        self.render_current_page()
        self.setFocus()

    def render_current_page(self):
        page = self.doc[self.current_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        self._image_buffer = bytes(pix.samples)
        fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
        img = QImage(self._image_buffer, pix.width, pix.height, pix.stride, fmt).copy()
        self.rendered_pixmap = QPixmap.fromImage(img)
        self.update_displayed_image()
        self.update_status_bar()

    def update_displayed_image(self):
        if self.rendered_pixmap:
            scaled = self.rendered_pixmap.scaledToWidth(
                self.scroll_area.viewport().width(), Qt.SmoothTransformation
            )
            self.pdf_label.setPixmap(scaled)
            self.pdf_label.adjustSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_displayed_image()

    # ========= Navigation =========
    def next_page(self):
        if self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.render_current_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_current_page()

    def next_file(self):
        self.current_index += 1
        self.load_current_pdf()

    # ========= Utilities =========
    def get_current_pdf(self):
        return self.pdf_files[self.current_index]

    def get_sidecar(self):
        return self.get_current_pdf().with_name(f"{self.get_current_pdf().name}.meta.json")

    def current_pdf_name(self):
        return self.get_current_pdf().name

    # ========= Status Handling =========
    def read_status(self):
        s = self.get_sidecar()
        if s.exists():
            try:
                return json.loads(s.read_text()).get("review_status")
            except json.JSONDecodeError:
                return None
        return None

    def write_status(self, status):
        sidecar = self.get_sidecar()
        backup = sidecar.read_text() if sidecar.exists() else "{}"
        ACTIONS_STACK.append((self.current_index, backup))

        try:
            data = json.loads(backup) if backup.strip() else {}
        except json.JSONDecodeError:
            data = {}

        data["review_status"] = status
        sidecar.write_text(json.dumps(data, indent=2))

    def set_status(self, status):
        self.write_status(status)
        self.status_line.setText(f"{self.current_pdf_name()} marked {status}")
        self.next_file()

    def undo_action(self):
        if not ACTIONS_STACK:
            self.status_line.setText("Nothing to undo.")
            return
        idx, backup = ACTIONS_STACK.pop()
        sidecar = self.pdf_files[idx].with_name(f"{self.pdf_files[idx].name}.meta.json")
        sidecar.write_text(backup)
        self.current_index = idx
        self.load_current_pdf()
        self.status_line.setText(f"Undo applied to {self.current_pdf_name()}")

    def update_status_bar(self):
        total = len(self.pdf_files)
        st = self.read_status()
        icon = "✅" if st == "confirmed" else ("❌" if st == "rejected" else "")
        self.progress_label.setText(
            f"File {self.current_index+1} / {total} – {self.current_pdf_name()} {icon}"
        )

    # ========= 📅 Change Date =========
    def change_date(self):
        pdf_path = self.get_current_pdf()
        match = self.DATE_PATTERN.match(pdf_path.name)
        if not match:
            QMessageBox.warning(self, "Rename Failed", "Filename does not match expected pattern.")
            return

        prefix, old_date = match.groups()
        new_date, ok = QInputDialog.getText(
            self, "Change Date", "Enter new date (YYYY, YYYYMM, YYYYMMDD):", text=old_date
        )
        if not ok or not new_date:
            return
        if not re.fullmatch(r"\d{4}|\d{6}|\d{8}", new_date):
            QMessageBox.warning(self, "Invalid Format", "Date must be YYYY, YYYYMM, or YYYYMMDD.")
            return

        new_name = f"{prefix}{new_date}.pdf"
        new_pdf = pdf_path.with_name(new_name)

        pdf_path.rename(new_pdf)
        old_sidecar = pdf_path.with_name(f"{pdf_path.name}.meta.json")
        if old_sidecar.exists():
            old_sidecar.rename(new_pdf.with_name(f"{new_pdf.name}.meta.json"))

        self.pdf_files[self.current_index] = new_pdf
        self.status_line.setText(f"Renamed to {new_name}")

    # ========= In-GUI Help =========
    def show_shortcuts(self):
        QMessageBox.information(self, "Keyboard Shortcuts", SHORTCUTS)

    # ========= Keyboard Shortcuts =========
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_Left:
            self.prev_page()
        elif key == Qt.Key_Right:
            self.next_page()
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_C):
            self.set_status("confirmed")
        elif key == Qt.Key_R:
            self.set_status("rejected")
        elif key == Qt.Key_U:
            self.undo_action()
        elif key in (Qt.Key_N, Qt.Key_Space):
            self.next_file()
        elif key == Qt.Key_D:
            self.change_date()
        elif key == Qt.Key_Q:
            self.close()
        else:
            super().keyPressEvent(event)


# ========= CLI =========
def parse_args():
    parser = argparse.ArgumentParser(
        description="Review classified PDFs, confirm/reject, and update sidecar metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=SHORTCUTS,
    )
    parser.add_argument("folder", nargs="?", help="Folder containing classified PDFs")
    parser.add_argument(
        "--all", action="store_true", help="Review all PDFs (including already reviewed)"
    )
    return parser.parse_args()


# ========= Entry Point =========
def main():
    args = parse_args()
    app = QApplication(sys.argv)
    folder = (
        Path(args.folder)
        if args.folder
        else Path(QFileDialog.getExistingDirectory(None, "Select Classified PDFs"))
    )
    if not folder or not folder.exists():
        print("No folder selected or folder does not exist.")
        sys.exit(1)
    viewer = PDFReviewer(folder, args.all)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
