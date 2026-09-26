#!/usr/bin/env bash
# One-time: let GitHub Actions deploy to the XORA App Service via OIDC (no stored secrets).
# Creates a user-assigned managed identity, trusts the repo's "azure" environment,
# and grants Website Contributor on the web app only. Then sets the repo secrets.
# Requires: az login, gh auth login (for the secrets step).
set -euo pipefail

RG="${RG:-rg-xora-chart-ai}"
APP="${APP:-xora-chart-ai-1790394016}"
REPO="${REPO:-admin-xtinex/xora_chart_ai}"
ID_NAME="${ID_NAME:-id-xora-github-deploy}"
# This repo uses GitHub's immutable OIDC subject format (owner@id/repo@id).
SUBJECT="${SUBJECT:-repo:admin-xtinex@270872005/xora_chart_ai@1346776376:environment:azure}"
LOCATION="$(az webapp show -g "$RG" -n "$APP" --query location -o tsv)"

az identity create -g "$RG" -n "$ID_NAME" -l "$LOCATION" -o none
az identity federated-credential create -g "$RG" --identity-name "$ID_NAME" -n github-azure-env \
  --issuer https://token.actions.githubusercontent.com \
  --subject "$SUBJECT" \
  --audiences api://AzureADTokenExchange -o none

CLIENT_ID="$(az identity show -g "$RG" -n "$ID_NAME" --query clientId -o tsv)"
PRINCIPAL_ID="$(az identity show -g "$RG" -n "$ID_NAME" --query principalId -o tsv)"
SCOPE="$(az webapp show -g "$RG" -n "$APP" --query id -o tsv)"
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "Website Contributor" --scope "$SCOPE" -o none

TENANT_ID="$(az account show --query tenantId -o tsv)"
SUBSCRIPTION_ID="$(az account show --query id -o tsv)"

if gh auth status >/dev/null 2>&1; then
  gh secret set AZURE_CLIENT_ID --repo "$REPO" --body "$CLIENT_ID"
  gh secret set AZURE_TENANT_ID --repo "$REPO" --body "$TENANT_ID"
  gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO" --body "$SUBSCRIPTION_ID"
  echo "GitHub secrets set on $REPO."
else
  echo "gh not logged in. Add these repo secrets manually (Settings > Secrets and variables > Actions):"
  echo "  AZURE_CLIENT_ID=$CLIENT_ID"
  echo "  AZURE_TENANT_ID=$TENANT_ID"
  echo "  AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
fi
