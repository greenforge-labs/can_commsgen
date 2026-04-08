# Feature: Configurable GVL Name

## Problem

The generator hardcodes `GVL` as the Global Variable List name. RECV function blocks reference received fields as `GVL.variableName`, and the output file is `GVL.st`.

When integrating into an existing PLC project, the consuming code already references a differently-named GVL. For example, Anvil's PLC code uses `PC_INTERFACE_OUT` throughout its state machine and actuator control code:

```pascal
(* existing code in the PLC that must NOT change *)
HARDWARE.request_steering_angle(PC_INTERFACE_OUT.requestedSteeringAngle_deg);
```

Without this feature, the user must find-and-replace every `PC_INTERFACE_OUT.` reference in their non-generated PLC code to `GVL.`, which is error-prone and couples the project to can_commsgen's arbitrary naming choice.

## Solution

Add an optional `gvl_name` field to the `plc` section of the YAML schema. When set, it replaces `GVL` everywhere in the generated PLC output. When omitted, the current default `GVL` is preserved.

### Schema change

**`schema.json`** — add `gvl_name` to the `plc` object:

```yaml
# before
plc:
  can_channel: CHAN_0

# after
plc:
  can_channel: CHAN_0
  gvl_name: PC_INTERFACE_OUT   # optional, defaults to "GVL"
```

JSON Schema addition to `plc.properties`:
```json
"gvl_name": {
    "type": "string",
    "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
    "description": "Name of the generated Global Variable List. Defaults to 'GVL'. Controls both the output filename and the qualifier prefix used in RECV function blocks."
}
```

### Data model change

**`schema.py`** — extend `PlcConfig`:

```python
@dataclass
class PlcConfig:
    can_channel: str
    gvl_name: str = "GVL"
```

Update `_build_plc_config()` (or wherever `PlcConfig` is constructed from raw YAML) to read the optional `gvl_name` key.

### Code generation changes

Three places reference the GVL name:

1. **`plc.py` → `_generate_gvl()`** — output filename
   - Currently: `(output_dir / "GVL.st").write_text(rendered)`
   - Change to: `(output_dir / f"{schema.plc.gvl_name}.st").write_text(rendered)`

2. **`plc.py` → `_generate_recv_fbs()`** — GVL variable references in RECV FBs
   - Currently (line 184): `gvl_ref = f"GVL.{f.plc_var_name}"`
   - Change to: `gvl_ref = f"{schema.plc.gvl_name}.{f.plc_var_name}"`

3. **`plc.py` → `_generate_recv_fbs()`** — timeout variable reference
   - Currently in template (`recv_fb.st.j2`, line 28): `GVL.{{ timeout_var }}`
   - Pass `gvl_name` to the template context and change to: `{{ gvl_name }}.{{ timeout_var }}`

### Template change

**`templates/plc/recv_fb.st.j2`** — line 28:

```jinja2
{# before #}
GVL.{{ timeout_var }} := NOT timer.Q;

{# after #}
{{ gvl_name }}.{{ timeout_var }} := NOT timer.Q;
```

### Files to modify

| File | Change |
|---|---|
| `schema.json` | Add `gvl_name` to `plc` properties |
| `can_commsgen/schema.py` | Add `gvl_name` field to `PlcConfig`, parse from YAML |
| `can_commsgen/plc.py` | Use `schema.plc.gvl_name` for filename and GVL references (3 sites) |
| `can_commsgen/templates/plc/recv_fb.st.j2` | Replace hardcoded `GVL.` with `{{ gvl_name }}.` |

### Tests

- Update the existing test schema YAML to set `gvl_name: GVL` explicitly (no output change — confirms default behavior still works).
- Add a second test case with `gvl_name: CUSTOM_GVL` and verify:
  - Output file is `CUSTOM_GVL.st` (not `GVL.st`)
  - RECV FB bodies contain `CUSTOM_GVL.fieldName` references
  - Timeout lines contain `CUSTOM_GVL.timeoutVar`
- Golden file updates as needed.

### Scope

This is the only change needed for GVL integration. The variable naming convention (camelCase + unit suffix) already matches the existing Anvil PLC code. For example, a schema field `requested_steering_angle` with unit `deg` generates `requestedSteeringAngle_deg` — identical to the existing `PC_INTERFACE_OUT.requestedSteeringAngle_deg`.

The SEND function blocks are unaffected — they take field values as `VAR_INPUT` parameters, not from the GVL. The calling code (user-written, not generated) passes in values like `HARDWARE_OUT.steeringAngle_deg`.
