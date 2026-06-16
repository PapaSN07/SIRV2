# E2E Sprint 5 - Indicateurs CRSE (END / SAIFI / SAIDI / tableau de bord)
# Prerequis : make seed-dev (ou make seed-indicateurs apres seeds de base)
# Usage: powershell -ExecutionPolicy Bypass -File scripts/e2e_sprint5_indicateurs.ps1

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

Write-Host "=== E2E Sprint 5 - Indicateurs CRSE ===" -ForegroundColor Cyan

Write-Host "`n[1/6] Login Admin SAQS (saqs.dev)..." -ForegroundColor Yellow
$token = Get-Token -Login "saqs.dev" -Password "DevSir123!"
$me = Invoke-SirApi -Method GET -Path "/auth/me" -Token $token
Write-Host "  OK - $($me.data.prenom) $($me.data.nom) ($($me.data.role_label))" -ForegroundColor Green

Write-Host "`n[2/6] GET /indicateurs/end (2026-06)..." -ForegroundColor Yellow
$end = Invoke-SirApi -Method GET -Path "/indicateurs/end?annee=2026&mois=6" -Token $token
if ($end.status -ne "success") { throw "GET end failed: $($end.error)" }
Write-Host "  OK - END agrégé = $($end.data.aggregate.end_mwh) MWh" -ForegroundColor Green

Write-Host "`n[3/6] GET /indicateurs/saifi + /saidi..." -ForegroundColor Yellow
$saifi = Invoke-SirApi -Method GET -Path "/indicateurs/saifi?annee=2026&mois=6" -Token $token
$saidi = Invoke-SirApi -Method GET -Path "/indicateurs/saidi?annee=2026&mois=6" -Token $token
Write-Host "  OK - SAIFI=$($saifi.data.aggregate.saifi) SAIDI=$($saidi.data.aggregate.saidi)" -ForegroundColor Green

Write-Host "`n[4/6] GET /indicateurs/tableau-de-bord..." -ForegroundColor Yellow
$dashboard = Invoke-SirApi -Method GET -Path "/indicateurs/tableau-de-bord?periode=2026-06" -Token $token
$kpi = $dashboard.data
Write-Host "  OK - END=$($kpi.end_mois) SAIFI=$($kpi.saifi) actives=$($kpi.nb_interruptions_actives)" -ForegroundColor Green

Write-Host "`n[5/6] GET /indicateurs/historique?type=saifi..." -ForegroundColor Yellow
$hist = Invoke-SirApi -Method GET -Path "/indicateurs/historique?type=saifi&annees=1" -Token $token
Write-Host "  OK - $($hist.data.points.Count) points mensuels" -ForegroundColor Green

Write-Host "`n[6/6] GET /indicateurs/top-feeders..." -ForegroundColor Yellow
$top = Invoke-SirApi -Method GET -Path "/indicateurs/top-feeders?periode=2026-06&limit=5" -Token $token
$count = $top.data.items.Count
Write-Host "  OK - $count feeder(s) classés" -ForegroundColor Green

Write-Host "`n=== E2E Sprint 5 indicateurs : SUCCES ===" -ForegroundColor Cyan
