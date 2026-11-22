# FUTUREO VJOY - limpieza de dispositivos VHF unicamente.
# Para preview NO escribe ni altera el equipo. No ejecuta bcdedit/sc/force.
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("VistaPrevia","Eliminar")]
    [string]$Modo
)
$ErrorActionPreference = "Stop"
$thumb = 'D09A97E4E02004E08CB6998E1604F7383E268469'
$subject = 'CN=FUTUREO VJOY LAB TEST ONLY'
$rootPattern = '^ROOT\\FUTJOY0[1-8]\\'

function Inventario {
    $rootDevices = @(
        Get-PnpDevice -ErrorAction Stop | Where-Object {
            $_.InstanceId -match $rootPattern
        } | Sort-Object InstanceId -Unique
    )
    $drivers = @(
        Get-WindowsDriver -Online -ErrorAction Stop | Where-Object {
            $_.OriginalFileName -match '(^|[\\/])FutJoy\.inf$' -and
            $_.ProviderName -eq 'FUTUREO' -and
            $_.Driver -match '^oem\d+\.inf$'
        } | Sort-Object Driver -Unique
    )
    return [pscustomobject]@{
        Devices = $rootDevices
        Drivers = $drivers
    }
}

function CertificadoFutJoy([string]$store) {
    $p = 'Cert:\LocalMachine\' + $store + '\' + $thumb
    $cert = Get-Item -LiteralPath $p -ErrorAction SilentlyContinue
    if ($cert -and $cert.Thumbprint -eq $thumb -and $cert.Subject -eq $subject) {
        return $cert
    }
    if($cert){ Write-Warning "Huella encontrada con sujeto inesperado en $store; no tocar." }
    return $null
}

function ListarAlias {
    $root = 'System\CurrentControlSet\Control\MediaProperties\PrivateProperties'
    foreach($n in 1..8) {
        foreach($base in @(0x2100,0x2200)) {
            $pid = '{0:X4}' -f ($base + $n)
            $vidPid = 'VID_F7A0&PID_' + $pid
            foreach($entry in @(
                @{Hive='HKCU'; Path="$root\Joystick\OEM\$vidPid"; Name="OEMName"},
                @{Hive='HKLM'; Path="$root\Joystick\OEM\$vidPid"; Name="OEMName"},
                @{Hive='HKLM'; Path="$root\DirectInput\$vidPid\OEM"; Name="OEM Name"}
            )) {
                $path = $entry.Hive + ':\' + $entry.Path
                $key = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
                if(-not $key) {continue}
                try {
                    $value = $key.GetValue($entry.Name, $null)
                    if($null -eq $value) {continue}
                    $expected = '^FUTUREO VJOY' + $n + '( - PLAYER ' + $n + ')?$'
                    if($value -match $expected) {
                        [pscustomobject]@{ Path=$path; Name=$entry.Name; Value=$value }
                    }
                } finally { $key.Close() }
            }
        }
    }
}

Write-Output '=============================================================='
Write-Output "FUTUREO VJOY - VHF (modo: $Modo)"
Write-Output 'Sin tocar controles fisicos, teclado, raton o TESTSIGNING.'
Write-Output '=============================================================='
$before=Inventario
Write-Output ("ROOT\FUTJOY01..08 encontrados: " + $before.Devices.Count)
foreach($d in $before.Devices) {Write-Output ('  ROOT: ' + $d.InstanceId)}
Write-Output ("Paquetes FutJoy.inf del proveedor FUTUREO: " + $before.Drivers.Count)
foreach($pkg in $before.Drivers) {Write-Output ('  INF: ' + $pkg.Driver + ' / ' + $pkg.OriginalFileName)}
foreach($store in @('Root','TrustedPublisher')) {
    if(CertificadoFutJoy $store) { Write-Output ("  Certificado local en " + $store) }
}
$aliases=@(ListarAlias)
Write-Output ("Etiquetas antiguas de FUTUREO (solo valores coincidentes): " + $aliases.Count)
foreach($alias in $aliases) { Write-Output ('  ' + $alias.Path + ' / ' + $alias.Name + ' = ' + $alias.Value) }

if($Modo -eq "VistaPrevia") {
    Write-Output "VISTA PREVIA FINALIZADA. No se elimino ningun dispositivo."
    exit 0
}
$errors=0
foreach($d in $before.Devices) {
    Write-Output ('RETIRANDO ROOT: ' + $d.InstanceId)
    & pnputil.exe /remove-device $d.InstanceId | Out-Host
    if($LASTEXITCODE -ne 0) {
        Write-Warning "No se pudo retirar $($d.InstanceId) : codigo $LASTEXITCODE"
        $errors++
    }
}
foreach($pkg in $before.Drivers) {
    Write-Output ('RETIRANDO INF: ' + $pkg.Driver)
    & pnputil.exe /delete-driver $pkg.Driver /uninstall | Out-Host
    if($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 3010) {
        Write-Warning "No se pudo retirar $($pkg.Driver) : codigo $LASTEXITCODE"
        $errors++
    } elseif($LASTEXITCODE -eq 3010) {
        Write-Output "Windows solicito reinicio para completar $($pkg.Driver)."
    }
}
$after=Inventario
if($after.Devices.Count -gt 0 -or $after.Drivers.Count -gt 0) {
    Write-Warning "Aun hay ROOT ($($after.Devices.Count)) o INF ($($after.Drivers.Count)). No retirar certificados."
    $errors++
} else {
    foreach($store in @('Root','TrustedPublisher')) {
        if(CertificadoFutJoy $store) {
            $p='Cert:\LocalMachine\' + $store + '\' + $thumb
            try {
                Remove-Item -LiteralPath $p -Force -ErrorAction Stop
                Write-Output ("Certificado FUTUREO LAB retirado de " + $store)
            } catch {
                Write-Warning "No se pudo retirar certificado de $store : $($_.Exception.Message)"
                $errors++
            }
        }
    }
}
# Solo borrar valores OEM que coincidan EXACTAMENTE con los nombres
# FUTUREO de laboratorio. Nunca se eliminan claves ni valores de otros VID/PID.
foreach($alias in $aliases) {
    try {
        $key=Get-Item -LiteralPath $alias.Path -ErrorAction SilentlyContinue
        if(-not $key) {continue}
        try {
            $now=$key.GetValue($alias.Name,$null)
        } finally { $key.Close() }
        if($now -eq $alias.Value) {
            Remove-ItemProperty -LiteralPath $alias.Path -Name $alias.Name -ErrorAction Stop
            Write-Output ('Etiqueta FUTUREO retirada: ' + $alias.Path)
        }
    } catch {
        Write-Warning "No se pudo retirar etiqueta FUTUREO: $($alias.Path) / $($_.Exception.Message)"
        $errors++
    }
}
Write-Output 'Modo de prueba de Windows (TESTSIGNING): no modificado.'
Write-Output ("Dispositivos ROOT restantes: " + $after.Devices.Count)
Write-Output ("Paquetes FutJoy.inf restantes: " + $after.Drivers.Count)
if($errors -gt 0) {
    Write-Warning "Limpieza VHF incompleta; $errors incidencia(s). Revisa el log."
    exit 2
}
Write-Output 'LIMPIEZA FUTJOY/VHF COMPLETADA.'
exit 0
