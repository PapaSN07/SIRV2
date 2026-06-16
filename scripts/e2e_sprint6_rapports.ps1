# E2E Sprint 6 - Rapports CRSE (journalier async : POST -> poll status -> download)
# Prerequis : docker compose up (api + worker + redis), alembic upgrade head, seed-dev
#             apres deploiement code rapports : docker compose restart worker
# Usage: powershell -ExecutionPolicy Bypass -File scripts/e2e_sprint6_rapports.ps1

$ErrorActionPreference = "Stop"
$Base = "http://localhost:8000/api/v1"
$PollIntervalSec = 3
$PollTimeoutSec = 120

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
    if ($res.status -ne "success") { throw "Login $Login echoue : $($res.error)" }
    return $res.data.access_token
}

function Wait-RapportReady {
    param(
        [string]$Token,
        [string]$TaskId
    )
    $deadline = (Get-Date).AddSeconds($PollTimeoutSec)
    $attempt = 0

    while ((Get-Date) -lt $deadline) {
        $attempt++
        $status = Invoke-SirApi -Method GET -Path "/rapports/$TaskId/status" -Token $Token
        if ($status.status -ne "success") { throw "GET status echoue : $($status.error)" }

        $statut = $status.data.statut
        Write-Host "  poll #$attempt - statut=$statut" -ForegroundColor DarkGray

        if ($statut -eq "success") { return $status.data }
        if ($statut -eq "failure") {
            throw "Generation en echec : $($status.data.error_message)"
        }

        Start-Sleep -Seconds $PollIntervalSec
    }

    throw "Timeout apres ${PollTimeoutSec}s (statut toujours pending/started). Verifier le worker Celery : make logs-worker"
}

function Save-RapportDownload {
    param(
        [string]$Token,
        [string]$TaskId,
        [string]$OutFile
    )
    $headers = @{ "Authorization" = "Bearer $Token" }
    Invoke-WebRequest -Uri "$Base/rapports/$TaskId/download" -Headers $headers -OutFile $OutFile | Out-Null
}

Write-Host "=== E2E Sprint 6 - Rapports CRSE ===" -ForegroundColor Cyan

Write-Host "`n[1/5] Login Admin SAQS (saqs.dev)..." -ForegroundColor Yellow
$token = Get-Token -Login "saqs.dev" -Password "DevSir123!"
$me = Invoke-SirApi -Method GET -Path "/auth/me" -Token $token
Write-Host "  OK - $($me.data.prenom) $($me.data.nom) ($($me.data.role_label))" -ForegroundColor Green

$reportDate = (Get-Date).ToString("yyyy-MM-dd")

Write-Host "`n[2/5] POST /rapports/journalier (date=$reportDate, format pdf)..." -ForegroundColor Yellow
$enqueue = Invoke-SirApi -Method POST -Path "/rapports/journalier" -Token $token -Body @{
    date   = $reportDate
    format = "pdf"
}
if ($enqueue.status -ne "success") { throw "POST journalier echoue : $($enqueue.error)" }
$taskId = $enqueue.data.task_id
Write-Host "  OK - task_id=$taskId type=$($enqueue.data.type_rapport) statut=$($enqueue.data.statut)" -ForegroundColor Green

Write-Host "`n[3/5] Polling GET /rapports/$taskId/status..." -ForegroundColor Yellow
$ready = Wait-RapportReady -Token $token -TaskId $taskId
Write-Host "  OK - fichier=$($ready.file_name) expire=$($ready.expires_at)" -ForegroundColor Green

Write-Host "`n[4/5] GET /rapports/$taskId/download..." -ForegroundColor Yellow
$outDir = Join-Path $PSScriptRoot "e2e_output"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$outFile = Join-Path $outDir $ready.file_name
Save-RapportDownload -Token $token -TaskId $taskId -OutFile $outFile
$fileInfo = Get-Item $outFile
if ($fileInfo.Length -le 0) { throw "Fichier telecharge vide : $outFile" }
Write-Host "  OK - $($fileInfo.Length) octets -> $outFile" -ForegroundColor Green

Write-Host "`n[5/5] Controle statut final..." -ForegroundColor Yellow
$final = Invoke-SirApi -Method GET -Path "/rapports/$taskId/status" -Token $token
if ($final.data.statut -ne "success") { throw "Statut final inattendu : $($final.data.statut)" }
Write-Host "  OK - statut=success" -ForegroundColor Green

Write-Host "`n=== E2E Sprint 6 rapports : SUCCES ===" -ForegroundColor Cyan
Write-Host "  task_id  : $taskId"
Write-Host "  fichier  : $outFile"
Write-Host "  taille   : $($fileInfo.Length) octets"
