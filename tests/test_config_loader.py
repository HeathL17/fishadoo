"""Tests for shared/config_loader.py."""

import json
from pathlib import Path

import pytest

from shared.config_loader import _DEFAULTS, load_config


class TestLoadConfig:
    """Tests for load_config."""

    def test_loads_valid_config(self, tmp_path: Path) -> None:
        """Valid config.json is loaded and merged with defaults."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps({"seed": "my-seed", "string_length": 64}), encoding="utf-8"
        )

        result = load_config(cfg_file)

        assert result["seed"] == "my-seed"
        assert result["string_length"] == 64
        # Defaults for unspecified keys should be present.
        assert result["string_charset"] == _DEFAULTS["string_charset"]
        assert result["schedule"] == _DEFAULTS["schedule"]

    def test_returns_defaults_when_file_missing(self, tmp_path: Path) -> None:
        """Missing config.json falls back to defaults without raising."""
        result = load_config(tmp_path / "nonexistent.json")

        assert result == _DEFAULTS

    def test_returns_defaults_on_invalid_json(self, tmp_path: Path) -> None:
        """Malformed JSON falls back to defaults without raising."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text("{ this is not json }", encoding="utf-8")

        result = load_config(cfg_file)

        assert result == _DEFAULTS

    def test_invalid_string_length_reverts_to_default(self, tmp_path: Path) -> None:
        """Non-positive string_length is replaced with the default."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"string_length": -5}), encoding="utf-8")

        result = load_config(cfg_file)

        assert result["string_length"] == _DEFAULTS["string_length"]

    def test_zero_string_length_reverts_to_default(self, tmp_path: Path) -> None:
        """Zero string_length is replaced with the default."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"string_length": 0}), encoding="utf-8")

        result = load_config(cfg_file)

        assert result["string_length"] == _DEFAULTS["string_length"]

    def test_string_length_type_mismatch_reverts_to_default(
        self, tmp_path: Path
    ) -> None:
        """A non-integer string_length reverts to the default."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"string_length": "lots"}), encoding="utf-8")

        result = load_config(cfg_file)

        assert result["string_length"] == _DEFAULTS["string_length"]

    def test_extra_keys_are_preserved(self, tmp_path: Path) -> None:
        """Unknown keys in config.json pass through (forward-compatibility)."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"future_option": True}), encoding="utf-8")

        result = load_config(cfg_file)

        assert result["future_option"] is True

    def test_defaults_not_mutated_across_calls(self, tmp_path: Path) -> None:
        """Each call returns an independent copy; mutating it does not change defaults."""
        result1 = load_config(tmp_path / "nonexistent.json")
        result1["seed"] = "mutated"
        result2 = load_config(tmp_path / "nonexistent.json")

        assert result2["seed"] == _DEFAULTS["seed"]
