"""PLC Structured Text code generation from CAN schema."""

from __future__ import annotations

from pathlib import Path

import jinja2

from can_commsgen.schema import Schema


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

    # Enum files
    _generate_enums(schema, output_dir, env)

    # Bit helper functions (static content)
    _generate_bit_helpers(output_dir, env)


def _generate_bit_helpers(output_dir: Path, env: jinja2.Environment) -> None:
    """Generate CAN_EXTRACT_BITS.st and CAN_INSERT_BITS.st helper functions."""
    extract_template = env.get_template("extract_bits.st.j2")
    (output_dir / "CAN_EXTRACT_BITS.st").write_text(extract_template.render())

    insert_template = env.get_template("insert_bits.st.j2")
    (output_dir / "CAN_INSERT_BITS.st").write_text(insert_template.render())


def _generate_enums(
    schema: Schema, output_dir: Path, env: jinja2.Environment
) -> None:
    """Generate one .st file per enum definition."""
    template = env.get_template("enum.st.j2")
    for enum in schema.enums:
        max_name_len = max(len(name) for name in enum.values)
        rendered = template.render(enum=enum, max_name_len=max_name_len)
        (output_dir / f"{enum.name}.st").write_text(rendered)
