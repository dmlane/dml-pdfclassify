"""LabelBoostManager - Load and apply configurable boost logic for semantic PDF classification.

This manager loads the boost configuration from disk, validates its structure,
and provides access to boost values and related metadata for each label.

It also supports identifying training labels that are missing configuration entries.
"""

import json
import logging
from typing import Dict, Optional, Set

from pdfclassify._util import CONFIG  # pylint: disable=no-name-in-module
from pdfclassify.label_config import LabelConfig


class LabelBoostManager:
    """Handles boost logic and metadata for labels."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the LabelBoostManager with a logger and validated config."""
        self.logger = logger or logging.getLogger("LabelBoostManager")
        self.config: Dict[str, LabelConfig] = self._load_config()
        self.sync_with_training_labels()  # Always sync at init

    def _load_config(self) -> Dict[str, LabelConfig]:
        """Load and validate the boost config from the configured path."""
        if CONFIG.label_config_path.exists():
            try:
                with open(CONFIG.label_config_path, "r", encoding="utf-8") as file:
                    raw = json.load(file)
                    return {
                        label: LabelConfig.from_dict(value)
                        for label, value in raw.items()
                        if isinstance(value, dict)
                    }
            except (json.JSONDecodeError, OSError) as exc:
                self.logger.warning("Failed to load boost config: %s", exc)
        return {}

    def get(self, label: str) -> LabelConfig:
        """Return the LabelConfig for a given label or a default-initialized one."""
        return self.config.get(label, LabelConfig())

    def boost_score(self, label: str, text: str) -> float:
        """Return a boost value if a boost phrase for the label appears in the text."""
        config = self.get(label)
        score = config.get_boost_if_matched(text)
        if score > 0.0:
            self.logger.info("Boosted %%s by %%.2f due to matching phrase", label, score)
        return score

    def missing_labels(self) -> Set[str]:
        """Return a set of training directory labels missing from the config."""
        if not CONFIG.training_data_dir.exists():
            return set()
        training_labels = {
            path.name for path in CONFIG.training_data_dir.iterdir() if path.is_dir()
        }
        return training_labels - self.config.keys()

    def sync_with_training_labels(self, interactive: bool = False) -> None:
        """Ensure all training labels are represented in the config.

        If `interactive` is True, print additions.
        """
        for label in self.missing_labels():
            self.config[label] = LabelConfig()
            if interactive:
                print(f"➕ Added config entry for training label: {label}")

    def is_complete(self, label: str) -> bool:
        """Check if a label's config is complete."""
        return self.get(label).is_complete()

    def save(self) -> None:
        """Save current config back to disk."""
        with open(CONFIG.label_config_path, "w", encoding="utf-8") as file:
            json.dump(
                {label: cfg.to_dict() for label, cfg in self.config.items()},
                file,
                indent=2,
                ensure_ascii=False,
            )
