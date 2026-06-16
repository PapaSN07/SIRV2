# E2E Sprint 3 - BCC saisie -> cloture -> Superviseur validation
# Usage: powershell -ExecutionPolicy Bypass -File scripts/e2e_sprint3_distribution.ps1

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

Write-Host "=== E2E Sprint 3 - Interruptions Distribution ===" -ForegroundColor Cyan

Write-Host "`n[1/7] Login BCC (bcc.dev)..." -ForegroundColor Yellow
$bccToken = Get-Token -Login "bcc.dev" -Password "DevSir123!"
$me = Invoke-SirApi -Method GET -Path "/auth/me" -Token $bccToken
Write-Host "  OK - $($me.data.prenom) $($me.data.nom) ($($me.data.role_label))" -ForegroundColor Green

Write-Host "`n[2/7] Chargement feeders + referentiels..." -ForegroundColor Yellow
$feeders = Invoke-SirApi -Method GET -Path "/reseau/feeders?page=1&page_size=5" -Token $bccToken
$feederId = $feeders.data.items[0].id
$causes = Invoke-SirApi -Method GET -Path "/referentiel/causes?page=1&page_size=5&type_reseau=distribution" -Token $bccToken
$natures = Invoke-SirApi -Method GET -Path "/referentiel/natures?page=1&page_size=5" -Token $bccToken
$sieges = Invoke-SirApi -Method GET -Path "/referentiel/sieges?page=1&page_size=5&type_reseau=distribution" -Token $bccToken
$sigs = Invoke-SirApi -Method GET -Path "/referentiel/signalisations?page=1&page_size=5&type_reseau=distribution" -Token $bccToken
$postes = Invoke-SirApi -Method GET -Path "/reseau/postes?page=1&page_size=5&feeder_id=$feederId" -Token $bccToken
$posteId = $postes.data.items[0].id
Write-Host "  feeder_id=$feederId poste_id=$posteId" -ForegroundColor Green

Write-Host "`n[3/7] Creation interruption..." -ForegroundColor Yellow
$apparition = (Get-Date).AddHours(-2).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss")
$create = Invoke-SirApi -Method POST -Path "/interruptions/distribution" -Token $bccToken -Body @{
    date_apparition     = $apparition
    feeder_id           = $feederId
    cause_id            = $causes.data.items[0].id
    nature_id           = $natures.data.items[0].id
    siege_id            = $sieges.data.items[0].id
    signalisation_id    = $sigs.data.items[0].id
    puissance_coupee_mw = 2.5
    observations        = "E2E test $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}
$id = $create.data.id
Write-Host "  OK - interruption #$($create.data.numero_interruption) id=$id statut=$($create.data.statut)" -ForegroundColor Green

Write-Host "`n[4/7] Association poste impacte..." -ForegroundColor Yellow
Invoke-SirApi -Method POST -Path "/interruptions/distribution/$id/postes" -Token $bccToken -Body @{
    poste_id               = $posteId
    nombre_clients_touches = 85
} | Out-Null
Write-Host "  OK - poste $posteId associe" -ForegroundColor Green

Write-Host "`n[5/7] Cloture..." -ForegroundColor Yellow
$remise = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss")
$cloture = Invoke-SirApi -Method PATCH -Path "/interruptions/distribution/$id/cloturer" -Token $bccToken -Body @{
    date_remise = $remise
}
Write-Host "  OK - statut=$($cloture.data.statut) duree=$($cloture.data.duree_minutes) min" -ForegroundColor Green

Write-Host "`n[6/7] Login Superviseur (superviseur.dev)..." -ForegroundColor Yellow
$supToken = Get-Token -Login "superviseur.dev" -Password "DevSir123!"

Write-Host "`n[7/7] Validation..." -ForegroundColor Yellow
$valide = Invoke-SirApi -Method PATCH -Path "/interruptions/distribution/$id/valider" -Token $supToken -Body @{}
Write-Host "  OK - statut=$($valide.data.statut)" -ForegroundColor Green

$detail = Invoke-SirApi -Method GET -Path "/interruptions/distribution/$id" -Token $supToken
Write-Host "`n=== RESULTAT FINAL ===" -ForegroundColor Cyan
Write-Host "  ID          : $($detail.data.id)"
Write-Host "  Numero      : $($detail.data.numero_interruption)"
Write-Host "  Statut      : $($detail.data.statut)"
Write-Host "  Postes      : $($detail.data.postes_impactes.Count)"
Write-Host "  END (MWh)   : $($detail.data.end_mwh)"
Write-Host "  Valide par  : $($detail.data.validated_by.prenom) $($detail.data.validated_by.nom)"
Write-Host "`nE2E API : SUCCES" -ForegroundColor Green
$uiUrl = "http://localhost:4200/interruptions/distribution/$id"
Write-Host "URL frontend : $uiUrl" -ForegroundColor Cyan
