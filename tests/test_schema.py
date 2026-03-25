import re
from pathlib import Path

import jsonschema
import pytest

from can_commsgen.schema import (
    FieldDef,
    PlcConfig,
    Schema,
    SchemaError,
    load_schema,
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
