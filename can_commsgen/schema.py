"""Schema model dataclasses and loading for CAN YAML schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Type mappings ────────────────────────────────────────────────────────────

# Endpoint type name → (PLC type, C++ type, bit width, is_signed)
ENDPOINT_TYPES: dict[str, tuple[str, str, int, bool]] = {
    "bool":   ("BOOL",   "bool",     1,  False),
    "uint8":  ("USINT",  "uint8_t",  8,  False),
    "int8":   ("SINT",   "int8_t",   8,  True),
    "uint16": ("UINT",   "uint16_t", 16, False),
    "int16":  ("INT",    "int16_t",  16, True),
    "uint32": ("UDINT",  "uint32_t", 32, False),
    "int32":  ("DINT",   "int32_t",  32, True),
    "uint64": ("ULINT",  "uint64_t", 64, False),
    "int64":  ("LINT",   "int64_t",  64, True),
    "real":   ("REAL",   "double",   0,  False),  # bit width derived from range
}

# Integer endpoint type ranges (min, max) for validation.
INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "uint8":  (0, 255),
    "int8":   (-128, 127),
    "uint16": (0, 65535),
    "int16":  (-32768, 32767),
    "uint32": (0, 2**32 - 1),
    "int32":  (-(2**31), 2**31 - 1),
    "uint64": (0, 2**64 - 1),
    "int64":  (-(2**63), 2**63 - 1),
}

# Backing type selection: max_value → (PLC type, C++ type)
BACKING_TYPES: list[tuple[int, str, str]] = [
    (255,        "USINT",  "uint8_t"),
    (65535,      "UINT",   "uint16_t"),
    (2**32 - 1,  "UDINT",  "uint32_t"),
    (2**64 - 1,  "ULINT",  "uint64_t"),
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
