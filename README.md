# 📄 pdfclassify

> ⚠️ **WARNING: This project is under active development and is not ready for production use. APIs and functionality may change without notice.**

**pdfclassify** is a smart PDF classification and metadata management tool. It uses semantic embeddings to classify documents into labeled categories and stores custom metadata inside PDFs, such as the original filename, modification date, and classification result.

## 🚀 Features

- 📂 Automatically classifies PDF documents using semantic similarity
- 🧠 Embeds document content and caches embeddings for efficiency
- 🏷️ Writes classification and metadata directly into PDF custom fields
- 🕓 Preserves original modification times and filenames
- 🔄 Supports restoring renamed PDFs to their original state
- ✅ Includes robust unit tests and CI via GitHub Actions

## 🛠️ Installation

```bash
git clone https://github.com/dmlane/pdfclassify.git
cd pdfclassify
poetry install
```

📁 Directory Structure

src/pdfclassify/
├── main.py               # CLI entry point
├── pdf_process.py        # Core processing class
├── pdf_metadata_manager.py
├── pdf_semantic_classifier.py
├── argument_handler.py   # CLI argument parser
tests/
├── test_pdf_metadata_manager.py
├── test_pdf_semantic_classifier.py
📦 Usage

Classify a PDF file
python src/pdfclassify/main.py -o OUTPUT_DIR path/to/input.pdf
Restore a PDF to its original name and timestamp
python src/pdfclassify/main.py -r path/to/renamed.pdf
Options
Option	Description
-o	Output directory for classified PDFs
-r	Restore original filename and timestamp
🧪 Running Tests

pytest
🧹 Code Quality

Code is checked with pylint
Formatting is enforced with black and isort
Pre-commit hooks are configured in .pre-commit-config.yaml
Run locally with:

pre-commit run --all-files
🧠 Training Data

Training data must be organized into subdirectories representing labels:

training_data/
├── invoice/
│   ├── invoice_1.pdf
│   └── ...
├── report/
│   ├── report_1.pdf
│   └── ...
📁 Embedding Cache

Embeddings and hashes are stored in:

~/Library/Caches/net.dmlane/pdfclassify/
🤝 Contributing

Contributions welcome! Please:

Fork the repository
Create a branch
Add your changes with tests
Open a pull request
📝 License

This project is licensed under the MIT License. See LICENSE for details.


---

Would you like a badge section (build status, Python version, etc.) or example screenshots added as well?



