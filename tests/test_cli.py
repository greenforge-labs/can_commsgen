"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from can_commsgen.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_SCHEMA = FIXTURES / "example_schema.yaml"

EXPECTED_PLC_FILES = [
    "CAN_EXTRACT_BITS.st",
    "CAN_INSERT_BITS.st",
    "DriveMode.st",
    "MOTOR_COMMAND_RECV.st",
    "PC_STATE_RECV.st",
    "DRIVE_STATUS_SEND.st",
    "GVL.st",
    "main_input.st",
]


def test_cli_smoke(tmp_path: Path) -> None:
    """CLI exits 0 and produces expected files."""
    plc_dir = tmp_path / "plc"
    cpp_dir = tmp_path / "cpp"
    report_path = tmp_path / "report" / "packing_report.txt"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--schema", str(EXAMPLE_SCHEMA),
            "--out-plc", str(plc_dir),
            "--out-cpp", str(cpp_dir),
            "--out-report", str(report_path),
        ],
    )

    assert result.exit_code == 0, result.output

    # PLC files exist
    for fname in EXPECTED_PLC_FILES:
        assert (plc_dir / fname).exists(), f"Missing PLC file: {fname}"

    # C++ header exists
    assert (cpp_dir / "can_messages.hpp").exists()

    # Report exists
    assert report_path.exists()


def test_cli_no_report(tmp_path: Path) -> None:
    """CLI works without --out-report."""
    plc_dir = tmp_path / "plc"
    cpp_dir = tmp_path / "cpp"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--schema", str(EXAMPLE_SCHEMA),
            "--out-plc", str(plc_dir),
            "--out-cpp", str(cpp_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (cpp_dir / "can_messages.hpp").exists()


def test_cli_invalid_schema(tmp_path: Path) -> None:
    """CLI exits 1 with error on stderr for invalid schema."""
    bad_schema = tmp_path / "bad.yaml"
    bad_schema.write_text("version: 1\nmessages: not_a_list\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--schema", str(bad_schema),
            "--out-plc", str(tmp_path / "plc"),
            "--out-cpp", str(tmp_path / "cpp"),
        ],
    )

    assert result.exit_code == 1
    assert result.output.strip()  # error message printed
