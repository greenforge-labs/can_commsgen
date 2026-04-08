"""PLC Structured Text code generation from CAN schema."""

from __future__ import annotations

from pathlib import Path

import jinja2

from can_commsgen.schema import (
    ENDPOINT_TYPES,
    EnumDef,
    FieldDef,
    Schema,
    _snake_to_camel,
    fb_name,
)


def _template_env() -> jinja2.Environment:
    """Create a Jinja2 environment loading from the templates/plc directory."""
    template_dir = Path(__file__).parent / "templates" / "plc"
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
        lstrip_blocks=True,
        trim_blocks=True,
    )


def generate_plc(schema: Schema, output_dir: Path) -> None:
    """Generate all PLC Structured Text files into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _template_env()

    # Enum files and conversion functions
    _generate_enums(schema, output_dir, env)

    # Bit helper functions (static content)
    _generate_bit_helpers(output_dir, env)

    # RECV function blocks (pc_to_plc messages)
    _generate_recv_fbs(schema, output_dir, env)

    # SEND function blocks (plc_to_pc messages)
    _generate_send_fbs(schema, output_dir, env)

    # Global Variable List (pc_to_plc fields + timeout booleans)
    _generate_gvl(schema, output_dir, env)

    # CAN_RECV.st — PROGRAM that calls all RECV FBs
    _generate_main_input(schema, output_dir, env)


def _generate_bit_helpers(output_dir: Path, env: jinja2.Environment) -> None:
    """Generate CAN_EXTRACT_BITS.st and CAN_INSERT_BITS.st helper functions."""
    extract_template = env.get_template("extract_bits.st.j2")
    (output_dir / "CAN_EXTRACT_BITS.st").write_text(extract_template.render())

    insert_template = env.get_template("insert_bits.st.j2")
    (output_dir / "CAN_INSERT_BITS.st").write_text(insert_template.render())


def _enum_from_int_fn_name(enum_name: str) -> str:
    """Return the name of the integer-to-enum conversion function."""
    return f"{enum_name}_FROM_INT"


def _generate_enums(schema: Schema, output_dir: Path, env: jinja2.Environment) -> None:
    """Generate one .st file per enum definition, plus a conversion function."""
    enum_template = env.get_template("enum.st.j2")
    conv_template = env.get_template("enum_from_int.st.j2")
    for enum in schema.enums:
        max_name_len = max(len(name) for name in enum.values)
        rendered = enum_template.render(enum=enum, max_name_len=max_name_len)
        (output_dir / f"{enum.name}.st").write_text(rendered)

        first_value = next(iter(enum.values))
        fn_name = _enum_from_int_fn_name(enum.name)
        rendered = conv_template.render(enum=enum, fn_name=fn_name, first_value=first_value)
        (output_dir / f"{fn_name}.st").write_text(rendered)


def _gvl_plc_type(field: FieldDef, enum_names: set[str]) -> str:
    """Return the PLC type string for a GVL variable."""
    if field.type == "real":
        return "REAL"
    elif field.type == "bool":
        return "BOOL"
    elif field.type in enum_names:
        return field.type
    else:
        return ENDPOINT_TYPES[field.type][0]


def _generate_gvl(schema: Schema, output_dir: Path, env: jinja2.Environment) -> None:
    """Generate GVL.st with received fields and timeout booleans."""
    template = env.get_template("gvl.st.j2")
    enum_names = {e.name for e in schema.enums}

    # Collect all variable names and types across all pc_to_plc messages
    # to compute global padding.
    all_var_names: list[str] = []
    messages_data: list[dict[str, object]] = []

    for msg in schema.messages:
        if msg.direction != "pc_to_plc":
            continue

        vars_info: list[dict[str, str]] = []
        for f in msg.fields:
            name = f.plc_var_name
            type_str = _gvl_plc_type(f, enum_names)
            all_var_names.append(name)
            vars_info.append({"name": name, "type_str": type_str})

        # Timeout boolean
        timeout_name = _snake_to_camel(msg.name) + "WithinTimeout"
        all_var_names.append(timeout_name)
        vars_info.append({"name": timeout_name, "type_str": "BOOL"})

        messages_data.append(
            {
                "name": msg.name,
                "can_id": f"{msg.id:08X}",
                "direction": msg.direction,
                "vars": vars_info,
            }
        )

    # Pad all variable names to the same width across all messages
    max_name_len = max(len(n) for n in all_var_names) if all_var_names else 0
    for msg_data in messages_data:
        for var in msg_data["vars"]:  # type: ignore[union-attr]
            var["name_padded"] = var["name"].ljust(max_name_len)  # type: ignore[index]

    rendered = template.render(messages=messages_data)
    (output_dir / f"{schema.plc.gvl_name}.gvl.st").write_text(rendered)


def _send_plc_type(field: FieldDef, enum_names: set[str]) -> str:
    """Return the PLC type string for a SEND FB VAR_INPUT field."""
    if field.type == "real":
        return "REAL"
    elif field.type == "bool":
        return "BOOL"
    elif field.type in enum_names:
        return field.type
    else:
        return ENDPOINT_TYPES[field.type][0]


def _send_insert_expr(field: FieldDef) -> str:
    """Build the TO_LINT(...) expression for a SEND FB CAN_INSERT_BITS call."""
    var = field.plc_var_name

    if field.type == "real":
        assert field.resolution is not None
        conv = "REAL_TO_INT" if field.wire_signed else "REAL_TO_UINT"
        return f"TO_LINT({conv}({var} / {field.resolution:g}))"
    elif field.type == "bool":
        return f"TO_LINT(BOOL_TO_USINT({var}))"
    else:
        # Integer or enum — direct cast
        return f"TO_LINT({var})"


def _recv_extract_expr(field: FieldDef, enum_map: dict[str, "EnumDef"]) -> str:
    """Build the PLC extraction expression for a RECV FB field."""
    signed = "TRUE" if field.wire_signed else "FALSE"
    extract = f"CAN_EXTRACT_BITS(rxData, {field.bit_offset}, " f"{field.wire_bits}, {signed})"

    if field.type == "real":
        return f"TO_REAL({extract}) * {field.resolution:g}"
    elif field.type == "bool":
        return f"{extract} <> 0"
    elif field.type in enum_map:
        fn = _enum_from_int_fn_name(field.type)
        backing_plc = enum_map[field.type].backing_type_plc
        return f"{fn}(TO_{backing_plc}({extract}))"
    else:
        # Integer type — cast to PLC type
        plc_type = ENDPOINT_TYPES[field.type][0]
        return f"TO_{plc_type}({extract})"


def _generate_recv_fbs(schema: Schema, output_dir: Path, env: jinja2.Environment) -> None:
    """Generate RECV function block files for pc_to_plc messages."""
    template = env.get_template("recv_fb.st.j2")
    enum_map = {e.name: e for e in schema.enums}

    for msg in schema.messages:
        if msg.direction != "pc_to_plc":
            continue

        # Build field info for template
        fields_info: list[dict[str, str]] = []
        for f in msg.fields:
            gvl_ref = f"{schema.plc.gvl_name}.{f.plc_var_name}"
            expr = _recv_extract_expr(f, enum_map)
            fields_info.append({"gvl_ref": gvl_ref, "expr": expr})

        max_gvl_len = max(len(fi["gvl_ref"]) for fi in fields_info) if fields_info else 0

        for fi in fields_info:
            fi["gvl_padded"] = fi["gvl_ref"].ljust(max_gvl_len)

        name = fb_name(msg.name, msg.direction)
        timeout_var = _snake_to_camel(msg.name) + "WithinTimeout"
        can_id = f"{msg.id:08X}"

        rendered = template.render(
            fb_name=name,
            can_id=can_id,
            dlc=msg.dlc,
            fields=fields_info,
            timeout_ms=msg.timeout_ms,
            timeout_var=timeout_var,
            gvl_name=schema.plc.gvl_name,
        )

        (output_dir / f"{name}.st").write_text(rendered)


def _generate_send_fbs(schema: Schema, output_dir: Path, env: jinja2.Environment) -> None:
    """Generate SEND function block files for plc_to_pc messages."""
    template = env.get_template("send_fb.st.j2")
    enum_names = {e.name for e in schema.enums}

    for msg in schema.messages:
        if msg.direction != "plc_to_pc":
            continue

        # Build VAR_INPUT entries: channel first, then each field
        var_input_names = ["channel"]
        var_input_types = ["ifmDevice.CAN_CHANNEL"]
        for f in msg.fields:
            var_input_names.append(f.plc_var_name)
            var_input_types.append(_send_plc_type(f, enum_names))

        max_name_len = max(len(n) for n in var_input_names)
        var_inputs = [
            {"name_padded": n.ljust(max_name_len), "type_str": t} for n, t in zip(var_input_names, var_input_types)
        ]

        # Build CAN_INSERT_BITS lines with column alignment
        fields_data: list[dict[str, object]] = []
        for f in msg.fields:
            fields_data.append(
                {
                    "expr": _send_insert_expr(f),
                    "offset": f.bit_offset,
                    "bits": f.wire_bits,
                }
            )

        # Build column-aligned CAN_INSERT_BITS lines.
        # Prefix "CAN_INSERT_BITS(expr," is ljust-padded so spaces go
        # after the comma. Then offset and bits blocks use ljust to
        # align their trailing separators.
        prefixes = [f"CAN_INSERT_BITS({fd['expr']}," for fd in fields_data]
        max_prefix_len = max(len(p) for p in prefixes) if prefixes else 0
        max_off_digits = max(len(str(fd["offset"])) for fd in fields_data) if fields_data else 0
        max_bits_digits = max(len(str(fd["bits"])) for fd in fields_data) if fields_data else 0

        insert_lines: list[str] = []
        for fd, prefix in zip(fields_data, prefixes):
            padded_prefix = prefix.ljust(max_prefix_len)
            off_digits = len(str(fd["offset"]))
            bits_digits = len(str(fd["bits"]))
            gap = 1 + off_digits + max_bits_digits - bits_digits
            off_block = f"{fd['offset']},".ljust(max_off_digits + 2)
            bits_block = f"{fd['bits']},".ljust(max_bits_digits + 2)
            line = f"{padded_prefix}{' ' * gap}" f"{off_block}{bits_block}data);"
            insert_lines.append(line)

        name = fb_name(msg.name, msg.direction)
        can_id = f"{msg.id:08X}"

        rendered = template.render(
            fb_name=name,
            can_id=can_id,
            dlc=msg.dlc,
            var_inputs=var_inputs,
            insert_lines=insert_lines,
        )

        (output_dir / f"{name}.st").write_text(rendered)


def _generate_main_input(schema: Schema, output_dir: Path, env: jinja2.Environment) -> None:
    """Generate CAN_RECV.st — PROGRAM that calls all RECV FBs."""
    template = env.get_template("main_input.st.j2")

    names = [fb_name(msg.name, msg.direction) for msg in schema.messages if msg.direction == "pc_to_plc"]
    max_len = max((len(f"fb{n}") for n in names), default=0)
    recv_fbs = [
        {"fb_name": n, "inst_padded": f"fb{n}".ljust(max_len)} for n in names
    ]

    rendered = template.render(
        recv_fbs=recv_fbs,
        can_channel=schema.plc.can_channel,
    )
    (output_dir / "CAN_RECV.st").write_text(rendered)
