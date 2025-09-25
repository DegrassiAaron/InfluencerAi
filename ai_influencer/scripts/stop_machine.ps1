<#
.SYNOPSIS
Arresta i container Docker Compose del progetto AI Influencer.

.DESCRIPTION
Ferma i servizi Docker Compose e, opzionalmente, rimuove i volumi associati.
#>

param(
    [string]$ComposeFile,
    [switch]$RemoveVolumes
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

$composeArgs = @('compose', '-f', $ComposeFile, 'down', '--remove-orphans')
if ($RemoveVolumes) {
    $composeArgs += '--volumes'
}

Write-Host 'Arresto dei servizi Docker Compose...' -ForegroundColor Yellow

try {
    docker @composeArgs | Out-Host
    Write-Host 'Container arrestati. Usa "docker volume ls" per verificare i volumi residui.' -ForegroundColor Green
}
catch {
    Write-Error "Errore durante l'arresto dei container: $($_.Exception.Message)"
}
