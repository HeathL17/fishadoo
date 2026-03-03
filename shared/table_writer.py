"""Azure Table Storage writer for Fishadoo.

Encapsulates all Table Storage interactions so they can be tested in isolation
and extended easily when additional data sources are added.

Authentication priority
-----------------------
1. ``TABLE_ACCOUNT_NAME`` is set → authenticate via ``DefaultAzureCredential``
   (managed identity in Azure, ``az login`` / environment credential locally).
   The table endpoint is derived as
   ``https://<account-name>.table.core.windows.net``.
2. ``TABLE_CONNECTION_STRING`` is set → authenticate via connection string.
   Use ``UseDevelopmentStorage=true`` for the local Azurite emulator.
3. Neither is set → ``ValueError`` is raised at startup.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from azure.core.exceptions import AzureError, HttpResponseError, ResourceExistsError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential

from shared.config_loader import load_config
from shared.string_generator import generate_random_string

logger = logging.getLogger(__name__)

# Environment variable names – never hard-code connection strings.
_ENV_ACCOUNT_NAME = "TABLE_ACCOUNT_NAME"
_ENV_CONNECTION_STRING = "TABLE_CONNECTION_STRING"
_ENV_TABLE_NAME = "TABLE_NAME"
_DEFAULT_TABLE_NAME = "RandomStrings"

# Partition key used for all records written by this function.
# Using a single partition keeps queries simple now while a future
# data-source refactor can introduce per-source partition keys.
_PARTITION_KEY = "random_strings"


def _get_table_client(table_name: str):
    """Create (and ensure existence of) an Azure Table Storage client.

    Prefers managed identity (``TABLE_ACCOUNT_NAME``) over a connection string
    (``TABLE_CONNECTION_STRING``) so that no secrets need to be stored in app
    settings or environment variables in production.

    Args:
        table_name: Name of the table to write to.

    Returns:
        A ``TableClient`` ready for entity operations.

    Raises:
        ValueError: If neither ``TABLE_ACCOUNT_NAME`` nor
            ``TABLE_CONNECTION_STRING`` is set.
        AzureError: If the client or table cannot be created.
    """
    account_name = os.environ.get(_ENV_ACCOUNT_NAME)
    if account_name:
        credential = DefaultAzureCredential()
        endpoint = f"https://{account_name}.table.core.windows.net"
        service_client = TableServiceClient(endpoint=endpoint, credential=credential)
        logger.debug("Authenticating to Table Storage via DefaultAzureCredential.")
    else:
        connection_string = os.environ.get(_ENV_CONNECTION_STRING)
        if not connection_string:
            raise ValueError(
                f"Neither '{_ENV_ACCOUNT_NAME}' nor '{_ENV_CONNECTION_STRING}' "
                "environment variable is set. "
                f"Set '{_ENV_ACCOUNT_NAME}' to your storage account name (preferred – "
                "uses managed identity / DefaultAzureCredential), or set "
                f"'{_ENV_CONNECTION_STRING}' to an Azure Storage connection string "
                "or 'UseDevelopmentStorage=true' for the local Azurite emulator."
            )
        service_client = TableServiceClient.from_connection_string(connection_string)
        logger.debug("Authenticating to Table Storage via connection string.")

    # create_table_if_not_exists is idempotent – safe to call on every run.
    service_client.create_table_if_not_exists(table_name)
    return service_client.get_table_client(table_name)


def build_entity(config: dict[str, Any]) -> dict[str, Any]:
    """Build the Table Storage entity dict from runtime config.

    Separating entity construction from I/O makes this logic unit-testable
    without needing a real storage account.

    Args:
        config: Loaded configuration dictionary (from ``load_config``).

    Returns:
        A dict ready to pass to ``TableClient.create_entity``.
    """
    length = config.get("string_length", 32)
    charset = config.get("string_charset", "alphanumeric")
    seed = config.get("seed", "")

    random_value = generate_random_string(length=length, charset=charset)

    now = datetime.now(timezone.utc)
    return {
        "PartitionKey": _PARTITION_KEY,
        "RowKey": str(uuid.uuid4()),
        "value": random_value,
        "seed": seed,
        "length": length,
        "charset": charset,
        "source": "random_string_writer",
        "created_at": now.isoformat(),
    }


def write_random_string() -> None:
    """Generate a random string and persist it to Azure Table Storage.

    Configuration (seed, length, charset) is read from ``config.json``.
    Authentication uses ``DefaultAzureCredential`` when ``TABLE_ACCOUNT_NAME``
    is set (preferred for Azure deployments), or falls back to a connection
    string from ``TABLE_CONNECTION_STRING`` (useful for local Azurite dev).
    No secrets are required in production.

    Raises:
        ValueError: If neither ``TABLE_ACCOUNT_NAME`` nor
            ``TABLE_CONNECTION_STRING`` env variable is set.
        HttpResponseError: On a non-retryable Azure HTTP error.
        AzureError: On any other Azure SDK error.
    """
    table_name = os.environ.get(_ENV_TABLE_NAME, _DEFAULT_TABLE_NAME)

    config = load_config()
    entity = build_entity(config)

    logger.info(
        "Writing random string to table '%s' (RowKey=%s, seed=%r, length=%d).",
        table_name,
        entity["RowKey"],
        entity["seed"],
        entity["length"],
    )

    try:
        table_client = _get_table_client(table_name)
        table_client.create_entity(entity=entity)
        logger.info(
            "Successfully wrote entity RowKey=%s to table '%s'.",
            entity["RowKey"],
            table_name,
        )
    except ResourceExistsError:
        # UUID collision is astronomically unlikely; log a warning and continue.
        logger.warning(
            "Entity with RowKey=%s already exists in table '%s'. Skipping.",
            entity["RowKey"],
            table_name,
        )
    except HttpResponseError as exc:
        logger.error(
            "HTTP error writing to table '%s': status=%s message=%s",
            table_name,
            exc.status_code,
            exc.message,
        )
        raise
    except AzureError as exc:
        logger.error(
            "Azure SDK error writing to table '%s': %s", table_name, exc
        )
        raise
