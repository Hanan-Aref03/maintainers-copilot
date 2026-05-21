param(
    [string]$VaultAddr,
    [string]$VaultToken,
    [string]$VaultNamespace,
    [string]$JwtSecret,
    [string]$GeminiApiKey,
    [string]$VoyageApiKey,
    [string]$DbPassword,
    [string]$MinioRootUser,
    [string]$MinioRootPassword,
    [string]$GithubToken,
    [string]$PolicyName = "copilot",
    [string]$MountPath = "kv",
    [switch]$CreateToken,
    [string]$TokenOutputPath,
    [int]$MaxWaitSeconds = 120,
    [int]$PollIntervalSeconds = 2
)

$ErrorActionPreference = 'Stop'

function Import-DotEnv {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()

        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) {
            continue
        }

        if ($trimmed -match '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim()

            if (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }

            if ([string]::IsNullOrWhiteSpace([System.Environment]::GetEnvironmentVariable($key))) {
                Set-Item -Path "Env:$key" -Value $value
            }
        }
    }
}

function Resolve-Value {
    param(
        [string]$Name,
        [string]$Value,
        [string]$Default = $null,
        [string[]]$Aliases = @()
    )

    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }

    foreach ($candidate in @($Name) + $Aliases) {
        $candidateValue = [System.Environment]::GetEnvironmentVariable($candidate)
        if (-not [string]::IsNullOrWhiteSpace($candidateValue)) {
            return $candidateValue
        }
    }

    return $Default
}

function Invoke-VaultApi {
    param(
        [ValidateSet('GET', 'POST', 'PUT', 'DELETE')]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $uri = "{0}{1}" -f $script:BaseUri, $Path
    $params = @{
        Uri         = $uri
        Method      = $Method
        Headers     = $script:Headers
        ErrorAction = 'Stop'
    }

    if ($null -ne $Body) {
        $params.ContentType = 'application/json'
        $params.Body = $Body | ConvertTo-Json -Depth 20 -Compress
    }

    Invoke-RestMethod @params
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Import-DotEnv -Path (Join-Path $repoRoot '.env')

$VaultAddr = Resolve-Value -Name 'VAULT_ADDR' -Value $VaultAddr -Default 'http://localhost:8200'
$VaultToken = Resolve-Value -Name 'VAULT_TOKEN' -Value $VaultToken -Default 'devroot'
$JwtSecret = Resolve-Value -Name 'JWT_SECRET' -Value $JwtSecret
$GeminiApiKey = Resolve-Value -Name 'GEMINI_API_KEY' -Value $GeminiApiKey -Aliases @('OPENAI_API_KEY')
$VoyageApiKey = Resolve-Value -Name 'VOYAGE_API_KEY' -Value $VoyageApiKey
$DbPassword = Resolve-Value -Name 'DB_PASSWORD' -Value $DbPassword
$MinioRootUser = Resolve-Value -Name 'MINIO_ROOT_USER' -Value $MinioRootUser
$MinioRootPassword = Resolve-Value -Name 'MINIO_ROOT_PASSWORD' -Value $MinioRootPassword
$GithubToken = Resolve-Value -Name 'GITHUB_TOKEN' -Value $GithubToken

$script:BaseUri = $VaultAddr.TrimEnd('/')
$script:Headers = @{
    'X-Vault-Token' = $VaultToken
}

if (-not [string]::IsNullOrWhiteSpace($VaultNamespace)) {
    $script:Headers['X-Vault-Namespace'] = $VaultNamespace
}

$healthUri = "{0}/v1/sys/health?standbyok=true&sealedcode=503&uninitcode=503" -f $script:BaseUri
Write-Host "Waiting for Vault at $VaultAddr..."

$deadline = (Get-Date).AddSeconds($MaxWaitSeconds)
while ($true) {
    try {
        Invoke-RestMethod -Uri $healthUri -Method Get -TimeoutSec 5 | Out-Null
        break
    } catch {
        if ((Get-Date) -ge $deadline) {
            throw "Vault did not become ready within $MaxWaitSeconds seconds."
        }

        Start-Sleep -Seconds $PollIntervalSeconds
    }
}

if ([string]::IsNullOrWhiteSpace($JwtSecret)) {
    throw "Set JWT_SECRET before running this script."
}

if (
    [string]::IsNullOrWhiteSpace($GeminiApiKey) -and
    [string]::IsNullOrWhiteSpace($VoyageApiKey)
) {
    throw "Set GEMINI_API_KEY or VOYAGE_API_KEY before running this script. OPENAI_API_KEY is still accepted as a legacy alias for GEMINI_API_KEY."
}

if ([string]::IsNullOrWhiteSpace($DbPassword)) {
    throw "Set DB_PASSWORD before running this script."
}

if ([string]::IsNullOrWhiteSpace($MinioRootUser)) {
    throw "Set MINIO_ROOT_USER before running this script."
}

if ([string]::IsNullOrWhiteSpace($MinioRootPassword)) {
    throw "Set MINIO_ROOT_PASSWORD before running this script."
}

if ([string]::IsNullOrWhiteSpace($GithubToken)) {
    throw "Set GITHUB_TOKEN before running this script."
}

$mountPath = $MountPath.Trim('/')
$mountName = "$mountPath/"
$mounts = Invoke-VaultApi -Method GET -Path '/v1/sys/mounts'
$mountProperty = $mounts.data.PSObject.Properties | Where-Object { $_.Name -eq $mountName } | Select-Object -First 1

if ($null -eq $mountProperty) {
    Invoke-VaultApi -Method POST -Path "/v1/sys/mounts/$mountPath" -Body @{
        type    = 'kv'
        options = @{ version = '2' }
    } | Out-Null
    Write-Host "Enabled KV v2 at $mountName"
} else {
    $current = $mountProperty.Value
    $currentVersion = $null

    if ($null -ne $current.options -and ($current.options.PSObject.Properties.Name -contains 'version')) {
        $currentVersion = [string]$current.options.version
    }

    if ($currentVersion -ne '2') {
        throw "Vault mount $mountName already exists but is not KV v2. Migrate it manually before continuing."
    }

    Write-Host "KV v2 already enabled at $mountName"
}

$secretData = @{
    jwt_secret       = $JwtSecret
    db_password      = $DbPassword
    minio_access_key = $MinioRootUser
    minio_secret_key = $MinioRootPassword
    github_token     = $GithubToken
}

if (-not [string]::IsNullOrWhiteSpace($GeminiApiKey)) {
    $secretData['gemini_api_key'] = $GeminiApiKey
}

if (-not [string]::IsNullOrWhiteSpace($VoyageApiKey)) {
    $secretData['voyage_api_key'] = $VoyageApiKey
}

Invoke-VaultApi -Method POST -Path "/v1/$mountPath/data/copilot" -Body @{
    data = $secretData
} | Out-Null

$policy = @"
path "$mountPath/data/copilot" {
  capabilities = ["read"]
}
"@

Invoke-VaultApi -Method POST -Path "/v1/sys/policies/acl/$PolicyName" -Body @{
    policy = $policy
} | Out-Null

if ($CreateToken.IsPresent -or ($env:CREATE_TOKEN -eq 'true')) {
    $tokenResponse = Invoke-VaultApi -Method POST -Path '/v1/auth/token/create' -Body @{
        policies = @($PolicyName)
    }

    $clientToken = $tokenResponse.auth.client_token

    if (-not [string]::IsNullOrWhiteSpace($TokenOutputPath)) {
        Set-Content -LiteralPath $TokenOutputPath -Value $clientToken -NoNewline
        Write-Host "Token written to $TokenOutputPath"
    } else {
        Write-Host "Created token:"
        Write-Output $clientToken
    }
}

Write-Host "Vault bootstrap complete."
