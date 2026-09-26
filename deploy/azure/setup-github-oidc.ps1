# One-time: let GitHub Actions deploy to the XORA App Service via OIDC (no stored secrets).
# Creates a user-assigned managed identity, trusts the repo's "azure" environment,
# and grants Website Contributor on the web app only. Then sets the repo secrets.
# Requires: az login; optionally gh auth login (for the secrets step).
param(
    [string]$ResourceGroup = "rg-xora-chart-ai",
    [string]$AppName = "xora-chart-ai-1790394016",
    [string]$Repo = "admin-xtinex/xora_chart_ai",
    [string]$IdentityName = "id-xora-github-deploy",
    # This repo uses GitHub's immutable OIDC subject format (owner@id/repo@id).
    [string]$Subject = "repo:admin-xtinex@270872005/xora_chart_ai@1346776376:environment:azure"
)
$ErrorActionPreference = "Stop"

function Invoke-Az {
    $out = & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed" }
    return $out
}

$location = Invoke-Az webapp show -g $ResourceGroup -n $AppName --query location -o tsv

Write-Host "Creating managed identity $IdentityName..."
Invoke-Az identity create -g $ResourceGroup -n $IdentityName -l $location -o none

Write-Host "Adding GitHub federated credential..."
Invoke-Az identity federated-credential create -g $ResourceGroup --identity-name $IdentityName -n github-azure-env `
    --issuer https://token.actions.githubusercontent.com `
    --subject $Subject `
    --audiences api://AzureADTokenExchange -o none

$clientId = Invoke-Az identity show -g $ResourceGroup -n $IdentityName --query clientId -o tsv
$principalId = Invoke-Az identity show -g $ResourceGroup -n $IdentityName --query principalId -o tsv
$scope = Invoke-Az webapp show -g $ResourceGroup -n $AppName --query id -o tsv

Write-Host "Granting Website Contributor on $AppName (may take a moment to propagate)..."
Invoke-Az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
    --role "Website Contributor" --scope $scope -o none

$tenantId = Invoke-Az account show --query tenantId -o tsv
$subscriptionId = Invoke-Az account show --query id -o tsv

& gh auth status *> $null
if ($LASTEXITCODE -eq 0) {
    gh secret set AZURE_CLIENT_ID --repo $Repo --body $clientId
    gh secret set AZURE_TENANT_ID --repo $Repo --body $tenantId
    gh secret set AZURE_SUBSCRIPTION_ID --repo $Repo --body $subscriptionId
    Write-Host "GitHub secrets set on $Repo. Starting the deploy workflow..."
    gh workflow run deploy-azure.yml --repo $Repo --ref main
} else {
    Write-Host "gh not logged in. Add these repo secrets manually (Settings > Secrets and variables > Actions):"
    Write-Host "  AZURE_CLIENT_ID=$clientId"
    Write-Host "  AZURE_TENANT_ID=$tenantId"
    Write-Host "  AZURE_SUBSCRIPTION_ID=$subscriptionId"
}
