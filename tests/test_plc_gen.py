"""Tests for PLC Structured Text generation."""

from pathlib import Path

import yaml

from can_commsgen.plc import (
    _enum_from_int_fn_name,
    _recv_extract_expr,
    generate_plc,
)
from can_commsgen.schema import EnumDef, FieldDef, load_schema


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


def test_enum_from_int_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated DriveMode_FROM_INT.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "DriveMode_FROM_INT.st").read_text()
    expected = (golden_plc_dir / "DriveMode_FROM_INT.st").read_text()
    assert generated == expected


def test_enum_from_int_fn_name() -> None:
    """_enum_from_int_fn_name produces expected naming."""
    assert _enum_from_int_fn_name("DriveMode") == "DriveMode_FROM_INT"
    assert _enum_from_int_fn_name("ErrorCode") == "ErrorCode_FROM_INT"


def test_recv_extract_expr_enum_uses_from_int() -> None:
    """Enum fields in RECV FBs use the _FROM_INT conversion function."""
    enum = EnumDef(
        name="DriveMode",
        values={"IDLE": 0, "VELOCITY": 1},
        wire_bits=2,
        backing_type_plc="USINT",
        backing_type_cpp="uint8_t",
    )
    field = FieldDef(
        name="drive_mode",
        type="DriveMode",
        wire_bits=2,
        wire_signed=False,
        bit_offset=0,
    )
    result = _recv_extract_expr(field, {"DriveMode": enum})
    assert result == "DriveMode_FROM_INT(TO_USINT(CAN_EXTRACT_BITS(rxData, 0, 2, FALSE)))"


def test_recv_extract_expr_integer_unchanged() -> None:
    """Integer fields still use direct TO_<type> cast."""
    field = FieldDef(
        name="fault_code",
        type="uint8",
        wire_bits=8,
        wire_signed=False,
        bit_offset=0,
    )
    result = _recv_extract_expr(field, {})
    assert result == "TO_USINT(CAN_EXTRACT_BITS(rxData, 0, 8, FALSE))"


def test_enum_from_int_file_generated_per_enum(tmp_path: Path) -> None:
    """Each enum produces a corresponding _FROM_INT.st file."""
    schema = load_schema([Path("tests/fixtures/example_schema.yaml")])
    generate_plc(schema, tmp_path)

    for enum in schema.enums:
        fn_file = tmp_path / f"{enum.name}_FROM_INT.st"
        assert fn_file.exists(), f"Missing {fn_file.name}"
        content = fn_file.read_text()
        assert f"FUNCTION {enum.name}_FROM_INT" in content
        assert f": {enum.name}" in content
        # Default falls back to first enum value
        first_value = next(iter(enum.values))
        assert f"{enum.name}.{first_value}" in content


def test_send_fb_data_inline_init(
    example_schema_path: Path,
    tmp_path: Path,
) -> None:
    """SEND FB initializes data array inline rather than with a separate statement."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    send_text = (tmp_path / "DRIVE_STATUS_SEND.st").read_text()
    assert "data : ARRAY[0..7] OF USINT := [0, 0, 0, 0, 0, 0, 0, 0];" in send_text
    assert "data := [8(0)];" not in send_text


def test_templates_have_begin_implementation_comment(
    example_schema_path: Path,
    tmp_path: Path,
) -> None:
    """All generated FBs and helpers include the BEGIN IMPLEMENTATION comment."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    files_with_impl_comment = [
        "CAN_EXTRACT_BITS.st",
        "CAN_INSERT_BITS.st",
        "MOTOR_COMMAND_RECV.st",
        "DRIVE_STATUS_SEND.st",
        "PC_STATE_RECV.st",
        "DriveMode_FROM_INT.st",
    ]
    for fname in files_with_impl_comment:
        content = (tmp_path / fname).read_text()
        assert "// --- BEGIN IMPLEMENTATION ---" in content, f"Missing comment in {fname}"
