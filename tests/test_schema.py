import re
from pathlib import Path

import jsonschema
import pytest

from can_commsgen.schema import (
    FieldDef,
    PlcConfig,
    Schema,
    SchemaError,
    cpp_var_name,
    enum_backing_type,
    fb_name,
    load_schema,
    plc_var_name,
    struct_name,
)

SCHEMA_JSON_PATH = Path(__file__).parent.parent / "schema.json"


@pytest.fixture()
def json_schema() -> dict:
    """Load the JSON Schema for CAN YAML validation."""
    import json

    with open(SCHEMA_JSON_PATH) as f:
        return json.load(f)


# ── JSON Schema structural validation tests ─────────────────────────────────


def test_example_schema_loads(example_schema_raw: dict) -> None:
    """Verify the example schema YAML can be loaded and has expected top-level keys."""
    assert "version" in example_schema_raw
    assert "messages" in example_schema_raw


def test_example_schema_validates(example_schema_raw: dict, json_schema: dict) -> None:
    """The example schema YAML must validate against schema.json."""
    jsonschema.validate(instance=example_schema_raw, schema=json_schema)


@pytest.mark.parametrize(
    "snippet, expected_error",
    [
        pytest.param(
            {"plc": {"can_channel": "CHAN_0"}, "messages": [{"name": "m", "id": 1, "direction": "pc_to_plc", "fields": [{"name": "f", "type": "bool"}]}]},
            "'version' is a required property",
            id="missing_version",
        ),
        pytest.param(
            {"version": "1", "messages": [{"name": "m", "id": 1, "direction": "pc_to_plc", "fields": [{"name": "f", "type": "bool"}]}]},
            "'plc' is a required property",
            id="missing_plc",
        ),
        pytest.param(
            {"version": "1", "plc": {"can_channel": "CHAN_0"}},
            "'messages' is a required property",
            id="missing_messages",
        ),
        pytest.param(
            {"version": "2", "plc": {"can_channel": "CHAN_0"}, "messages": [{"name": "m", "id": 1, "direction": "pc_to_plc", "fields": [{"name": "f", "type": "bool"}]}]},
            "'2' is not one of ['1']",
            id="bad_version",
        ),
        pytest.param(
            {"version": "1", "plc": {"can_channel": "CHAN_0"}, "messages": [{"name": "m", "id": 1, "direction": "sideways", "fields": [{"name": "f", "type": "bool"}]}]},
            "'sideways' is not one of",
            id="bad_direction",
        ),
        pytest.param(
            {"version": "1", "plc": {"can_channel": "CHAN_0"}, "messages": [{"name": "m", "id": 1, "direction": "pc_to_plc", "fields": [{"name": "f", "type": "bool", "extra": 1}]}]},
            "Additional properties are not allowed",
            id="extra_field_property",
        ),
        pytest.param(
            {"version": "1", "plc": {"can_channel": "CHAN_0"}, "messages": [{"name": "m", "id": 1, "direction": "pc_to_plc", "fields": []}]},
            "[] should be non-empty",
            id="empty_fields",
        ),
        pytest.param(
            {"version": "1", "plc": {"can_channel": "CHAN_0"}, "messages": []},
            "[] should be non-empty",
            id="empty_messages",
        ),
    ],
)
def test_invalid_schema_rejected(snippet: dict, expected_error: str, json_schema: dict) -> None:
    """Invalid YAML snippets must be rejected by schema.json."""
    with pytest.raises(jsonschema.ValidationError, match=re.escape(expected_error)):
        jsonschema.validate(instance=snippet, schema=json_schema)


# ── load_schema() tests ─────────────────────────────────────────────────────


def test_load_example_schema(example_schema_path: Path) -> None:
    """Loading example_schema.yaml returns a Schema with 1 enum and 3 messages."""
    schema = load_schema([example_schema_path])

    assert isinstance(schema, Schema)
    assert isinstance(schema.plc, PlcConfig)
    assert schema.plc.can_channel == "CHAN_0"

    assert len(schema.enums) == 1
    assert schema.enums[0].name == "DriveMode"
    assert schema.enums[0].values == {"IDLE": 0, "VELOCITY": 1, "POSITION": 2, "TORQUE": 3}

    assert len(schema.messages) == 3
    assert schema.messages[0].name == "motor_command"
    assert schema.messages[1].name == "drive_status"
    assert schema.messages[2].name == "pc_state"


def test_load_schema_message_fields(example_schema_path: Path) -> None:
    """Verify fields are correctly parsed from the example schema."""
    schema = load_schema([example_schema_path])

    motor_cmd = schema.messages[0]
    assert motor_cmd.id == 0x00000100
    assert motor_cmd.direction == "pc_to_plc"
    assert motor_cmd.timeout_ms == 500
    assert len(motor_cmd.fields) == 2

    vel = motor_cmd.fields[0]
    assert vel.name == "target_velocity"
    assert vel.type == "real"
    assert vel.min == -3200.0
    assert vel.max == 3200.0
    assert vel.resolution == 0.1
    assert vel.unit == "rpm"

    torque = motor_cmd.fields[1]
    assert torque.name == "torque_limit"
    assert torque.type == "real"
    assert torque.min == 0.0
    assert torque.max == 655.35
    assert torque.resolution == 0.01
    assert torque.unit == "Nm"


def test_load_schema_message_no_timeout(example_schema_path: Path) -> None:
    """Messages without timeout_ms should have None."""
    schema = load_schema([example_schema_path])
    drive_status = schema.messages[1]
    assert drive_status.timeout_ms is None


def test_load_schema_field_optional_properties(example_schema_path: Path) -> None:
    """Fields without min/max/resolution/unit have None for those."""
    schema = load_schema([example_schema_path])
    fault_code = schema.messages[1].fields[3]  # drive_status.fault_code
    assert fault_code.name == "fault_code"
    assert fault_code.type == "uint8"
    assert fault_code.min is None
    assert fault_code.max is None
    assert fault_code.resolution is None
    assert fault_code.unit is None


def test_load_schema_enum_field(example_schema_path: Path) -> None:
    """Fields referencing an enum type are loaded correctly."""
    schema = load_schema([example_schema_path])
    pc_state = schema.messages[2]
    assert pc_state.name == "pc_state"
    assert len(pc_state.fields) == 1
    assert pc_state.fields[0].name == "drive_mode"
    assert pc_state.fields[0].type == "DriveMode"


def test_load_invalid_yaml_raises(tmp_path: Path) -> None:
    """Loading a structurally invalid YAML raises SchemaError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text('version: "2"\nplc:\n  can_channel: CHAN_0\nmessages:\n  - name: m\n    id: 1\n    direction: pc_to_plc\n    fields:\n      - name: f\n        type: bool\n')
    with pytest.raises(SchemaError, match="'2' is not one of"):
        load_schema([bad])


def test_load_no_paths_raises() -> None:
    """Calling load_schema with empty list raises SchemaError."""
    with pytest.raises(SchemaError, match="No schema paths provided"):
        load_schema([])


def test_load_merge_multiple_files(tmp_path: Path) -> None:
    """Multiple schema files should merge enums and messages."""
    file1 = tmp_path / "a.yaml"
    file1.write_text(
        'version: "1"\n'
        "plc:\n  can_channel: CHAN_0\n"
        "enums:\n"
        "  - name: Mode\n"
        "    values:\n"
        "      OFF: 0\n"
        "      ON: 1\n"
        "messages:\n"
        "  - name: msg_a\n"
        "    id: 0x100\n"
        "    direction: pc_to_plc\n"
        "    fields:\n"
        "      - name: x\n"
        "        type: bool\n"
    )
    file2 = tmp_path / "b.yaml"
    file2.write_text(
        'version: "1"\n'
        "plc:\n  can_channel: CHAN_1\n"
        "messages:\n"
        "  - name: msg_b\n"
        "    id: 0x200\n"
        "    direction: plc_to_pc\n"
        "    fields:\n"
        "      - name: y\n"
        "        type: uint8\n"
    )

    schema = load_schema([file1, file2])
    # plc config from first file
    assert schema.plc.can_channel == "CHAN_0"
    # enums merged
    assert len(schema.enums) == 1
    assert schema.enums[0].name == "Mode"
    # messages merged
    assert len(schema.messages) == 2
    assert schema.messages[0].name == "msg_a"
    assert schema.messages[1].name == "msg_b"


# ── Wire type inference tests ────────────────────────────────────────────────


def _find_field(schema: Schema, msg_name: str, field_name: str) -> FieldDef:
    """Helper to find a field by message and field name."""
    for msg in schema.messages:
        if msg.name == msg_name:
            for f in msg.fields:
                if f.name == field_name:
                    return f
    raise ValueError(f"Field {msg_name}.{field_name} not found")


@pytest.mark.parametrize(
    "msg_name, field_name, expected_bits, expected_signed, expected_wire_min, expected_wire_max",
    [
        pytest.param(
            "motor_command", "target_velocity", 16, True, -32000, 32000,
            id="real_signed_target_velocity",
        ),
        pytest.param(
            "motor_command", "torque_limit", 16, False, 0, 65535,
            id="real_unsigned_torque_limit",
        ),
        pytest.param(
            "drive_status", "motor_temp", 12, True, -400, 2000,
            id="real_signed_motor_temp",
        ),
        pytest.param(
            "drive_status", "bus_voltage", 10, False, 0, 1023,
            id="real_unsigned_bus_voltage",
        ),
        pytest.param(
            "drive_status", "fault_code", 8, False, 0, 255,
            id="integer_bare_fault_code",
        ),
        pytest.param(
            "pc_state", "drive_mode", 2, False, 0, 3,
            id="enum_drive_mode",
        ),
    ],
)
def test_wire_type_inference(
    example_schema_path: Path,
    msg_name: str,
    field_name: str,
    expected_bits: int,
    expected_signed: bool,
    expected_wire_min: int,
    expected_wire_max: int,
) -> None:
    """Wire type inference matches design.md worked examples."""
    schema = load_schema([example_schema_path])
    f = _find_field(schema, msg_name, field_name)

    assert f.wire_bits == expected_bits, f"wire_bits: {f.wire_bits} != {expected_bits}"
    assert f.wire_signed == expected_signed, f"wire_signed: {f.wire_signed} != {expected_signed}"
    assert f.wire_min == expected_wire_min, f"wire_min: {f.wire_min} != {expected_wire_min}"
    assert f.wire_max == expected_wire_max, f"wire_max: {f.wire_max} != {expected_wire_max}"


def test_enum_derived_properties(example_schema_path: Path) -> None:
    """Enum backing type and wire bits are derived correctly."""
    schema = load_schema([example_schema_path])
    drive_mode = schema.enums[0]
    assert drive_mode.name == "DriveMode"
    assert drive_mode.wire_bits == 2
    assert drive_mode.backing_type_plc == "USINT"
    assert drive_mode.backing_type_cpp == "uint8_t"


def test_bool_wire_type(tmp_path: Path) -> None:
    """Bool fields are always 1 bit, unsigned."""
    yaml_file = tmp_path / "schema.yaml"
    yaml_file.write_text(
        'version: "1"\n'
        "plc:\n  can_channel: CHAN_0\n"
        "messages:\n"
        "  - name: test_msg\n"
        "    id: 0x100\n"
        "    direction: pc_to_plc\n"
        "    fields:\n"
        "      - name: flag\n"
        "        type: bool\n"
    )
    schema = load_schema([yaml_file])
    f = schema.messages[0].fields[0]
    assert f.wire_bits == 1
    assert f.wire_signed is False
    assert f.wire_min == 0
    assert f.wire_max == 1


def test_integer_with_range(tmp_path: Path) -> None:
    """Integer with explicit min/max is bitpacked to minimum bits."""
    yaml_file = tmp_path / "schema.yaml"
    yaml_file.write_text(
        'version: "1"\n'
        "plc:\n  can_channel: CHAN_0\n"
        "messages:\n"
        "  - name: test_msg\n"
        "    id: 0x100\n"
        "    direction: pc_to_plc\n"
        "    fields:\n"
        "      - name: voltage_raw\n"
        "        type: uint16\n"
        "        min: 0\n"
        "        max: 1023\n"
    )
    schema = load_schema([yaml_file])
    f = schema.messages[0].fields[0]
    assert f.wire_bits == 10
    assert f.wire_signed is False
    assert f.wire_min == 0
    assert f.wire_max == 1023


# ── Naming transform tests ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field_name, unit, expected",
    [
        pytest.param("target_velocity", "rpm", "targetVelocity_rpm", id="with_unit"),
        pytest.param("fault_code", None, "faultCode", id="no_unit"),
        pytest.param("drive_mode", None, "driveMode", id="no_unit_two_words"),
        pytest.param("bus_voltage", "V", "busVoltage_V", id="single_char_unit"),
    ],
)
def test_plc_var_name(field_name: str, unit: str | None, expected: str) -> None:
    """PLC variable names: camelCase + optional _unit suffix."""
    assert plc_var_name(field_name, unit) == expected


@pytest.mark.parametrize(
    "field_name, unit, expected",
    [
        pytest.param("target_velocity", "rpm", "target_velocity_rpm", id="with_unit"),
        pytest.param("fault_code", None, "fault_code", id="no_unit"),
        pytest.param("drive_mode", None, "drive_mode", id="no_unit_two_words"),
        pytest.param("bus_voltage", "V", "bus_voltage_V", id="single_char_unit"),
    ],
)
def test_cpp_var_name(field_name: str, unit: str | None, expected: str) -> None:
    """C++ variable names: snake_case + optional _unit suffix."""
    assert cpp_var_name(field_name, unit) == expected


@pytest.mark.parametrize(
    "message_name, direction, expected",
    [
        pytest.param("motor_command", "pc_to_plc", "MOTOR_COMMAND_RECV", id="recv"),
        pytest.param("drive_status", "plc_to_pc", "DRIVE_STATUS_SEND", id="send"),
        pytest.param("pc_state", "pc_to_plc", "PC_STATE_RECV", id="recv_two_words"),
    ],
)
def test_fb_name(message_name: str, direction: str, expected: str) -> None:
    """Function block names: UPPER_SNAKE_CASE + _RECV/_SEND."""
    assert fb_name(message_name, direction) == expected


@pytest.mark.parametrize(
    "message_name, expected",
    [
        pytest.param("motor_command", "MotorCommand", id="two_words"),
        pytest.param("drive_status", "DriveStatus", id="two_words_2"),
        pytest.param("pc_state", "PcState", id="two_words_3"),
    ],
)
def test_struct_name(message_name: str, expected: str) -> None:
    """C++ struct names: PascalCase from snake_case."""
    assert struct_name(message_name) == expected


# ── Bitpacking + DLC tests ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg_name, expected_dlc",
    [
        pytest.param("motor_command", 4, id="motor_command_dlc"),
        pytest.param("drive_status", 6, id="drive_status_dlc"),
        pytest.param("pc_state", 1, id="pc_state_dlc"),
    ],
)
def test_dlc_computation(
    example_schema_path: Path, msg_name: str, expected_dlc: int
) -> None:
    """DLC = ceil(total_bits / 8) for each message."""
    schema = load_schema([example_schema_path])
    msg = next(m for m in schema.messages if m.name == msg_name)
    assert msg.dlc == expected_dlc


@pytest.mark.parametrize(
    "msg_name, field_name, expected_offset",
    [
        pytest.param("motor_command", "target_velocity", 0, id="mc_target_velocity"),
        pytest.param("motor_command", "torque_limit", 16, id="mc_torque_limit"),
        pytest.param("drive_status", "actual_velocity", 0, id="ds_actual_velocity"),
        pytest.param("drive_status", "motor_temp", 16, id="ds_motor_temp"),
        pytest.param("drive_status", "bus_voltage", 28, id="ds_bus_voltage"),
        pytest.param("drive_status", "fault_code", 38, id="ds_fault_code"),
        pytest.param("pc_state", "drive_mode", 0, id="ps_drive_mode"),
    ],
)
def test_bit_offsets(
    example_schema_path: Path, msg_name: str, field_name: str, expected_offset: int
) -> None:
    """Fields are assigned sequential bit offsets."""
    schema = load_schema([example_schema_path])
    f = _find_field(schema, msg_name, field_name)
    assert f.bit_offset == expected_offset


def test_naming_applied_in_load_schema(example_schema_path: Path) -> None:
    """Verify naming transforms are applied to fields during schema loading."""
    schema = load_schema([example_schema_path])

    # target_velocity with unit rpm
    vel = _find_field(schema, "motor_command", "target_velocity")
    assert vel.plc_var_name == "targetVelocity_rpm"
    assert vel.cpp_var_name == "target_velocity_rpm"

    # fault_code with no unit
    fault = _find_field(schema, "drive_status", "fault_code")
    assert fault.plc_var_name == "faultCode"
    assert fault.cpp_var_name == "fault_code"

    # drive_mode enum field with no unit
    mode = _find_field(schema, "pc_state", "drive_mode")
    assert mode.plc_var_name == "driveMode"
    assert mode.cpp_var_name == "drive_mode"


# ── Validation rule tests ────────────────────────────────────────────────


def _make_schema_yaml(
    messages_yaml: str,
    enums_yaml: str = "",
) -> str:
    """Build a minimal valid YAML schema string with custom messages/enums."""
    base = 'version: "1"\nplc:\n  can_channel: CHAN_0\n'
    if enums_yaml:
        base += f"enums:\n{enums_yaml}"
    base += f"messages:\n{messages_yaml}"
    return base


@pytest.mark.parametrize(
    "messages_yaml, enums_yaml, expected_error",
    [
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: real\n        min: 0.0\n        max: 10.0\n",
            "",
            "type 'real' requires min, max, and resolution",
            id="real_missing_resolution",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: real\n        resolution: 0.1\n",
            "",
            "type 'real' requires min, max, and resolution",
            id="real_missing_min_max",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: uint8\n        min: 0\n        max: 100\n        resolution: 0.1\n",
            "",
            "'resolution' is only valid on type 'real'",
            id="resolution_on_non_real",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: bool\n        min: 0\n        max: 1\n",
            "",
            "'min'/'max' not valid on type 'bool'",
            id="min_max_on_bool",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: Mode\n        min: 0\n        max: 3\n",
            "  - name: Mode\n    values:\n      OFF: 0\n      ON: 1\n      AUTO: 2\n      MANUAL: 3\n",
            "'min'/'max' not valid on enum type 'Mode'",
            id="min_max_on_enum",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: uint8\n        min: 0\n        max: 300\n",
            "",
            "exceeds uint8 bounds",
            id="integer_range_outside_type",
        ),
        pytest.param(
            "  - name: m1\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: bool\n"
            "  - name: m2\n    id: 0x100\n    direction: plc_to_pc\n    fields:\n"
            "      - name: y\n        type: bool\n",
            "",
            "Duplicate CAN ID",
            id="duplicate_can_id",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: Bogus\n",
            "",
            "unknown type 'Bogus'",
            id="undeclared_enum",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: x\n        type: uint16\n        min: -10\n        max: 100\n",
            "",
            "unsigned type 'uint16' cannot have negative min",
            id="unsigned_negative_min",
        ),
        pytest.param(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: a\n        type: uint64\n"
            "      - name: b\n        type: bool\n",
            "",
            "exceeds CAN frame capacity",
            id="frame_exceeds_64_bits",
        ),
    ],
)
def test_validation_rules(
    tmp_path: Path,
    messages_yaml: str,
    enums_yaml: str,
    expected_error: str,
) -> None:
    """Each semantic validation rule produces a clear SchemaError."""
    yaml_file = tmp_path / "schema.yaml"
    yaml_file.write_text(_make_schema_yaml(messages_yaml, enums_yaml))
    with pytest.raises(SchemaError, match=re.escape(expected_error)):
        load_schema([yaml_file])


def test_frame_overflow_rich_error(tmp_path: Path) -> None:
    """Frame overflow error includes field breakdown, overflow marker, and suggestions."""
    yaml_file = tmp_path / "schema.yaml"
    yaml_file.write_text(
        _make_schema_yaml(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: a\n        type: uint64\n"
            "      - name: b\n        type: bool\n"
        )
    )
    with pytest.raises(SchemaError, match=re.escape("exceeds CAN frame capacity")) as exc_info:
        load_schema([yaml_file])

    error_text = str(exc_info.value)
    # Header info
    assert "Total packed size: 65 bits" in error_text
    assert "Overflow:          1 bits" in error_text
    # Field breakdown
    assert "Field breakdown:" in error_text
    assert "a  64 bits  (bit 0..63)" in error_text
    assert "b   1 bits  (bit 64..64)" in error_text
    # Overflow marker
    assert "\u2190 exceeds frame at bit 64" in error_text
    # Suggestions
    assert "Reduce the range" in error_text
    assert "Split this message" in error_text


def test_frame_overflow_real_field_inference_note(tmp_path: Path) -> None:
    """Frame overflow with real fields includes per-field inference notes."""
    yaml_file = tmp_path / "schema.yaml"
    # A real field with fine resolution (0.001) on a wide range uses many bits,
    # plus a uint64 to push the total over 64.
    yaml_file.write_text(
        _make_schema_yaml(
            "  - name: m\n    id: 0x100\n    direction: pc_to_plc\n    fields:\n"
            "      - name: pressure\n        type: real\n"
            "        min: -100.0\n        max: 5000.0\n        resolution: 0.001\n"
            "      - name: big\n        type: uint64\n"
        )
    )
    with pytest.raises(SchemaError, match=re.escape("exceeds CAN frame capacity")) as exc_info:
        load_schema([yaml_file])

    error_text = str(exc_info.value)
    # Field-level inference note for the real field
    assert "Field 'pressure'" in error_text
    assert "type: real, min: -100.0, max: 5000.0, resolution: 0.001" in error_text
    assert "Inferred wire range: [-100000, 5000000]" in error_text
    assert "24 bits (signed)" in error_text
    assert "This field uses 24 of 64 available bits." in error_text
    # Resolution suggestions (×10 and ×100)
    assert "0.01" in error_text
    assert "0.1" in error_text


# ── Enum backing type tests ────────────────────────────────────────────


@pytest.mark.parametrize(
    "max_value, expected_plc, expected_cpp",
    [
        pytest.param(0, "USINT", "uint8_t", id="zero"),
        pytest.param(3, "USINT", "uint8_t", id="small_enum"),
        pytest.param(255, "USINT", "uint8_t", id="uint8_max"),
        pytest.param(256, "UINT", "uint16_t", id="uint8_overflow"),
        pytest.param(65535, "UINT", "uint16_t", id="uint16_max"),
        pytest.param(65536, "UDINT", "uint32_t", id="uint16_overflow"),
        pytest.param(2**32 - 1, "UDINT", "uint32_t", id="uint32_max"),
        pytest.param(2**32, "ULINT", "uint64_t", id="uint32_overflow"),
    ],
)
def test_enum_backing_type(
    max_value: int, expected_plc: str, expected_cpp: str
) -> None:
    """enum_backing_type selects the smallest integer type fitting max_value."""
    plc, cpp = enum_backing_type(max_value)
    assert plc == expected_plc
    assert cpp == expected_cpp


def test_enum_backing_type_in_loaded_schema(example_schema_path: Path) -> None:
    """DriveMode (max 3) gets USINT/uint8_t backing type after full schema load."""
    schema = load_schema([example_schema_path])
    dm = schema.enums[0]
    assert dm.name == "DriveMode"
    assert dm.backing_type_plc == "USINT"
    assert dm.backing_type_cpp == "uint8_t"
    assert dm.wire_bits == 2


# ── Full integration test (plan item 2.9) ─────────────────────────────────


def test_full_schema_integration(example_schema_path: Path) -> None:
    """Load example_schema.yaml end-to-end and verify every derived value."""
    schema = load_schema([example_schema_path])

    # ── Top-level structure ──
    assert schema.plc.can_channel == "CHAN_0"
    assert len(schema.enums) == 1
    assert len(schema.messages) == 3

    # ── Enum: DriveMode ──
    dm = schema.enums[0]
    assert dm.name == "DriveMode"
    assert dm.values == {"IDLE": 0, "VELOCITY": 1, "POSITION": 2, "TORQUE": 3}
    assert dm.wire_bits == 2
    assert dm.backing_type_plc == "USINT"
    assert dm.backing_type_cpp == "uint8_t"

    # ── Message: motor_command ──
    mc = schema.messages[0]
    assert mc.name == "motor_command"
    assert mc.id == 0x00000100
    assert mc.direction == "pc_to_plc"
    assert mc.timeout_ms == 500
    assert mc.dlc == 4
    assert len(mc.fields) == 2

    tv = mc.fields[0]
    assert tv.name == "target_velocity"
    assert tv.type == "real"
    assert tv.wire_bits == 16
    assert tv.wire_signed is True
    assert tv.bit_offset == 0
    assert tv.wire_min == -32000
    assert tv.wire_max == 32000
    assert tv.plc_var_name == "targetVelocity_rpm"
    assert tv.cpp_var_name == "target_velocity_rpm"

    tl = mc.fields[1]
    assert tl.name == "torque_limit"
    assert tl.type == "real"
    assert tl.wire_bits == 16
    assert tl.wire_signed is False
    assert tl.bit_offset == 16
    assert tl.wire_min == 0
    assert tl.wire_max == 65535
    assert tl.plc_var_name == "torqueLimit_Nm"
    assert tl.cpp_var_name == "torque_limit_Nm"

    # ── Message: drive_status ──
    ds = schema.messages[1]
    assert ds.name == "drive_status"
    assert ds.id == 0x00000200
    assert ds.direction == "plc_to_pc"
    assert ds.timeout_ms is None
    assert ds.dlc == 6
    assert len(ds.fields) == 4

    av = ds.fields[0]
    assert av.name == "actual_velocity"
    assert av.type == "real"
    assert av.wire_bits == 16
    assert av.wire_signed is True
    assert av.bit_offset == 0
    assert av.wire_min == -32000
    assert av.wire_max == 32000
    assert av.plc_var_name == "actualVelocity_rpm"
    assert av.cpp_var_name == "actual_velocity_rpm"

    mt = ds.fields[1]
    assert mt.name == "motor_temp"
    assert mt.type == "real"
    assert mt.wire_bits == 12
    assert mt.wire_signed is True
    assert mt.bit_offset == 16
    assert mt.wire_min == -400
    assert mt.wire_max == 2000
    assert mt.plc_var_name == "motorTemp_degC"
    assert mt.cpp_var_name == "motor_temp_degC"

    bv = ds.fields[2]
    assert bv.name == "bus_voltage"
    assert bv.type == "real"
    assert bv.wire_bits == 10
    assert bv.wire_signed is False
    assert bv.bit_offset == 28
    assert bv.wire_min == 0
    assert bv.wire_max == 1023
    assert bv.plc_var_name == "busVoltage_V"
    assert bv.cpp_var_name == "bus_voltage_V"

    fc = ds.fields[3]
    assert fc.name == "fault_code"
    assert fc.type == "uint8"
    assert fc.wire_bits == 8
    assert fc.wire_signed is False
    assert fc.bit_offset == 38
    assert fc.wire_min == 0
    assert fc.wire_max == 255
    assert fc.plc_var_name == "faultCode"
    assert fc.cpp_var_name == "fault_code"

    # ── Message: pc_state ──
    ps = schema.messages[2]
    assert ps.name == "pc_state"
    assert ps.id == 0x00000300
    assert ps.direction == "pc_to_plc"
    assert ps.timeout_ms == 1000
    assert ps.dlc == 1
    assert len(ps.fields) == 1

    dmode = ps.fields[0]
    assert dmode.name == "drive_mode"
    assert dmode.type == "DriveMode"
    assert dmode.wire_bits == 2
    assert dmode.wire_signed is False
    assert dmode.bit_offset == 0
    assert dmode.wire_min == 0
    assert dmode.wire_max == 3
    assert dmode.plc_var_name == "driveMode"
    assert dmode.cpp_var_name == "drive_mode"
