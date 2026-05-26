[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUser,

    [Parameter(Mandatory = $true)]
    [ValidateSet("add", "remove", "list", "check")]
    [string]$Action,

    [string]$RemoteHost = "192.168.173.22",

    [int]$RemotePort = 22,

    [string]$RemotePath = "D:\ProgramFiles\checkCivitai",

    [string]$IdentityFile,

    [string]$ModelUrl,

    [string]$Alias,

    [string]$ModelKey
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
        [string]$StepName
    )

    Write-Host "==> $StepName" -ForegroundColor Cyan
    Write-Host ((@($FilePath) + $Arguments) -join " ")

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
}

function Convert-ToEncodedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandText
    )

    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($CommandText))
}

$defaultIdentityFile = Join-Path $env:USERPROFILE ".ssh\checkcivitai_ed25519"
if (-not $IdentityFile -and (Test-Path -LiteralPath $defaultIdentityFile)) {
    $IdentityFile = $defaultIdentityFile
}

if ($Action -eq "add" -and -not $ModelUrl) {
    throw "-ModelUrl is required when Action is add."
}

if ($Action -eq "remove" -and -not $ModelKey) {
    throw "-ModelKey is required when Action is remove."
}

$composeProjectName = "checkcivitai"
$serviceName = "civitai-checker"
$remoteTarget = "$RemoteUser@$RemoteHost"
$sshCommand = (Get-Command ssh -ErrorAction Stop).Source
$commonSshArgs = @("-p", $RemotePort.ToString())

if ($IdentityFile) {
    $commonSshArgs += @("-i", $IdentityFile)
}

$escapedRemotePath = $RemotePath.Replace("'", "''")
$remoteCliCommand = switch ($Action) {
    "add" {
        $escapedModelUrl = $ModelUrl.Replace("'", "''")
        if ($Alias) {
            $escapedAlias = $Alias.Replace("'", "''")
            "docker compose -p $composeProjectName exec -T $serviceName python civitai_checker.py --add '$escapedModelUrl' --alias '$escapedAlias'"
        }
        else {
            "docker compose -p $composeProjectName exec -T $serviceName python civitai_checker.py --add '$escapedModelUrl'"
        }
    }
    "remove" {
        $escapedModelKey = $ModelKey.Replace("'", "''")
        "docker compose -p $composeProjectName exec -T $serviceName python civitai_checker.py --remove '$escapedModelKey'"
    }
    "list" {
        "docker compose -p $composeProjectName exec -T $serviceName python civitai_checker.py --list"
    }
    "check" {
        "docker compose -p $composeProjectName exec -T $serviceName python civitai_checker.py --check"
    }
}

$remoteScript = @"
`$ErrorActionPreference = 'Stop'
Set-Location '$escapedRemotePath'
$remoteCliCommand
if (`$LASTEXITCODE -ne 0) {
    throw 'Remote management command failed.'
}
"@

$remoteCommand = "powershell -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $(Convert-ToEncodedCommand -CommandText $remoteScript)"
Invoke-NativeCommand -FilePath $sshCommand -Arguments ($commonSshArgs + @($remoteTarget, $remoteCommand)) -StepName "Running remote $Action command"