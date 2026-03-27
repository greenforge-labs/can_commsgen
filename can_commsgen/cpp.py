"""C++ code generation from CAN schema."""

from __future__ import annotations

from pathlib import Path

import jinja2

from can_commsgen.schema import (
    ENDPOINT_TYPES,
    EnumDef,
    FieldDef,
    MessageDef,
    Schema,
    struct_name,
)


def _template_env() -> jinja2.Environment:
    """Create a Jinja2 environment loading from the templates/cpp directory."""
    template_dir = Path(__file__).parent / "templates" / "cpp"
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
        lstrip_blocks=True,
        trim_blocks=True,
    )


def _msg_comment(msg: MessageDef) -> str:
    """Build comment text: name (0xID, direction[, timeout Nms])."""
    parts = [f"0x{msg.id:08X}", msg.direction]
    if msg.timeout_ms is not None:
        parts.append(f"timeout {msg.timeout_ms}ms")
    return f"{msg.name} ({', '.join(parts)})"


def _cpp_field_type(field: FieldDef, enum_names: set[str]) -> str:
    """Return the C++ type string for a struct member."""
    if field.type == "real":
        return "double"
    if field.type == "bool":
        return "bool"
    if field.type in enum_names:
        return field.type
    return ENDPOINT_TYPES[field.type][1]


def _enum_data(enum: EnumDef) -> dict[str, object]:
    """Prepare template data for an enum class."""
    max_name_len = max(len(name) for name in enum.values)
    entries = [f"{name.ljust(max_name_len)} = {value}" for name, value in enum.values.items()]
    return {
        "name": enum.name,
        "backing_type_cpp": enum.backing_type_cpp,
        "entries": entries,
    }


def _struct_members(msg: MessageDef, enum_names: set[str]) -> list[str]:
    """Format struct member declarations with aligned comments for real fields."""
    decls: list[str] = []
    comments: list[str | None] = []

    for f in msg.fields:
        cpp_type = _cpp_field_type(f, enum_names)
        decl = f"{cpp_type} {f.cpp_var_name};"
        decls.append(decl)

        if f.type == "real":
            comments.append(f"// [{f.min}, {f.max}], res {f.resolution}")
        else:
            comments.append(None)

    max_decl_len = max(
        (len(d) for d, c in zip(decls, comments) if c is not None),
        default=0,
    )

    members: list[str] = []
    for decl, comment in zip(decls, comments):
        if comment:
            members.append(f"{decl.ljust(max_decl_len)}  {comment}")
        else:
            members.append(decl)

    return members


def _parse_lines(msg: MessageDef, enum_names: set[str]) -> list[str]:
    """Build fully-indented parse assignment lines for a message."""
    fields = msg.fields
    if not fields:
        return []

    max_lhs_len = max(len(f"msg.{f.cpp_var_name}") for f in fields)
    max_offset_digits = max(len(str(f.bit_offset)) for f in fields)
    max_bits_digits = max(len(str(f.wire_bits)) for f in fields)

    lines: list[str] = []
    for f in fields:
        lhs = f"msg.{f.cpp_var_name}".ljust(max_lhs_len)
        offset_part = f"{f.bit_offset},".ljust(max_offset_digits + 1)
        bits_part = f"{f.wire_bits},".ljust(max_bits_digits + 1)
        signed_str = "true" if f.wire_signed else "false"

        if f.type == "real":
            closing = f"{signed_str})".ljust(7)
            extract = f"detail::extract_bits(frame.data, " f"{offset_part} {bits_part} {closing}"
            lines.append(f"    {lhs} = {extract}* {f.resolution:g};")
        elif f.type == "bool":
            closing = f"{signed_str})".ljust(7)
            extract = f"detail::extract_bits(frame.data, " f"{offset_part} {bits_part} {closing}"
            lines.append(f"    {lhs} = {extract}!= 0;")
        elif f.type in enum_names:
            indent = " " * (4 + max_lhs_len + 3)
            extract = f"detail::extract_bits(frame.data, " f"{offset_part} {bits_part} {signed_str})"
            lines.append(f"    {lhs} = static_cast<{f.type}>(")
            lines.append(f"{indent}{extract});")
        else:
            cpp_type = ENDPOINT_TYPES[f.type][1]
            indent = " " * (4 + max_lhs_len + 3)
            extract = f"detail::extract_bits(frame.data, " f"{offset_part} {bits_part} {signed_str})"
            lines.append(f"    {lhs} = static_cast<{cpp_type}>(")
            lines.append(f"{indent}{extract});")

    return lines


def _build_lines(msg: MessageDef, enum_names: set[str]) -> list[str]:
    """Build fully-indented insert_bits lines for a message."""
    fields = msg.fields
    if not fields:
        return []

    max_offset_digits = max(len(str(f.bit_offset)) for f in fields)
    max_bits_digits = max(len(str(f.wire_bits)) for f in fields)

    lines: list[str] = []
    for f in fields:
        offset_part = f"{f.bit_offset},".ljust(max_offset_digits + 1)
        bits_part = f"{f.wire_bits},".ljust(max_bits_digits + 1)

        if f.type == "real":
            value_expr = f"static_cast<int64_t>" f"(std::round(msg.{f.cpp_var_name} / {f.resolution:g}))"
        elif f.type == "bool":
            value_expr = f"msg.{f.cpp_var_name} ? 1 : 0"
        else:
            value_expr = f"static_cast<int64_t>(msg.{f.cpp_var_name})"

        lines.append(f"    detail::insert_bits(frame.data, " f"{offset_part} {bits_part} {value_expr});")

    return lines


def _message_data(msg: MessageDef, enum_names: set[str]) -> dict[str, object]:
    """Prepare template data for a single message."""
    return {
        "name": msg.name,
        "struct_name": struct_name(msg.name),
        "can_id_hex": f"0x{msg.id:08X}",
        "dlc": msg.dlc,
        "comment": _msg_comment(msg),
        "members": _struct_members(msg, enum_names),
        "parse_lines": _parse_lines(msg, enum_names),
        "build_lines": _build_lines(msg, enum_names),
    }


def _interface_message_data(msg: MessageDef) -> dict[str, object]:
    """Prepare template data for a message in the interface templates."""
    return {
        "name": msg.name,
        "struct_name": struct_name(msg.name),
        "can_id_hex": f"0x{msg.id:08X}",
        "comment": _msg_comment(msg),
        "timeout_ms": msg.timeout_ms,
    }


def generate_cpp(schema: Schema, output_dir: Path) -> None:
    """Generate can_messages.hpp, can_interface.hpp, and can_interface.cpp."""
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _template_env()

    enum_names = {e.name for e in schema.enums}

    # --- can_messages.hpp ---
    enums = [_enum_data(e) for e in schema.enums]
    messages = [_message_data(m, enum_names) for m in schema.messages]

    rendered = env.get_template("can_messages.hpp.j2").render(
        enums=enums,
        messages=messages,
    )
    (output_dir / "can_messages.hpp").write_text(rendered)

    # --- can_interface.hpp / .cpp ---
    plc_to_pc = [_interface_message_data(m) for m in schema.messages if m.direction == "plc_to_pc"]
    pc_to_plc = [_interface_message_data(m) for m in schema.messages if m.direction == "pc_to_plc"]
    timeout_msgs = [m for m in plc_to_pc if m["timeout_ms"] is not None]

    interface_ctx = {
        "plc_to_pc_messages": plc_to_pc,
        "pc_to_plc_messages": pc_to_plc,
        "timeout_messages": timeout_msgs,
    }

    for filename in ("can_interface.hpp", "can_interface.cpp"):
        rendered = env.get_template(f"{filename}.j2").render(**interface_ctx)
        (output_dir / filename).write_text(rendered)
