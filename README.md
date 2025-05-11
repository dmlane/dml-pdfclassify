# 📄 pdfclassify

⚠️ **WARNING: This project is under active development and is not ready for production use. APIs and functionality may change without notice.**

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

## 🛠️ Configuration

PDFClassify uses a TOML configuration file to set default paths and thresholds.

### Default Config File

If present, the following file will be loaded automatically:

- `~/.config/pdfclassify/pdfclassify.toml`

If not present, the project will fall back to an internal default bundled with the package.

### Example `pdfclassify.toml`

```toml
# Default output directory where processed PDFs will be saved
output_dir = "~/Documents/pdfclassify/output"

# Directory containing labeled training PDFs (used for training classifier)
training_data_dir = "~/.config/pdfclassify/training_data"

# Directory where cached embeddings and model files will be stored
cache_dir = "~/.cache/pdfclassify"

[settings]
# Confidence threshold for classification (0.0 to 1.0)
confidence_threshold = 0.75
```

### Path Expansion

Paths may include:

- `~` or `$HOME` to refer to the user's home directory
- `APPDIR:cache`, `APPDIR:config`, or `APPDIR:data` to refer to platform-appropriate directories provided by `platformdirs`

For example:

```toml
output_dir = "APPDIR:data/output"
training_data_dir = "APPDIR:config/training_data"
```

These will be expanded at runtime using `platformdirs` to resolve to user-specific directories.

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

## 📝 Legal Disclaimer

This software is provided "as is", without warranty of any kind, express or implied. Use at your own risk. The authors disclaim all liability for any damages arising from the use of this software.

You are responsible for ensuring this software meets your requirements and complies with applicable laws and data privacy regulations.

---

For questions or issues, please [open an issue](https://github.com/dmlane/pdfclassify/issues).

## 📝 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
