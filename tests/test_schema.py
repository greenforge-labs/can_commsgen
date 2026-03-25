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
            "total frame bits (65) exceeds maximum of 64",
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
