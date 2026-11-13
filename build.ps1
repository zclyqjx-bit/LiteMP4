$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$framework = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$compiler = Join-Path $framework 'csc.exe'
$gacRoot = Join-Path $env:WINDIR 'Microsoft.NET\assembly'

if (-not (Test-Path -LiteralPath $compiler)) {
    throw 'The .NET Framework C# compiler was not found. Use 64-bit Windows 10/11.'
}

function Find-WpfAssembly([string]$name) {
    foreach ($category in @('GAC_64', 'GAC_MSIL', 'GAC_32')) {
        $directory = Join-Path (Join-Path $gacRoot $category) $name
        if (Test-Path -LiteralPath $directory) {
            $assembly = Get-ChildItem -LiteralPath $directory -Filter "$name.dll" -Recurse |
                Where-Object { $_.Directory.Name -like 'v4.0_*' } |
                Sort-Object FullName -Descending |
                Select-Object -First 1
            if ($assembly) { return $assembly.FullName }
        }
    }
    throw "WPF assembly not found: $name"
}

$outputDirectory = Join-Path $root 'dist'
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$output = Join-Path $outputDirectory 'LiteMP4.exe'
$references = @(
    (Join-Path $framework 'System.dll'),
    (Join-Path $framework 'System.Core.dll'),
    (Join-Path $framework 'System.Xaml.dll'),
    (Find-WpfAssembly 'WindowsBase'),
    (Find-WpfAssembly 'PresentationCore'),
    (Find-WpfAssembly 'PresentationFramework')
)

$arguments = @(
    '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/langversion:5',
    '/codepage:65001', '/utf8output',
    "/out:$output",
    "/win32manifest:$(Join-Path $root 'app.manifest')",
    "/win32icon:$(Join-Path $root 'assets\LitePlayer.ico')"
)
foreach ($reference in $references) { $arguments += "/reference:$reference" }
$arguments += Get-ChildItem -LiteralPath (Join-Path $root 'src') -Filter '*.cs' |
    ForEach-Object { $_.FullName }

& $compiler @arguments
if ($LASTEXITCODE -ne 0) { throw "Compilation failed with exit code $LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $output)) { throw 'Compilation finished without an output file.' }

$runtimeSource = Join-Path $root 'runtime'
if (Test-Path -LiteralPath (Join-Path $runtimeSource 'libmpv-2.dll')) {
    $runtimeOutput = Join-Path $outputDirectory 'runtime'
    New-Item -ItemType Directory -Path $runtimeOutput -Force | Out-Null
    Copy-Item -Path (Join-Path $runtimeSource '*') -Destination $runtimeOutput -Recurse -Force
}

$file = Get-Item -LiteralPath $output
Write-Host ''
Write-Host "Build succeeded: $($file.FullName)" -ForegroundColor Green
Write-Host "File size: $([Math]::Round($file.Length / 1KB, 1)) KB"
