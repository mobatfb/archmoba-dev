<#
FUTUREO VJOY - compilador/diagnostico WDK (sin instalar drivers).
Uso: powershell -NoProfile -File tools\compilar_driver.ps1

Requiere SDK y WDK del MISMO build + Visual Studio compatible.
NO firma, NO instala y NO desactiva Secure Boot.
#>
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "driver\FutJoy.vcxproj"

if ($PSVersionTable.PSEdition -eq "Core" -and -not $IsWindows) {
    throw "Este script requiere Windows."
}
if (-not (Test-Path $project)) {
    throw "Proyecto no localizado: $project"
}

Write-Host "FUTUREO VJOY - Compilacion x64 / $Configuration" -ForegroundColor Cyan
$x86 = [Environment]::GetFolderPath("ProgramFilesX86")
$vswhere = Join-Path $x86 "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    throw "Visual Studio no detectado. Instala Visual Studio con herramientas C++ y WDK."
}
$vsinstall = & $vswhere -latest -products * -property installationPath
if (-not $vsinstall) {
    throw "Visual Studio no encontrado por vswhere."
}
$msbuild = Join-Path $vsinstall "MSBuild\Current\Bin\MSBuild.exe"
if (-not (Test-Path $msbuild)) {
    throw "MSBuild no existe en: $msbuild"
}

$kitroot = Join-Path $x86 "Windows Kits\10\Include"
$versions = @()
if (Test-Path $kitroot) {
    $versions = @(Get-ChildItem $kitroot -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName "km\wdf.h")
    } | Select-Object -ExpandProperty Name)
}
if ($versions.Count -eq 0) {
    Write-Warning "No se detectan encabezados KMDF. Instala WDK y SDK compatibles."
} else {
    Write-Host "Versiones con encabezados KMDF: $($versions -join ', ')"
}

Write-Host "Compilando fuente (NO se ejecutara ni instalara el controlador)..."
& $msbuild $project /t:Build "/p:Configuration=$Configuration" "/p:Platform=x64" /nologo /v:minimal
if ($LASTEXITCODE -ne 0) {
    throw "MSBuild fallo ($LASTEXITCODE). Copia el error para corregir el codigo."
}
Write-Host "Compilacion completada. Verifica el .sys y el INF con InfVerif." -ForegroundColor Green
$sysfiles = @(Get-ChildItem $root -Recurse -Filter "FutJoy.sys" -File -ErrorAction SilentlyContinue)
if ($sysfiles.Count -eq 0) {
    Write-Warning "MSBuild termino, pero no se encontro FutJoy.sys en la carpeta."
} else {
    $sysfiles | ForEach-Object { Write-Host "SYS: $($_.FullName)" }
}
Write-Warning "Un .sys no es instalable en Windows normal sin catalogo y firma valida."
Write-Warning "No desactives Secure Boot en tu equipo principal."
