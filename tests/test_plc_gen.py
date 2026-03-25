"""Tests for PLC Structured Text generation."""

from pathlib import Path

from can_commsgen.plc import generate_plc
from can_commsgen.schema import load_schema


def test_enum_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated DriveMode.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "DriveMode.st").read_text()
    expected = (golden_plc_dir / "DriveMode.st").read_text()
    assert generated == expected


def test_extract_bits_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated CAN_EXTRACT_BITS.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "CAN_EXTRACT_BITS.st").read_text()
    expected = (golden_plc_dir / "CAN_EXTRACT_BITS.st").read_text()
    assert generated == expected


def test_insert_bits_generation(
    example_schema_path: Path,
    golden_plc_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated CAN_INSERT_BITS.st matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_plc(schema, tmp_path)

    generated = (tmp_path / "CAN_INSERT_BITS.st").read_text()
    expected = (golden_plc_dir / "CAN_INSERT_BITS.st").read_text()
    assert generated == expected
