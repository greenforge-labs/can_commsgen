"""Tests for C++ code generation."""

from pathlib import Path
import shutil
import subprocess

import pytest

from can_commsgen.cpp import generate_cpp
from can_commsgen.schema import load_schema

CPP_TESTS_DIR = Path(__file__).parent / "cpp_tests"


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


def test_can_interface_hpp_generation(
    example_schema_path: Path,
    golden_cpp_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated can_interface.hpp matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_cpp(schema, tmp_path)

    generated = (tmp_path / "can_interface.hpp").read_text()
    expected = (golden_cpp_dir / "can_interface.hpp").read_text()
    assert generated == expected


def test_can_interface_cpp_generation(
    example_schema_path: Path,
    golden_cpp_dir: Path,
    tmp_path: Path,
) -> None:
    """Generated can_interface.cpp matches the golden file."""
    schema = load_schema([example_schema_path])
    generate_cpp(schema, tmp_path)

    generated = (tmp_path / "can_interface.cpp").read_text()
    expected = (golden_cpp_dir / "can_interface.cpp").read_text()
    assert generated == expected


@pytest.mark.skipif(
    shutil.which("cmake") is None or shutil.which("g++") is None,
    reason="C++ toolchain (cmake, g++) not available",
)
def test_cpp_roundtrip(
    example_schema_path: Path,
    tmp_path: Path,
) -> None:
    """Generate can_messages.hpp, compile, and run C++ roundtrip tests."""
    schema = load_schema([example_schema_path])

    # Generate all C++ files into the roundtrip test's expected location
    generated_dir = CPP_TESTS_DIR / "generated"
    generated_dir.mkdir(exist_ok=True)
    generate_cpp(schema, generated_dir)

    # Verify interface files are present (compiled as part of cmake build)
    assert (generated_dir / "can_interface.hpp").exists()
    assert (generated_dir / "can_interface.cpp").exists()

    # Build with cmake in a temporary build directory
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    cmake_result = subprocess.run(
        ["cmake", str(CPP_TESTS_DIR)],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert cmake_result.returncode == 0, f"cmake configure failed:\n{cmake_result.stderr}"

    build_result = subprocess.run(
        ["cmake", "--build", "."],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"cmake build failed:\n{build_result.stderr}"

    # Run the roundtrip tests via ctest
    test_result = subprocess.run(
        ["ctest", "--output-on-failure"],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert test_result.returncode == 0, f"C++ roundtrip tests failed:\n{test_result.stdout}\n{test_result.stderr}"
