"""Unit tests for LabelBoostManager class.

Tests include config loading, boost scoring, missing label detection,
and synchronization logic.
"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pdfclassify.label_boost_manager import LabelBoostManager
from pdfclassify.label_config import LabelConfig


@pytest.fixture(name="temp_config_file")
def fixture_temp_config_file(tmp_path):
    """Create a temporary label_config_path for testing."""
    config_path = tmp_path / "label_boosts.json"
    config_data = {
        "invoice": {
            "boost_phrases": ["total", "invoice number"],
            "boost": 0.06,
            "final_name_pattern": "invoice_{date}",
            "devonthink_group": "Finances/Invoices",
            "preferred_context": ["header"],
            "minimum_parts": ["month", "year"],
        }
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    return config_path


@pytest.fixture(name="patched_config")
def fixture_patched_config(temp_config_file):
    """Mock CONFIG to point to the temp config file and fake training data dir."""
    with patch("pdfclassify.label_boost_manager.CONFIG") as mock:
        mock.label_config_path = temp_config_file
        with tempfile.TemporaryDirectory() as temp_dir:
            mock.training_data_dir = Path(temp_dir)  # ← FIXED HERE
            training_path = mock.training_data_dir
            (training_path / "invoice").mkdir()
            (training_path / "receipt").mkdir()
            yield mock


def test_load_config(patched_config):  # pylint: disable=unused-argument
    """Test that LabelBoostManager loads config correctly from JSON."""
    manager = LabelBoostManager()
    assert "invoice" in manager.config
    config = manager.get("invoice")
    assert isinstance(config, LabelConfig)
    assert config.boost == 0.06
    assert config.devonthink_group == "Finances/Invoices"


def test_boost_score_match(patched_config):  # pylint: disable=unused-argument
    """Test that a matching phrase returns the correct boost value."""
    manager = LabelBoostManager()
    score = manager.boost_score("invoice", "Invoice Number: 123")
    assert score == 0.06


def test_boost_score_nomatch(patched_config):  # pylint: disable=unused-argument
    """Test that non-matching text returns zero boost."""
    manager = LabelBoostManager()
    score = manager.boost_score("invoice", "Random content")
    assert score == 0.0


def test_missing_labels_detection(patched_config):  # pylint: disable=unused-argument
    """Test detection of training labels not yet in config."""
    with patch.object(LabelBoostManager, "sync_with_training_labels"):
        manager = LabelBoostManager()
        missing = manager.missing_labels()
        assert "receipt" in missing


def test_sync_with_training_labels(patched_config):  # pylint: disable=unused-argument
    """Test that missing labels are added with default configs."""
    manager = LabelBoostManager()
    manager.sync_with_training_labels()
    assert "receipt" in manager.config
    assert isinstance(manager.config["receipt"], LabelConfig)


def test_is_complete(patched_config):  # pylint: disable=unused-argument
    """Test that completeness check works for known label."""
    manager = LabelBoostManager()
    assert manager.is_complete("invoice")
    assert not manager.is_complete("receipt")


def test_boost_score_logs_correctly(patched_config, caplog):
    """Ensure boost_score logs without raising formatting errors."""
    # Use a logger configured to propagate messages to caplog
    logger = logging.getLogger("LabelBoostManagerTest")
    logger.setLevel(logging.INFO)
    caplog.set_level(logging.INFO)

    # Inject logger into manager
    manager = LabelBoostManager(logger=logger)

    # The config already has 'invoice' with matching phrase "invoice number"
    text = "Invoice Number: 12345"

    # Calling boost_score should trigger a log message and not raise any errors
    score = manager.boost_score("invoice", text)
    assert score > 0  # must have triggered boost
    # Assert there were no logging-related errors
    for record in caplog.records:
        assert "TypeError" not in record.getMessage()
    # Verify that an informative log was produced
    assert any("Boosted" in r.getMessage() for r in caplog.records)
