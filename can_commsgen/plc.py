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


def _generate_enums(
    schema: Schema, output_dir: Path, env: jinja2.Environment
) -> None:
    """Generate one .st file per enum definition."""
    template = env.get_template("enum.st.j2")
    for enum in schema.enums:
        max_name_len = max(len(name) for name in enum.values)
        rendered = template.render(enum=enum, max_name_len=max_name_len)
        (output_dir / f"{enum.name}.st").write_text(rendered)
