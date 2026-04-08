"""Tests for packing report generation."""

from pathlib import Path

from can_commsgen.report import generate_report
from can_commsgen.schema import load_schema


def test_packing_report_matches_golden(
    example_schema_path: Path,
    golden_report_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated packing report matches the golden file."""
    schema = load_schema([example_schema_path])
    output_path = tmp_path / "packing_report.txt"
    generate_report(schema, output_path)

    generated = output_path.read_text()
    expected = (golden_report_dir / "packing_report.txt").read_text()
    assert generated == expected
