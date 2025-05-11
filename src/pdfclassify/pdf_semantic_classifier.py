"""Multilingual PDF Semantic Classifier

This module defines a single class:
- PDFSemanticClassifier: Uses multilingual embeddings and cosine similarity for DEVONthink-style
classification.

The classifier caches its model and only retrains when new, modified, or deleted PDF files are
detected.
Embeddings for each PDF file are persisted individually for incremental training.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from json import JSONDecodeError  # at top of file
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import List

import joblib
import numpy as np
import torch
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError
from platformdirs import user_cache_dir, user_log_dir
from sentence_transformers import SentenceTransformer

ORGANISATION = "net.dmlane"
APP_NAME = "pdfclassify"

logging.getLogger("pdfminer").setLevel(logging.ERROR)


@dataclass
class Classification:
    """Classification result."""

    confidence: float
    label: str
    success: bool = True


def get_logger(app_name=APP_NAME, org_name=ORGANISATION, filename="retrain.log") -> logging.Logger:
    """
    Create a weekly rotating file logger in the macOS standard log location (rotates Sunday at
    midnight).
    """
    log_dir = Path(user_log_dir())
    log_dir = log_dir / org_name / app_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / filename

    logger = logging.getLogger(app_name)
    if not logger.handlers:
        handler = TimedRotatingFileHandler(
            log_path,
            when="W0",  # Rotate every week on Sunday at midnight
            interval=1,
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger


class PDFSemanticClassifier:
    """Multilingual embedding-based PDF classifier (DEVONthink-style)."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, data_dir: str, cache_name: str = "semantic_pdf_classifier"):
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(user_cache_dir())
        self.cache_dir = self.cache_dir / ORGANISATION / APP_NAME / cache_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = self.cache_dir / "model.joblib"
        self.hash_path = self.cache_dir / "file_hashes.json"
        self.embeddings_dir = self.cache_dir / "embeddings"
        self.embeddings_dir.mkdir(exist_ok=True, parents=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()

        self.labels: List[str] = []

        device = (
            "cuda"
            if torch.cuda.is_available()
            else ("mps" if torch.backends.mps.is_available() else "cpu")
        )
        self.embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device=device)
        self.doc_vectors = None

    def _compute_file_hash(self, path: Path) -> str:
        """Compute a hash of the contents and metadata of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(4096), b""):
                    hash_md5.update(chunk)

            hash_md5.update(str(path.stat().st_mtime).encode())
        except (OSError, IOError) as exc:
            self.logger.warning("Failed to compute hash for %s: %s", path, exc)
        return hash_md5.hexdigest()

    def _embedding_path(self, file_path: str) -> Path:
        """Get path to cached embedding for a given file."""
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return self.embeddings_dir / f"{file_hash}.joblib"

    def _load_data(self, previous_hashes: dict) -> dict:
        """Load or compute embeddings for changed files; track deleted ones."""
        # pylint: disable=too-many-locals
        embeddings: List[np.ndarray] = []
        labels: List[str] = []
        new_hashes = {}
        all_current_files = set()

        for label_dir in self.data_dir.iterdir():
            if not label_dir.is_dir():
                continue
            label = label_dir.name
            for pdf_file in label_dir.glob("*.pdf"):
                file_path_str = str(pdf_file)
                all_current_files.add(file_path_str)
                file_hash = self._compute_file_hash(pdf_file)
                new_hashes[file_path_str] = file_hash
                embedding_path = self._embedding_path(file_path_str)

                if previous_hashes.get(file_path_str) != file_hash or not embedding_path.exists():
                    try:
                        # pylint: disable=unexpected-keyword-arg
                        text = extract_text(pdf_file)
                        if text.strip():
                            vec = self.embedder.encode([text], convert_to_numpy=True)[0]
                            joblib.dump((vec, label), embedding_path)
                            self.logger.info("Updated embedding: %s", pdf_file)

                    except (OSError, ValueError, PDFSyntaxError) as exc:

                        self.logger.warning("Failed to embed %s: %s", pdf_file, exc)

                if embedding_path.exists():
                    try:
                        vec, lbl = joblib.load(embedding_path)
                        embeddings.append(vec)
                        labels.append(lbl)
                    except (
                        EOFError,
                        joblib.externals.loky.process_executor.TerminatedWorkerError,
                    ) as exc:
                        self.logger.warning("Failed to load embedding %s: %s", embedding_path, exc)

        deleted_files = set(previous_hashes.keys()) - all_current_files
        for deleted_path in deleted_files:
            self.logger.info("Removed: %s", deleted_path)
            deleted_embedding = self._embedding_path(deleted_path)
            if deleted_embedding.exists():
                deleted_embedding.unlink()

        self.doc_vectors = np.stack(embeddings) if embeddings else None
        self.labels = labels
        return new_hashes

    def train(self) -> None:
        """
        Train or update the model from persistent embeddings. Also prune empty label directories.
        """
        for label_dir in self.data_dir.iterdir():
            if label_dir.is_dir() and not any(label_dir.glob("*.pdf")):
                self.logger.info("Pruning empty label directory: %s", label_dir)
                try:
                    label_dir.rmdir()
                except OSError as exc:
                    self.logger.warning("Failed to remove %s: %s", label_dir, exc)

        previous_hashes = {}

        if self.hash_path.exists():
            try:
                with open(self.hash_path, "r", encoding="utf-8") as f:
                    previous_hashes = json.load(f)
            except (JSONDecodeError, ValueError):
                self.logger.warning(
                    "Could not parse %r (invalid JSON); starting from a clean hash set.",
                    self.hash_path,
                )
                previous_hashes = {}
        updated_hashes = self._load_data(previous_hashes)

        if self.doc_vectors is None or not self.labels:
            self.logger.info("No valid data to train the model.")
            return

        joblib.dump((self.doc_vectors, self.labels), self.model_path)
        with open(self.hash_path, "w", encoding="utf-8") as f:
            json.dump(updated_hashes, f)
        self.logger.info("Model trained and saved with %d documents.", len(self.labels))

    def _load_cached_model(self) -> None:
        """Load embedding vectors and labels from disk."""
        self.doc_vectors, self.labels = joblib.load(self.model_path)

    def predict(self, pdf_path: str, confidence_threshold: float = 0.75) -> Classification:
        """Predict the label for a PDF based on cosine similarity."""
        self.logger.info(
            "Predicting label for %s with threshold %.2f", pdf_path, confidence_threshold
        )

        # First, make sure we can even read and extract text from the PDF
        try:
            text = extract_text(pdf_path)
        except Exception as exc:
            # e.g. PDFSyntaxError, FileNotFoundError, etc.
            raise ValueError(f"Failed to extract PDF: {exc}") from exc
        if not text.strip():
            raise ValueError("PDF text is empty.")

        if not self.model_path.exists() or not self.hash_path.exists():
            self.logger.info("Model or hash file missing — triggering train().")
            self.train()
        elif self.doc_vectors is None or not self.labels:
            try:
                self._load_cached_model()
            except (EOFError, joblib.externals.loky.process_executor.TerminatedWorkerError) as exc:
                self.logger.warning("Failed to load cached model: %s. Retraining.", exc)
                self.train()

        if self.doc_vectors is None:
            raise RuntimeError("Model is not trained. Run train() first.")
        try:
            text = extract_text(pdf_path)
        except PDFSyntaxError:
            text = ""
        except Exception as exc:

            raise ValueError(f"Failed to extract PDF: {exc}") from exc

        if not text.strip():
            raise ValueError("PDF text is empty.")

        vec = self.embedder.encode([text], convert_to_numpy=True)
        vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)
        doc_vecs = self.doc_vectors / np.linalg.norm(self.doc_vectors, axis=1, keepdims=True)
        sims = np.dot(vec, doc_vecs.T)[0]
        best_index = np.argmax(sims)
        best_score = sims[best_index]
        predicted_label = self.labels[best_index]
        if best_score < confidence_threshold:
            self.logger.info(
                "Prediction below threshold: score=%.3f, assigned=__uncertain__", best_score
            )
            success = False
        else:
            self.logger.info(
                "Prediction above threshold: score=%.3f, assigned=%s", best_score, predicted_label
            )

            success = True
        return Classification(label=predicted_label, confidence=best_score, success=success)
