using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Threading;
using System.Security.Principal;
using System.Runtime.InteropServices;
using System.IO;
using HIDMaestro;
using System.Windows.Forms;

namespace FutureoNombresReales;

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        // Prueba automatizada del bundle: no abre GUI, no requiere UAC y
        // NUNCA instala un controlador. Valida recursos del SDK embebido.
        if (args.Length == 2 && args[0] == "--self-test")
        {
            try
            {
                var assembly = typeof(HMBuildInfo).Assembly;
                var resourceCount = assembly.GetManifestResourceNames().Length;
                var hasDriver = HMBuildInfo.DriverArchitectures.Contains(Architecture.X64);
                var hasOemApi = typeof(HMOemNameOverride).GetMethod("Set") != null;
                File.WriteAllText(args[1],
                    $"UMDF2 x64 embedded: {hasDriver}; OEM API: {hasOemApi}; "
                    + $"Resources: {resourceCount}; SingleFile: "
                    + $"{string.IsNullOrEmpty(assembly.Location)}");
                if (!hasDriver || !hasOemApi || resourceCount < 10)
                    Environment.ExitCode = 21;
            }
            catch (Exception ex)
            {
                File.WriteAllText(args[1], "SELFTEST ERROR: " + ex);
                Environment.ExitCode = 22;
            }
            return;
        }

        // El EXE es portable. Solo la instalacion del CONTROLADOR requiere
        // permisos UAC. Se solicita la elevacion de forma explicita.
        using (var identity = WindowsIdentity.GetCurrent())
        {
            if (!new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator))
            {
                try
                {
                    Process.Start(new ProcessStartInfo(Environment.ProcessPath!)
                    {
                        UseShellExecute = true, Verb = "runas"
                    });
                }
                catch (Exception ex)
                {
                    MessageBox.Show(
                        "La instalacion del controlador necesita permisos de administrador.\n"
                        + "Abre el EXE con clic derecho > Ejecutar como administrador.\n\n"
                        + ex.Message, "FUTUREO VJOY", MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                }
                return;
            }
        }

        // Evita dos copias simultaneas que disputen los dispositivos
        // y sus nombres OEM respaldados por HIDMaestro.
        using var singleInstance = new Mutex(true, @"Local\FUTUREO_VJOY_PORTABLE_V070", out bool first);
        ApplicationConfiguration.Initialize();
        if (!first)
        {
            MessageBox.Show(
                "FUTUREO VJOY Portable ya esta abierto. Usa la ventana existente.",
                "FUTUREO VJOY", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        Application.Run(new LabForm());
    }
}

internal sealed class LabForm : Form
{
    private HMContext? motor;
    private readonly Dictionary<int, HMController> mandos = new();
    private readonly HashSet<int> nombresOemAplicados = new();
    private readonly NumericUpDown total = new()
    {
        Minimum = 1, Maximum = 8, Value = 4, Width = 64
    };
    private readonly NumericUpDown elegido = new()
    {
        Minimum = 1, Maximum = 8, Value = 1, Width = 64
    };
    private readonly TextBox registro = new()
    {
        ReadOnly = true, Multiline = true, ScrollBars = ScrollBars.Vertical,
        BackColor = Color.FromArgb(11, 30, 49), ForeColor = Color.White,
        Font = new Font("Consolas", 10f), Dock = DockStyle.Fill
    };
    private readonly Button instalar = Boton("1. INSTALAR Y CREAR MANDOS");
    private readonly Button crear = Boton("2. VOLVER A CREAR MANDOS");
    private readonly Button identificar = Boton("IDENTIFICAR P SELECCIONADO");
    private readonly Button cerrar = Boton("QUITAR MANDOS VIRTUALES");
    private readonly Button joy = Boton("ABRIR JOY.CPL");
    private bool ocupado;
    private bool preparado;

    private static Button Boton(string titulo) => new()
    {
        Text = titulo, AutoSize = true, Height = 44, Padding = new Padding(10, 6, 10, 6),
        FlatStyle = FlatStyle.System, Margin = new Padding(5)
    };

    public LabForm()
    {
        Text = "FUTUREO VJOY v0.7.0 | PORTABLE";
        StartPosition = FormStartPosition.CenterScreen;
        Size = new Size(860, 675);
        MinimumSize = new Size(730, 600);
        BackColor = Color.FromArgb(13, 27, 48);
        ForeColor = Color.White;
        Font = new Font("Segoe UI", 10);

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5,
            Padding = new Padding(15), AutoScroll = false
        };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 78));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 65));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 72));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        Controls.Add(layout);

        var head = new Label
        {
            Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
            ForeColor = Color.LightCyan,
            Text = "FUTUREO VJOY | INSTALADOR PORTABLE v0.7.0\n"
                + "Crea 1 a 8 mandos: FUTUREO_VJOY1 ... FUTUREO_VJOY8",
            Font = new Font("Segoe UI", 15, FontStyle.Bold)
        };
        layout.Controls.Add(head, 0, 0);

        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = true };
        panel.Controls.Add(new Label
        {
            Text = "Cantidad de mandos:", AutoSize = true,
            ForeColor = Color.White, Margin = new Padding(7, 12, 5, 0)
        });
        panel.Controls.Add(total);
        panel.Controls.Add(instalar);
        panel.Controls.Add(crear);
        layout.Controls.Add(panel, 0, 1);

        var middle = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = true };
        middle.Controls.Add(new Label
        {
            Text = "Identificar mando:", AutoSize = true,
            ForeColor = Color.White, Margin = new Padding(7, 12, 5, 0)
        });
        middle.Controls.Add(elegido);
        middle.Controls.Add(identificar);
        middle.Controls.Add(joy);
        layout.Controls.Add(middle, 0, 2);

        var foot = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = true };
        foot.Controls.Add(cerrar);
        foot.Controls.Add(new Label
        {
            AutoSize = true, MaximumSize = new Size(430, 0),
            ForeColor = Color.LightYellow,
            Text = "Los mandos existen mientras esta aplicacion siga abierta. "
                 + "No borra controladores VHF ni cambia TESTSIGNING."
        });
        layout.Controls.Add(foot, 0, 3);
        layout.Controls.Add(registro, 0, 4);

        crear.Enabled = false;
        identificar.Enabled = false;
        cerrar.Enabled = false;
        instalar.Click += async (_, _) => await PrepararAsync();
        crear.Click += async (_, _) => await CrearAsync();
        identificar.Click += async (_, _) => await IdentificarAsync();
        cerrar.Click += (_, _) => CerrarMandos();
        joy.Click += (_, _) =>
        {
            try { Process.Start(new ProcessStartInfo("control.exe", "joy.cpl") { UseShellExecute = true }); }
            catch (Exception ex) { Error(ex); }
        };
        FormClosing += (_, e) =>
        {
            if (ocupado)
            {
                e.Cancel = true;
                Log("Espera a finalizar la operacion de esta ventana antes de cerrarla.");
                return;
            }
            CerrarMandos();
            motor?.Dispose();
            motor = null;
        };
        Log("FUTUREO PORTABLE: no requiere instalar la aplicacion ni configurar rutas.");
        Log("8 puestos independientes: VID F7A0, PID 2201..2208.");
        Log("No modifica tus archivos FutJoy.sys, FutJoy.cat ni los controles anteriores.");
        Log("Requiere Windows 10/11 x64 y permisos UAC para instalar el driver HID.");
        Log("AVISO: instalar el controlador UMDF2 de terceros modifica drivers/certificados del sistema.");
        Log("Cierra la version v0.6.x, Steam y joy.cpl antes de instalar. Pulsa INSTALAR Y CREAR.");
        Log("Los nombres OEM se respaldan y aplican solo mientras los mandos estan activos.");
        Log("El programa es portable; el CONTROLADOR requiere instalacion en Windows.");
    }

    private void Log(string text)
    {
        if (IsDisposed) return;
        if (InvokeRequired) { BeginInvoke(new Action<string>(Log), text); return; }
        registro.AppendText($"[{DateTime.Now:HH:mm:ss}] {text}{Environment.NewLine}");
    }

    private void Error(Exception ex)
    {
        Log("ERROR: " + ex.Message);
        MessageBox.Show(this, ex.Message, "FUTUREO LAB", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private bool EsAdmin()
    {
        using var id = WindowsIdentity.GetCurrent();
        return new WindowsPrincipal(id).IsInRole(WindowsBuiltInRole.Administrator);
    }

    private void SetBusy(bool value)
    {
        ocupado = value;
        instalar.Enabled = !value && !preparado;
        crear.Enabled = !value && preparado && mandos.Count == 0;
        identificar.Enabled = !value && mandos.Count > 0;
        cerrar.Enabled = !value && mandos.Count > 0;
    }

    private async Task PrepararAsync()
    {
        if (ocupado || preparado) return;
        if (!EsAdmin())
        {
            MessageBox.Show(this, "Abre FUTUREO_VJOY_PORTABLE.exe con clic derecho > Ejecutar como administrador.",
                            "UAC necesario", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        if (MessageBox.Show(this,
            "FUTUREO VJOY PORTABLE\n\n"
          + "Se instalara el controlador UMDF2 de HIDMaestro (terceros), "
          + "con certificado local y privilegios de administrador.\n\n"
          + $"Se crearan {(int)total.Value} mandos independientes con nombre "
          + "FUTUREO_VJOY1, FUTUREO_VJOY2, etc. Windows guardara sus "
          + "controladores; los mandos desapareceran al cerrar la aplicacion.\n\n"
          + "NO elimina controladores VHF previos ni modifica TESTSIGNING. "
          + "Usa esta version en tu PC secundaria. ¿Continuar?",
            "CONSENTIMIENTO DEL CONTROLADOR", MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning) != DialogResult.Yes) return;
        SetBusy(true);
        try
        {
            Log("Preparando motor de HIDMaestro 2.3.0, solo con consentimiento...");
            await Task.Run(() =>
            {
                motor ??= new HMContext(HMBackend.Umdf2);
                motor.InstallDriver();
            });
            preparado = true;
            Log("Motor HIDMaestro preparado. Creando mandos de forma automatica...");
        }
        catch (Exception ex) { Error(ex); }
        finally { SetBusy(false); }
        if (preparado && mandos.Count == 0)
            await CrearAsync(false);
    }

    private static HMProfile Perfil(int n)
    {
        // PIDs 2201..2208 NO coinciden con los originales de VHF, 2101..2108.
        var nombre = $"FUTUREO_VJOY{n}";
        return new HMProfileBuilder()
             .Id($"futureo-portable-v070-p{n}")
            .Name(nombre)
            .DeviceDescription(nombre)
            .Vendor("FUTUREO LAB")
            .Vid(0xF7A0).Pid((ushort)(0x2200 + n))
            .ProductString(nombre)
            .ManufacturerString("FUTUREO LAB")
            .Type("gamepad")
            .Connection("usb")
            .FromDescriptorBuilder(new HidDescriptorBuilder()
                .Gamepad().AddStick("Left", bits: 16).AddButtons(16))
            .Build();
    }

    private async Task CrearAsync(bool confirmar = true)
    {
        if (ocupado || !preparado || motor is null || mandos.Count > 0) return;
        var n = (int)total.Value;
        if (confirmar && MessageBox.Show(this,
            $"Crear {n} mandos FUTUREO_VJOY1 ... FUTUREO_VJOY{n}?\n\n"
          + "Se aplicaran nombres OEM reversibles para joy.cpl y DirectInput. "
          + "Cierra ventanas joy.cpl y juegos antes de continuar.",
            "FUTUREO VJOY PORTABLE", MessageBoxButtons.YesNo,
            MessageBoxIcon.Question) != DialogResult.Yes) return;
        SetBusy(true);
        try
        {
            var dispositivos = await Task.Run(() =>
            {
                var resultado = new Dictionary<int, HMController>();
                var aplicados = new List<int>();
                try
                {
                    for (int slot = 1; slot <= n; slot++)
                    {
                        resultado[slot] = motor.CreateController(
                            Perfil(slot), $"futureo-portable-v070-slot-{slot}", HMBackend.Umdf2);
                        // El ProductString de HID se ajusta arriba.
                        // joy.cpl puede seguir usando el OEMName antiguo de HKCU,
                        // por eso HIDMaestro respalda y actualiza las 3 rutas OEM.
                        aplicados.Add(slot);
                        HMOemNameOverride.Set(0xF7A0, (ushort)(0x2200 + slot),
                            $"FUTUREO_VJOY{slot}");
                    }
                    return resultado;
                }
                catch
                {
                    foreach (var item in resultado.Values)
                    {
                        try { item.Dispose(); } catch { }
                    }
                    foreach (var slot in aplicados)
                    {
                        try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
                        catch { /* el SDK conserva recuperacion de las etiquetas */ }
                    }
                    throw;
                }
            });
            foreach (var entry in dispositivos)
            {
                mandos.Add(entry.Key, entry.Value);
                nombresOemAplicados.Add(entry.Key);
            }
            elegido.Maximum = n;
            Log($"OK: {mandos.Count} mandos creados. Cierra y abre joy.cpl para ver los nombres.");
            for (int i = 1; i <= n; i++)
                Log($"P{i}: VID F7A0 / PID {0x2200+i:X4} / FUTUREO_VJOY{i}");
        }
        catch (Exception ex) { Error(ex); }
        finally { SetBusy(false); }
    }

    private async Task IdentificarAsync()
    {
        if (ocupado) return;
        int numero = (int)elegido.Value;
        if (!mandos.TryGetValue(numero, out var pad)) { Log($"P{numero} no creado."); return; }
        SetBusy(true);
        try
        {
            Log($"P{numero}: tienes 4 segundos para abrir sus Propiedades en joy.cpl.");
            await Task.Delay(4000);
            for (int i = 0; i < 5; i++)
            {
                pad.SubmitState(new HMGamepadState
                {
                    Axes = new Dictionary<HMAxis, float> { [HMAxis.X] = 0.85f },
                    Buttons = HMButton.A
                });
                await Task.Delay(650);
                pad.SubmitState(new HMGamepadState());
                await Task.Delay(350);
            }
            Log($"P{numero} identificado, botones liberados.");
        }
        catch (Exception ex) { Error(ex); }
        finally { SetBusy(false); }
    }

    private void CerrarMandos()
    {
        if (ocupado) return;
        foreach (var mando in mandos.Values)
        {
            try { mando.Dispose(); } catch (Exception ex) { Log("Cierre: " + ex.Message); }
        }
        mandos.Clear();
        foreach (var slot in nombresOemAplicados.OrderByDescending(x => x))
        {
            try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
            catch (Exception ex) { Log($"P{slot}: restauracion OEM pendiente: {ex.Message}"); }
        }
        nombresOemAplicados.Clear();
        Log("Mandos retirados y alias OEM restaurados. El driver instalado permanece.");
        SetBusy(false);
    }
}
