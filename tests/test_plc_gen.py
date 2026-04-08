"""Tests for PLC Structured Text generation."""

from pathlib import Path

import yaml

from can_commsgen.plc import generate_plc
from can_commsgen.schema import load_schema


def test_enum_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated DriveMode.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "DriveMode.st").read_text()
    expected = (golden_plc_dir / "DriveMode.st").read_text()
    assert generated == expected


def test_extract_bits_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated CAN_EXTRACT_BITS.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "CAN_EXTRACT_BITS.st").read_text()
    expected = (golden_plc_dir / "CAN_EXTRACT_BITS.st").read_text()
    assert generated == expected


def test_insert_bits_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated CAN_INSERT_BITS.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "CAN_INSERT_BITS.st").read_text()
    expected = (golden_plc_dir / "CAN_INSERT_BITS.st").read_text()
    assert generated == expected


def test_motor_command_recv_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated MOTOR_COMMAND_RECV.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "MOTOR_COMMAND_RECV.st").read_text()
    expected = (golden_plc_dir / "MOTOR_COMMAND_RECV.st").read_text()
    assert generated == expected


def test_drive_status_send_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated DRIVE_STATUS_SEND.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "DRIVE_STATUS_SEND.st").read_text()
    expected = (golden_plc_dir / "DRIVE_STATUS_SEND.st").read_text()
    assert generated == expected


def test_gvl_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated GVL.gvl.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "GVL.gvl.st").read_text()
    expected = (golden_plc_dir / "GVL.gvl.st").read_text()
    assert generated == expected


def test_pc_state_recv_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated PC_STATE_RECV.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "PC_STATE_RECV.st").read_text()
    expected = (golden_plc_dir / "PC_STATE_RECV.st").read_text()
    assert generated == expected


def test_main_input_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated main_input.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "main_input.st").read_text()
    expected = (golden_plc_dir / "main_input.st").read_text()
    assert generated == expected


def test_custom_gvl_name(
    example_schema_path: Path,
    tmp_path: Path,
) -> None:
    """Custom gvl_name controls output filename and GVL references."""
    # Create a schema with custom gvl_name
    with open(example_schema_path) as f:
        raw = yaml.safe_load(f)
    raw["plc"]["gvl_name"] = "CUSTOM_GVL"
    custom_yaml = tmp_path / "custom.yaml"
    with open(custom_yaml, "w") as f:
        yaml.dump(raw, f)

    schema = load_schema([custom_yaml])
    out = tmp_path / "out"
    generate_plc(schema, out)

    # GVL file should use custom name
    assert (out / "CUSTOM_GVL.gvl.st").exists()
    assert not (out / "GVL.gvl.st").exists()

    # RECV FBs should reference CUSTOM_GVL
    recv_text = (out / "MOTOR_COMMAND_RECV.st").read_text()
    assert "CUSTOM_GVL.targetVelocity_rpm" in recv_text
    assert "CUSTOM_GVL.torqueLimit_Nm" in recv_text
    assert "CUSTOM_GVL.motorCommandWithinTimeout" in recv_text

    pc_state_text = (out / "PC_STATE_RECV.st").read_text()
    assert "CUSTOM_GVL.driveMode" in pc_state_text
    assert "CUSTOM_GVL.pcStateWithinTimeout" in pc_state_text
