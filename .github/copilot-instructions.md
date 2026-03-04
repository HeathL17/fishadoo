# Copilot Instructions for fishadoo

## Project Overview

fishadoo is a personal data-gathering hub built on **Azure Functions (Python v2)** and deployed to Azure.  The v1 foundation is a timer-triggered function that writes a cryptographically random string to an Azure Storage Table every 10 minutes.

## Tech Stack

- **Runtime:** Python 3.11+ (Azure Functions v2 programming model)
- **Infrastructure:** Azure Functions (Consumption Plan), Azure Storage Tables, Application Insights – defined as Bicep templates in `infra/`
- **CI/CD:** GitHub Actions (`.github/workflows/ci.yml` for lint + test, `.github/workflows/deploy.yml` for Azure deployment)
- **Test framework:** pytest with pytest-mock and freezegun
- **Authentication:** `DefaultAzureCredential` (managed identity in Azure, `az login` locally)

## Repository Structure

```
fishadoo/
├── .github/
│   ├── copilot-instructions.md   # this file
│   └── workflows/
│       ├── ci.yml                # CI: lint + test
│       └── deploy.yml            # CD: deploy to Azure
├── infra/
│   ├── main.bicep                # Azure infrastructure as code
│   └── main.parameters.example.json
├── shared/                       # Business logic (independent of function trigger)
│   ├── __init__.py
│   ├── config_loader.py          # Reads & validates config.json
│   ├── string_generator.py       # Cryptographically secure random strings
│   └── table_writer.py           # Azure Table Storage I/O
├── tests/
│   ├── test_config_loader.py
│   ├── test_string_generator.py
│   └── test_table_writer.py
├── function_app.py               # Azure Functions v2 entry point
├── config.json                   # User-editable config (seed, length, charset, schedule)
├── host.json                     # Functions host configuration
├── local.settings.json.example   # Template – copy to local.settings.json (never commit)
├── requirements.txt              # Runtime dependencies
└── requirements-dev.txt          # Test/lint dependencies
```

## Development Workflow

### Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Run tests

```bash
python -m pytest tests/ -v
```

All tests run in < 1 second with no network required.

### Run a single test file

```bash
python -m pytest tests/test_string_generator.py -v
```

### Local function development

1. Start Azurite: `azurite --silent --location /tmp/azurite`
2. Copy settings: `cp local.settings.json.example local.settings.json`
3. Start the function host: `func start`
4. Trigger manually: `curl -X POST http://localhost:7071/admin/functions/random_string_writer -H "Content-Type: application/json" -d '{}'`

## Code Conventions

- **Python style:** Follow PEP 8. Use type hints throughout. Use `from __future__ import annotations` only if needed for forward references.
- **Docstrings:** Google-style docstrings on all public functions and modules. Document `Args`, `Returns`, and `Raises` sections.
- **Logging:** Use `logging.getLogger(__name__)` in every module. Use `%s`-style formatting (not f-strings) in log calls to defer string interpolation.
- **Errors:** Raise `ValueError` for configuration / input errors. Let unexpected exceptions propagate and be caught at the function entrypoint (`function_app.py`).
- **Security:** Use `secrets.choice()` (CSPRNG) for all production string generation. Never use `random` in production paths. Never commit `local.settings.json` or credentials.
- **Shared logic lives in `shared/`:** Keep business logic independent of the Azure Functions trigger. New data sources should add a module to `shared/` and a new function registration in `function_app.py`.
- **Configuration:** Read runtime config from `config.json` via `shared/config_loader.py`. Read Azure connection details from environment variables (`TABLE_ACCOUNT_NAME`, `TABLE_CONNECTION_STRING`, `TABLE_NAME`, `SCHEDULE`).

## Adding a New Data Source

1. Create `shared/<new_source>_writer.py` following the pattern of `shared/table_writer.py`.
2. Register a new timer-triggered function in `function_app.py` using `@app.timer_trigger(...)`.
3. Use a distinct `PartitionKey` in the Azure Storage Table to keep data queryable by source.
4. Add tests in `tests/test_<new_source>_writer.py` following the existing test patterns.

## Testing Conventions

- Use `pytest-mock` (`mocker` fixture) for patching external dependencies (e.g., `TableClient`, environment variables).
- Use `freezegun` (`freeze_time`) when testing time-dependent behaviour.
- Tests must not require a network connection or running Azure services.
- Use `seed_override` parameter in `generate_random_string()` for deterministic test strings.
- Patch at the point of use (e.g., `shared.table_writer.TableClient`), not at the source.

## Infrastructure Notes

- All Azure infrastructure is defined in `infra/main.bicep`.
- Deployment is triggered automatically on push to `main` or manually via `workflow_dispatch`.
- The Function App uses a **system-assigned managed identity** with the **Storage Table Data Contributor** role – no connection strings are stored in Azure app settings.
- TLS 1.2 minimum, HTTPS-only, and FTPS disabled are enforced in Bicep.
