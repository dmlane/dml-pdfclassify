"""LabelConfig: Represents a single label's configuration for PDF classification.

This class handles validation, defaulting, and serialization of label-specific
boost and metadata settings.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

_ALLOWED_MINIMUM_PARTS = {"day", "month", "year"}
_DEFAULT_MINIMUM_PARTS = ["day", "month", "year"]


# 🔧 To ADD or REMOVE fields, edit both SCHEMA and the LabelConfig dataclass fields below.
def is_list_of_str(val: Any) -> bool:
    """Check if value is a list of strings."""
    return isinstance(val, list) and all(isinstance(i, str) for i in val)


def is_optional_str(val: Any) -> bool:
    """Check if value is a string or None."""
    return val is None or isinstance(val, str)


def is_valid_parts(val: Any) -> bool:
    """Check if value is a valid list of allowed date parts."""
    return isinstance(val, list) and all(
        isinstance(i, str) and i in _ALLOWED_MINIMUM_PARTS for i in val
    )


SCHEMA: Dict[str, Dict[str, Union[Any, Callable[[], Any], Callable[[Any], bool]]]] = {
    "boost_phrases": {
        "default": list,
        "validate": is_list_of_str,
    },
    "boost": {
        "default": -1.0,
        "validate": lambda x: isinstance(x, (int, float)),
        "clamp_max": 0.07,
    },
    "final_name_pattern": {
        "default": None,
        "validate": is_optional_str,
    },
    "devonthink_group": {
        "default": None,
        "validate": is_optional_str,
    },
    "preferred_context": {
        "default": list,
        "validate": is_list_of_str,
    },
    "minimum_parts": {
        "default": _DEFAULT_MINIMUM_PARTS.copy,
        "validate": is_valid_parts,
    },
}


@dataclass
class LabelConfig:
    """Structured configuration for a single label entry.

    🔧 To ADD or REMOVE fields, update both this dataclass and the SCHEMA above.
    """

    boost_phrases: List[str] = field(default_factory=list)
    boost: float = -1.0
    final_name_pattern: Optional[str] = None
    devonthink_group: Optional[str] = None
    preferred_context: List[str] = field(default_factory=list)
    minimum_parts: List[str] = field(default_factory=_DEFAULT_MINIMUM_PARTS.copy)

    @staticmethod
    def validate_field(field_name: str, value: Any) -> Any:
        """Validate and convert a single field value."""
        rules = SCHEMA.get(field_name)
        if not rules:
            raise ValueError(f"Unknown field: {field_name}")

        if "validate" in rules and callable(rules["validate"]):
            try:
                # Special case: try to parse lists from comma strings
                # pylint: disable=comparison-with-callable
                if rules["validate"] == is_list_of_str and isinstance(value, str):

                    value = [v.strip() for v in value.split(",") if v.strip()]
                elif rules["validate"] == is_valid_parts and isinstance(value, str):

                    value = [v.strip() for v in value.split(",") if v.strip()]

                if not rules["validate"](value):
                    raise ValueError(f"Invalid value for field: {field_name}")
            except Exception as exc:
                raise ValueError(f"Validation failed for {field_name}: {exc}") from exc
        return value

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "LabelConfig":
        """Create a LabelConfig instance from a raw dictionary, applying defaults and validation."""
        data = {}
        for field_name, rules in SCHEMA.items():
            value = raw.get(field_name, None)

            # Apply validation if available
            if "validate" in rules and callable(rules["validate"]):
                if not rules["validate"](value):
                    value = rules["default"]() if callable(rules["default"]) else rules["default"]
            elif value is None:
                value = rules["default"]() if callable(rules["default"]) else rules["default"]

            # Apply clamping if defined
            if field_name == "boost":
                if isinstance(value, (int, float)):
                    if value < 0.0:
                        value = -1.0
                    elif value > rules.get("clamp_max", value):
                        value = rules["clamp_max"]

            if field_name == "minimum_parts":
                if isinstance(value, list):
                    value = [p for p in value if p in _ALLOWED_MINIMUM_PARTS]
                    if not value:
                        value = _DEFAULT_MINIMUM_PARTS.copy()

            data[field_name] = value

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this LabelConfig to a dictionary using the SCHEMA definition."""
        return {field_name: getattr(self, field_name) for field_name in SCHEMA}

    def is_complete(self) -> bool:
        """Return True if this label's config is complete (e.g., usable)."""
        return (
            isinstance(self.boost_phrases, list)
            and isinstance(self.boost, float)
            and self.boost >= 0.0
        )

    def matches_phrase(self, text: str) -> bool:
        """Return True if any boost phrase appears in the given text (case-insensitive)."""
        return any(p.lower() in text.lower() for p in self.boost_phrases)

    def get_boost_if_matched(self, text: str) -> float:
        """Return the boost value if a phrase matches the given text, else 0.0."""
        return self.boost if self.matches_phrase(text) else 0.0
