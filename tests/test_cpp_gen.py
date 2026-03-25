"""Tests for C++ code generation."""

from pathlib import Path

from can_commsgen.cpp import generate_cpp
from can_commsgen.schema import load_schema


def test_can_messages_hpp_generation(
    example_schema_path: Path,
    golden_cpp_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated can_messages.hpp matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_cpp(schema, tmp_path)

    generated = (tmp_path / "can_messages.hpp").read_text()
    expected = (golden_cpp_dir / "can_messages.hpp").read_text()
    assert generated == expected
