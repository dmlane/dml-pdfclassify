"""Main entry point for pdfclassify"""

import sys

if sys.version_info[:2] != (3, 12):
    print(
        "pdfclassify requires Python 3.12 currently, but found Python "
        + f"{sys.version_info[0]}.{sys.version_info[1]}."
    )

    sys.exit(1)
else:
    import argparse
    from importlib.metadata import version
    from pathlib import Path

    from pdfclassify._util import MyException, RawFormatter
    from pdfclassify.pdf_semantic_classifier import PDFSemanticClassifier

HOME = Path.home()
CLOUD_DIR = HOME / "Library/Mobile Documents/com~apple~CloudDocs/net.dmlane/pdfclassify"


class Pdfclassify:
    """Main class"""

    parser = None
    version = None
    verbose = False
    input_file = None
    data_dir = None
    output_path = None

    def __init__(self):
        pass

    def make_cmd_line_parser(self):
        """Set up the command line parser"""
        self.parser = argparse.ArgumentParser(
            formatter_class=RawFormatter,
            description="PDF classifier based on content etc",
        )
        self.parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=version("pdfclassify"),
            help="Print the version number",
        )
        self.parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            default=False,
            help="Verbose output",
        )
        self.parser.add_argument(
            "-d",
            "--data-dir",
            default=str(CLOUD_DIR / "training_data"),
            help="Path to the directory containing the training data",
        )

        self.parser.add_argument(
            "-o",
            "--output-path",
            default=str(CLOUD_DIR / "output"),
            help="Path to save the labelled file",
        )
        self.parser.add_argument(
            "input_file",
            help="Input PDF file to classify",
        )

    def parse_args(self):
        """Parse the command line arguments"""
        args = self.parser.parse_args()

        self.verbose = args.verbose
        self.input_file = args.input_file
        self.data_dir = args.data_dir
        self.output_path = args.output_path
        if self.input_file is None:
            raise MyException("Input file is required", 1)

    def run(self):
        """Main entry point"""
        self.make_cmd_line_parser()
        self.parse_args()

        classifier = PDFSemanticClassifier(data_dir=self.data_dir)
        classifier.train()
        label = classifier.predict(
            pdf_path=self.input_file,
            confidence_threshold=0.7,
        )
        print(f"Predicted label: {label}")


def main():
    """Main entry point"""
    try:
        Pdfclassify().run()
    except MyException as e:
        print(e.msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
