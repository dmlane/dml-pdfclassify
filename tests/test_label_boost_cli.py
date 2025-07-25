"""Tests for the interactive label boost CLI."""

import json
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from pdfclassify.label_boost_cli import LabelBoostCLI, LabelConfig


@pytest.fixture(name="test_config_path")
def test_config_path_fixture(tmp_path: Path) -> Generator[Path, Any, None]:
    """Create a dummy label_boosts.json and patch CONFIG."""
    test_dir = tmp_path / "cache"
    test_dir.mkdir()
    config_path = test_dir / "label_boosts.json"
    config_path.write_text(
        json.dumps({"testlabel": {"boost_phrases": [], "boost": 0.06}}),
        encoding="utf-8",
    )

    with patch("pdfclassify.label_boost_cli.CONFIG") as mock_config:
        mock_config.label_config_path = config_path
        mock_config.training_data_dir = tmp_path
        mock_config.cache_dir = test_dir
        yield config_path


@patch("pdfclassify.label_boost_cli.questionary")
@patch("pdfclassify.label_boost_cli.LabelBoostManager")
def test_edit_label(mock_manager_class, mock_questionary, _test_config_path):
    """Test editing a label's config using real LabelConfig and validated inputs."""
    real_label = LabelConfig(
        boost_phrases=["phrase1"],
        boost=0.06,
        final_name_pattern="",
        devonthink_group="",
        preferred_context=[],
    )

    manager = mock_manager_class.return_value
    manager.get.return_value = real_label
    manager.config = {"testlabel": real_label}

    captured_updated_config = {}

    original_from_dict = LabelConfig.from_dict

    def capture_from_dict(updated_dict: dict) -> LabelConfig:
        nonlocal captured_updated_config
        captured_updated_config = updated_dict
        return original_from_dict(updated_dict)

    def make_mock_ask(val):
        return MagicMock(ask=MagicMock(return_value=val))

    mock_questionary.text.side_effect = [
        make_mock_ask("updated phrase"),
        make_mock_ask("0.07"),
        make_mock_ask("Updated Pattern"),
        make_mock_ask("Updated Group"),
        make_mock_ask("ctx1, ctx2"),
        make_mock_ask("day, month"),
    ]

    mock_questionary.autocomplete.return_value.ask.return_value = "Updated Group"

    with patch("pdfclassify.label_boost_cli.LabelConfig.from_dict", side_effect=capture_from_dict):
        cli = LabelBoostCLI()
        cli._edit_label("testlabel")  # pylint: disable=protected-access

    assert captured_updated_config["boost_phrases"] == ["updated phrase"]
    assert captured_updated_config["boost"] == 0.07
    assert captured_updated_config["final_name_pattern"] == "Updated Pattern"
    assert captured_updated_config["devonthink_group"] == "Updated Group"
    assert captured_updated_config["preferred_context"] == ["ctx1", "ctx2"]
