# Bascule le poste sur la base Docker locale (chez vous)
$env:SIR_PROFILE = "docker"
Write-Host "SIR_PROFILE=docker — base SQL Server container (db:1433/SIR)"
Write-Host "Migration : make upgrade  (ou docker compose exec api alembic upgrade head)"
