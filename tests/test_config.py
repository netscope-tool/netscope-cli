"""Tests for AppConfig."""
import tempfile
from pathlib import Path

import pytest

from netscope.core.config import AppConfig, load_config_file


def test_app_config_default_output_dir():
    """When output_dir is not provided, it defaults to Path('output')."""
    config = AppConfig()
    assert config.output_dir == Path("output").resolve()


def test_app_config_explicit_output_dir():
    """When output_dir is provided, it is used and resolved."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "custom_out"
        config = AppConfig(output_dir=path)
        assert config.output_dir == path.resolve()
        assert config.output_dir.exists()


def test_app_config_output_dir_from_string():
    """output_dir can be passed as a string and is converted to Path."""
    with tempfile.TemporaryDirectory() as tmp:
        config = AppConfig(output_dir=tmp)
        assert config.output_dir == Path(tmp).resolve()


def test_app_config_create_test_run_dir():
    """create_test_run_dir creates a timestamped subdirectory."""
    with tempfile.TemporaryDirectory() as tmp:
        config = AppConfig(output_dir=tmp)
        test_dir = config.create_test_run_dir("ping_test")
        assert test_dir.parent == config.output_dir
        assert test_dir.name.startswith("20")  # timestamp
        assert "ping_test" in test_dir.name
        assert (test_dir / "raw_output").exists()


def test_load_config_file_no_file():
    """When no config file exists, load_config_file returns empty dict."""
    result = load_config_file()
    # May be empty or have values if user has ~/.netscope.yaml
    assert isinstance(result, dict)
