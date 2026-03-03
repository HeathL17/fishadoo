"""Tests for shared/table_writer.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shared.table_writer import build_entity, write_random_string


class TestBuildEntity:
    """Tests for build_entity – pure logic, no I/O."""

    def _config(self, **overrides) -> dict:
        base = {
            "seed": "test-seed",
            "string_length": 16,
            "string_charset": "alphanumeric",
        }
        return {**base, **overrides}

    def test_entity_has_required_keys(self) -> None:
        entity = build_entity(self._config())
        for key in ("PartitionKey", "RowKey", "value", "seed", "length", "charset",
                    "source", "created_at"):
            assert key in entity, f"Missing key: {key}"

    def test_value_has_correct_length(self) -> None:
        entity = build_entity(self._config(string_length=24))
        assert len(entity["value"]) == 24

    def test_seed_stored_as_metadata(self) -> None:
        entity = build_entity(self._config(seed="my-project-seed"))
        assert entity["seed"] == "my-project-seed"

    def test_source_is_correct(self) -> None:
        entity = build_entity(self._config())
        assert entity["source"] == "random_string_writer"

    def test_row_key_is_unique_across_calls(self) -> None:
        entity1 = build_entity(self._config())
        entity2 = build_entity(self._config())
        assert entity1["RowKey"] != entity2["RowKey"]

    def test_charset_stored_in_entity(self) -> None:
        entity = build_entity(self._config(string_charset="hex"))
        assert entity["charset"] == "hex"

    def test_created_at_is_iso_format(self) -> None:
        entity = build_entity(self._config())
        # Should be parseable as an ISO datetime.
        from datetime import datetime
        datetime.fromisoformat(entity["created_at"])


class TestWriteRandomString:
    """Tests for write_random_string – interactions with Azure SDK are mocked."""

    def _patch_env(self, monkeypatch, connection_string="UseDevelopmentStorage=true",
                   table_name="TestTable"):
        monkeypatch.setenv("TABLE_CONNECTION_STRING", connection_string)
        monkeypatch.delenv("TABLE_ACCOUNT_NAME", raising=False)
        monkeypatch.setenv("TABLE_NAME", table_name)

    def test_raises_when_connection_string_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("TABLE_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("TABLE_ACCOUNT_NAME", raising=False)
        with pytest.raises(ValueError, match="TABLE_ACCOUNT_NAME"):
            write_random_string()

    @patch("shared.table_writer._get_table_client")
    def test_calls_create_entity(self, mock_get_client, monkeypatch) -> None:
        self._patch_env(monkeypatch)
        mock_table_client = MagicMock()
        mock_get_client.return_value = mock_table_client

        write_random_string()

        mock_table_client.create_entity.assert_called_once()

    @patch("shared.table_writer._get_table_client")
    def test_entity_written_contains_expected_fields(
        self, mock_get_client, monkeypatch, tmp_path: Path
    ) -> None:
        """Entity passed to create_entity must contain all required fields."""
        self._patch_env(monkeypatch)
        # Write a temporary config so we control the values.
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps({"seed": "unit-test-seed", "string_length": 8}),
            encoding="utf-8",
        )

        mock_table_client = MagicMock()
        mock_get_client.return_value = mock_table_client

        with patch("shared.table_writer.load_config", return_value={
            "seed": "unit-test-seed",
            "string_length": 8,
            "string_charset": "alphanumeric",
        }):
            write_random_string()

        call_kwargs = mock_table_client.create_entity.call_args
        entity = call_kwargs.kwargs.get("entity") or call_kwargs.args[0]
        assert entity["seed"] == "unit-test-seed"
        assert len(entity["value"]) == 8
        assert entity["source"] == "random_string_writer"

    @patch("shared.table_writer._get_table_client")
    def test_resource_exists_error_is_swallowed(
        self, mock_get_client, monkeypatch
    ) -> None:
        """A duplicate RowKey (astronomically unlikely) is logged, not raised."""
        from azure.core.exceptions import ResourceExistsError

        self._patch_env(monkeypatch)
        mock_table_client = MagicMock()
        mock_table_client.create_entity.side_effect = ResourceExistsError()
        mock_get_client.return_value = mock_table_client

        # Should not raise.
        write_random_string()

    @patch("shared.table_writer._get_table_client")
    def test_http_response_error_is_propagated(
        self, mock_get_client, monkeypatch
    ) -> None:
        from azure.core.exceptions import HttpResponseError

        self._patch_env(monkeypatch)
        mock_table_client = MagicMock()
        mock_table_client.create_entity.side_effect = HttpResponseError()
        mock_get_client.return_value = mock_table_client

        with pytest.raises(HttpResponseError):
            write_random_string()

    @patch("shared.table_writer._get_table_client")
    def test_azure_error_is_propagated(
        self, mock_get_client, monkeypatch
    ) -> None:
        from azure.core.exceptions import AzureError

        self._patch_env(monkeypatch)
        mock_table_client = MagicMock()
        mock_table_client.create_entity.side_effect = AzureError("connection failed")
        mock_get_client.return_value = mock_table_client

        with pytest.raises(AzureError):
            write_random_string()

    @patch("shared.table_writer.TableServiceClient")
    @patch("shared.table_writer.DefaultAzureCredential")
    def test_uses_default_azure_credential_when_account_name_set(
        self, mock_cred_cls, mock_service_client_cls, monkeypatch
    ) -> None:
        """When TABLE_ACCOUNT_NAME is set, DefaultAzureCredential is used (no connection string)."""
        monkeypatch.setenv("TABLE_ACCOUNT_NAME", "mystorageaccount")
        monkeypatch.delenv("TABLE_CONNECTION_STRING", raising=False)
        monkeypatch.setenv("TABLE_NAME", "TestTable")

        mock_cred_cls.return_value = MagicMock()
        mock_service_client = MagicMock()
        mock_service_client_cls.return_value = mock_service_client
        mock_service_client.get_table_client.return_value = MagicMock()

        from shared.table_writer import _get_table_client

        _get_table_client("TestTable")

        # Verify TableServiceClient was called with an endpoint URL, not from_connection_string.
        mock_service_client_cls.assert_called_once()
        call_kwargs = mock_service_client_cls.call_args
        endpoint_arg = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("endpoint")
        assert endpoint_arg == "https://mystorageaccount.table.core.windows.net"
