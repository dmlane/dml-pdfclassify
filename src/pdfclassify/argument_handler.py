"""Argument handler for this project."""

from argparse import ArgumentParser, Namespace, _HelpAction
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pdfclassify._util import CONFIG, RawFormatter

ICLOUD_PATH = "Library/Mobile Documents/com~apple~CloudDocs/net.dmlane/pdfclassify"
CLOUD_DIR = Path.home() / ICLOUD_PATH
DEFAULT_TRAINING_PATH = (CLOUD_DIR / "training_data").as_posix()
DEFAULT_OUTPUT_PATH = (CLOUD_DIR / "output").as_posix()


class HelpAndCustom(_HelpAction):
    """Help action that prints the help text and then runs custom logic."""

    def __call__(self, parser, namespace, values, option_string=None):
        # 1) Print the normal help text
        parser.print_help()
        # 2) Then run your custom code
        CONFIG.show_config()
        # 3) Exit as usual
        parser.exit()


def get_version() -> str:
    """Lazy import of package version to speed up CLI loading."""
    from importlib.metadata import version  # pylint: disable=import-outside-toplevel

    return version("pdfclassify")


@dataclass
class ParsedArgs:
    """Parsed command-line arguments for the PDF classifier."""

    verbose: bool
    input_file: str
    training_data_path: str
    output_path: str
    no_rename: bool
    restore_original: bool
    info: bool


class CustomArgumentParser(ArgumentParser):
    """Custom ArgumentParser with overridden error method."""

    def error(self, message):
        """Override default error method to add a leading newline."""
        self.print_usage()
        self.exit(2, f"\nerror: {message}\n")


class ArgumentHandler:
    """Class for handling command-line arguments."""

    def __init__(self):
        self.parser = self._make_cmd_line_parser()

    def _make_cmd_line_parser(self) -> ArgumentParser:
        parser = CustomArgumentParser(
            description="Classify PDF files based on semantic embeddings",
            formatter_class=RawFormatter,
            add_help=False,
        )
        parser.add_argument(
            "-h",
            "--help",
            action=HelpAndCustom,
            help="show this help message and then run custom code",
        )
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=get_version(),
            help="Print the version number",
        )
        parser.add_argument(
            "-v", "--verbose", action="store_true", default=False, help="Verbose output"
        )
        parser.add_argument(
            "-t",
            "--training-data-path",
            default=CONFIG.training_data_dir,
            help="Path to the directory containing the training data",
        )
        parser.add_argument(
            "-o",
            "--output-path",
            default=CONFIG.output_dir,
            help="Path to save the labelled file",
        )

        exclusive_group = parser.add_mutually_exclusive_group()
        exclusive_group.add_argument(
            "-n", "--no-rename", action="store_true", help="Do not rename the input file"
        )
        exclusive_group.add_argument(
            "-r", "--restore-original", action="store_true", help="Restore original filename"
        )
        exclusive_group.add_argument(
            "-i", "--info", action="store_true", help="Display file metadata"
        )

        parser.add_argument("input_file", help="Input PDF file to classify")
        return parser

    def parse_args(self) -> ParsedArgs:
        """Parse the command-line arguments from sys.argv."""
        return self._parse(self.parser.parse_args())

    def parse_args_from(self, argv: Sequence[str]) -> ParsedArgs:
        """Parse arguments from a provided argument list (for testing)."""
        return self._parse(self.parser.parse_args(argv))

    def _parse(self, args: Namespace) -> ParsedArgs:
        """Convert Namespace to ParsedArgs dataclass."""
        if not args.input_file or not args.input_file.strip():
            raise ValueError("Input file is required")

        return ParsedArgs(
            verbose=args.verbose,
            input_file=args.input_file,
            training_data_path=args.training_data_path,
            output_path=args.output_path,
            no_rename=args.no_rename,
            restore_original=args.restore_original,
            info=args.info,
        )
