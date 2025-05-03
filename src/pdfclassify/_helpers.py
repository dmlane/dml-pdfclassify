# pylint: disable=line-too-long

"""Multilingual PDF Semantic Classifier

This module defines a single class:
- PDFSemanticClassifier: Uses multilingual embeddings and cosine similarity for DEVONthink-style classification.

The classifier caches its model and only retrains when new or modified PDF files are detected.
"""

import hashlib
import os
from pathlib import Path
from typing import List

import joblib
import numpy as np
from pdfminer.high_level import extract_text
from platformdirs import user_cache_dir
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class PDFSemanticClassifier:
    #pylint: disable=too-many-instance-attributes
    """Multilingual embedding-based PDF classifier (DEVONthink-style)."""

    def __init__(self, data_dir: str, cache_name: str = "semantic_pdf_classifier"):
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(user_cache_dir("net.dmlane.pdf_classifier"), cache_name)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = self.cache_dir / "model.joblib"
        self.hash_path = self.cache_dir / "data_hash.txt"

        self.documents: List[str] = []
        self.labels: List[str] = []
        self.embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self.doc_vectors = None

    def _compute_data_hash(self) -> str:
        """Generate a hash of file names and modification times to detect changes."""
        hash_md5 = hashlib.md5()
        for dirpath, _, filenames in os.walk(self.data_dir):
            for filename in sorted(filenames):
                if filename.lower().endswith(".pdf"):
                    path = Path(dirpath) / filename
                    hash_md5.update(str(path).encode())
                    hash_md5.update(str(path.stat().st_mtime).encode())
        return hash_md5.hexdigest()

    def _load_data(self) -> None:
        """Extract and store texts and labels from PDF files."""
        self.documents.clear()
        self.labels.clear()
        for label_dir in self.data_dir.iterdir():
            if not label_dir.is_dir():
                continue
            label = label_dir.name
            for pdf_file in label_dir.glob("*.pdf"):
                try:
                    text = extract_text(pdf_file, maxpages=2)
                    if text.strip():
                        self.documents.append(text)
                        self.labels.append(label)

                except Exception as exc: # pylint: disable=broad-except
                    print(f"Error reading {pdf_file}: {exc}")

    def train(self) -> None:
        """Train or load the embedding model based on changes in PDF data."""
        current_hash = self._compute_data_hash()
        if self.model_path.exists() and self.hash_path.exists():
            with open(self.hash_path, "r", encoding="utf-8") as file:
                if file.read() == current_hash:
                    print("Model loaded from cache.")
                    self._load_cached_model()
                    return

        print("Training embedding model...")
        self._load_data()
        self.doc_vectors = self.embedder.encode(self.documents, convert_to_numpy=True)

        joblib.dump((self.doc_vectors, self.labels), self.model_path)
        with open(self.hash_path, "w", encoding="utf-8") as file:
            file.write(current_hash)
        print(f"Model trained and cached with {len(self.labels)} documents.")

    def _load_cached_model(self) -> None:
        """Load embedding vectors and labels from disk."""
        self.doc_vectors, self.labels = joblib.load(self.model_path)

    def predict(self, pdf_path: str) -> str:
        """Predict the label for a PDF based on cosine similarity."""
        if self.doc_vectors is None:
            raise RuntimeError("Model is not trained. Run train() first.")
        try:
            text = extract_text(pdf_path, maxpages=2)
        except Exception as exc: #pylint disable=broad-except
            raise ValueError(f"Failed to extract PDF: {exc}") from exc
        if not text.strip():
            raise ValueError("PDF text is empty.")

        vec = self.embedder.encode([text], convert_to_numpy=True)
        sims = cosine_similarity(vec, self.doc_vectors)[0]
        return self.labels[np.argmax(sims)]
