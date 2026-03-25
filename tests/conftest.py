from pathlib import Path

import pytest
import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.fixture()
def example_schema_raw() -> dict:
    """Load example_schema.yaml and return the raw YAML dict."""
    schema_path = FIXTURES_DIR / "example_schema.yaml"
    with open(schema_path) as f:
        return yaml.safe_load(f)


@pytest.fixture()
def example_schema_path() -> Path:
    """Return the path to the example schema YAML file."""
    return FIXTURES_DIR / "example_schema.yaml"


@pytest.fixture()
def golden_plc_dir() -> Path:
    """Return the path to the golden PLC output directory."""
    return GOLDEN_DIR / "plc"


@pytest.fixture()
def golden_cpp_dir() -> Path:
    """Return the path to the golden C++ output directory."""
    return GOLDEN_DIR / "cpp"


@pytest.fixture()
def golden_report_dir() -> Path:
    """Return the path to the golden report output directory."""
    return GOLDEN_DIR / "report"
