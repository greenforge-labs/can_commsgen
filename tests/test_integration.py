"""End-to-end integration tests for the full pipeline."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from can_commsgen.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"
EXAMPLE_SCHEMA = FIXTURES / "example_schema.yaml"

GOLDEN_PLC_FILES = [
    "CAN_EXTRACT_BITS.st",
    "CAN_INSERT_BITS.st",
    "DriveMode.st",
    "DRIVE_STATUS_SEND.st",
    "GVL.st",
    "main_input.st",
    "MOTOR_COMMAND_RECV.st",
    "PC_STATE_RECV.st",
]

GOLDEN_CPP_FILES = [
    "can_messages.hpp",
]

GOLDEN_REPORT_FILES = [
    "packing_report.txt",
]


def test_e2e_snapshot_all_outputs(tmp_path: Path) -> None:
    """Run CLI and compare ALL output files against golden files."""
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

    assert result.exit_code == 0, f"CLI failed:\n{result.output}"

    # Compare all PLC golden files
    for fname in GOLDEN_PLC_FILES:
        golden = (GOLDEN / "plc" / fname).read_text()
        generated = (plc_dir / fname).read_text()
        assert generated == golden, (
            f"PLC file {fname} does not match golden file"
        )

    # Compare C++ golden files
    for fname in GOLDEN_CPP_FILES:
        golden = (GOLDEN / "cpp" / fname).read_text()
        generated = (cpp_dir / fname).read_text()
        assert generated == golden, (
            f"C++ file {fname} does not match golden file"
        )

    # Compare report golden file
    for fname in GOLDEN_REPORT_FILES:
        golden = (GOLDEN / "report" / fname).read_text()
        generated = report_path.read_text()
        assert generated == golden, (
            f"Report file {fname} does not match golden file"
        )

    # Verify no unexpected files were generated
    generated_plc_files = sorted(f.name for f in plc_dir.iterdir())
    assert generated_plc_files == sorted(GOLDEN_PLC_FILES), (
        f"Unexpected PLC files: {set(generated_plc_files) - set(GOLDEN_PLC_FILES)}"
    )

    generated_cpp_files = sorted(f.name for f in cpp_dir.iterdir())
    assert generated_cpp_files == sorted(GOLDEN_CPP_FILES), (
        f"Unexpected C++ files: {set(generated_cpp_files) - set(GOLDEN_CPP_FILES)}"
    )
