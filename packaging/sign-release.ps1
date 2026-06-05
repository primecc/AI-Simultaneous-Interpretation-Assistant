param(
    [string]$CertificatePath = $env:WINDOWS_SIGN_CERT_PATH,

    [string]$CertificatePassword = $env:WINDOWS_SIGN_CERT_PASSWORD,

    [string]$CertificateThumbprint = $env:WINDOWS_SIGN_CERT_THUMBPRINT,

    [string]$CertificateSubject = $env:WINDOWS_SIGN_CERT_SUBJECT,

    [string]$TimestampUrl = "http://timestamp.digicert.com",

    [switch]$SignAllBinaries
)

$ErrorActionPreference = "Stop"

function Add-SignTarget {
    param(
        [System.Collections.Generic.List[string]]$Targets,
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $Targets.Contains($resolved)) {
        $Targets.Add($resolved) | Out-Null
    }
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$distDir = Join-Path $projectRoot "dist\AI-Simultaneous-Interpreter"
$rootInternalDir = Join-Path $projectRoot "_internal"
$distExe = Join-Path $distDir "AI-Simultaneous-Interpreter.exe"

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if ($null -eq $signtool) {
    throw "signtool.exe was not found. Install Windows SDK and add signtool.exe to PATH."
}

$targets = [System.Collections.Generic.List[string]]::new()
Add-SignTarget -Targets $targets -Path $distExe
Get-ChildItem -LiteralPath $projectRoot -File -Filter "*.exe" |
    ForEach-Object { Add-SignTarget -Targets $targets -Path $_.FullName }

if ($SignAllBinaries) {
    foreach ($directory in @($distDir, $rootInternalDir)) {
        if (Test-Path -LiteralPath $directory) {
            Get-ChildItem -LiteralPath $directory -Recurse -File -Include *.exe, *.dll, *.pyd |
                ForEach-Object { Add-SignTarget -Targets $targets -Path $_.FullName }
        }
    }
}

if ($targets.Count -eq 0) {
    throw "No signing targets were found. Build the Windows release first."
}

$signArgs = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256", "/v")
if ($CertificatePath) {
    if (-not (Test-Path -LiteralPath $CertificatePath)) {
        throw "Certificate file does not exist: $CertificatePath"
    }

    $signArgs += @("/f", (Resolve-Path -LiteralPath $CertificatePath).Path)
    if ($CertificatePassword) {
        $signArgs += @("/p", $CertificatePassword)
    }
} elseif ($CertificateThumbprint) {
    $signArgs += @("/sha1", $CertificateThumbprint)
} elseif ($CertificateSubject) {
    $signArgs += @("/a", "/n", $CertificateSubject)
} else {
    throw "No trusted code signing certificate was provided. Pass -CertificatePath or -CertificateThumbprint, or set WINDOWS_SIGN_CERT_PATH/WINDOWS_SIGN_CERT_THUMBPRINT."
}

foreach ($target in $targets) {
    & $signtool.Source @signArgs $target
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed: $target"
    }

    $signature = Get-AuthenticodeSignature -LiteralPath $target
    if ($signature.Status -ne "Valid") {
        throw "Signature verification failed after signing: $target, status: $($signature.Status)"
    }
}

Write-Host "Signing completed and verified: $($targets.Count) files"
