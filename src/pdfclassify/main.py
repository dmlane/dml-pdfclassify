"""Main entry point for pdfclassify"""

import sys

from pdfclassify.argument_handler import ArgumentHandler
from pdfclassify.pdf_process import PdfProcess

REQUIRED_PYTHON = (3, 12)

if sys.version_info[:2] != REQUIRED_PYTHON:
    print(
        f"pdfclassify requires Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}, but found Python "
        f"{sys.version_info[0]}.{sys.version_info[1]}."
    )
    sys.exit(1)
else:
    from pdfclassify._util import MyException


class Pdfclassify:
    """Main class"""

    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.parser = ArgumentHandler()

    def run(self):
        """Main entry point"""

        args = self.parser.parse_args()
        pdf = PdfProcess(args.input_file)

        if args.info:
            pdf.display_info()
            return
        if args.restore_original:
            pdf.restore_original_state()
            return
        pdf.predict(args)


def main():
    """Main entry point"""

    try:
        Pdfclassify().run()
    except MyException as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
