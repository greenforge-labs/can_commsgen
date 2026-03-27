"""Click CLI for CAN comms code generation."""

from __future__ import annotations

from pathlib import Path
import sys

import click

from can_commsgen.cpp import generate_cpp
from can_commsgen.plc import generate_plc
from can_commsgen.report import generate_report
from can_commsgen.schema import load_schema


@click.command()
@click.option(
    "--schema",
    "schema_paths",
    required=True,
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="YAML schema file (repeatable).",
)
@click.option(
    "--out-plc",
    required=True,
    type=click.Path(path_type=Path),
    help="Output directory for PLC Structured Text files.",
)
@click.option(
    "--out-cpp",
    required=True,
    type=click.Path(path_type=Path),
    help="Output directory for C++ header.",
)
@click.option(
    "--out-report",
    default=None,
    type=click.Path(path_type=Path),
    help="Output path for packing report (optional).",
)
def main(
    schema_paths: tuple[Path, ...],
    out_plc: Path,
    out_cpp: Path,
    out_report: Path | None,
) -> None:
    """Generate PLC Structured Text and C++ code from CAN YAML schemas."""
    try:
        schema = load_schema(list(schema_paths))
    except Exception as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    out_plc.mkdir(parents=True, exist_ok=True)
    out_cpp.mkdir(parents=True, exist_ok=True)

    generate_plc(schema, out_plc)
    generate_cpp(schema, out_cpp)

    if out_report is not None:
        out_report.parent.mkdir(parents=True, exist_ok=True)
        generate_report(schema, out_report)
