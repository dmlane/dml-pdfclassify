"""PDFSemanticClassifier - Uses multilingual embeddings and optional label boosts for classification."""

import hashlib
import json
import logging
from json import JSONDecodeError
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

from pdfclassify._util import CONFIG
from pdfclassify.label_boost_manager import LabelBoostManager

logging.getLogger("pdfminer").setLevel(logging.ERROR)


class Classification:
    """Classification result including confidence, label, and optional metadata."""

    def __init__(self, confidence: float, label: str, success: bool = True):
        self.confidence = confidence
        self.label = label
        self.success = success
        self.final_name_pattern = None
        self.devonthink_group = None


class PDFSemanticClassifier:
    """Multilingual embedding-based PDF classifier with optional label boosts."""

    def __init__(self, data_dir: str, cache_name: str = "semantic_pdf_classifier"):
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(user_cache_dir()) / CONFIG.org / CONFIG.app / cache_name
        self.model_path = self.cache_dir / "model.joblib"
        self.hash_path = self.cache_dir / "file_hashes.json"
        self.embeddings_dir = self.cache_dir / "embeddings"
        self.labels: List[str] = []
        self.doc_vectors = None
        self.logger = self._setup_logger()
        self.boosts = LabelBoostManager(self.logger)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_dir.mkdir(exist_ok=True, parents=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        device = (
            "cuda"
            if torch.cuda.is_available()
            else ("mps" if torch.backends.mps.is_available() else "cpu")
        )
        self.embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device=device)

    def _setup_logger(self) -> logging.Logger:
        """Configure a rotating file logger."""
        log_dir = Path(user_log_dir()) / CONFIG.org / CONFIG.app
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "retrain.log"

        logger = logging.getLogger(CONFIG.app)
        if not logger.handlers:
            handler = logging.handlers.TimedRotatingFileHandler(
                log_path, when="W0", interval=1, backupCount=5, encoding="utf-8"
            )
            formatter = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        return logger

    def _compute_file_hash(self, path: Path) -> str:
        """Compute a hash of the contents and modification time of a file."""
        hash_md5 = hashlib.md5()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hash_md5.update(chunk)
        hash_md5.update(str(path.stat().st_mtime).encode())
        return hash_md5.hexdigest()

    def _embedding_path(self, file_path: str) -> Path:
        """Get path to cached embedding for a given file."""
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return self.embeddings_dir / f"{file_hash}.joblib"

    def train(self) -> None:
        """Train or update the model from persistent embeddings."""
        for label_dir in self.data_dir.iterdir():
            if label_dir.is_dir() and not any(label_dir.glob("*.pdf")):
                try:
                    label_dir.rmdir()
                except OSError as exc:
                    self.logger.warning("Could not remove %s: %s", label_dir, exc)

        previous_hashes = {}
        if self.hash_path.exists():
            try:
                with self.hash_path.open("r", encoding="utf-8") as f:
                    previous_hashes = json.load(f)
            except (JSONDecodeError, ValueError):
                self.logger.warning("Invalid JSON in %s, starting fresh", self.hash_path)

        updated_hashes = {}
        embeddings: List[np.ndarray] = []
        labels: List[str] = []
        all_current_files = set()

        for label_dir in self.data_dir.iterdir():
            if not label_dir.is_dir():
                continue
            label = label_dir.name
            for pdf_file in label_dir.glob("*.pdf"):
                file_path_str = str(pdf_file)
                all_current_files.add(file_path_str)
                file_hash = self._compute_file_hash(pdf_file)
                updated_hashes[file_path_str] = file_hash
                embed_path = self._embedding_path(file_path_str)

                if previous_hashes.get(file_path_str) != file_hash or not embed_path.exists():
                    try:
                        text = extract_text(pdf_file)
                        if text.strip():
                            vec = self.embedder.encode([text], convert_to_numpy=True)[0]
                            joblib.dump((vec, label), embed_path)
                    except (OSError, ValueError, PDFSyntaxError) as exc:
                        self.logger.warning("Embedding failed for %s: %s", pdf_file, exc)

                if embed_path.exists():
                    try:
                        vec, lbl = joblib.load(embed_path)
                        embeddings.append(vec)
                        labels.append(lbl)
                    except (
                        EOFError,
                        joblib.externals.loky.process_executor.TerminatedWorkerError,
                    ) as exc:
                        self.logger.warning("Failed to load embedding: %s", exc)

        for deleted_path in set(previous_hashes) - all_current_files:
            embed = self._embedding_path(deleted_path)
            if embed.exists():
                embed.unlink()

        self.doc_vectors = np.stack(embeddings) if embeddings else None
        self.labels = labels

        joblib.dump((self.doc_vectors, self.labels), self.model_path)
        with self.hash_path.open("w", encoding="utf-8") as f:
            json.dump(updated_hashes, f)

    def _load_cached_model(self) -> None:
        """Load model vectors and labels from disk."""
        self.doc_vectors, self.labels = joblib.load(self.model_path)

    def predict(self, pdf_path: str, confidence_threshold: float = 0.75) -> Classification:
        """Predict the label for a PDF based on cosine similarity and optional boost."""
        try:
            text = extract_text(pdf_path)
        except (PDFSyntaxError, OSError, ValueError) as exc:
            raise ValueError(f"Failed to extract PDF: {exc}") from exc

        if not text.strip():
            raise ValueError("PDF text is empty.")

        if not self.model_path.exists() or not self.hash_path.exists():
            self.train()
        elif self.doc_vectors is None or not self.labels:
            try:
                self._load_cached_model()
            except (EOFError, joblib.externals.loky.process_executor.TerminatedWorkerError):
                self.train()

        if self.doc_vectors is None:
            raise RuntimeError("Model is not trained.")

        vec = self.embedder.encode([text], convert_to_numpy=True)
        vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)
        doc_vecs = self.doc_vectors / np.linalg.norm(self.doc_vectors, axis=1, keepdims=True)
        sims = np.dot(vec, doc_vecs.T)[0]

        # Apply boosts without clamping
        boosted_sims = []
        for i, label in enumerate(self.labels):
            boost = self.boosts.boost_score(label, text)
            raw_score = sims[i]
            boosted_score = raw_score + boost
            boosted_sims.append(boosted_score)
            self.logger.debug(
                "Label: %s | Raw: %.3f | Boost: %.3f | Boosted: %.3f",
                label,
                raw_score,
                boost,
                boosted_score,
            )

        best_index = int(np.argmax(boosted_sims))
        predicted_label = self.labels[best_index]
        raw_confidence = boosted_sims[best_index]
        confidence = min(raw_confidence, 1.0)
        success = confidence >= confidence_threshold

        classification = Classification(
            confidence=confidence,
            label=predicted_label,
            success=success,
        )
        label_meta = self.boosts.get(predicted_label)
        classification.final_name_pattern = label_meta.get("final_name_pattern")
        classification.devonthink_group = label_meta.get("devonthink_group")

        return classification
