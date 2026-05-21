[CmdletBinding()]
param(
    [switch]$SkipVaultBootstrap,
    [switch]$SkipDatabaseSnapshot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title
    )

    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & docker compose @Args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Args -join ' ') failed."
    }
}

function Wait-Http {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [int]$TimeoutSeconds = 300,
        [int]$PollSeconds = 5,
        [string]$Label = $Uri
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ($true) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 10
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Host "$Label is ready."
                return
            }
        } catch {
            if ((Get-Date) -ge $deadline) {
                throw "$Label did not become ready within $TimeoutSeconds seconds."
            }
            Start-Sleep -Seconds $PollSeconds
        }
    }
}

function Invoke-Psql {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Sql
    )

    & docker compose exec -T db psql -U copilot -d maintainers -v ON_ERROR_STOP=1 -c $Sql
    if ($LASTEXITCODE -ne 0) {
        throw "psql query failed."
    }
}

function Show-DatabaseSnapshot {
    Write-Section "Postgres tables"
    Invoke-Psql @"
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
"@

    Write-Section "Postgres foreign keys"
    Invoke-Psql @"
SELECT
  tc.table_name AS table_name,
  kcu.column_name AS column_name,
  ccu.table_name AS referenced_table,
  ccu.column_name AS referenced_column,
  tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position;
"@
}

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.env'))) {
    throw "Missing .env. Copy .env.example to .env and fill in the real values before running this script."
}

Assert-Command -Name 'docker'

Write-Section "Starting infrastructure"
Invoke-Compose -Args @('up', '-d', 'db', 'redis', 'minio', 'vault', 'jaeger', 'pgadmin')

Write-Section "Waiting for Vault"
Wait-Http -Uri 'http://localhost:8200/v1/sys/health?standbyok=true&sealedcode=503&uninitcode=503' -Label 'Vault'

if (-not $SkipVaultBootstrap.IsPresent) {
    Write-Section "Bootstrapping Vault"
    & powershell.exe -ExecutionPolicy Bypass -File (Join-Path $repoRoot 'scripts\bootstrap_vault.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw "Vault bootstrap failed."
    }
}

Write-Section "Running database migrations"
Invoke-Compose -Args @('run', '--rm', 'migrate')

Write-Section "Starting application services"
Invoke-Compose -Args @('up', '-d', '--build', 'model-server', 'api', 'streamlit', 'widget', 'host')

Write-Section "Waiting for services"
Wait-Http -Uri 'http://localhost:8011/health' -Label 'Model server'
Wait-Http -Uri 'http://localhost:8010/health' -Label 'API'
Wait-Http -Uri 'http://localhost:8501/healthz' -Label 'Streamlit'
Wait-Http -Uri 'http://localhost:8080/widget.js' -Label 'Widget bundle'
Wait-Http -Uri 'http://localhost:3000/' -Label 'Host demo'

if (-not $SkipDatabaseSnapshot.IsPresent) {
    Show-DatabaseSnapshot
}

Write-Section "Ready"
Write-Host "API:        http://localhost:8010"
Write-Host "Docs:       http://localhost:8010/docs"
Write-Host "Model:      http://localhost:8011"
Write-Host "Streamlit:  http://localhost:8501"
Write-Host "Widget:     http://localhost:8080"
Write-Host "Host demo:  http://localhost:3000"
Write-Host "pgAdmin:    http://localhost:5050"
Write-Host "Vault:      http://localhost:8200"
Write-Host "Jaeger:     http://localhost:16686"
Write-Host ""
Write-Host "Postgres connection details for pgAdmin:"
Write-Host "  Host: db"
Write-Host "  Port: 5432"
Write-Host "  Database: maintainers"
Write-Host "  User: copilot"
Write-Host "  Password: from .env -> DB_PASSWORD"
Write-Host ""
Write-Host "If you want an interactive shell in Postgres, run:"
Write-Host "  docker compose exec db psql -U copilot -d maintainers"
