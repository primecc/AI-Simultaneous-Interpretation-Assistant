param(
    [string]$Subject = "AI Simultaneous Interpreter Local Test Publisher",

    [switch]$SignCurrentBuild,

    [switch]$SignAllBinaries,

    [switch]$RefreshReleaseZip
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$releaseZip = Join-Path $projectRoot "release\AI-Simultaneous-Interpreter-windows.zip"
$distDir = Join-Path $projectRoot "dist\AI-Simultaneous-Interpreter"
$certSubject = if ($Subject.StartsWith("CN=")) { $Subject } else { "CN=$Subject" }

$cert = Get-ChildItem -Path Cert:\CurrentUser\My -CodeSigningCert |
    Where-Object { $_.Subject -eq $certSubject -and $_.HasPrivateKey } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

if (-not $cert) {
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $certSubject `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyUsage DigitalSignature `
        -KeyAlgorithm RSA `
        -KeyLength 3072 `
        -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(3)
    Write-Host "Created local test code-signing certificate: $($cert.Thumbprint)"
} else {
    Write-Host "Reusing local test code-signing certificate: $($cert.Thumbprint)"
}

$publicCertPath = Join-Path $env:TEMP "ai-interpreter-local-test-publisher.cer"
Export-Certificate -Cert $cert -FilePath $publicCertPath -Force | Out-Null
Import-Certificate -FilePath $publicCertPath -CertStoreLocation Cert:\CurrentUser\TrustedPublisher | Out-Null
Import-Certificate -FilePath $publicCertPath -CertStoreLocation Cert:\CurrentUser\Root | Out-Null

Write-Host "Trusted local test publisher for current Windows user: $certSubject"

if ($SignCurrentBuild) {
    $signArgs = @{
        CertificateThumbprint = $cert.Thumbprint
    }
    if ($SignAllBinaries) {
        $signArgs.SignAllBinaries = $true
    }

    & (Join-Path $PSScriptRoot "sign-release.ps1") @signArgs

    if ($RefreshReleaseZip) {
        if (-not (Test-Path -LiteralPath $distDir)) {
            throw "Dist directory does not exist: $distDir"
        }

        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $releaseZip) | Out-Null
        if (Test-Path -LiteralPath $releaseZip) {
            Remove-Item -LiteralPath $releaseZip -Force
        }
        Compress-Archive -LiteralPath $distDir -DestinationPath $releaseZip -Force
        Write-Host "Release zip refreshed with the signed dist EXE: $releaseZip"
    }
}
