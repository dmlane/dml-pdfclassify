"""Load configuration from TOML file."""

import os
import tomllib
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir


def resolve_and_expand_path(raw: str, app_name: str = "pdfclassify") -> Path:
    """
    Resolve APPDIR: prefixes and expand ~ or $HOME.
    Supports:
    - APPDIR:cache
    - APPDIR:config
    - APPDIR:data
    """
    if raw.startswith("APPDIR:"):
        _, subpath = raw.split(":", 1)
        if subpath.startswith("cache"):
            base = user_cache_dir(app_name)
            rest = subpath[6:]  # skip 'cache' itself
        elif subpath.startswith("config"):
            base = user_config_dir(app_name)
            rest = subpath[6:]
        elif subpath.startswith("data"):
            base = user_data_dir(app_name)
            rest = subpath[4:]
        else:
            raise ValueError(f"Unknown APPDIR prefix: {subpath}")
        path = os.path.join(base, rest.lstrip("/\\"))
    else:
        path = raw

    return expand_path(path)


def expand_path(path_str: str) -> Path:
    """Expand environment variables and ~ in a path string."""
    return Path(os.path.expanduser(os.path.expandvars(path_str)))


class PDFClassifyConfig:
    """Load configuration from TOML file."""

    # pylint: disable=too-few-public-methods
    DEFAULT_CONFIG_PATH = Path(__file__).parent / "pdfclassify.toml"
    USER_CONFIG_PATH = expand_path("~/.config/pdfclassify/pdfclassify.toml")

    def __init__(self):
        config = self._load_config()
        self.output_dir = resolve_and_expand_path(
            config.get("output_dir", "~/Documents/pdfclassify/output")
        )
        self.training_data_dir = resolve_and_expand_path(
            config.get("training_data_dir", "~/.config/pdfclassify/training_data")
        )
        self.cache_dir = expand_path(config.get("cache_dir", "~/.cache/pdfclassify"))
        self.confidence_threshold = config.get("settings", {}).get("confidence_threshold", 0.75)

    def _load_config(self) -> dict:
        if self.USER_CONFIG_PATH.exists():
            with open(self.USER_CONFIG_PATH, "rb") as f:
                return tomllib.load(f)
        elif self.DEFAULT_CONFIG_PATH.exists():
            with open(self.DEFAULT_CONFIG_PATH, "rb") as f:
                return tomllib.load(f)
        return {}
