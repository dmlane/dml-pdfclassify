"""Unit tests for the LabelConfig class.

Covers defaulting, validation, serialization, and matching logic.
"""

from pdfclassify.label_config import _DEFAULT_MINIMUM_PARTS, LabelConfig


def test_from_dict_defaults():
    """Test that missing fields are correctly defaulted."""
    config = LabelConfig.from_dict({})
    assert config.boost == -1.0
    assert config.boost_phrases == []
    assert config.final_name_pattern is None
    assert config.devonthink_group is None
    assert config.preferred_context == []
    assert config.minimum_parts == _DEFAULT_MINIMUM_PARTS


def test_boost_clamping():
    """Test that boost values are clamped correctly."""
    config = LabelConfig.from_dict({"boost": 0.5})
    assert config.boost == 0.07
    config = LabelConfig.from_dict({"boost": -10.0})
    assert config.boost == -1.0


def test_minimum_parts_validation():
    """Test that invalid parts are filtered and defaults restored if necessary."""
    config = LabelConfig.from_dict({"minimum_parts": ["month", "day", "foo"]})
    assert "foo" not in config.minimum_parts
    assert set(config.minimum_parts).issubset({"day", "month", "year"})
    config = LabelConfig.from_dict({"minimum_parts": ["unknown"]})
    assert config.minimum_parts == _DEFAULT_MINIMUM_PARTS


def test_matches_and_boost():
    """Test that boost phrases match and return correct boost value."""
    config = LabelConfig.from_dict({"boost_phrases": ["invoice", "statement"], "boost": 0.05})
    assert config.matches_phrase("This is an invoice for services.")
    assert config.get_boost_if_matched("statement enclosed") == 0.05
    assert config.get_boost_if_matched("receipt enclosed") == 0.0


def test_is_complete():
    """Test completeness check for empty and valid configurations."""
    incomplete = LabelConfig.from_dict({})
    assert not incomplete.is_complete()

    complete = LabelConfig.from_dict(
        {
            "boost_phrases": ["report"],
            "boost": 0.06,
        }
    )
    assert complete.is_complete()


def test_to_dict_roundtrip():
    """Test serialization and roundtrip through from_dict and to_dict."""
    data = {
        "boost_phrases": ["alpha", "beta"],
        "boost": 0.03,
        "final_name_pattern": "pattern",
        "devonthink_group": "Some/Group",
        "preferred_context": ["context1"],
        "minimum_parts": ["month", "year"],
    }
    config = LabelConfig.from_dict(data)
    result = config.to_dict()
    for key, value in data.items():
        assert result[key] == value
