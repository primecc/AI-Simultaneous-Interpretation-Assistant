param(
    [Parameter(Mandatory = $true)]
    [string]$CertificatePath,

    [Parameter(Mandatory = $true)]
    [string]$CertificatePassword,

    [string]$TimestampUrl = "http://timestamp.digicert.com",

    [switch]$SignAllBinaries
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$releaseDir = Join-Path $projectRoot "dist\AI-Simultaneous-Interpreter"
$mainExe = Join-Path $releaseDir "AI-Simultaneous-Interpreter.exe"

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if ($null -eq $signtool) {
    throw "未找到 signtool.exe。请安装 Windows SDK，并把 signtool.exe 加入 PATH。"
}

if (-not (Test-Path -LiteralPath $CertificatePath)) {
    throw "证书文件不存在：$CertificatePath"
}

if (-not (Test-Path -LiteralPath $mainExe)) {
    throw "未找到待签名 EXE：$mainExe。请先运行 PyInstaller 打包。"
}

$targets = @($mainExe)
if ($SignAllBinaries) {
    $targets = Get-ChildItem -LiteralPath $releaseDir -Recurse -Include *.exe,*.dll,*.pyd |
        Select-Object -ExpandProperty FullName
}

foreach ($target in $targets) {
    & $signtool.Source sign `
        /f $CertificatePath `
        /p $CertificatePassword `
        /fd SHA256 `
        /tr $TimestampUrl `
        /td SHA256 `
        /v `
        $target
}

Write-Host "签名完成：$($targets.Count) 个文件"
