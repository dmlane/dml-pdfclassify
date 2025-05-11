"""Tests for the PDFClassifyConfig class and path expansion logic."""

from pathlib import Path

import pytest

from pdfclassify.config import PDFClassifyConfig, expand_path, resolve_and_expand_path


def test_expand_path_home_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure expand_path correctly resolves ~ and $HOME."""
    monkeypatch.setenv("HOME", "/custom/home")
    expanded = expand_path("~/.cache")
    assert str(expanded).startswith("/custom/home")


@pytest.mark.parametrize(
    "input_path, expected_substring",
    [
        ("APPDIR:cache/subdir", "pdfclassify"),
        ("APPDIR:config/xyz", "pdfclassify"),
        ("APPDIR:data/models", "pdfclassify"),
        ("~/mydir", str(Path.home())),
        ("$HOME/myotherdir", str(Path.home())),
    ],
)
def test_resolve_and_expand_path(input_path: str, expected_substring: str) -> None:
    """Check that APPDIR and home paths resolve as expected."""
    resolved = resolve_and_expand_path(input_path)
    assert isinstance(resolved, Path)
    assert expected_substring in str(resolved)


def test_default_config_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to default values when no config file is found."""
    monkeypatch.setattr(
        "pdfclassify.config.PDFClassifyConfig.USER_CONFIG_PATH", tmp_path / "none.toml"
    )
    monkeypatch.setattr(
        "pdfclassify.config.PDFClassifyConfig.DEFAULT_CONFIG_PATH", tmp_path / "none.toml"
    )

    config = PDFClassifyConfig()
    assert isinstance(config.output_dir, Path)
    assert isinstance(config.training_data_dir, Path)
    assert isinstance(config.cache_dir, Path)
    assert isinstance(config.confidence_threshold, float)
    assert 0.0 <= config.confidence_threshold <= 1.0
