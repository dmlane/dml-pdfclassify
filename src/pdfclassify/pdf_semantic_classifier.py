# pylint: disable=line-too-long, broad-exception-caught
"""Multilingual PDF Semantic Classifier

This module defines a single class:
- PDFSemanticClassifier: Uses multilingual embeddings and cosine similarity for DEVONthink-style classification.

The classifier caches its model and only retrains when new, modified, or deleted PDF files are detected.
Embeddings for each PDF file are persisted individually for incremental training.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List

import joblib
import numpy as np
import torch
from pdfminer.high_level import extract_text
from platformdirs import user_cache_dir, user_log_dir
from sentence_transformers import SentenceTransformer


class PDFSemanticClassifier:
    """Multilingual embedding-based PDF classifier (DEVONthink-style)."""

    # pylint: disable=too-many-instance-attributes
    def _log(self, message: str) -> None:
        """Append a timestamped message to the retrain log."""
        with open(self.log_path, "a", encoding="utf-8") as log:
            log.write(f"[{datetime.now().isoformat()}] {message}\n")

    def __init__(self, data_dir: str, cache_name: str = "semantic_pdf_classifier"):
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(user_cache_dir("net.dmlane.pdf_classifier"), cache_name)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.log_dir = Path(user_log_dir("pdfclassify", "net.dmlane"))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = self.cache_dir / "model.joblib"
        self.hash_path = self.cache_dir / "file_hashes.json"
        self.embeddings_dir = self.cache_dir / "embeddings"
        self.embeddings_dir.mkdir(exist_ok=True)
        self.log_path = self.log_dir / "retrain.log"

        self.documents: List[str] = []
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
        except Exception as exc:
            self._log(f"Failed to compute hash for {path}: {exc}")
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
                        text = extract_text(pdf_file)
                        if text.strip():
                            vec = self.embedder.encode([text], convert_to_numpy=True)[0]
                            joblib.dump((vec, label), embedding_path)
                            self._log(f"Updated embedding: {pdf_file}")
                    except Exception as exc:
                        self._log(f"Failed to embed {pdf_file}: {exc}")

                if embedding_path.exists():
                    try:
                        vec, lbl = joblib.load(embedding_path)
                        embeddings.append(vec)
                        labels.append(lbl)
                    except Exception as exc:
                        self._log(f"Failed to load embedding {embedding_path}: {exc}")

        deleted_files = set(previous_hashes.keys()) - all_current_files
        for deleted_path in deleted_files:
            self._log(f"Removed: {deleted_path}")
            deleted_embedding = self._embedding_path(deleted_path)
            if deleted_embedding.exists():
                deleted_embedding.unlink()

        self.doc_vectors = np.stack(embeddings) if embeddings else None
        self.labels = labels
        return new_hashes

    def train(self) -> None:
        """Train or update the model from persistent embeddings. Also prune empty label directories."""
        for label_dir in self.data_dir.iterdir():
            if label_dir.is_dir() and not any(label_dir.glob("*.pdf")):
                self._log(f"Pruning empty label directory: {label_dir}")
                try:
                    label_dir.rmdir()
                except Exception as exc:
                    self._log(f"Failed to remove {label_dir}: {exc}")

        previous_hashes = {}
        if self.hash_path.exists():
            with open(self.hash_path, "r", encoding="utf-8") as f:
                previous_hashes = json.load(f)

        updated_hashes = self._load_data(previous_hashes)

        if self.doc_vectors is None or not self.labels:
            self._log("No valid data to train the model.")
            return

        joblib.dump((self.doc_vectors, self.labels), self.model_path)
        with open(self.hash_path, "w", encoding="utf-8") as f:
            json.dump(updated_hashes, f)
        self._log(f"Model trained and saved with {len(self.labels)} documents.")

    def _load_cached_model(self) -> None:
        """Load embedding vectors and labels from disk."""
        self.doc_vectors, self.labels = joblib.load(self.model_path)

    def predict(self, pdf_path: str, confidence_threshold: float = 0.5) -> str:
        """Predict the label for a PDF based on cosine similarity."""
        self._log(f"Predicting label for {pdf_path} with threshold {confidence_threshold}")

        # Automatically retrain if needed
        if not self.model_path.exists() or not self.hash_path.exists():
            self._log("Model or hash file missing — triggering train().")
            self.train()
        elif self.doc_vectors is None or not self.labels:
            try:
                self._load_cached_model()
            except Exception as exc:
                self._log(f"Failed to load cached model: {exc}. Retraining.")
                self.train()

        if self.doc_vectors is None:
            raise RuntimeError("Model is not trained. Run train() first.")
        try:
            text = extract_text(pdf_path)
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
        if best_score < confidence_threshold:
            pct_label = "__uncertain__" + self.labels[best_index] + f"({best_score:.3f})"
            self._log(f"Prediction below threshold: score={best_score:.3f}, assigned={pct_label}")
            return pct_label
        predicted_label = self.labels[best_index]
        self._log(f"Prediction above threshold: score={best_score:.3f}, assigned={predicted_label}")
        return predicted_label
