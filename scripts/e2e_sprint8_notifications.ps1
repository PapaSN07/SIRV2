# E2E Sprint 8 — Notifications SMS (liste + envoi manuel mock)
# Usage: powershell -ExecutionPolicy Bypass -File scripts/e2e_sprint8_notifications.ps1

$ErrorActionPreference = "Stop"
$Base = "http://localhost:8000/api/v1"

function Invoke-SirApi {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Token = "",
        [object]$Body = $null
    )
    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }

    $params = @{
        Uri     = "$Base$Path"
        Method  = $Method
        Headers = $headers
    }
    if ($null -ne $Body) {
        $params["Body"] = ($Body | ConvertTo-Json -Depth 5 -Compress)
    }
    return Invoke-RestMethod @params
}

function Get-Token {
    param([string]$Login, [string]$Password)
    $res = Invoke-SirApi -Method POST -Path "/auth/login" -Body @{
        login    = $Login
        password = $Password
    }
    if ($res.status -ne "success") { throw "Login $Login failed: $($res.error)" }
    return $res.data.access_token
}

Write-Host "=== E2E Sprint 8 — Notifications SMS ===" -ForegroundColor Cyan

Write-Host "`n[1/4] Login ADMIN_SCR..." -ForegroundColor Yellow
$token = Get-Token -Login "admin_scr.dev" -Password "MotDePasse123!"

Write-Host "`n[2/4] Liste SMS..." -ForegroundColor Yellow
$list = Invoke-SirApi -Method GET -Path "/notifications/sms?page=1&page_size=5" -Token $token
if ($list.status -ne "success") { throw "List SMS failed: $($list.error)" }
Write-Host "  OK — total=$($list.data.total)" -ForegroundColor Green

Write-Host "`n[3/4] Liste destinataires actifs..." -ForegroundColor Yellow
$dest = Invoke-SirApi -Method GET -Path "/notifications/destinataires?page=1&page_size=10&is_active=true" -Token $token
if ($dest.status -ne "success") { throw "List destinataires failed: $($dest.error)" }
$destId = $dest.data.items[0].id
if (-not $destId) { throw "Aucun destinataire actif pour le test d'envoi" }
Write-Host "  OK — destinataire_id=$destId" -ForegroundColor Green

Write-Host "`n[4/4] Envoi SMS manuel (mock gateway)..." -ForegroundColor Yellow
$send = Invoke-SirApi -Method POST -Path "/notifications/sms/send" -Token $token -Body @{
    message          = "Test E2E Sprint 8 SIR"
    destinataire_ids = @($destId)
}
if ($send.status -ne "success") { throw "Send SMS failed: $($send.error)" }
Write-Host "  OK — sent_count=$($send.data.sent_count) sms_ids=$($send.data.sms_ids -join ',')" -ForegroundColor Green

Write-Host "`n=== E2E Sprint 8 terminé avec succès ===" -ForegroundColor Cyan
