[CmdletBinding()]
param(
    [string]$InnoSetupPath
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $InnoSetupPath) {
    $candidates = @(
        (Join-Path $root 'tools\InnoSetup\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe',
        'C:\Program Files (x86)\Inno Setup 5\ISCC.exe'
    )
    $InnoSetupPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $InnoSetupPath) {
    throw 'Inno Setup compiler was not found. Run tools/bootstrap_inno.ps1 first.'
}
if (-not (Test-Path -LiteralPath $InnoSetupPath)) {
    throw "Inno Setup compiler does not exist: $InnoSetupPath"
}
$script = Join-Path $root 'installer\LiteMP4-Setup.iss'
$output = Join-Path $root 'dist\LiteMP4-Setup-v1.7.exe'
$process = Start-Process -FilePath $InnoSetupPath -ArgumentList @('/Q', $script) -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Inno Setup failed with exit code $($process.ExitCode)"
}
if (-not (Test-Path -LiteralPath $output)) {
    throw "Installer was not created: $output"
}
Get-Item -LiteralPath $output | Select-Object FullName, Length, LastWriteTime
