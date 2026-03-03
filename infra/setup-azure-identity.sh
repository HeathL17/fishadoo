#!/usr/bin/env bash
# =============================================================================
# setup-azure-identity.sh
#
# One-time script: creates the Microsoft Entra ID app registration, service
# principal, role assignment, and federated credential that allow the
# "Deploy" GitHub Actions workflow to authenticate to Azure without secrets.
#
# Usage:
#   chmod +x infra/setup-azure-identity.sh
#   ./infra/setup-azure-identity.sh
#
# Requirements:
#   • Azure CLI 2.50+ (az login already run, correct subscription selected)
#   • jq  (available via: brew install jq  /  apt install jq)
#
# The script is idempotent: re-running it will skip steps that are already
# complete rather than create duplicate resources.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration – edit these if your setup differs from the defaults
# ---------------------------------------------------------------------------
GITHUB_ORG="HeathL17"
GITHUB_REPO="fishadoo"
RESOURCE_GROUP="fishadoo-rg"
APP_DISPLAY_NAME="fishadoo-github-deploy"
FEDCRED_NAME="fishadoo-production"
ENVIRONMENT="production"
# ---------------------------------------------------------------------------

echo "==> Fetching current subscription …"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "    Subscription: $SUBSCRIPTION_ID"

# 1. Create (or re-use) the app registration
echo ""
echo "==> Checking for existing app registration '${APP_DISPLAY_NAME}' …"
EXISTING_APP=$(az ad app list --display-name "${APP_DISPLAY_NAME}" --query "[0].appId" -o tsv 2>/dev/null || true)

if [ -n "${EXISTING_APP}" ]; then
  APP_ID="${EXISTING_APP}"
  echo "    App already exists – appId: ${APP_ID}"
else
  echo "    Creating app registration …"
  APP_ID=$(az ad app create --display-name "${APP_DISPLAY_NAME}" --query appId -o tsv)
  echo "    Created – appId: ${APP_ID}"
fi

# 2. Create (or re-use) the service principal
echo ""
echo "==> Ensuring service principal exists …"
SP_EXISTS=$(az ad sp show --id "${APP_ID}" --query appId -o tsv 2>/dev/null || true)
if [ -z "${SP_EXISTS}" ]; then
  az ad sp create --id "${APP_ID}" > /dev/null
  echo "    Service principal created."
else
  echo "    Service principal already exists."
fi

# 3. Assign Contributor on the resource group (skip if already assigned)
echo ""
echo "==> Assigning Contributor role on resource group '${RESOURCE_GROUP}' …"
SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
RA_EXISTS=$(az role assignment list \
  --assignee "${APP_ID}" \
  --role Contributor \
  --scope "${SCOPE}" \
  --query "[0].id" -o tsv 2>/dev/null || true)

if [ -z "${RA_EXISTS}" ]; then
  az role assignment create \
    --assignee "${APP_ID}" \
    --role Contributor \
    --scope "${SCOPE}" > /dev/null
  echo "    Role assignment created."
else
  echo "    Role assignment already exists."
fi

# 4. Create the federated credential (skip if already present)
echo ""
echo "==> Adding federated credential '${FEDCRED_NAME}' …"
FC_EXISTS=$(az ad app federated-credential list --id "${APP_ID}" \
  --query "[?name=='${FEDCRED_NAME}'].name" -o tsv 2>/dev/null || true)

if [ -z "${FC_EXISTS}" ]; then
  # Write JSON to a temp file so the Azure CLI receives valid JSON on all
  # platforms (avoids macOS shell control-character injection with inline JSON).
  FEDCRED_FILE=$(mktemp -t fishadoo-fedcred.XXXXXX.json)
  trap 'rm -f "${FEDCRED_FILE}"' EXIT

  cat > "${FEDCRED_FILE}" << EOF
{
  "name": "${FEDCRED_NAME}",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${GITHUB_ORG}/${GITHUB_REPO}:environment:${ENVIRONMENT}",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF

  az ad app federated-credential create --id "${APP_ID}" --parameters "${FEDCRED_FILE}" > /dev/null
  echo "    Federated credential created."
else
  echo "    Federated credential already exists."
fi

# 5. Print the values needed for GitHub Secrets
echo ""
echo "========================================================================"
echo "  Setup complete. Add the following to your GitHub repository:"
echo "  Settings → Secrets and variables → Actions"
echo "========================================================================"
TENANT_ID=$(az account show --query tenantId -o tsv)
echo ""
echo "  AZURE_CLIENT_ID       = ${APP_ID}"
echo "  AZURE_TENANT_ID       = ${TENANT_ID}"
echo "  AZURE_SUBSCRIPTION_ID = ${SUBSCRIPTION_ID}"
echo ""
echo "  Also add the following repository variable:"
echo "  AZURE_RESOURCE_GROUP  = ${RESOURCE_GROUP}"
echo "========================================================================"
