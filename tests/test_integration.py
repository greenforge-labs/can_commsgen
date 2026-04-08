"""End-to-end integration tests for the full pipeline."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from click.testing import CliRunner
import pytest

from can_commsgen.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"
EXAMPLE_SCHEMA = FIXTURES / "example_schema.yaml"

GOLDEN_PLC_FILES = [
    "CAN_EXTRACT_BITS.st",
    "CAN_INSERT_BITS.st",
    "DriveMode.st",
    "DRIVE_STATUS_SEND.st",
    "GVL.gvl.st",
    "main_input.st",
    "MOTOR_COMMAND_RECV.st",
    "PC_STATE_RECV.st",
]

GOLDEN_CPP_FILES = [
    "can_interface.cpp",
    "can_interface.hpp",
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
            "--schema",
            str(EXAMPLE_SCHEMA),
            "--out-plc",
            str(plc_dir),
            "--out-cpp",
            str(cpp_dir),
            "--out-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, f"CLI failed:\n{result.output}"

    # Compare all PLC golden files
    for fname in GOLDEN_PLC_FILES:
        golden = (GOLDEN / "plc" / fname).read_text()
        generated = (plc_dir / fname).read_text()
        assert generated == golden, f"PLC file {fname} does not match golden file"

    # Compare C++ golden files
    for fname in GOLDEN_CPP_FILES:
        golden = (GOLDEN / "cpp" / fname).read_text()
        generated = (cpp_dir / fname).read_text()
        assert generated == golden, f"C++ file {fname} does not match golden file"

    # Compare report golden file
    for fname in GOLDEN_REPORT_FILES:
        golden = (GOLDEN / "report" / fname).read_text()
        generated = report_path.read_text()
        assert generated == golden, f"Report file {fname} does not match golden file"

    # Verify no unexpected files were generated
    generated_plc_files = sorted(f.name for f in plc_dir.iterdir())
    assert generated_plc_files == sorted(
        GOLDEN_PLC_FILES
    ), f"Unexpected PLC files: {set(generated_plc_files) - set(GOLDEN_PLC_FILES)}"

    generated_cpp_files = sorted(f.name for f in cpp_dir.iterdir())
    assert generated_cpp_files == sorted(
        GOLDEN_CPP_FILES
    ), f"Unexpected C++ files: {set(generated_cpp_files) - set(GOLDEN_CPP_FILES)}"


def test_multi_schema_merge(tmp_path: Path) -> None:
    """Split example schema into two files, merge via CLI, verify output matches golden."""
    # File 1: motor_command only (no enums)
    schema_a = tmp_path / "schema_a.yaml"
    schema_a.write_text("""\
version: "1"

plc:
  can_channel: CHAN_0

messages:
  - name: motor_command
    id: 0x00000100
    direction: pc_to_plc
    timeout_ms: 500
    fields:
      - name: target_velocity
        type: real
        min: -3200.0
        max: 3200.0
        resolution: 0.1
        unit: rpm
      - name: torque_limit
        type: real
        min: 0.0
        max: 655.35
        resolution: 0.01
        unit: Nm
""")

    # File 2: drive_status + pc_state (with DriveMode enum)
    schema_b = tmp_path / "schema_b.yaml"
    schema_b.write_text("""\
version: "1"

plc:
  can_channel: CHAN_0

enums:
  - name: DriveMode
    values:
      IDLE:     0
      VELOCITY: 1
      POSITION: 2
      TORQUE:   3

messages:
  - name: drive_status
    id: 0x00000200
    direction: plc_to_pc
    fields:
      - name: actual_velocity
        type: real
        min: -3200.0
        max: 3200.0
        resolution: 0.1
        unit: rpm
      - name: motor_temp
        type: real
        min: -40.0
        max: 200.0
        resolution: 0.1
        unit: degC
      - name: bus_voltage
        type: real
        min: 0.0
        max: 102.3
        resolution: 0.1
        unit: V
      - name: fault_code
        type: uint8

  - name: pc_state
    id: 0x00000300
    direction: pc_to_plc
    timeout_ms: 1000
    fields:
      - name: drive_mode
        type: DriveMode
""")

    plc_dir = tmp_path / "plc"
    cpp_dir = tmp_path / "cpp"
    report_path = tmp_path / "report" / "packing_report.txt"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--schema",
            str(schema_a),
            "--schema",
            str(schema_b),
            "--out-plc",
            str(plc_dir),
            "--out-cpp",
            str(cpp_dir),
            "--out-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, f"CLI failed:\n{result.output}"

    # Compare all PLC golden files
    for fname in GOLDEN_PLC_FILES:
        golden = (GOLDEN / "plc" / fname).read_text()
        generated = (plc_dir / fname).read_text()
        assert generated == golden, f"PLC file {fname} does not match golden file"

    # Compare C++ golden files
    for fname in GOLDEN_CPP_FILES:
        golden = (GOLDEN / "cpp" / fname).read_text()
        generated = (cpp_dir / fname).read_text()
        assert generated == golden, f"C++ file {fname} does not match golden file"

    # Compare report golden file
    golden = (GOLDEN / "report" / "packing_report.txt").read_text()
    generated = report_path.read_text()
    assert generated == golden, "Report does not match golden file"


@pytest.mark.skipif(
    shutil.which("cmake") is None or shutil.which("g++") is None,
    reason="C++ toolchain (cmake, g++) not available",
)
def test_cpp_roundtrip_via_cli(tmp_path: Path) -> None:
    """Run CLI to generate C++, then compile and run the C++ roundtrip tests."""
    cpp_dir = tmp_path / "cpp"
    plc_dir = tmp_path / "plc"

    # Generate via CLI
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--schema",
            str(EXAMPLE_SCHEMA),
            "--out-plc",
            str(plc_dir),
            "--out-cpp",
            str(cpp_dir),
        ],
    )
    assert result.exit_code == 0, f"CLI failed:\n{result.output}"

    # Copy generated C++ files into the roundtrip test's expected location
    roundtrip_dir = Path(__file__).parent / "cpp_tests"
    generated_dir = roundtrip_dir / "generated"
    generated_dir.mkdir(exist_ok=True)
    for fname in ("can_messages.hpp", "can_interface.hpp", "can_interface.cpp"):
        shutil.copy2(cpp_dir / fname, generated_dir / fname)

    # Build with cmake
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    cmake_result = subprocess.run(
        ["cmake", str(roundtrip_dir)],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert cmake_result.returncode == 0, f"cmake configure failed:\n{cmake_result.stderr}"

    build_result = subprocess.run(
        ["cmake", "--build", "."],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"cmake build failed:\n{build_result.stderr}"

    # Run roundtrip tests via ctest
    test_result = subprocess.run(
        ["ctest", "--output-on-failure"],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert test_result.returncode == 0, f"C++ roundtrip tests failed:\n{test_result.stdout}\n{test_result.stderr}"
