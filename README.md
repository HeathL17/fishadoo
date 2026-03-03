# fishadoo  🎣

A personal data-gathering hub built on Azure Functions and Python.  This is the **v1 foundation** – a timer-triggered function that writes a cryptographically random string to an Azure Storage Table every 10 minutes.  It is intentionally small so you can build on top of it confidently.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Configuration](#configuration)
5. [Local Development & Testing](#local-development--testing)
6. [Deployment to Azure](#deployment-to-azure)
7. [Running Tests](#running-tests)
8. [Operations](#operations)
9. [Troubleshooting](#troubleshooting)
10. [Security Notes](#security-notes)
11. [Extending the Project](#extending-the-project)

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Azure Function App (Consumption Plan)  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  random_string_writer             │  │
│  │  Timer trigger – every 10 min    │  │
│  │                                   │  │
│  │  1. load_config(config.json)     │  │
│  │  2. generate_random_string()     │  │
│  │  3. write entity → Table Storage │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Application Insights (telemetry)       │
└─────────────────────────────────────────┘
            │
            ▼
 ┌────────────────────┐
 │  Azure Storage     │
 │  Table: RandomStrings│
 │  (expandable)      │
 └────────────────────┘
```

**Key design decisions with growth in mind:**

| Decision | Rationale |
|---|---|
| `PartitionKey = "random_strings"` | Easy to query all records.  Future data sources get their own partition keys. |
| UUID `RowKey` | Collision-proof.  Works across distributed writers. |
| `source` field on every entity | Enables filtering when multiple function instances write to the same table. |
| `shared/` package | Business logic is independent of the Function trigger – testable and reusable. |
| `config.json` external configuration | Change seed, length, or charset without touching code. |

---

## Project Structure

```
fishadoo/
├── .github/
│   └── workflows/
│       ├── ci.yml              # CI: lint + test on every push / PR
│       └── deploy.yml          # CD: deploy infrastructure + function app to Azure
├── infra/
│   ├── main.bicep              # Azure infrastructure as code
│   └── main.parameters.example.json
├── shared/
│   ├── __init__.py
│   ├── config_loader.py        # Reads & validates config.json
│   ├── string_generator.py     # Cryptographically secure random strings
│   └── table_writer.py         # Azure Table Storage I/O
├── tests/
│   ├── test_config_loader.py
│   ├── test_string_generator.py
│   └── test_table_writer.py
├── function_app.py             # Azure Functions v2 entry point
├── host.json                   # Functions host configuration
├── config.json                 # User-editable configuration (seed, length…)
├── local.settings.json.example # Template – copy to local.settings.json
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Test/lint dependencies
└── README.md
```

---

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Python | 3.11 | Function runtime |
| [Homebrew](https://brew.sh) | latest | macOS package manager (macOS only) |
| [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) | v4 | Local function host |
| [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) | 3.x | Local Storage emulator |
| [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) | 2.50+ | One-time identity setup (see [Deployment](#deployment-to-azure)) |

### Installing prerequisites on macOS

Install [Homebrew](https://brew.sh) if you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install Python 3.11:

```bash
brew install python@3.11
```

Install Azure Functions Core Tools (recommended for macOS):

```bash
brew tap azure/functions
brew install azure-functions-core-tools@4
```

Install Azure CLI:

```bash
brew install azure-cli
```

Install Azurite (local Storage emulator):

```bash
npm install -g azurite
```

> **Other platforms:** On Linux/Windows use `npm install -g azure-functions-core-tools@4 --unsafe-perm true` for Azure Functions Core Tools, and follow the [Azure CLI install guide](https://learn.microsoft.com/cli/azure/install-azure-cli) for your OS.

---

## Configuration

### `config.json` – what you can change

| Key | Default | Description |
|---|---|---|
| `seed` | `"fishadoo-default-seed"` | Stored as metadata with every record.  Change this to identify your data source or distinguish multiple deployments. |
| `string_length` | `32` | Number of characters per generated string. |
| `string_charset` | `"alphanumeric"` | Character set.  Options: `alphanumeric`, `alpha`, `digits`, `hex`, `printable`. |
| `schedule` | `"0 */10 * * * *"` | CRON expression (documentation only).  The **actual** schedule is controlled by the `SCHEDULE` app setting (see below). |

> **Note:** The `schedule` field in `config.json` is informational – it helps you keep the two in sync.  The live schedule is always driven by the `SCHEDULE` environment variable / app setting.

### Converting minutes to a CRON schedule

| Every N minutes | CRON expression |
|---|---|
| 1 | `0 * * * * *` |
| 5 | `0 */5 * * * *` |
| 10 (default) | `0 */10 * * * *` |
| 15 | `0 */15 * * * *` |
| 30 | `0 */30 * * * *` |
| 60 | `0 0 * * * *` |

### `local.settings.json` – local secrets (never committed)

Copy the example file and edit it:

```bash
cp local.settings.json.example local.settings.json
```

| Setting | Description |
|---|---|
| `AzureWebJobsStorage` | Use `UseDevelopmentStorage=true` for Azurite |
| `TABLE_CONNECTION_STRING` | Use `UseDevelopmentStorage=true` for Azurite (local dev only) |
| `TABLE_NAME` | Table to write to (created automatically) |
| `SCHEDULE` | Six-field CRON expression |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Leave blank locally; set in Azure for telemetry |

> **Prefer `TABLE_ACCOUNT_NAME` over `TABLE_CONNECTION_STRING` when connecting to a real Azure Storage account locally.**  Set `TABLE_ACCOUNT_NAME` to your storage account name and authenticate via `az login` – no shared key or connection string needed.  See [Local Development & Testing](#local-development--testing) for details.

---

## Local Development & Testing

### Step 1 – Fork and clone the repository

If you are a first-time contributor, fork the repository on GitHub first.

```bash
# Clone your fork (replace <your-github-username> with your GitHub username)
git clone https://github.com/<your-github-username>/fishadoo.git
cd fishadoo

# Add the upstream remote so you can sync future changes
git remote add upstream https://github.com/HeathL17/fishadoo.git
```

> **Already have a clone?**  Keep it up to date before starting new work:
>
> ```bash
> git fetch upstream
> git checkout main
> git merge upstream/main        # fast-forward your local main
> git push origin main           # push the update to your fork
> ```

Work on a dedicated branch rather than directly on `main`:

```bash
git checkout -b feature/my-change
```

### Step 2 – Set up a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

> **macOS note:** If you installed Python via Homebrew (`brew install python@3.11`), use `python3.11` explicitly: `python3.11 -m venv .venv`.

### Step 3 – Copy and edit local settings

```bash
cp local.settings.json.example local.settings.json
# The defaults work for Azurite – no edits needed unless you want to change the schedule.
```

### Step 4 – Start the Azurite storage emulator

Open a separate terminal and run:

```bash
azurite --silent --location /tmp/azurite --debug /tmp/azurite/debug.log
```

> **macOS note:** `/tmp` on macOS is a symlink to `/private/tmp`. The command above works as-is, but if you prefer a persistent directory you can use `~/azurite` instead:
> ```bash
> mkdir -p ~/azurite
> azurite --silent --location ~/azurite --debug ~/azurite/debug.log
> ```

Azurite listens on:
- Blob: `http://127.0.0.1:10000`
- Queue: `http://127.0.0.1:10001`
- Table: `http://127.0.0.1:10002`

### Step 5 – Start the Azure Functions host

```bash
func start
```

You should see output like:

```
Functions:
    random_string_writer: timerTrigger
```

### Step 6 – Trigger the function manually

To trigger the function without waiting for the timer:

```bash
curl -X POST http://localhost:7071/admin/functions/random_string_writer \
     -H "Content-Type: application/json" \
     -d '{}'
```

### Step 7 – Verify the data was written

Use [Azure Storage Explorer](https://azure.microsoft.com/products/storage/storage-explorer/) connected to Azurite (`UseDevelopmentStorage=true`) and browse to:

```
Emulator & Attached → Storage Accounts → (Emulator - Default Ports) → Tables → RandomStrings
```

Each row will contain:

| Field | Example |
|---|---|
| `PartitionKey` | `random_strings` |
| `RowKey` | `3fa85f64-5717-4562-b3fc-2c963f66afa6` |
| `value` | `K7mNqPzRxTyWvUhJ2cAeBfGdLsOiElMn` |
| `seed` | `fishadoo-default-seed` |
| `length` | `32` |
| `charset` | `alphanumeric` |
| `source` | `random_string_writer` |
| `created_at` | `2024-01-15T14:30:00.123456+00:00` |

### Optional: connect to a real Azure Storage account locally

Instead of Azurite you can authenticate to a real Azure Storage account using your own identity (no connection string or shared key needed):

```bash
az login   # sign in once with the Azure CLI

# In local.settings.json, set TABLE_ACCOUNT_NAME and remove TABLE_CONNECTION_STRING:
#   "TABLE_ACCOUNT_NAME": "<your-storage-account-name>"
```

`DefaultAzureCredential` will pick up your `az login` session automatically.  Ensure your account has the **Storage Table Data Contributor** role on the storage account.

---

## Deployment to Azure

Deployment is handled exclusively via the **Deploy** GitHub Actions workflow (`.github/workflows/deploy.yml`).  It runs automatically on every push to `main` and can also be triggered manually via `workflow_dispatch`.

### Step 1 – Create an Azure resource group

Before the first run, create the resource group once (this step is only needed once):

```bash
az login
az account set --subscription "<your-subscription-id>"
az group create --name fishadoo-rg --location eastus
```

### Step 2 – Configure an Azure identity for GitHub Actions

Create a **Microsoft Entra ID** application with a **federated credential** so GitHub Actions can authenticate to Azure without storing a password or client secret.

```bash
# 1. Create an app registration
az ad app create --display-name "fishadoo-github-deploy"

# 2. Note the appId, then create a service principal
APP_ID="<appId from previous command>"
az ad sp create --id "$APP_ID"

# 3. Assign Contributor on the resource group
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
az role assignment create \
  --assignee "$APP_ID" \
  --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/fishadoo-rg"

# 4. Add a federated credential for the main branch
TENANT_ID=$(az account show --query tenantId -o tsv)
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "fishadoo-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<your-github-username>/<your-repo-name>:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

### Step 3 – Add GitHub secrets and variables

In your GitHub repository go to **Settings → Secrets and variables → Actions** and add:

| Type | Name | Value |
|---|---|---|
| Secret | `AZURE_CLIENT_ID` | `appId` from Step 2 |
| Secret | `AZURE_TENANT_ID` | `tenantId` from Step 2 |
| Secret | `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |
| Variable | `AZURE_RESOURCE_GROUP` | `fishadoo-rg` (or your chosen name) |

### Step 4 – (Optional) customise deployment parameters

Edit `infra/main.parameters.example.json` to adjust the base name, region, schedule, or Python version before pushing.  The file contains no secrets and is used directly by the Deploy workflow, so commit your edits alongside the code.

### Step 5 – Push to `main` to deploy

```bash
git push origin main
```

The **Deploy** workflow will:
1. Authenticate to Azure using the federated identity
2. Deploy (or update) all Azure infrastructure via Bicep
3. Package and publish the Python function app code

The deployment creates:
- Storage Account (houses Function App state **and** the `RandomStrings` table)
- Log Analytics Workspace + Application Insights
- Consumption App Service Plan
- Function App with a **system-assigned managed identity**
- RBAC role assignment (Storage Table Data Contributor) on the Storage Account

You can also trigger a deployment manually: **Actions → Deploy → Run workflow**.

### Step 6 – Verify in the Azure Portal

1. Go to the Function App → **Functions** → `random_string_writer`.
2. Click **Monitor** to see recent executions.
3. Open **Application Insights** → **Live Metrics** to watch the function fire in real time.
4. Browse **Storage Account** → **Tables** → `RandomStrings` to see the written rows.

---

## Running Tests

```bash
# Activate the virtual environment first
python -m pytest tests/ -v
```

Expected output: all tests in `tests/` pass in < 1 second (no network required).

To run a single test file:

```bash
python -m pytest tests/test_string_generator.py -v
```

---

## Operations

### Changing the schedule

1. Edit `config.json` → update `schedule` (for documentation).
2. Edit `infra/main.parameters.example.json` → update the `schedule` parameter value.
3. Commit and push to `main` – the Deploy workflow re-runs the Bicep template with the new schedule, which updates the `SCHEDULE` app setting automatically.
4. The change takes effect on the next Function App restart (usually within seconds).

### Changing the seed or string configuration

1. Edit `config.json`.
2. Commit and push to `main` – the Deploy workflow re-packages and publishes the function automatically.

### Viewing logs in Azure

**Portal:**  Function App → Functions → `random_string_writer` → Monitor → Invocation Details

**CLI (streaming):**
```bash
func azure functionapp logstream "$FUNCTION_APP_NAME"
```

**Application Insights (KQL):**
```kusto
-- All successful executions in the last hour
traces
| where timestamp > ago(1h)
| where message contains "random_string_writer"
| order by timestamp desc
```

### Querying the table

Using the Azure CLI:

```bash
az storage entity query \
  --account-name "<storage-account-name>" \
  --table-name RandomStrings \
  --filter "PartitionKey eq 'random_strings'" \
  --auth-mode login
```

---

## Troubleshooting

### Function never fires / timer is silent

| Symptom | Likely cause | Fix |
|---|---|---|
| No invocations in Monitor | `SCHEDULE` setting is invalid | Verify the CRON format (6 fields, seconds first) |
| `past_due` warning in logs | Function App was scaled down or throttled | Check the Consumption plan quotas; consider Premium plan |
| Function App not starting | Missing `AzureWebJobsStorage` | Ensure the storage account setting is correct |

### `TABLE_ACCOUNT_NAME` / `TABLE_CONNECTION_STRING` not set

```
Neither 'TABLE_ACCOUNT_NAME' nor 'TABLE_CONNECTION_STRING' environment variable is set.
```

**Fix:**
- **Azure (preferred):** Ensure `TABLE_ACCOUNT_NAME` is set in the Function App configuration blade.  The Bicep deployment sets this automatically.  Also verify the managed identity has the **Storage Table Data Contributor** role on the storage account.
- **Local (Azurite):** Ensure Azurite is running and `local.settings.json` contains `TABLE_CONNECTION_STRING: UseDevelopmentStorage=true`.
- **Local (real Azure account):** Set `TABLE_ACCOUNT_NAME` in `local.settings.json` and run `az login`.

### `UseDevelopmentStorage=true` fails with connection refused

Azurite is not running.  Start it:

```bash
azurite --silent --location /tmp/azurite
```

> **macOS:** Use `~/azurite` if you prefer a persistent directory (see [Step 3](#step-3--start-the-azurite-storage-emulator)).

### HTTP 403 when writing to table storage (Azure)

The managed identity has not been assigned the **Storage Table Data Contributor** role, or the role assignment has not yet propagated (can take up to 5 minutes).

```bash
# Check role assignments
az role assignment list \
  --assignee "<function-app-principal-id>" \
  --scope "/subscriptions/<sub-id>/resourceGroups/fishadoo-rg/providers/Microsoft.Storage/storageAccounts/<storage-name>"
```

### Stale config after deploying

The function loads `config.json` at each invocation, but the file must be included in the deployment package.  If you changed `config.json` locally, commit and push to `main` to trigger a new Deploy workflow run.

### Enabling debug logging locally

Set the log level in `host.json`:

```json
"logLevel": {
  "default": "Debug"
}
```

Then restart `func start`.

---

## Security Notes

| Practice | Implementation |
|---|---|
| No secrets in source control | `local.settings.json` is in `.gitignore`; use environment variables / app settings |
| No secrets in app settings (Azure) | Function App uses `TABLE_ACCOUNT_NAME` + managed identity; `TABLE_CONNECTION_STRING` is never stored in Azure app settings |
| Managed Identity in Azure | Function App accesses Table Storage via its system-assigned managed identity (Storage Table Data Contributor role); no shared keys or connection strings in Azure |
| `DefaultAzureCredential` in code | Supports managed identity (Azure), `az login` (local real-account dev), and environment credentials transparently |
| Passwordless CI/CD | GitHub Actions authenticates to Azure via OIDC federated credentials; no client secrets or passwords are stored as GitHub secrets |
| TLS 1.2 minimum | Enforced on Storage Account and Function App in Bicep |
| HTTPS-only Function App | `httpsOnly: true` in Bicep |
| No public blob access | `allowBlobPublicAccess: false` on Storage Account |
| FTPS disabled | `ftpsState: Disabled` in Bicep |
| Cryptographically secure RNG | `secrets.choice()` (CSPRNG) used for all production string generation |

---

## Extending the Project

This codebase is designed to grow.  Here are suggested next steps:

1. **Add a new data source** – Create a new timer-triggered function in `function_app.py` and a corresponding writer in `shared/`.  Reuse `config_loader` and `table_writer` patterns.

2. **Add more data types** – Use additional Table partition keys (e.g., `"weather"`, `"prices"`) to keep all data in one table while keeping sources queryable separately.

3. **Add an HTTP-triggered function** – Use `@app.route()` to expose a simple API for querying the table.

4. **Add alerting** – Create Application Insights alert rules in Bicep to notify on function failures.

5. **Switch to Premium plan** – For lower cold-start latency and VNet integration, update the Bicep `sku` from `Y1` to `EP1`.
