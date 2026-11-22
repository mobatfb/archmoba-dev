<#
FUTUREO VJOY - diagnostico de IDs PnP y nombres OEM en Windows.
No crea dispositivos, no instala drivers, no modifica el Registro.
Comando: powershell -NoProfile -File tools\diagnosticar_windows.ps1
#>
$ErrorActionPreference = "Stop"
if (-not (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue)) { throw "Solo Windows con PowerShell/PnP" }
$devices = @(Get-PnpDevice -PresentOnly -ErrorAction Stop)
$out = @()
for ($i=1; $i -le 8; $i++) {
    $rootId = "ROOT\FUTJOY{0:D2}" -f $i
    $pid = "PID_{0:X4}" -f (0x2100 + $i)
    $pattern = "VID_F7A0&$pid"
    $root = @($devices | Where-Object { $_.InstanceId -like "$rootId*" })
    $hid = @($devices | Where-Object { $_.InstanceId.ToUpperInvariant().Contains($pattern) })
    $oemPath = "HKLM:\SYSTEM\CurrentControlSet\Control\MediaProperties\PrivateProperties\Joystick\OEM\$pattern"
    $oemName = $null
    if (Test-Path $oemPath) { $oemName = (Get-ItemProperty $oemPath -ErrorAction SilentlyContinue).OEMName }
    $out += [PSCustomObject]@{
        Puesto = "P$i"
        Identidad = "FUTUREO VJOY$i"
        PnPRoot = if ($root) { $root[0].FriendlyName } else { "NO DETECTADO" }
        EstadoRoot = if ($root) { $root[0].Status } else { "Ausente" }
        HIDDetectado = ($hid.Count -gt 0)
        NombreHID = if ($hid) { $hid[0].FriendlyName } else { "-" }
        AliasOEM = if ($oemName) { $oemName } else { "-" }
        ProductID = $pid
    }
}
$out | Format-Table -AutoSize
Write-Host ""
Write-Host "Los nombres PnP y OEM son distintos de la cadena HID Product String." -ForegroundColor Yellow
Write-Host "Comprueba los nombres del juego por separado: un alias no garantiza que cambie su lista." -ForegroundColor Yellow
Write-Host "Esta herramienta es de solo lectura y no toca vJoy instalado."
