# 📄 pdfclassify

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

## 📁 Directory Structure

```text
src/pdfclassify/
├── main.py               # CLI entry point
├── pdf_process.py        # Core processing class
├── pdf_metadata_manager.py
├── pdf_semantic_classifier.py
├── argument_handler.py   # CLI argument parser
tests/
├── test_pdf_metadata_manager.py
├── test_pdf_semantic_classifier.py
```

## 📦 Usage

### Classify a PDF file

```bash
python src/pdfclassify/main.py -o OUTPUT_DIR path/to/input.pdf
```

### Restore a PDF to its original name and timestamp

```bash
python src/pdfclassify/main.py -r path/to/renamed.pdf
```

### Options

| Option | Description |
|--------|-------------|
| `-o`   | Output directory for classified PDFs |
| `-r`   | Restore original filename and timestamp |

## 🧪 Running Tests

```bash
pytest
```

## 🧹 Code Quality

- Code is checked with `pylint`
- Formatting is enforced with `black` and `isort`
- Pre-commit hooks are configured in `.pre-commit-config.yaml`

Run locally with:

```bash
pre-commit run --all-files
```

## 🧠 Training Data

Training data must be organized into subdirectories representing labels:

```
training_data/
├── invoice/
│   ├── invoice_1.pdf
│   └── ...
├── report/
│   ├── report_1.pdf
│   └── ...
```

## 📁 Embedding Cache

Embeddings and hashes are stored in:

```bash
~/Library/Caches/net.dmlane/pdfclassify/
```

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a branch
3. Add your changes with tests
4. Open a pull request

## 📝 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
