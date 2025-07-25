"""Load configuration from TOML file."""

import os
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
            rest = subpath[6:]
        elif subpath.startswith("config"):
            base = user_config_dir(app_name)
            rest = subpath[6:]
        elif subpath.startswith("data"):
            base = user_data_dir(app_name)
            rest = subpath[4:]
        else:
            raise ValueError(f"Unknown APPDIR prefix: {subpath}")
        path_str = os.path.join(base, rest.lstrip("/\\"))
    else:
        path_str = raw

    return expand_path(path_str)


def expand_path(path_str: str) -> Path:
    """Expand environment variables and ~ in a path string."""
    return Path(os.path.expanduser(os.path.expandvars(path_str)))


class PDFClassifyConfig:  # pylint: disable=too-many-instance-attributes
    """Load configuration from TOML file."""

    # pylint: disable=too-few-public-methods
    DEFAULT_CONFIG_PATH: Path = Path(__file__).parent / "pdfclassify.toml"
    USER_CONFIG_PATH: Path = expand_path("~/.config/pdfclassify/pdfclassify.toml")

    def __init__(self):
        # Load config and record which file was used
        config, loaded_path = self._load_config()
        self.loaded_path: Optional[Path] = loaded_path

        # Resolve and expand paths
        self.output_dir = resolve_and_expand_path(
            str(config.get("paths", {}).get("output_dir", "~/Documents/pdfclassify/output"))
        )
        self.training_data_dir = resolve_and_expand_path(
            str(
                config.get("paths", {}).get(
                    "training_data_dir", "~/.config/pdfclassify/training_data"
                )
            )
        )
        self.cache_dir = expand_path(
            str(config.get("paths", {}).get("cache_dir", "~/.cache/pdfclassify"))
        )
        self.confidence_threshold: float = float(
            config.get("settings", {}).get("confidence_threshold", 0.75)
        )
        self.label_config_path = resolve_and_expand_path(
            str(
                config.get("paths", {}).get(
                    "label_config_path", "~/.config/pdfclassify/label_config.json"
                )
            )
        )
        self.org = "dmlane.net"
        self.app = "pdfclassify"

    def _load_config(self) -> Tuple[Dict[str, Any], Optional[Path]]:
        """
        Load TOML from USER_CONFIG_PATH, then DEFAULT_CONFIG_PATH, or return empty.
        Returns (config_dict, path_used) or ({}, None) if no file found.
        """
        if self.USER_CONFIG_PATH.exists():
            path = self.USER_CONFIG_PATH
        elif self.DEFAULT_CONFIG_PATH.exists():
            path = self.DEFAULT_CONFIG_PATH
        else:
            return {}, None

        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data, path

    def show_config(self) -> None:
        """
        Print out which TOML file was loaded (or '<none>') and all resolved settings
        in aligned columns.
        """
        # Prepare config entries
        entries = {
            "Loaded config file": str(self.loaded_path or "<none>"),
            "Output directory": str(self.output_dir),
            "Training data directory": str(self.training_data_dir),
            "Cache directory": str(self.cache_dir),
            "Confidence threshold": str(self.confidence_threshold),
        }
        # Determine column widths
        max_key_len = max(len(key) for key in entries)
        # Print aligned
        print("\n\n")
        for key, val in entries.items():
            print(f"{key.ljust(max_key_len)} : {val}")
