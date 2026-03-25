"""Packing report generation from CAN schema."""

from __future__ import annotations

from pathlib import Path

from can_commsgen.schema import FieldDef, MessageDef, Schema

SEPARATOR = "=" * 80
INNER_SEP = "-" * 80

HEADERS = [
    "Bit offset",
    "Bits",
    "Signed",
    "Field",
    "Type",
    "Wire range",
    "Physical range",
    "Resolution",
]

# Fixed widths for the first 3 columns.
_FIXED_WIDTHS = [12, 6, 8]

# Data field width is always 21; header uses 20.
_FIELD_DATA_WIDTH = 21

# Per-column dynamic config: (data_gap_hi, header_len)
# When max_data > header_len + 1 ("data dominates"), gap = data_gap_hi.
# When header dominates, gap = 2 from header_len.
# Type has a minimum width of 7.
_TYPE_IDX = 4
_WR_IDX = 5
_PR_IDX = 6
_DATA_GAPS_HI = {_TYPE_IDX: 3, _WR_IDX: 5, _PR_IDX: 3}


def _format_wire_range(f: FieldDef) -> str:
    return f"[{f.wire_min}, {f.wire_max}]"


def _format_physical_range(f: FieldDef) -> str:
    if f.type == "real":
        assert f.min is not None and f.max is not None and f.unit is not None
        return f"[{f.min}, {f.max}] {f.unit}"
    return "--"


def _format_resolution(f: FieldDef) -> str:
    if f.type == "real":
        assert f.resolution is not None
        return str(f.resolution)
    return "--"


def _build_row(f: FieldDef) -> list[str]:
    return [
        str(f.bit_offset),
        str(f.wire_bits),
        "yes" if f.wire_signed else "no",
        f.name,
        f.type,
        _format_wire_range(f),
        _format_physical_range(f),
        _format_resolution(f),
    ]


def _compute_data_widths(rows: list[list[str]]) -> list[int]:
    """Compute column widths for data rows."""
    widths: list[int] = []
    for i in range(len(HEADERS)):
        max_data = max(len(row[i]) for row in rows)
        header_len = len(HEADERS[i])

        if i < len(_FIXED_WIDTHS):
            widths.append(_FIXED_WIDTHS[i])
        elif i == 3:  # Field
            widths.append(_FIELD_DATA_WIDTH)
        elif i < len(HEADERS) - 1:  # Dynamic columns
            if max_data > header_len + 1:
                # Data dominates
                width = max_data + _DATA_GAPS_HI[i]
            else:
                # Header dominates
                width = header_len + 2
            # Type column has a minimum width
            if i == _TYPE_IDX:
                width = max(width, header_len + 3)
            widths.append(width)
        else:
            widths.append(0)  # Resolution: no padding
    return widths


def _compute_header_widths(
    data_widths: list[int], rows: list[list[str]]
) -> list[int]:
    """Compute column widths for the header row.

    Field is 1 narrower than data (20 vs 21). The first header-dominated
    dynamic column after Field gets +1 to compensate.
    """
    header_widths = list(data_widths)
    header_widths[3] = _FIELD_DATA_WIDTH - 1  # Field header = 20

    # Compensate: add 1 to the first truly header-dominated dynamic column
    # (where the header text is strictly longer than the widest data value).
    for i in range(4, len(HEADERS) - 1):
        max_data = max(len(row[i]) for row in rows)
        header_len = len(HEADERS[i])
        if max_data < header_len:  # header text strictly wider
            header_widths[i] += 1
            break

    return header_widths


def _format_line(values: list[str], widths: list[int]) -> str:
    parts: list[str] = []
    for i, (val, width) in enumerate(zip(values, widths)):
        if i < len(values) - 1:
            parts.append(val.ljust(width))
        else:
            parts.append(val)
    return "  " + "".join(parts)


def _format_message(msg: MessageDef) -> list[str]:
    lines: list[str] = []

    # Message header
    lines.append(SEPARATOR)
    header = f"{msg.name}  (0x{msg.id:08X}, {msg.direction}"
    if msg.timeout_ms is not None:
        header += f", timeout {msg.timeout_ms}ms"
    header += ")"
    lines.append(header)

    total_bits = sum(f.wire_bits for f in msg.fields)
    lines.append(f"  DLC: {msg.dlc} bytes ({total_bits} bits used / 64 max)")
    lines.append(INNER_SEP)

    # Build rows and compute column widths
    rows = [_build_row(f) for f in msg.fields]
    data_widths = _compute_data_widths(rows)
    header_widths = _compute_header_widths(data_widths, rows)

    # Table header
    lines.append(_format_line(HEADERS, header_widths))

    # Data rows
    for row in rows:
        lines.append(_format_line(row, data_widths))

    lines.append(SEPARATOR)
    return lines


def generate_report(schema: Schema, output_path: Path) -> None:
    """Generate a human-readable packing report."""
    lines: list[str] = []
    lines.append("can_commsgen packing report")
    lines.append("Schema: example_schema.yaml")
    lines.append("")

    for i, msg in enumerate(schema.messages):
        if i > 0:
            lines.append("")
        lines.extend(_format_message(msg))

    lines.append("")  # trailing newline

    output_path.write_text("\n".join(lines))
