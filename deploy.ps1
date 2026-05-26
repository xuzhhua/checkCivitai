[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUser,

    [string]$RemoteHost = "192.168.173.22",

    [int]$RemotePort = 22,

    [string]$RemotePath = "D:\ProgramFiles\checkCivitai",

    [string]$ProxyUrl = "127.0.0.1:10808",

    [string]$NoProxy = "localhost,127.0.0.1,::1,192.168.173.22",

    [string]$IdentityFile,

    [switch]$UploadConfig,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$StepName,

        [switch]$DryRunMode
    )

    Write-Host "==> $StepName" -ForegroundColor Cyan
    Write-Host ((@($FilePath) + $Arguments) -join " ")

    if ($DryRunMode) {
        return
    }

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
}

function Convert-ToScpPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return ($Path -replace "\\", "/")
}

function Convert-ToEncodedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandText
    )

    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($CommandText))
}

function Normalize-ProxyUrl {
    param(
        [string]$Value
    )

    if (-not $Value) {
        return $null
    }

    if ($Value -match '^[a-zA-Z][a-zA-Z0-9+.-]*://') {
        return $Value
    }

    return "http://$Value"
}

function Set-ProcessEnvironmentVariable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [string]$Value
    )

    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}

function Set-DeploymentProxyEnvironment {
    param(
        [string]$Proxy,

        [string]$NoProxyValue
    )

    if (-not $Proxy) {
        return $null
    }

    $backup = @{}
    $proxyNames = @('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy')
    $noProxyNames = @('NO_PROXY', 'no_proxy')

    Write-Host "==> Applying local build proxy" -ForegroundColor Cyan
    Write-Host "HTTP(S)_PROXY=$Proxy"
    if ($NoProxyValue) {
        Write-Host "NO_PROXY=$NoProxyValue"
    }

    foreach ($name in ($proxyNames + $noProxyNames)) {
        $backup[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }

    foreach ($name in $proxyNames) {
        Set-ProcessEnvironmentVariable -Name $name -Value $Proxy
    }

    foreach ($name in $noProxyNames) {
        Set-ProcessEnvironmentVariable -Name $name -Value $NoProxyValue
    }

    return $backup
}

function Restore-EnvironmentVariables {
    param(
        $Backup
    )

    if (-not $Backup) {
        return
    }

    foreach ($name in $Backup.Keys) {
        Set-ProcessEnvironmentVariable -Name $name -Value $Backup[$name]
    }
}

$projectRoot = $PSScriptRoot
$localConfigPath = Join-Path $projectRoot "config.json"
$defaultIdentityFile = Join-Path $env:USERPROFILE ".ssh\checkcivitai_ed25519"
$ProxyUrl = Normalize-ProxyUrl -Value $ProxyUrl
$proxyEnvironmentBackup = $null

if (-not $IdentityFile -and (Test-Path -LiteralPath $defaultIdentityFile)) {
    $IdentityFile = $defaultIdentityFile
}

if ($UploadConfig -and -not (Test-Path -LiteralPath $localConfigPath)) {
    throw "Local config.json was not found. Remove -UploadConfig or create config.json first."
}

$sshCommand = (Get-Command ssh -ErrorAction Stop).Source
$scpCommand = (Get-Command scp -ErrorAction Stop).Source
$dockerCommand = (Get-Command docker -ErrorAction Stop).Source

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("checkcivitai-deploy-" + [Guid]::NewGuid().ToString("N"))
$stagingDir = Join-Path $tempRoot "staging"
$archivePath = Join-Path $tempRoot "checkcivitai-deploy.zip"
$imageArchivePath = Join-Path $tempRoot "checkcivitai-image.tar"

$excludedTopLevelNames = @(".git", ".venv", "venv", ".pytest_cache", "config.json", "model_history.json", "data")
$excludedDirectoryNames = @(".git", "__pycache__", ".venv", "venv", ".pytest_cache")
$remoteTarget = "$RemoteUser@$RemoteHost"
$remoteArchivePath = Join-Path $RemotePath "checkcivitai-deploy.zip"
$remoteImageArchivePath = Join-Path $RemotePath "checkcivitai-image.tar"
$remoteExtractPath = Join-Path $RemotePath ".deploy-extract"
$composeProjectName = "checkcivitai"
$localImageName = "$composeProjectName-civitai-checker"

New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

try {
    $proxyEnvironmentBackup = Set-DeploymentProxyEnvironment -Proxy $ProxyUrl -NoProxyValue $NoProxy

    Push-Location $projectRoot
    try {
        Invoke-NativeCommand -FilePath $dockerCommand -Arguments @("compose", "-p", $composeProjectName, "build") -StepName "Building local deployment image" -DryRunMode:$DryRun
        Invoke-NativeCommand -FilePath $dockerCommand -Arguments @("save", "-o", $imageArchivePath, $localImageName) -StepName "Exporting deployment image archive" -DryRunMode:$DryRun
    }
    finally {
        Pop-Location
    }

    Write-Host "==> Preparing deployment archive" -ForegroundColor Cyan

    Get-ChildItem -LiteralPath $projectRoot -Force |
        Where-Object { $excludedTopLevelNames -notcontains $_.Name } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $stagingDir -Recurse -Force
        }

    Get-ChildItem -LiteralPath $stagingDir -Recurse -Force -Directory |
        Where-Object { $excludedDirectoryNames -contains $_.Name } |
        Sort-Object FullName -Descending |
        Remove-Item -Recurse -Force

    Get-ChildItem -LiteralPath $stagingDir -Recurse -Force -File |
        Where-Object {
            $_.Extension -in @(".pyc", ".pyo") -or
            $_.Name -like "*.log"
        } |
        Remove-Item -Force

    if ($UploadConfig) {
        $stagingDataDir = Join-Path $stagingDir "data"
        New-Item -ItemType Directory -Path $stagingDataDir -Force | Out-Null
        Copy-Item -LiteralPath $localConfigPath -Destination (Join-Path $stagingDataDir "config.json") -Force
    }

    $archiveEntries = Get-ChildItem -LiteralPath $stagingDir -Force | Select-Object -ExpandProperty FullName
    if (-not $archiveEntries) {
        throw "No files were collected for deployment."
    }

    Compress-Archive -Path $archiveEntries -DestinationPath $archivePath -Force

    $commonSshArgs = @("-p", $RemotePort.ToString())
    $commonScpArgs = @("-P", $RemotePort.ToString())

    if ($IdentityFile) {
        $commonSshArgs += @("-i", $IdentityFile)
        $commonScpArgs += @("-i", $IdentityFile)
    }

    $escapedRemotePath = $RemotePath.Replace("'", "''")
    $escapedArchivePath = $remoteArchivePath.Replace("'", "''")
    $escapedImageArchivePath = $remoteImageArchivePath.Replace("'", "''")
    $escapedExtractPath = $remoteExtractPath.Replace("'", "''")

    $prepareRemoteScript = @"
`$ErrorActionPreference = 'Stop'
`$ProgressPreference = 'SilentlyContinue'
if (-not (Test-Path -LiteralPath '$escapedRemotePath')) {
    New-Item -ItemType Directory -Path '$escapedRemotePath' -Force | Out-Null
}
if (-not (Test-Path -LiteralPath (Join-Path '$escapedRemotePath' 'data'))) {
    New-Item -ItemType Directory -Path (Join-Path '$escapedRemotePath' 'data') -Force | Out-Null
}
"@

    $prepareRemoteCommand = "powershell -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $(Convert-ToEncodedCommand -CommandText $prepareRemoteScript)"
    Invoke-NativeCommand -FilePath $sshCommand -Arguments ($commonSshArgs + @($remoteTarget, $prepareRemoteCommand)) -StepName "Creating remote deployment directory" -DryRunMode:$DryRun

    $scpDestination = "${remoteTarget}:$(Convert-ToScpPath -Path $remoteArchivePath)"
    Invoke-NativeCommand -FilePath $scpCommand -Arguments ($commonScpArgs + @($archivePath, $scpDestination)) -StepName "Uploading deployment archive" -DryRunMode:$DryRun

    $imageScpDestination = "${remoteTarget}:$(Convert-ToScpPath -Path $remoteImageArchivePath)"
    Invoke-NativeCommand -FilePath $scpCommand -Arguments ($commonScpArgs + @($imageArchivePath, $imageScpDestination)) -StepName "Uploading image archive" -DryRunMode:$DryRun

    $deployRemoteScript = @"
`$ErrorActionPreference = 'Stop'
`$ProgressPreference = 'SilentlyContinue'
`$remotePath = '$escapedRemotePath'
`$archivePath = '$escapedArchivePath'
`$imageArchivePath = '$escapedImageArchivePath'
`$extractPath = '$escapedExtractPath'
`$dataPath = Join-Path `$remotePath 'data'
`$configPath = Join-Path `$dataPath 'config.json'

if (Test-Path -LiteralPath `$extractPath) {
    Remove-Item -LiteralPath `$extractPath -Recurse -Force
}

New-Item -ItemType Directory -Path `$extractPath -Force | Out-Null
Expand-Archive -LiteralPath `$archivePath -DestinationPath `$extractPath -Force

Get-ChildItem -LiteralPath `$extractPath -Force | ForEach-Object {
    Copy-Item -LiteralPath `$_.FullName -Destination `$remotePath -Recurse -Force
}

Remove-Item -LiteralPath `$extractPath -Recurse -Force
Remove-Item -LiteralPath `$archivePath -Force

if (-not (Test-Path -LiteralPath `$dataPath)) {
    New-Item -ItemType Directory -Path `$dataPath -Force | Out-Null
}

if (-not (Test-Path -LiteralPath `$configPath)) {
    throw 'Remote data/config.json was not found. Create it on the server first or rerun with -UploadConfig.'
}

docker load -i `$imageArchivePath
if (`$LASTEXITCODE -ne 0) {
    throw "docker load failed with exit code `$LASTEXITCODE"
}

Remove-Item -LiteralPath `$imageArchivePath -Force

Set-Location `$remotePath
docker compose -p $composeProjectName up -d --no-build
if (`$LASTEXITCODE -ne 0) {
    throw "docker compose up failed with exit code `$LASTEXITCODE"
}

docker compose -p $composeProjectName ps
if (`$LASTEXITCODE -ne 0) {
    throw "docker compose ps failed with exit code `$LASTEXITCODE"
}
"@

    $deployRemoteCommand = "powershell -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $(Convert-ToEncodedCommand -CommandText $deployRemoteScript)"
    Invoke-NativeCommand -FilePath $sshCommand -Arguments ($commonSshArgs + @($remoteTarget, $deployRemoteCommand)) -StepName "Deploying and restarting remote container" -DryRunMode:$DryRun

    if ($DryRun) {
        Write-Host "Dry run completed. No remote changes were made." -ForegroundColor Yellow
    }
    else {
        Write-Host "Remote deployment completed." -ForegroundColor Green
    }
}
finally {
    Restore-EnvironmentVariables -Backup $proxyEnvironmentBackup

    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}