def test_example_schema_loads(example_schema_raw: dict) -> None:
    """Verify the example schema YAML can be loaded and has expected top-level keys."""
    assert "version" in example_schema_raw
    assert "messages" in example_schema_raw
