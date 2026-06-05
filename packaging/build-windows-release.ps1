param(
    [string]$Python = $env:PYTHON,

    [string]$CertificatePath = $env:WINDOWS_SIGN_CERT_PATH,

    [string]$CertificatePassword = $env:WINDOWS_SIGN_CERT_PASSWORD,

    [string]$CertificateThumbprint = $env:WINDOWS_SIGN_CERT_THUMBPRINT,

    [string]$CertificateSubject = $env:WINDOWS_SIGN_CERT_SUBJECT,

    [string]$TimestampUrl = "http://timestamp.digicert.com",

    [switch]$SignAllBinaries,

    [switch]$SkipSignature
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$distDir = Join-Path $projectRoot "dist\AI-Simultaneous-Interpreter"
$rootInternalDir = Join-Path $projectRoot "_internal"
$releaseDir = Join-Path $projectRoot "release"
$releaseZip = Join-Path $releaseDir "AI-Simultaneous-Interpreter-windows.zip"
$rootExeName = -join @("AI", [char]0x540c, [char]0x58f0, [char]0x4f20, [char]0x8bd1, [char]0x52a9, [char]0x624b, ".exe")
$usageDocName = -join @(
    "Windows-EXE-",
    [char]0x4f7f,
    [char]0x7528,
    [char]0x8bf4,
    [char]0x660e,
    ".md"
)
$packedUsageDocName = -join @([char]0x4f7f, [char]0x7528, [char]0x8bf4, [char]0x660e, ".md")
$rootUsageDocName = -join @("EXE", [char]0x4f7f, [char]0x7528, [char]0x8bf4, [char]0x660e, ".md")

function Copy-DirectoryContents {
    param(
        [string]$Source,
        [string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    Get-ChildItem -LiteralPath $Source -Recurse -Directory | ForEach-Object {
        $relative = $_.FullName.Substring($Source.Length).TrimStart("\")
        New-Item -ItemType Directory -Force -Path (Join-Path $Destination $relative) | Out-Null
    }

    Get-ChildItem -LiteralPath $Source -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($Source.Length).TrimStart("\")
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        try {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force -ErrorAction Stop
        } catch {
            if ((Test-Path -LiteralPath $target) -and ((Get-Item -LiteralPath $target).Length -eq $_.Length)) {
                Write-Warning "Skipped locked unchanged file: $relative"
            } else {
                throw
            }
        }
    }
}

if (-not $Python) {
    $Python = "python"
}

Push-Location $projectRoot
try {
    & $Python -m PyInstaller "packaging\AI-Simultaneous-Interpreter.spec" --noconfirm --clean
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    Copy-Item -LiteralPath (Join-Path "packaging" $usageDocName) -Destination (Join-Path $distDir $packedUsageDocName) -Force
    Copy-Item -LiteralPath ".env.example" -Destination (Join-Path $distDir ".env.example") -Force

    Copy-DirectoryContents -Source (Join-Path $distDir "_internal") -Destination $rootInternalDir
    Copy-Item -LiteralPath (Join-Path $distDir "AI-Simultaneous-Interpreter.exe") -Destination (Join-Path $projectRoot $rootExeName) -Force
    Copy-Item -LiteralPath (Join-Path $distDir $packedUsageDocName) -Destination (Join-Path $projectRoot $rootUsageDocName) -Force

    if ($SkipSignature) {
        Write-Warning "Code signing was skipped. This package is only for local development and must not be used as an official release."
    } else {
        $signArgs = @{
            TimestampUrl = $TimestampUrl
        }
        if ($CertificatePath) { $signArgs.CertificatePath = $CertificatePath }
        if ($CertificatePassword) { $signArgs.CertificatePassword = $CertificatePassword }
        if ($CertificateThumbprint) { $signArgs.CertificateThumbprint = $CertificateThumbprint }
        if ($CertificateSubject) { $signArgs.CertificateSubject = $CertificateSubject }
        if ($SignAllBinaries) { $signArgs.SignAllBinaries = $true }

        & (Join-Path $PSScriptRoot "sign-release.ps1") @signArgs

        $verifyArgs = @{}
        if ($SignAllBinaries) { $verifyArgs.AllBinaries = $true }
        & (Join-Path $PSScriptRoot "verify-release-signature.ps1") @verifyArgs
    }

    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    if (Test-Path -LiteralPath $releaseZip) {
        Remove-Item -LiteralPath $releaseZip -Force
    }
    Compress-Archive -LiteralPath $distDir -DestinationPath $releaseZip -Force

    Write-Host "Windows release package generated: $releaseZip"
} finally {
    Pop-Location
}
