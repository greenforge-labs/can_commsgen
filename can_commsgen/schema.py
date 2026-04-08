"""Schema model dataclasses and loading for CAN YAML schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path

import jsonschema
import yaml

# ── Type mappings ────────────────────────────────────────────────────────────

# Endpoint type name → (PLC type, C++ type, bit width, is_signed)
ENDPOINT_TYPES: dict[str, tuple[str, str, int, bool]] = {
    "bool": ("BOOL", "bool", 1, False),
    "uint8": ("USINT", "uint8_t", 8, False),
    "int8": ("SINT", "int8_t", 8, True),
    "uint16": ("UINT", "uint16_t", 16, False),
    "int16": ("INT", "int16_t", 16, True),
    "uint32": ("UDINT", "uint32_t", 32, False),
    "int32": ("DINT", "int32_t", 32, True),
    "uint64": ("ULINT", "uint64_t", 64, False),
    "int64": ("LINT", "int64_t", 64, True),
    "real": ("REAL", "double", 0, False),  # bit width derived from range
}

# Integer endpoint type ranges (min, max) for validation.
INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "uint8": (0, 255),
    "int8": (-128, 127),
    "uint16": (0, 65535),
    "int16": (-32768, 32767),
    "uint32": (0, 2**32 - 1),
    "int32": (-(2**31), 2**31 - 1),
    "uint64": (0, 2**64 - 1),
    "int64": (-(2**63), 2**63 - 1),
}

# Backing type selection: max_value → (PLC type, C++ type)
BACKING_TYPES: list[tuple[int, str, str]] = [
    (255, "USINT", "uint8_t"),
    (65535, "UINT", "uint16_t"),
    (2**32 - 1, "UDINT", "uint32_t"),
    (2**64 - 1, "ULINT", "uint64_t"),
]


# ── Naming helpers ───────────────────────────────────────────────────────────


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(p.capitalize() for p in name.split("_"))


def plc_var_name(name: str, unit: str | None) -> str:
    """PLC variable name: camelCase + optional _unit suffix."""
    base = _snake_to_camel(name)
    if unit:
        return f"{base}_{unit}"
    return base


def cpp_var_name(name: str, unit: str | None) -> str:
    """C++ variable name: snake_case + optional _unit suffix."""
    if unit:
        return f"{name}_{unit}"
    return name


def fb_name(message_name: str, direction: str) -> str:
    """Function block name: UPPER_SNAKE_RECV or UPPER_SNAKE_SEND."""
    suffix = "RECV" if direction == "pc_to_plc" else "SEND"
    return f"{message_name.upper()}_{suffix}"


def struct_name(message_name: str) -> str:
    """C++ struct name: PascalCase from snake_case."""
    return _snake_to_pascal(message_name)


def enum_backing_type(max_value: int) -> tuple[str, str]:
    """Return (plc_type, cpp_type) for the smallest integer fitting max_value."""
    for threshold, plc_type, cpp_type in BACKING_TYPES:
        if max_value <= threshold:
            return plc_type, cpp_type
    return "ULINT", "uint64_t"


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class PlcConfig:
    """PLC configuration from the schema."""

    can_channel: str


@dataclass
class EnumDef:
    """An enum definition with derived wire properties."""

    name: str
    values: dict[str, int]

    # Derived (populated during schema processing)
    wire_bits: int = 0
    backing_type_plc: str = ""
    backing_type_cpp: str = ""


@dataclass
class FieldDef:
    """A message field with derived wire and naming properties."""

    name: str
    type: str
    min: float | None = None
    max: float | None = None
    resolution: float | None = None
    unit: str | None = None

    # Derived (populated during schema processing)
    wire_bits: int = 0
    wire_signed: bool = False
    bit_offset: int = 0
    wire_min: int = 0
    wire_max: int = 0
    plc_var_name: str = ""
    cpp_var_name: str = ""


@dataclass
class MessageDef:
    """A CAN message definition with derived properties."""

    name: str
    id: int
    direction: str
    fields: list[FieldDef] = field(default_factory=list)
    timeout_ms: int | None = None

    # Derived (populated during schema processing)
    dlc: int = 0


@dataclass
class Schema:
    """Top-level schema containing PLC config, enums, and messages."""

    plc: PlcConfig
    enums: list[EnumDef] = field(default_factory=list)
    messages: list[MessageDef] = field(default_factory=list)


# ── Schema JSON path ────────────────────────────────────────────────────────


def _find_schema_json() -> Path:
    """Locate schema.json: check package dir first, then repo root."""
    pkg = Path(__file__).parent / "schema.json"
    if pkg.exists():
        return pkg
    repo = Path(__file__).parent.parent / "schema.json"
    if repo.exists():
        return repo
    raise FileNotFoundError("schema.json not found")


_SCHEMA_JSON_PATH = _find_schema_json()


# ── Loading ─────────────────────────────────────────────────────────────────


class SchemaError(Exception):
    """Raised when schema loading or validation fails."""


def _load_json_schema() -> dict:  # type: ignore[type-arg]
    """Load the JSON Schema for CAN YAML structural validation."""
    with open(_SCHEMA_JSON_PATH) as f:
        return json.load(f)  # type: ignore[no-any-return]


def _parse_field(raw: dict) -> FieldDef:  # type: ignore[type-arg]
    """Convert a raw YAML field dict to a FieldDef dataclass."""
    return FieldDef(
        name=raw["name"],
        type=raw["type"],
        min=raw.get("min"),
        max=raw.get("max"),
        resolution=raw.get("resolution"),
        unit=raw.get("unit"),
    )


def _parse_message(raw: dict) -> MessageDef:  # type: ignore[type-arg]
    """Convert a raw YAML message dict to a MessageDef dataclass."""
    return MessageDef(
        name=raw["name"],
        id=raw["id"],
        direction=raw["direction"],
        fields=[_parse_field(f) for f in raw["fields"]],
        timeout_ms=raw.get("timeout_ms"),
    )


def _parse_enum(raw: dict) -> EnumDef:  # type: ignore[type-arg]
    """Convert a raw YAML enum dict to an EnumDef dataclass."""
    return EnumDef(
        name=raw["name"],
        values=raw["values"],
    )


def _bits_for_unsigned(wire_max: int) -> int:
    """Minimum bits to represent [0, wire_max] unsigned."""
    if wire_max == 0:
        return 1
    return math.ceil(math.log2(wire_max + 1))


def _bits_for_signed(wire_min: int, wire_max: int) -> int:
    """Minimum bits to represent [wire_min, wire_max] signed (two's complement)."""
    magnitude = max(abs(wire_min), abs(wire_max))
    if magnitude == 0:
        return 1
    return 1 + math.ceil(math.log2(magnitude + 1))


def _infer_wire_type(
    f: FieldDef,
    enum_map: dict[str, EnumDef],
) -> None:
    """Populate derived wire fields (wire_bits, wire_signed, wire_min, wire_max) on a FieldDef."""
    typ = f.type

    if typ == "bool":
        f.wire_bits = 1
        f.wire_signed = False
        f.wire_min = 0
        f.wire_max = 1
        return

    if typ in enum_map:
        enum = enum_map[typ]
        max_val = max(enum.values.values())
        f.wire_bits = _bits_for_unsigned(max_val)
        f.wire_signed = False
        f.wire_min = 0
        f.wire_max = max_val
        return

    if typ == "real":
        # real requires min, max, resolution (validation enforced elsewhere)
        assert f.min is not None and f.max is not None and f.resolution is not None
        f.wire_min = round(f.min / f.resolution)
        f.wire_max = round(f.max / f.resolution)
        f.wire_signed = f.min < 0
        if f.wire_signed:
            f.wire_bits = _bits_for_signed(f.wire_min, f.wire_max)
        else:
            f.wire_bits = _bits_for_unsigned(f.wire_max)
        return

    # Integer type
    if typ not in ENDPOINT_TYPES:
        return  # unknown type; validation catches this elsewhere

    _plc, _cpp, full_width, is_signed = ENDPOINT_TYPES[typ]

    if f.min is not None and f.max is not None:
        # Integer with explicit range
        f.wire_min = int(f.min)
        f.wire_max = int(f.max)
        f.wire_signed = is_signed
        if is_signed:
            f.wire_bits = _bits_for_signed(f.wire_min, f.wire_max)
        else:
            f.wire_bits = _bits_for_unsigned(f.wire_max)
    else:
        # Bare integer — full endpoint type width
        f.wire_signed = is_signed
        f.wire_bits = full_width
        if is_signed:
            type_min, type_max = INTEGER_RANGES[typ]
            f.wire_min = type_min
            f.wire_max = type_max
        else:
            f.wire_min = 0
            f.wire_max = INTEGER_RANGES[typ][1]


def _process_enums(enums: list[EnumDef]) -> None:
    """Populate derived fields on EnumDef instances."""
    for enum in enums:
        max_val = max(enum.values.values()) if enum.values else 0
        enum.wire_bits = _bits_for_unsigned(max_val)
        plc_bt, cpp_bt = enum_backing_type(max_val)
        enum.backing_type_plc = plc_bt
        enum.backing_type_cpp = cpp_bt


# ── Validation helpers ───────────────────────────────────────────────────────

_WIDER_TYPE: dict[str, str] = {
    "uint8": "uint16",
    "uint16": "uint32",
    "uint32": "uint64",
    "int8": "int16",
    "int16": "int32",
    "int32": "int64",
}


def _next_wider_type(typ: str) -> str | None:
    """Return the next wider integer type, or None if already the widest."""
    return _WIDER_TYPE.get(typ)


# ── Validation ──────────────────────────────────────────────────────────────


def _validate_schema(
    enums: list[EnumDef],
    messages: list[MessageDef],
) -> None:
    """Run semantic validation rules on a parsed schema.

    Raises SchemaError on the first violation found.
    """
    enum_names = {e.name for e in enums}

    # Rule 6: Duplicate CAN IDs
    seen_ids: dict[int, str] = {}
    for msg in messages:
        if msg.id in seen_ids:
            raise SchemaError(f"Duplicate CAN ID 0x{msg.id:X}: " f"'{msg.name}' and '{seen_ids[msg.id]}'")
        seen_ids[msg.id] = msg.name

    for msg in messages:
        field_bits: list[tuple[str, int]] = []
        for f in msg.fields:
            typ = f.type

            # Rule 1: real requires min, max, resolution
            if typ == "real":
                if f.min is None or f.max is None or f.resolution is None:
                    raise SchemaError(f"{msg.name}.{f.name}: type 'real' requires " f"min, max, and resolution")

            # Rule 2: resolution only on real
            if typ != "real" and f.resolution is not None:
                raise SchemaError(f"{msg.name}.{f.name}: 'resolution' is only " f"valid on type 'real'")

            # Rule 3: min/max on bool or enum
            if typ == "bool" and (f.min is not None or f.max is not None):
                raise SchemaError(f"{msg.name}.{f.name}: 'min'/'max' not valid on " f"type 'bool'")
            if typ in enum_names and (f.min is not None or f.max is not None):
                raise SchemaError(f"{msg.name}.{f.name}: 'min'/'max' not valid on " f"enum type '{typ}'")

            # Rule 7: undeclared enum reference
            if typ not in ENDPOINT_TYPES and typ not in enum_names:
                raise SchemaError(f"{msg.name}.{f.name}: unknown type '{typ}'")

            # Rule 8: unsigned type with min < 0
            if typ in ENDPOINT_TYPES and typ.startswith("uint"):
                if f.min is not None and f.min < 0:
                    raise SchemaError(
                        f"{msg.name}.{f.name}: unsigned type '{typ}' " f"cannot have negative min ({f.min})"
                    )

            # Rule 4: integer range outside endpoint type
            if typ in INTEGER_RANGES and f.min is not None and f.max is not None:
                type_min, type_max = INTEGER_RANGES[typ]
                if f.min < type_min or f.max > type_max:
                    lines = [
                        f"ERROR: Field '{f.name}' in message '{msg.name}' (0x{msg.id:08X}):",
                        f"  type: {typ}, min: {f.min}, max: {f.max}",
                    ]
                    # Identify which bound(s) exceeded
                    if f.max > type_max:
                        lines.append(f"  max value {f.max} exceeds {typ} range [{type_min}, {type_max}].")
                    if f.min < type_min:
                        lines.append(f"  min value {f.min} exceeds {typ} range [{type_min}, {type_max}].")
                    lines.append("")
                    # Suggest next wider type or range reduction
                    wider = _next_wider_type(typ)
                    if wider and f.max > type_max:
                        lines.append(f"  Either widen the type to {wider}, or reduce max to {type_max}.")
                    elif wider and f.min < type_min:
                        lines.append(f"  Either widen the type to {wider}, or increase min to {type_min}.")
                    elif f.max > type_max:
                        lines.append(f"  Reduce max to {type_max}.")
                    else:
                        lines.append(f"  Increase min to {type_min}.")
                    raise SchemaError("\n".join(lines))

            # Accumulate per-field bits for rule 5 check
            bits = 0
            if typ == "bool":
                bits = 1
            elif typ in enum_names:
                max_val = max(enums[next(i for i, e in enumerate(enums) if e.name == typ)].values.values())
                bits = _bits_for_unsigned(max_val)
            elif typ == "real":
                assert f.min is not None and f.max is not None and f.resolution is not None
                wire_min = round(f.min / f.resolution)
                wire_max = round(f.max / f.resolution)
                is_signed = f.min < 0
                if is_signed:
                    bits = _bits_for_signed(wire_min, wire_max)
                else:
                    bits = _bits_for_unsigned(wire_max)
            elif typ in ENDPOINT_TYPES:
                if f.min is not None and f.max is not None:
                    _plc, _cpp, _fw, is_signed = ENDPOINT_TYPES[typ]
                    if is_signed:
                        bits = _bits_for_signed(int(f.min), int(f.max))
                    else:
                        bits = _bits_for_unsigned(int(f.max))
                else:
                    bits = ENDPOINT_TYPES[typ][2]
            field_bits.append((f.name, bits))

        # Rule 5: frame > 64 bits
        total_bits = sum(b for _, b in field_bits)
        if total_bits > 64:
            overflow = total_bits - 64
            lines = [
                f"ERROR: Message '{msg.name}' (0x{msg.id:08X}) exceeds CAN frame capacity.",
                f"  Total packed size: {total_bits} bits ({total_bits / 8:.1f} bytes)",
                "  CAN maximum:      64 bits (8 bytes)",
                f"  Overflow:          {overflow} bits",
                "",
                "  Field breakdown:",
            ]
            bit_pos = 0
            name_width = max(len(name) for name, _ in field_bits)
            for name, bits in field_bits:
                end_bit = bit_pos + bits - 1
                entry = f"    {name:<{name_width}}  {bits:>2} bits  (bit {bit_pos}..{end_bit})"
                if bit_pos < 64 <= end_bit:
                    entry += "  \u2190 exceeds frame at bit 64"
                elif bit_pos >= 64:
                    entry += "  \u2190 exceeds frame at bit 64"
                bit_pos += bits
                lines.append(entry)
            # Per-field inference notes for real fields
            real_notes: list[str] = []
            for f in msg.fields:
                if f.type != "real":
                    continue
                assert f.min is not None and f.max is not None and f.resolution is not None
                wire_min = round(f.min / f.resolution)
                wire_max = round(f.max / f.resolution)
                is_signed = f.min < 0
                if is_signed:
                    bits = _bits_for_signed(wire_min, wire_max)
                else:
                    bits = _bits_for_unsigned(wire_max)
                sign_label = "signed" if is_signed else "unsigned"

                real_notes.append(
                    f"  Field '{f.name}' — type: real, " f"min: {f.min}, max: {f.max}, resolution: {f.resolution}"
                )
                real_notes.append(
                    f"    Inferred wire range: [{wire_min}, {wire_max}] " f"\u2192 {bits} bits ({sign_label})"
                )
                real_notes.append(f"    This field uses {bits} of 64 available bits.")

                # Suggest coarser resolutions (×10 and ×100)
                suggestions: list[str] = []
                for factor in (10, 100):
                    coarser = f.resolution * factor
                    c_wire_min = round(f.min / coarser)
                    c_wire_max = round(f.max / coarser)
                    if is_signed:
                        c_bits = _bits_for_signed(c_wire_min, c_wire_max)
                    else:
                        c_bits = _bits_for_unsigned(c_wire_max)
                    if c_bits < bits:
                        suggestions.append(f"{coarser} (\u2192 {c_bits} bits)")
                if suggestions:
                    real_notes.append(f"    Consider widening resolution to {' or '.join(suggestions)}.")

            if real_notes:
                lines.append("")
                lines.extend(real_notes)

            lines.append("")
            lines.append("  Suggestions:")
            lines.append("    - Reduce the range (min/max) of one or more fields")
            lines.append("    - Increase the resolution of real-valued fields (fewer bits per field)")
            lines.append("    - Split this message into two messages")
            raise SchemaError("\n".join(lines))


def load_schema(paths: list[Path]) -> Schema:
    """Load one or more YAML schema files, validate, merge, and return a Schema.

    Multiple files are merged by combining their enums and messages lists.
    The ``plc`` config is taken from the first file that declares it.
    """
    if not paths:
        raise SchemaError("No schema paths provided")

    json_schema = _load_json_schema()

    merged_plc: PlcConfig | None = None
    merged_enums: list[EnumDef] = []
    merged_messages: list[MessageDef] = []

    for path in paths:
        with open(path) as f:
            raw = yaml.safe_load(f)

        # Structural validation via JSON Schema
        try:
            jsonschema.validate(instance=raw, schema=json_schema)
        except jsonschema.ValidationError as e:
            raise SchemaError(f"{path}: {e.message}") from e

        # Merge plc config
        if merged_plc is None:
            merged_plc = PlcConfig(can_channel=raw["plc"]["can_channel"])

        # Merge enums
        for enum_raw in raw.get("enums", []):
            merged_enums.append(_parse_enum(enum_raw))

        # Merge messages
        for msg_raw in raw["messages"]:
            merged_messages.append(_parse_message(msg_raw))

    assert merged_plc is not None  # guaranteed by non-empty paths + validation

    # Semantic validation (before any derivation)
    _validate_schema(merged_enums, merged_messages)

    # Derive enum properties
    _process_enums(merged_enums)

    # Build enum lookup for wire type inference
    enum_map = {e.name: e for e in merged_enums}

    # Derive wire types, naming, bit offsets, and DLC for all messages
    for msg in merged_messages:
        bit_offset = 0
        for f in msg.fields:
            _infer_wire_type(f, enum_map)
            f.plc_var_name = plc_var_name(f.name, f.unit)
            f.cpp_var_name = cpp_var_name(f.name, f.unit)
            f.bit_offset = bit_offset
            bit_offset += f.wire_bits
        msg.dlc = math.ceil(bit_offset / 8)

    return Schema(plc=merged_plc, enums=merged_enums, messages=merged_messages)
