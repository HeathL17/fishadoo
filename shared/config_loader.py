"""Configuration loader for Fishadoo.

Reads config.json from the project root and merges it with safe defaults.
All configuration errors are logged and fall back to defaults so the function
continues to run even when the config file is missing or malformed.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to config.json, resolved relative to this file so it works both locally
# and inside the Azure Functions runtime where the working directory may differ.
_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

_DEFAULTS: dict[str, Any] = {
    "seed": "fishadoo-default-seed",
    "string_length": 32,
    "string_charset": "alphanumeric",
    "schedule": "0 */10 * * * *",
}


def load_config(config_path: Path = _CONFIG_PATH) -> dict[str, Any]:
    """Load configuration from config.json, falling back to defaults on error.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        A dictionary containing the merged configuration values.
    """
    try:
        with open(config_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        logger.info("Configuration loaded from '%s'", config_path)
    except FileNotFoundError:
        logger.error(
            "config.json not found at '%s'. Using default configuration.", config_path
        )
        return _DEFAULTS.copy()
    except json.JSONDecodeError as exc:
        logger.error(
            "Invalid JSON in config file '%s': %s. Using default configuration.",
            config_path,
            exc,
        )
        return _DEFAULTS.copy()

    config = {**_DEFAULTS, **raw}

    # Validate numeric fields so downstream code never receives bad types.
    if not isinstance(config["string_length"], int) or config["string_length"] <= 0:
        logger.warning(
            "Invalid string_length '%s'; reverting to default %d.",
            config["string_length"],
            _DEFAULTS["string_length"],
        )
        config["string_length"] = _DEFAULTS["string_length"]

    return config
