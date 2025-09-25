<#
.SYNOPSIS
Avvia i container Docker Compose del progetto AI Influencer.

.DESCRIPTION
Avvia i servizi definiti nel file docker-compose predefinito oppure in un file personalizzato.
#>

param(
    [string]$ComposeFile,
    [switch]$Recreate
)

$ErrorActionPreference = 'Stop'

if (-not $ComposeFile) {
    $repoRoot = Split-Path -Path $PSScriptRoot -Parent
    $ComposeFile = Join-Path $repoRoot 'docker\docker-compose.yaml'
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'Docker non è installato o non è presente nel PATH. Installa Docker Desktop e riprova.'
}

if (-not (Test-Path -Path $ComposeFile)) {
    Write-Error "File docker-compose non trovato: $ComposeFile"
}

$composeArgs = @('compose', '-f', $ComposeFile, 'up', '-d')
if ($Recreate) {
    $composeArgs += '--force-recreate'
}

Write-Host 'Avvio dei servizi Docker Compose...' -ForegroundColor Cyan

try {
    docker @composeArgs | Out-Host
    Write-Host 'Servizi avviati. Controlla "docker compose ps" per lo stato dei container.' -ForegroundColor Green
}
catch {
    Write-Error "Errore durante l'avvio dei container: $($_.Exception.Message)"
}
