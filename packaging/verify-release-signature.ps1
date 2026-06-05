param(
    [switch]$AllBinaries
)

$ErrorActionPreference = "Stop"

function Add-VerifyTarget {
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

$targets = [System.Collections.Generic.List[string]]::new()
Add-VerifyTarget -Targets $targets -Path $distExe
Get-ChildItem -LiteralPath $projectRoot -File -Filter "*.exe" |
    ForEach-Object { Add-VerifyTarget -Targets $targets -Path $_.FullName }

if ($AllBinaries) {
    foreach ($directory in @($distDir, $rootInternalDir)) {
        if (Test-Path -LiteralPath $directory) {
            Get-ChildItem -LiteralPath $directory -Recurse -File -Include *.exe, *.dll, *.pyd |
                ForEach-Object { Add-VerifyTarget -Targets $targets -Path $_.FullName }
        }
    }
}

if ($targets.Count -eq 0) {
    throw "No signature verification targets were found. Build the Windows release first."
}

$failures = @()
foreach ($target in $targets) {
    $signature = Get-AuthenticodeSignature -LiteralPath $target
    if ($signature.Status -ne "Valid") {
        $failures += "$target => $($signature.Status)"
    }
}

if ($failures.Count -gt 0) {
    $message = "Release signature verification failed. Smart App Control can block EXE files that do not have a trusted signature.`n" + ($failures -join "`n")
    throw $message
}

Write-Host "Release signature verification passed: $($targets.Count) files"
