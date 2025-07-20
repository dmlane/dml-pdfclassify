"""LabelBoostManager - Load and apply configurable boost logic for semantic PDF classification.

This manager loads the boost configuration from disk, validates its structure,
and provides access to boost values and related metadata for each label.

It also supports identifying training labels that are missing configuration entries.
"""

import json
import logging
from typing import Any, Dict, Optional, Set

from pdfclassify._util import CONFIG  # pylint: disable=no-name-in-module


class LabelBoostManager:
    """Handles boost logic and metadata for labels."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the LabelBoostManager with a logger and validated config."""
        self.logger = logger or logging.getLogger("LabelBoostManager")
        self.config: Dict[str, Dict[str, Any]] = self._load_config()
        self.sync_with_training_labels()  # Always sync at init

    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Load and validate the boost config from the configured path."""
        if CONFIG.label_config_path.exists():
            try:
                with open(CONFIG.label_config_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    return self._validate_config(raw)
            except (json.JSONDecodeError, OSError) as exc:
                self.logger.warning("Failed to load boost config: %s", exc)
        return {}

    def _validate_config(self, raw: dict) -> Dict[str, Dict[str, Any]]:
        """Validate the loaded configuration and discard invalid entries."""
        valid_config: Dict[str, Dict[str, Any]] = {}
        for label, value in raw.items():
            if not isinstance(value, dict):
                self.logger.warning(
                    "Invalid config for label %r: expected dict, got %s",
                    label,
                    type(value).__name__,
                )
                continue

            validated: Dict[str, Any] = {}

            if isinstance(value.get("boost_phrases"), list):
                validated["boost_phrases"] = [
                    str(p) for p in value["boost_phrases"] if isinstance(p, str)
                ]

            if isinstance(value.get("boost"), (int, float)):
                validated["boost"] = float(value["boost"])

            for key in ("final_name_pattern", "devonthink_group"):
                val = value.get(key)
                if isinstance(val, str) or val is None:
                    validated[key] = val

            if isinstance(value.get("preferred_context"), list):
                if all(isinstance(p, str) for p in value["preferred_context"]):
                    validated["preferred_context"] = value["preferred_context"]
                else:
                    self.logger.warning(
                        "Invalid preferred_context for label %r: expected list of strings", label
                    )

            if validated:
                valid_config[label] = validated

        return valid_config

    def get(self, label: str) -> Dict[str, Any]:
        """Return the config dictionary for a given label or an empty dict."""
        return self.config.get(label, {})

    def boost_score(self, label: str, text: str) -> float:
        """Return a boost value if a boost phrase for the label appears in the text."""
        config = self.get(label)
        phrases = config.get("boost_phrases", [])
        boost = config.get("boost", 0.05)
        for phrase in phrases:
            if phrase.lower() in text.lower():
                self.logger.info("Boosted %s by %.2f due to phrase %r", label, boost, phrase)
                return boost
        return 0.0

    def missing_labels(self) -> Set[str]:
        """Return a set of training directory labels missing from the config."""
        if not CONFIG.training_data_dir.exists():
            return set()
        training_labels = {p.name for p in CONFIG.training_data_dir.iterdir() if p.is_dir()}
        return training_labels - self.config.keys()

    def sync_with_training_labels(self, interactive: bool = False) -> None:
        """Ensure all training labels are represented in the config.

        If `interactive` is True, print additions.
        """
        new_labels = self.missing_labels()
        for label in new_labels:
            self.config[label] = {
                "boost_phrases": [],
                "boost": -1.0,  # Sentinel value for incomplete labels
                "final_name_pattern": None,
                "devonthink_group": None,
            }
            if interactive:
                print(f"➕ Added config entry for training label: {label}")

    def is_complete(self, label: str) -> bool:
        """Check if a label's config has all required fields populated."""
        entry = self.config.get(label)
        return (
            isinstance(entry, dict)
            and isinstance(entry.get("boost_phrases"), list)
            and isinstance(entry.get("boost"), float)
            and entry["boost"] >= 0.0
            and (
                isinstance(entry.get("final_name_pattern"), str)
                or entry.get("final_name_pattern") is None
            )
            and (
                isinstance(entry.get("devonthink_group"), str)
                or entry.get("devonthink_group") is None
            )
        )

    def save(self) -> None:
        """Save current config back to disk."""
        with open(CONFIG.label_config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
