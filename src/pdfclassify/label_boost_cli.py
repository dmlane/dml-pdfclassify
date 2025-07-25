"""Interactive CLI for managing label_boosts.json configuration with full
DEVONthink and validation support."""

import ast
import json
import subprocess
import sys
from typing import List

import questionary
from prompt_toolkit.styles import Style

from pdfclassify._util import CONFIG  # pylint: disable=no-name-in-module
from pdfclassify.label_boost_manager import LabelBoostManager
from pdfclassify.label_config import LabelConfig

# pylint: disable=too-few-public-methods, protected-access, no-member

CUSTOM_STYLE = Style.from_dict(
    {
        "question": "#00ffff bold",
        "answer": "#ffffff",
        "pointer": "#00ff00 bold",
        "highlighted": "#00ff00 bold",
        "selected": "#00ff00 bold",
        "instruction": "#888888 italic",
        "separator": "#cc5454",
        "text": "#ffffff",
    }
)

CACHE_PATH = CONFIG.cache_dir / "devonthink_groups.json"


class LabelBoostCLI:
    """Interactive CLI for editing the label_boosts.json config."""

    _devonthink_groups_cache: List[str] = []

    def __init__(self) -> None:
        self.boosts = LabelBoostManager()
        self.config = self.boosts.config

        for entry in self.config.values():
            if entry.preferred_context is None:
                entry.preferred_context = []

        if self.boosts.missing_labels():
            print("🔄 New training labels detected.")
            self.boosts.sync_with_training_labels(interactive=True)
            self.config = self.boosts.config
            self.boosts.save()

        self._maybe_refresh_devonthink_groups()

    def _maybe_refresh_devonthink_groups(self) -> None:
        if not self._get_devonthink_groups():
            refresh = questionary.confirm(
                "Refresh DEVONthink group list?", style=CUSTOM_STYLE
            ).ask()
            if refresh:
                self._get_devonthink_groups(force_refresh=True)

    def _get_devonthink_groups(self, force_refresh: bool = False) -> List[str]:
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

    def _edit_label(self, label: str) -> None:
        current = self.boosts.get(label)
        fields = list(current.to_dict().keys())
        updated = current.to_dict()

        print(f"\n🔧 Editing label: {label}\n")
        for field in fields:
            value = updated.get(field)
            default_str = ", ".join(value) if isinstance(value, list) else str(value)
            answer = questionary.text(f"{field}", default=default_str, style=CUSTOM_STYLE).ask()
            try:
                # 🔧 Convert to correct type before validation
                if field == "boost":
                    answer = float(answer)
                elif field in ("preferred_context", "minimum_parts"):
                    if isinstance(answer, str):
                        try:
                            parsed = ast.literal_eval(answer)
                            if isinstance(parsed, list):
                                answer = parsed
                            else:
                                raise ValueError
                        except Exception:  # pylint: disable=broad-exception-caught
                            # fallback to naive comma-split
                            answer = [item.strip() for item in answer.split(",") if item.strip()]

                updated[field] = LabelConfig.validate_field(field, answer)
            except ValueError as err:
                print(f"❌ Validation failed for {field}: {err}. Keeping previous value.")

        self.boosts.config[label] = LabelConfig.from_dict(updated)
        self.boosts.save()
        print("✅ Saved.")

    def run(self) -> None:
        """Run the label boost CLI."""
        while True:
            mode = questionary.select(
                "Choose filter:",
                choices=[
                    questionary.Choice("All labels", value="all"),
                    questionary.Choice("Only incomplete labels", value="incomplete"),
                    questionary.Choice("Quit", value="quit"),
                ],
                style=CUSTOM_STYLE,
            ).ask()

            if mode == "quit":
                break

            while True:
                labels = (
                    [l for l in sorted(self.config) if not self.boosts.is_complete(l)]
                    if mode == "incomplete"
                    else sorted(self.config)
                )

                if not labels:
                    print("✅ All labels are complete.")
                    break

                choices = [
                    questionary.Choice(
                        title=(f"{'✅' if self.boosts.is_complete(label) else '❌'} {label}"),
                        value=label,
                    )
                    for label in labels
                ]
                choices.append(questionary.Choice("Back", value="back"))

                selected = questionary.select(
                    "Select a label to edit:", choices=choices, style=CUSTOM_STYLE
                ).ask()

                if selected in (None, "back"):
                    break  # go back to filter selection

                self._edit_label(selected)


def main() -> None:
    """Main entry point for CLI."""
    if sys.platform == "darwin":
        result = subprocess.run(
            [
                "mdfind",
                "kMDItemCFBundleIdentifier == 'com.devon-technologies.think3' || "
                "kMDItemCFBundleIdentifier == 'com.devon-technologies.think4'",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if not result.stdout.strip():
            print("❌ DEVONthink is not installed or not scriptable.")
            sys.exit(1)

    try:
        LabelBoostCLI().run()
    except KeyboardInterrupt:
        print("\n👋 Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
