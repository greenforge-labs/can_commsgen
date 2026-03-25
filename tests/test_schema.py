import re
from pathlib import Path

import jsonschema
import pytest

SCHEMA_JSON_PATH = Path(__file__).parent.parent / "schema.json"


@pytest.fixture()
def json_schema() -> dict:
    """Load the JSON Schema for CAN YAML validation."""
    import json

    with open(SCHEMA_JSON_PATH) as f:
        return json.load(f)


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
