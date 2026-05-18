param(
    [string]$VaultAddr = $env:VAULT_ADDR,
    [string]$VaultToken = $env:VAULT_TOKEN,
    [string]$VaultNamespace = $env:VAULT_NAMESPACE,
    [string]$JwtSecret = $env:JWT_SECRET,
    [string]$OpenAiApiKey = $env:OPENAI_API_KEY,
    [string]$DbPassword = $env:DB_PASSWORD,
    [string]$MinioRootUser = $env:MINIO_ROOT_USER,
    [string]$MinioRootPassword = $env:MINIO_ROOT_PASSWORD,
    [string]$GithubToken = $env:GITHUB_TOKEN,
    [string]$PolicyName = "copilot",
    [string]$MountPath = "kv",
    [switch]$CreateToken,
    [string]$TokenOutputPath,
    [int]$MaxWaitSeconds = 120,
    [int]$PollIntervalSeconds = 2
)

$ErrorActionPreference = 'Stop'

function Require-Value {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "Set $Name before running this script."
    }

    return $Value
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

$VaultAddr = Require-Value -Name 'VAULT_ADDR' -Value $VaultAddr
$VaultToken = Require-Value -Name 'VAULT_TOKEN' -Value $VaultToken
$JwtSecret = Require-Value -Name 'JWT_SECRET' -Value $JwtSecret
$OpenAiApiKey = Require-Value -Name 'OPENAI_API_KEY' -Value $OpenAiApiKey
$DbPassword = Require-Value -Name 'DB_PASSWORD' -Value $DbPassword
$MinioRootUser = Require-Value -Name 'MINIO_ROOT_USER' -Value $MinioRootUser
$MinioRootPassword = Require-Value -Name 'MINIO_ROOT_PASSWORD' -Value $MinioRootPassword
$GithubToken = Require-Value -Name 'GITHUB_TOKEN' -Value $GithubToken

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

Invoke-VaultApi -Method POST -Path "/v1/$mountPath/data/copilot" -Body @{
    data = @{
        jwt_secret        = $JwtSecret
        openai_api_key    = $OpenAiApiKey
        db_password       = $DbPassword
        minio_access_key  = $MinioRootUser
        minio_secret_key  = $MinioRootPassword
        github_token      = $GithubToken
    }
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
