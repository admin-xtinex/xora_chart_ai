# Point xora.xtinex.com at the Azure App Service, bind it with a free managed
# SSL certificate, and (optionally) set the first admin login.
#
# Usage (from the repo root, after `az login`):
#   powershell -ExecutionPolicy Bypass -File .\deploy\azure\setup-custom-domain.ps1
#   ... -SkipAdmin                 # domain only
#   ... -RemoveBootstrapPassword   # after your first sign-in: delete the admin password app setting
#
# Safe to re-run: every step checks what already exists.
param(
    [string]$AppResourceGroup = "rg-xora-chart-ai",
    [string]$AppName = "xora-chart-ai-1790394016",
    [string]$DnsResourceGroup = "rg-dns-xtinex",
    [string]$Zone = "xtinex.com",
    [string]$Subdomain = "xora",
    [switch]$SkipAdmin,
    [switch]$RemoveBootstrapPassword
)
$ErrorActionPreference = "Stop"
$Hostname = "$Subdomain.$Zone"

function Invoke-Az {
    $out = & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args[0..2] -join ' ') ... failed (exit $LASTEXITCODE)" }
    return $out
}
function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

$null = Invoke-Az account show -o none

if ($RemoveBootstrapPassword) {
    Step "Removing XORA_ADMIN_PASSWORD app setting (the admin account already exists in users.json)"
    Invoke-Az webapp config appsettings delete -g $AppResourceGroup -n $AppName --setting-names XORA_ADMIN_PASSWORD -o none
    Write-Host "Done. Change passwords from Settings > Your account from now on."
    return
}

# ---------------------------------------------------------------- admin login
if (-not $SkipAdmin) {
    Step "First admin account"
    Write-Host "Used only when no users exist yet (first start). Min 8 characters."
    $adminUser = Read-Host "Admin username"
    $secure1 = Read-Host "Admin password" -AsSecureString
    $secure2 = Read-Host "Confirm password" -AsSecureString
    $toPlain = {
        param($s)
        $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
        try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
    }
    $pw1 = & $toPlain $secure1
    $pw2 = & $toPlain $secure2
    if ($pw1 -ne $pw2) { throw "Passwords do not match" }
    if ($pw1.Length -lt 8) { throw "Password must be at least 8 characters" }
    if ($adminUser -notmatch '^[a-zA-Z0-9_.@-]{3,64}$') { throw "Username must be 3-64 characters: letters, digits, . _ @ -" }

    # Pass the secret through a temp file so it never appears on a command line.
    $tmp = [IO.Path]::GetTempFileName()
    try {
        @{ XORA_ADMIN_USERNAME = $adminUser; XORA_ADMIN_PASSWORD = $pw1 } | ConvertTo-Json | Set-Content -Path $tmp -Encoding ascii
        Invoke-Az webapp config appsettings set -g $AppResourceGroup -n $AppName --settings "@$tmp" -o none
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        $pw1 = $null; $pw2 = $null
    }
    Write-Host "Admin settings saved; the app restarts and creates '$adminUser' on first start."
}

# ---------------------------------------------------------------- DNS records
$defaultHost = Invoke-Az webapp show -g $AppResourceGroup -n $AppName --query defaultHostName -o tsv
$verificationId = Invoke-Az webapp show -g $AppResourceGroup -n $AppName --query customDomainVerificationId -o tsv

Step "Domain verification TXT record asuid.$Subdomain"
$txt = & az network dns record-set txt show -g $DnsResourceGroup -z $Zone -n "asuid.$Subdomain" --query "TXTRecords[].value[]" -o tsv 2>$null
if ($txt -contains $verificationId) {
    Write-Host "Already present."
} else {
    Invoke-Az network dns record-set txt add-record -g $DnsResourceGroup -z $Zone -n "asuid.$Subdomain" -v $verificationId -o none
    Write-Host "Added."
}

Step "CNAME $Hostname -> $defaultHost"
$currentCname = & az network dns record-set cname show -g $DnsResourceGroup -z $Zone -n $Subdomain --query "CNAMERecord.cname" -o tsv 2>$null
if ($currentCname -eq $defaultHost) {
    Write-Host "Already points to Azure."
} else {
    $aRecords = & az network dns record-set a show -g $DnsResourceGroup -z $Zone -n $Subdomain --query "ARecords[].ipv4Address" -o tsv 2>$null
    if ($aRecords) {
        Write-Host "Current A record: $Hostname -> $($aRecords -join ', ')  (the GCP VM)" -ForegroundColor Yellow
        $answer = Read-Host "Replace it with the Azure CNAME? Live traffic moves to Azure. (yes/no)"
        if ($answer -ne "yes") { throw "Aborted; DNS unchanged." }
        Invoke-Az network dns record-set a delete -g $DnsResourceGroup -z $Zone -n $Subdomain --yes -o none
        Write-Host "A record removed."
    }
    Invoke-Az network dns record-set cname set-record -g $DnsResourceGroup -z $Zone -n $Subdomain -c $defaultHost --ttl 300 -o none
    Write-Host "CNAME set."
}

Step "Waiting for public DNS"
for ($i = 1; $i -le 30; $i++) {
    try {
        $resolved = Resolve-DnsName -Name $Hostname -Type CNAME -Server 8.8.8.8 -DnsOnly -ErrorAction Stop |
            Where-Object { $_.Type -eq "CNAME" } | Select-Object -First 1 -ExpandProperty NameHost
    } catch { $resolved = $null }
    if ($resolved -eq $defaultHost) { Write-Host "Resolves to $resolved"; break }
    Write-Host "  not yet ($i/30)..."; Start-Sleep -Seconds 10
}

# ---------------------------------------------------------------- hostname + SSL
Step "Binding $Hostname to $AppName"
$hosts = Invoke-Az webapp show -g $AppResourceGroup -n $AppName --query "hostNames" -o tsv
if ($hosts -contains $Hostname) {
    Write-Host "Already bound."
} else {
    Invoke-Az webapp config hostname add -g $AppResourceGroup --webapp-name $AppName --hostname $Hostname -o none
    Write-Host "Bound."
}

Step "Managed SSL certificate (free; issuance can take a few minutes)"
$thumb = & az webapp config ssl list -g $AppResourceGroup --query "[?subjectName=='$Hostname'].thumbprint | [0]" -o tsv 2>$null
if (-not $thumb) {
    for ($i = 1; $i -le 10 -and -not $thumb; $i++) {
        $thumb = & az webapp config ssl create -g $AppResourceGroup -n $AppName --hostname $Hostname --query thumbprint -o tsv 2>$null
        if (-not $thumb) { Write-Host "  not issued yet ($i/10), retrying in 30s..."; Start-Sleep -Seconds 30 }
    }
    if (-not $thumb) { throw "Certificate was not issued. Re-run this script in a few minutes." }
}
Write-Host "Certificate thumbprint $thumb"

$sslState = Invoke-Az webapp show -g $AppResourceGroup -n $AppName --query "hostNameSslStates[?name=='$Hostname'].sslState | [0]" -o tsv
if ($sslState -eq "SniEnabled") {
    Write-Host "SNI binding already active."
} else {
    Invoke-Az webapp config ssl bind -g $AppResourceGroup -n $AppName --certificate-thumbprint $thumb --ssl-type SNI --hostname $Hostname -o none
    Write-Host "SNI binding created."
}

# ---------------------------------------------------------------- verify
Step "Verifying https://$Hostname"
$ok = $false
for ($i = 1; $i -le 18 -and -not $ok; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "https://$Hostname/healthz" -UseBasicParsing -TimeoutSec 15
        $ok = $r.StatusCode -eq 200
    } catch { Start-Sleep -Seconds 10 }
}
if ($ok) {
    Write-Host "https://$Hostname is live on Azure." -ForegroundColor Green
    if (-not $SkipAdmin) {
        Write-Host "Sign in at https://$Hostname/charts, then run this script with -RemoveBootstrapPassword." -ForegroundColor Green
    }
} else {
    Write-Warning "https://$Hostname/healthz did not answer yet. DNS or certificate may still be propagating; re-run in a few minutes."
}
