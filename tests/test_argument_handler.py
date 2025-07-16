"""Unit tests for the ArgumentHandler class in pdfclassify.argument_handler."""

from importlib.metadata import version
from pathlib import Path

import pytest

from pdfclassify._util import CONFIG
from pdfclassify.argument_handler import ArgumentHandler, ParsedArgs


def test_valid_arguments() -> None:
    """Test parsing with all valid arguments including paths and flags."""
    args = ArgumentHandler().parse_args_from(
        ["-v", "-t", "/tmp/training", "-o", "/tmp/output", "-n", "sample.pdf"]
    )
    assert isinstance(args, ParsedArgs)
    assert args.verbose is True
    assert str(args.input_file) == "sample.pdf"
    assert str(args.training_data_path) == "/tmp/training"
    assert str(args.output_path) == "/tmp/output"
    assert args.no_rename is True
    assert args.restore_original is False
    assert args.info is False


def test_restore_original_flag() -> None:
    """Test that the --restore-original flag is parsed correctly."""
    args = ArgumentHandler().parse_args_from(["-r", "document.pdf"])
    assert args.restore_original is True
    assert not args.no_rename
    assert not args.info


def test_info_flag() -> None:
    """Test that the --info flag is parsed correctly."""
    args = ArgumentHandler().parse_args_from(["-i", "report.pdf"])
    assert args.info is True
    assert not args.no_rename
    assert not args.restore_original


def test_mutually_exclusive_flags_fail(capsys: pytest.CaptureFixture) -> None:
    """Test that combining mutually exclusive flags results in an error, and stderr
    is cleanly separated."""
    handler = ArgumentHandler()

    with pytest.raises(SystemExit):
        handler.parse_args_from(["-n", "-r", "file.pdf"])
    captured = capsys.readouterr()
    print("\n" + captured.err)

    with pytest.raises(SystemExit):
        handler.parse_args_from(["-i", "-r", "file.pdf"])
    captured = capsys.readouterr()
    print("\n" + captured.err)


def test_missing_input_file_raises(capsys: pytest.CaptureFixture) -> None:
    """Test that missing the required input_file argument raises SystemExit."""
    with pytest.raises(SystemExit):
        ArgumentHandler().parse_args_from([])
    captured = capsys.readouterr()
    print("\n" + captured.err)


def test_default_paths_are_set(monkeypatch) -> None:
    """Test that default training and output paths are set when omitted."""
    # Override CONFIG defaults for isolation

    test_train = Path("/tmp/training_data")
    test_output = Path("/tmp/output")
    monkeypatch.setattr(CONFIG, "training_data_dir", test_train)
    monkeypatch.setattr(CONFIG, "output_dir", test_output)

    args = ArgumentHandler().parse_args_from(["sample.pdf"])
    assert isinstance(args.training_data_path, Path)
    assert (
        test_train in Path(args.training_data_path).parents or args.training_data_path == test_train
    )
    assert isinstance(args.output_path, Path)
    assert test_output in Path(args.output_path).parents or args.output_path == test_output


def test_version_output(capsys: pytest.CaptureFixture) -> None:
    """Test that the --version flag prints the expected package version and exits."""
    expected_version = version("dml-pdfclassify")
    with pytest.raises(SystemExit):
        ArgumentHandler().parse_args_from(["--version"])
    captured = capsys.readouterr()
    assert expected_version in captured.out
