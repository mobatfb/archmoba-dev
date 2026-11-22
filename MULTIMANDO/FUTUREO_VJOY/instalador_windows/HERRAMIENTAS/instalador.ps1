#requires -version 5.1
<#
 FUTUREO VJOY - Instalador para equipo SECUNDARIO Windows 10/11 x64.
 Driver KMDF experimental con firma de prueba. No modifica vJoy existente.
 Ejecucion manual y consciente. No apaga Secure Boot ni BitLocker.
#>
param(
  [ValidateSet('Menu','Preparar','Instalar1','Instalar8','Diagnosticar','Desinstalar','ModoNormal')]
  [string] $Accion = 'Menu'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Driver = Join-Path $Root 'DRIVER'
$Inf = Join-Path $Driver 'FutJoy.inf'
$Sys = Join-Path $Driver 'FutJoy.sys'
$Cat = Join-Path $Driver 'FutJoy.cat'
$Cer = Join-Path $Driver 'FUTUREO_VJOY_PRUEBA.cer'
$HashFile = Join-Path $Driver 'SHA256SUMS.txt'

function Head([string] $Title) {
  Write-Host ''
  Write-Host '=========================================================' -ForegroundColor DarkCyan
  Write-Host " FUTUREO VJOY - $Title" -ForegroundColor Cyan
  Write-Host ' LABORATORIO / NO USAR EN EQUIPO PRINCIPAL' -ForegroundColor Yellow
  Write-Host '=========================================================' -ForegroundColor DarkCyan
}
function IsAdmin {
  $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
  $principal=New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Elevate([string] $Option) {
  $ps='"' + $PSCommandPath + '"'
  $arg='-NoProfile -ExecutionPolicy Bypass -File ' + $ps + ' -Accion ' + $Option
  Start-Process -FilePath powershell.exe -ArgumentList $arg -Verb RunAs -Wait
}
function Confirm([string] $Question) {
  $reply=Read-Host ($Question + ' (escribe SI para continuar)')
  return $reply -ceq 'SI'
}
function AssertLab {
  if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Requiere Windows.' }
  if (-not [Environment]::Is64BitOperatingSystem) { throw 'Solo Windows x64.' }
  if (-not (IsAdmin)) { throw 'Ejecuta como administrador.' }
}
function VerifyFiles {
  foreach($file in @($Inf,$Sys,$Cat,$Cer,$HashFile)) {
    if(-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Archivo requerido ausente: $file" }
  }
  $entries=Get-Content -LiteralPath $HashFile -Encoding ascii
  $checked=0
  foreach($line in $entries) {
    if($line -match '^([0-9a-fA-F]{64})\s+([^\\/:*?"<>|]+)$') {
      $expected=$Matches[1].ToUpperInvariant()
      $file=Join-Path $Driver $Matches[2]
      if(-not (Test-Path $file)) { throw "Falta archivo SHA256: $file" }
      $actual=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToUpperInvariant()
      if($actual -ne $expected) { throw "HASH NO COINCIDE: $file" }
      $checked++
    }
  }
  if($checked -lt 4) { throw 'Lista de hashes incompleta: se esperan 4 archivos firmados.' }
  $cert=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($Cer)
  if(-not $cert.Subject.Contains('FUTUREO VJOY LAB TEST ONLY')) {
    throw 'El certificado no corresponde al laboratorio FUTUREO VJOY.'
  }
  Write-Host "Hashes correctos ($checked archivos). Certificado: $($cert.Thumbprint)" -ForegroundColor Green
  return $cert
}
function PrintStatus {
  Head 'DIAGNOSTICO DE WINDOWS'
  Write-Host 'Modo de prueba (BCD):'
  try { bcdedit.exe /enum '{current}' | Select-String -Pattern 'testsigning|testsign|identifier|identificador' } catch { Write-Warning $_.Exception.Message }
  Write-Host ''
  Write-Host 'Dispositivos ROOT FUTJOY encontrados:'
  $devs=@(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'ROOT\FUTJOY0*' })
  if($devs.Count -gt 0){ $devs | Select-Object Status,FriendlyName,InstanceId | Format-Table -AutoSize }
  else { Write-Host '(ninguno instalado)' -ForegroundColor Yellow }
  if(Test-Path (Join-Path $Root 'PYTHON\diagnostico_hid.py')){
    $py=Get-Command py.exe -ErrorAction SilentlyContinue
    if($py){
      Write-Host ''
      Write-Host 'Lectura HID del nombre REAL:'
      & $py.Source -3 (Join-Path $Root 'PYTHON\diagnostico_hid.py') --count 8
    }else{
      Write-Warning 'Python no instalado: la lectura HID avanzada es opcional.'
    }
  }
  Write-Host ''
  Write-Host 'El nombre de un dispositivo ROOT o su PID no garantiza el nombre visible en el juego.' -ForegroundColor Yellow
}
function TestMode {
  $output=((bcdedit.exe /enum '{current}' 2>&1) | Out-String)
  if ($LASTEXITCODE -ne 0){ throw 'No se pudo consultar BCDEdit.' }
  return ($output -match '(?im)^testsigning\s+(Yes|Si|S[i\u00ed]|True|1)\s*$')
}
function PrepareTestMode {
  AssertLab
  Head 'ACTIVAR MODO DE FIRMA DE PRUEBA'
  Write-Host 'Esta opcion cambia la configuracion de arranque de Windows.' -ForegroundColor Yellow
  Write-Host 'NO desactiva Secure Boot, BitLocker ni Integridad de memoria.'
  Write-Host 'Si usas BitLocker, conserva tu clave de recuperacion antes de seguir.' -ForegroundColor Yellow
  if(-not (Confirm 'Deseas habilitar TESTSIGNING y reiniciar manualmente despues?')){return}
  & bcdedit.exe /set testsigning on
  if($LASTEXITCODE -ne 0){ throw 'Windows rechazo el cambio. Secure Boot puede bloquearlo. No lo desactives sin revisar BitLocker.' }
  Write-Host 'TESTSIGNING configurado. REINICIA LA PC MANUALMENTE antes de instalar.' -ForegroundColor Green
}
function ImportTestCertificate([System.Security.Cryptography.X509Certificates.X509Certificate2] $cert){
  Write-Host 'La instalacion confiara temporalmente en un certificado de prueba.' -ForegroundColor Yellow
  Write-Host 'Esto cambia las autoridades de confianza de LocalMachine. Certificado:'
  Write-Host " $($cert.Subject)"
  Write-Host " Huella: $($cert.Thumbprint)"
  if(-not (Confirm 'CONFIRMAS que quieres confiar en este certificado de prueba?')) { throw 'Importacion cancelada por el usuario.' }
  $res=Import-Certificate -FilePath $Cer -CertStoreLocation 'Cert:\LocalMachine\Root'
  if(-not $res){throw 'No se pudo agregar certificado en Root.'}
  $res=Import-Certificate -FilePath $Cer -CertStoreLocation 'Cert:\LocalMachine\TrustedPublisher'
  if(-not $res){throw 'No se pudo agregar certificado en TrustedPublisher.'}
  foreach($file in @($Sys,$Cat)){
    $signature=Get-AuthenticodeSignature -FilePath $file
    if($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or
       $signature.SignerCertificate.Thumbprint -ne $cert.Thumbprint) {
      throw "La firma del archivo no se pudo verificar: $file ($($signature.Status))"
    }
  }
  Write-Host 'Firmas SYS y CAT verificadas con el certificado de prueba.' -ForegroundColor Green
}
function BuildRootClass {
  $code=@'
using System;
using System.Text;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class FutureoRootDevice {
  private const uint DICD_GENERATE_ID = 0x1;
  private const uint SPDRP_HARDWAREID = 0x1;
  private const uint DIF_REGISTERDEVICE = 0x19;
  private const uint INSTALLFLAG_FORCE = 0x1;
  private const uint INSTALLFLAG_NONINTERACTIVE = 0x4;
  private static readonly Guid SystemClass = new Guid("4d36e97d-e325-11ce-bfc1-08002be10318");

  [StructLayout(LayoutKind.Sequential)]
  public struct SP_DEVINFO_DATA {
    public int cbSize;
    public Guid ClassGuid;
    public int DevInst;
    public IntPtr Reserved;
  }
  [DllImport("setupapi.dll", EntryPoint="SetupDiCreateDeviceInfoList", SetLastError=true)]
  private static extern IntPtr CreateList(ref Guid classGuid, IntPtr parent);
  [DllImport("setupapi.dll", EntryPoint="SetupDiCreateDeviceInfoW", CharSet=CharSet.Unicode, SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool CreateDevice(IntPtr list, string name, ref Guid classGuid,
      string description, IntPtr hwndParent, uint flags, ref SP_DEVINFO_DATA data);
  [DllImport("setupapi.dll", EntryPoint="SetupDiSetDeviceRegistryPropertyW", SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool SetProperty(IntPtr list, ref SP_DEVINFO_DATA data,
      uint property, byte[] value, uint length);
  [DllImport("setupapi.dll", EntryPoint="SetupDiCallClassInstaller", SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool CallInstaller(uint installFunction, IntPtr list, ref SP_DEVINFO_DATA data);
  [DllImport("setupapi.dll", EntryPoint="SetupDiDestroyDeviceInfoList", SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool DestroyList(IntPtr list);
  [DllImport("newdev.dll", EntryPoint="UpdateDriverForPlugAndPlayDevicesW", CharSet=CharSet.Unicode, SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool UpdateDriver(IntPtr hwndParent, string hardwareId,
      string infPath, uint flags, [MarshalAs(UnmanagedType.Bool)] out bool rebootRequired);

  private static void Check(bool good, string name) {
    if (!good) throw new Win32Exception(Marshal.GetLastWin32Error(), name);
  }
  public static string Create(int slot, string infFile) {
    if (slot < 1 || slot > 8) throw new ArgumentOutOfRangeException("slot");
    string hardwareId = "ROOT\\FUTJOY" + slot.ToString("00");
    Guid category = SystemClass;
    IntPtr list = CreateList(ref category, IntPtr.Zero);
    if (list == IntPtr.Zero || list == new IntPtr(-1))
      throw new Win32Exception(Marshal.GetLastWin32Error(), "SetupDiCreateDeviceInfoList");
    try {
      SP_DEVINFO_DATA data = new SP_DEVINFO_DATA();
      data.cbSize = Marshal.SizeOf(typeof(SP_DEVINFO_DATA));
      Check(CreateDevice(list, "FUTUREO VJOY" + slot, ref category,
          "FUTUREO VJOY" + slot, IntPtr.Zero, DICD_GENERATE_ID, ref data),
          "SetupDiCreateDeviceInfo");
      byte[] multiString = Encoding.Unicode.GetBytes(hardwareId + "\0\0");
      Check(SetProperty(list, ref data, SPDRP_HARDWAREID,
          multiString, (uint)multiString.Length), "SetupDiSetDeviceRegistryProperty");
      Check(CallInstaller(DIF_REGISTERDEVICE, list, ref data), "DIF_REGISTERDEVICE");
    } finally {
      DestroyList(list);
    }
    bool reboot;
    Check(UpdateDriver(IntPtr.Zero, hardwareId, infFile,
        INSTALLFLAG_FORCE | INSTALLFLAG_NONINTERACTIVE, out reboot),
        "UpdateDriverForPlugAndPlayDevices");
    return hardwareId + (reboot ? " (requiere reiniciar)" : " (listo)");
  }
}
'@
  Add-Type -TypeDefinition $code -Language CSharp -ErrorAction Stop
}
function InstallPads([int] $quantity) {
  AssertLab
  Head "INSTALAR $quantity MANDO(S)"
  if(-not (Confirm "Confirma instalar $quantity dispositivos virtuales FUTUREO en este equipo SECUNDARIO")){return}
  if(-not (TestMode)) {throw 'TESTSIGNING no aparece activado. Usa PREPARAR_MODO_PRUEBA.bat, reinicia y vuelve a intentar.'}
  $cert=VerifyFiles
  ImportTestCertificate $cert
  Write-Host 'Agregando paquete firmado al almacen de controladores Windows...'
  & pnputil.exe /add-driver $Inf /install
  if($LASTEXITCODE -ne 0){throw "PNPUTIL rechazo FutJoy.inf con codigo $LASTEXITCODE. Revisa %windir%\INF\setupapi.dev.log"}
  BuildRootClass
  for($slot=1;$slot -le $quantity;$slot++) {
    $id='ROOT\FUTJOY{0:D2}' -f $slot
    $already=@(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {$_.InstanceId -like ($id+'\*')})
    if($already.Count -gt 0) {
      Write-Host "$id ya existe; no se crea duplicado." -ForegroundColor Yellow
      continue
    }
    Write-Host "Creando dispositivo $id ..." -ForegroundColor Cyan
    $result=[FutureoRootDevice]::Create($slot,$Inf)
    Write-Host "Creado: $result" -ForegroundColor Green
  }
  & pnputil.exe /scan-devices | Out-Host
  Start-Sleep -Seconds 2
  PrintStatus
  Write-Host 'Revisa en Windows: Win+R -> joy.cpl. Si el dispositivo tiene error, no lo uses en un juego.' -ForegroundColor Yellow
}
function UninstallPads {
  AssertLab
  Head 'DESINSTALAR FUTUREO VJOY'
  if(-not (Confirm 'Eliminar SOLO los dispositivos ROOT\FUTJOY01..08 y su paquete de prueba?')){return}
  $devs=@(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match '^ROOT\\FUTJOY0[1-8]\\' })
  foreach($dev in $devs) {
    Write-Host "Quitando $($dev.InstanceId) ..."
    & pnputil.exe /remove-device $dev.InstanceId
    if($LASTEXITCODE -ne 0){Write-Warning "No se pudo retirar $($dev.InstanceId)"}
  }
  try {
    $files=@(Get-WindowsDriver -Online -ErrorAction Stop | Where-Object {
      $_.OriginalFileName -match 'FutJoy\.inf$' -and $_.ProviderName -eq 'FUTUREO'
    })
    foreach($f in $files) {
      Write-Host "Retirando paquete de controlador $($f.Driver) ..."
      & pnputil.exe /delete-driver $f.Driver /uninstall
      if($LASTEXITCODE -ne 0){Write-Warning "No se pudo quitar paquete $($f.Driver)"}
    }
  } catch { Write-Warning "No se pudo consultar paquete mediante DISM: $($_.Exception.Message)" }
  if(Test-Path $Cer){
    $cert=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($Cer)
    if(Confirm "Deseas quitar de Windows el certificado de PRUEBA $($cert.Thumbprint)?") {
      foreach($store in @('Root','TrustedPublisher')){
        $p='Cert:\LocalMachine\'+$store+'\'+$cert.Thumbprint
        if(Test-Path $p){Remove-Item -LiteralPath $p -Force}
      }
      Write-Host 'Certificado de FUTUREO retirado.' -ForegroundColor Green
    }
  }
  Write-Host 'Finalizado. TESTSIGNING no se cambia automaticamente.' -ForegroundColor Yellow
}
function DisableTestMode {
  AssertLab
  Head 'VOLVER A MODO NORMAL'
  Write-Host 'Si hay otros controladores firmados solo para prueba, dejaran de funcionar.' -ForegroundColor Yellow
  if(-not (Confirm 'Desactivar TESTSIGNING y reiniciar manualmente despues?')){return}
  & bcdedit.exe /set testsigning off
  if($LASTEXITCODE -ne 0){throw "BCDEdit fallo ($LASTEXITCODE)"}
  Write-Host 'Reinicia Windows manualmente para completar el cambio.' -ForegroundColor Green
}
function Menu {
  while($true){
    Head 'MENU PRINCIPAL'
    Write-Host '1. PREPARAR MODO DE PRUEBA (requiere reiniciar)'
    Write-Host '2. INSTALAR SOLO 1 MANDO (recomendado primero)'
    Write-Host '3. INSTALAR 8 MANDOS'
    Write-Host '4. DIAGNOSTICAR DISPOSITIVOS Y NOMBRES HID'
    Write-Host '5. DESINSTALAR FUTUREO VJOY'
    Write-Host '6. RESTAURAR MODO NORMAL TESTSIGNING OFF'
    Write-Host '0. SALIR'
    $reply=Read-Host 'Elige opcion'
    $target=switch($reply){
      '1' {'Preparar'} '2' {'Instalar1'} '3' {'Instalar8'}
      '4' {'Diagnosticar'} '5' {'Desinstalar'} '6' {'ModoNormal'}
      '0' {'Salir'} default {'Invalido'}
    }
    if($target -eq 'Salir'){break}
    if($target -eq 'Invalido'){continue}
    try { Execute $target } catch { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red }
    Read-Host 'Presiona ENTER para volver al menu' | Out-Null
  }
}
function Execute([string] $action) {
  switch($action) {
    'Menu' {Menu}
    'Preparar' {PrepareTestMode}
    'Instalar1' {InstallPads 1}
    'Instalar8' {InstallPads 8}
    'Diagnosticar' {PrintStatus}
    'Desinstalar' {UninstallPads}
    'ModoNormal' {DisableTestMode}
    default {throw "Accion incorrecta: $action"}
  }
}
if($Accion -in @('Preparar','Instalar1','Instalar8','Desinstalar','ModoNormal') -and -not (IsAdmin)) {
  try { Elevate $Accion } catch { Write-Host "No se concedio permiso administrador: $_" -ForegroundColor Red }
} else {
  try { Execute $Accion } catch { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
}