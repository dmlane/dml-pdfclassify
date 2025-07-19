"""Interactive CLI for managing label_boosts.json configuration."""

import ast
import json
import subprocess
import sys
from typing import Any, Dict, List

import questionary
from prompt_toolkit.styles import Style

from pdfclassify._util import CONFIG  # pylint: disable=no-name-in-module

# Custom style for better contrast
CUSTOM_STYLE = Style.from_dict(
    {
        "question": "#00ffff bold",  # Cyan
        "answer": "#ffffff",  # White
        "pointer": "#00ff00 bold",  # Green
        "highlighted": "#00ff00 bold",  # Green for selected
        "selected": "#00ff00 bold",  # Green
        "instruction": "#888888 italic",
        "separator": "#cc5454",
        "text": "#ffffff",
    }
)

REQUIRED_FIELDS = ["boost_phrases", "boost", "final_name_pattern", "devonthink_group"]
CACHE_PATH = CONFIG.cache_dir / "devonthink_groups.json"


# pylint: disable=too-few-public-methods
class LabelBoostCLI:
    """Interactive CLI for editing the label_boosts.json config."""

    _devonthink_groups_cache: List[str] = []

    @staticmethod
    def _get_devonthink_groups(force_refresh: bool = False) -> List[str]:
        """Query DEVONthink for all group paths using AppleScript, with optional cache."""
        if LabelBoostCLI._devonthink_groups_cache and not force_refresh:
            return LabelBoostCLI._devonthink_groups_cache

        if not force_refresh and CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if isinstance(cached, list):
                        LabelBoostCLI._devonthink_groups_cache = cached
                        return cached
            except (OSError, json.JSONDecodeError):
                print("⚠️ Failed to load group cache. Will re-query DEVONthink.")

        script = """
        tell application id "DNtp"
          set theGroups to {}
          repeat with theDatabase in databases
            repeat with theRecord in (get every parent of theDatabase whose tag type is not ordinary tag)
              set end of theGroups to (name of theDatabase & (location of theRecord) & name of theRecord)
            end repeat
          end repeat
          return theGroups
        end tell
        """
        try:
            result = subprocess.run(
                ["osascript", "-s", "s", "-e", script],
                capture_output=True,
                text=True,
                check=True,
            )
            raw_output = result.stdout.strip()
            try:
                parsed = ast.literal_eval(raw_output)
                groups = [g.strip('"') for g in parsed if isinstance(g, str)]
            except ValueError:
                print("⚠️ Failed to parse AppleScript result. Raw output:")
                print(raw_output)
                groups = []

            LabelBoostCLI._devonthink_groups_cache = groups
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(groups, f, indent=2, ensure_ascii=False)
            return groups
        except subprocess.CalledProcessError as err:
            print("⚠️ Could not retrieve groups from DEVONthink:", err)
            return []

    def __init__(self) -> None:
        self.config_path = CONFIG.label_config_path
        self.training_dir = CONFIG.training_data_dir
        self.config: Dict[str, Dict[str, Any]] = self._load_config()
        self._sync_labels()
        self._maybe_refresh_devonthink_groups()

    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Load the label_boosts.json configuration file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (OSError, json.JSONDecodeError):
                print("⚠️  Failed to parse config. Starting with empty config.")
        return {}

    def _save_config(self) -> None:
        """Write the label configuration to disk."""
        with open(self.config_path, "w", encoding="utf-8") as file:
            json.dump(self.config, file, indent=2, ensure_ascii=False)

    def _sync_labels(self) -> None:
        """Ensure config entries exist for all training labels, and optionally remove stale ones."""
        existing_labels = {p.name for p in self.training_dir.iterdir() if p.is_dir()}
        for label in sorted(existing_labels):
            if label not in self.config:
                self.config[label] = {
                    "boost_phrases": [],
                    "boost": 0.0,
                    "final_name_pattern": None,
                    "devonthink_group": None,
                }

        removed = [label for label in self.config if label not in existing_labels]
        if removed:
            print(f"🧹 Found stale config entries: {', '.join(removed)}")
            confirm = questionary.confirm(
                "Remove these entries from config?", style=CUSTOM_STYLE
            ).ask()
            if confirm:
                for label in removed:
                    del self.config[label]
                print("✅ Stale entries removed.")

    def _maybe_refresh_devonthink_groups(self) -> None:
        """Prompt the user to optionally refresh DEVONthink groups once per session."""
        refresh = questionary.confirm(
            "Refresh DEVONthink group list?", default=False, style=CUSTOM_STYLE
        ).ask()
        if refresh:
            self._get_devonthink_groups(force_refresh=True)
        else:
            self._get_devonthink_groups(force_refresh=False)

    def _is_complete(self, label: str) -> bool:
        """Return whether a label's configuration is complete."""
        entry = self.config[label]
        return all(
            field in entry
            and (entry[field] is None or isinstance(entry[field], (str, list, float)))
            for field in REQUIRED_FIELDS
        )

    def _edit_label(self, label: str) -> None:
        """Prompt user to edit a label's configuration."""
        if label not in self.config:
            print(f"⚠️  Unknown label selected: {label}")
            return

        entry = self.config[label]
        print(f"\n🔧 Editing label: {label}\n")

        phrases = questionary.text(
            "Boost phrases (comma-separated)",
            default=", ".join(entry.get("boost_phrases", [])),
            style=CUSTOM_STYLE,
        ).ask()
        entry["boost_phrases"] = [p.strip() for p in phrases.split(",") if p.strip()]

        boost = questionary.text(
            "Boost (0.0 to 1.0)",
            default=str(entry.get("boost") or "0.0"),
            validate=lambda x: x.replace(".", "", 1).isdigit() or "Must be a float",
            style=CUSTOM_STYLE,
        ).ask()
        entry["boost"] = float(boost)

        pattern = questionary.text(
            "Final name pattern", default=entry.get("final_name_pattern") or "", style=CUSTOM_STYLE
        ).ask()
        entry["final_name_pattern"] = pattern or None

        dt_groups = self._get_devonthink_groups()
        if dt_groups:
            devon_group = questionary.autocomplete(
                "Devonthink group (type to filter):",
                choices=dt_groups,
                default=entry.get("devonthink_group") or "",
                style=CUSTOM_STYLE,
            ).ask()
            entry["devonthink_group"] = devon_group or None
        else:
            print("⚠️ DEVONthink group list unavailable. Please enter manually.")
            devon_group = questionary.text(
                "Devonthink group", default=entry.get("devonthink_group") or "", style=CUSTOM_STYLE
            ).ask()
            entry["devonthink_group"] = devon_group or None

        self.config[label] = entry
        self._save_config()
        print("✅ Saved.")

    def run(self) -> None:
        """Run the menu-driven CLI."""
        while True:
            filter_mode = questionary.select(
                "What do you want to show?",
                choices=[
                    questionary.Choice("All labels", value="all"),
                    questionary.Choice("Only incomplete labels", value="incomplete"),
                    questionary.Choice("Quit", value="__quit__"),
                ],
                style=CUSTOM_STYLE,
            ).ask()

            if filter_mode == "__quit__" or filter_mode is None:
                break

            filtered_labels = (
                [label for label in sorted(self.config) if not self._is_complete(label)]
                if filter_mode == "incomplete"
                else sorted(self.config)
            )

            if not filtered_labels:
                print("✅ All labels are complete.")
                continue

            while True:
                choices = [
                    questionary.Choice(
                        title=f"{'✅' if self._is_complete(label) else '❌'} {label}", value=label
                    )
                    for label in filtered_labels
                ]
                choices.append(questionary.Choice("Back to filter selection", value="__back__"))

                result = questionary.select(
                    "Choose a label to edit:", choices=choices, style=CUSTOM_STYLE
                ).ask()
                if result == "__back__" or result is None:
                    break
                self._edit_label(result)


def main() -> None:
    """Entry point for CLI."""

    LabelBoostCLI().run()


if __name__ == "__main__":
    try:
        LabelBoostCLI().run()
    except KeyboardInterrupt:
        print("\n👋 Exiting.")
        sys.exit(0)
