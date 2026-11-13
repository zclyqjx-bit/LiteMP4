$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$cache = Join-Path $root '.cache'
$destination = Join-Path $root 'tools\InnoSetup'
$compiler = Join-Path $destination 'ISCC.exe'
New-Item -ItemType Directory -Path $cache -Force | Out-Null
$archive = Join-Path $cache 'inno-setup.exe'
$url = 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe'
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest -Uri $url -OutFile $archive
}
$bytes = [System.IO.File]::ReadAllBytes($archive)
if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
    throw 'Downloaded file is not a valid Windows installer.'
}
if (-not (Test-Path -LiteralPath $compiler)) {
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Start-Process -FilePath $archive -ArgumentList @('/VERYSILENT', '/NORESTART', "/DIR=$destination") -Wait
}
& (Join-Path $root 'tools\build_installer.ps1') -InnoSetupPath $compiler
