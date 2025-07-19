"""LabelBoostManager - Load and apply configurable boost logic for semantic PDF classification."""

import json
import logging
from typing import Any, Dict

from pdfclassify._util import CONFIG  # pylint: disable=no-name-in-module


class LabelBoostManager:
    """Handles boost logic and metadata for labels."""

    def __init__(self, logger: logging.Logger):
        """Initialize the LabelBoostManager with a logger and validated config."""
        self.logger = logger
        self.config: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        """Load and validate the boost config from the configured path."""
        if CONFIG.label_config_path.exists():
            try:
                with open(CONFIG.label_config_path, "r", encoding="utf-8") as file:
                    raw = json.load(file)
                    return self._validate(raw)
            except (json.JSONDecodeError, OSError) as exc:
                self.logger.warning("Failed to load boost config: %s", exc)
        return {}

    def _validate(self, config: dict) -> Dict[str, Dict[str, Any]]:
        """Validate the loaded boost configuration and discard invalid entries."""
        valid_config: Dict[str, Dict[str, Any]] = {}
        for label, value in config.items():
            if not isinstance(value, dict):
                self.logger.warning(
                    "Invalid config for label %r: expected dict, got %s",
                    label,
                    type(value).__name__,
                )
                continue

            validated: Dict[str, Any] = {}

            phrases = value.get("boost_phrases")
            if isinstance(phrases, list) and all(isinstance(p, str) for p in phrases):
                validated["boost_phrases"] = phrases
            elif "boost_phrases" in value:
                self.logger.warning(
                    "Invalid boost_phrases for label %r: must be list of strings", label
                )

            boost = value.get("boost")
            if isinstance(boost, (int, float)):
                validated["boost"] = float(boost)
            elif "boost" in value:
                self.logger.warning("Invalid boost for label %r: must be float", label)

            for key in ("final_name_pattern", "devonthink_group"):
                val = value.get(key)
                if isinstance(val, str):
                    validated[key] = val
                elif key in value:
                    self.logger.warning("Invalid %s for label %r: must be string", key, label)

            if validated:
                valid_config[label] = validated

        return valid_config

    def get(self, label: str) -> Dict[str, Any]:
        """Return the config dictionary for a given label or an empty dict."""
        return self.config.get(label, {})

    def boost_score(self, label: str, text: str) -> float:
        """Return a boost value if a boost phrase for the label appears in the text."""
        config = self.get(label)
        boost_phrases = config.get("boost_phrases", [])
        boost = config.get("boost", 0.05)
        for phrase in boost_phrases:
            if phrase.lower() in text.lower():
                self.logger.info("Boosted %s by %.2f due to phrase %r", label, boost, phrase)
                return boost
        return 0.0
