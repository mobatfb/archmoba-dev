using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Security.Principal;
using HIDMaestro;
using System.Windows.Forms;

namespace FutureoNombresReales;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new LabForm());
    }
}

internal sealed class LabForm : Form
{
    private HMContext? motor;
    private readonly Dictionary<int, HMController> mandos = new();
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
    private readonly Button instalar = Boton("1. PREPARAR MOTOR UMDF2");
    private readonly Button crear = Boton("2. CREAR MANDOS CON NOMBRES");
    private readonly Button identificar = Boton("IDENTIFICAR P SELECCIONADO");
    private readonly Button cerrar = Boton("QUITAR MANDOS DE ESTA PRUEBA");
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
        Text = "FUTUREO VJOY v0.6.1 LAB - NOMBRES REALES (motor independiente)";
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
            Text = "FUTUREO VJOY | NOMBRES REALES\n"
                + "Motor alternativo UMDF2 / prueba separada / NO reemplaza v0.5.x",
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
            Text = "Identificar jugador:", AutoSize = true,
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
            Text = "No instalar dos motores a la vez para uso normal. "
                 + "Los antiguos P1-P4 NO se tocan ni se eliminan."
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
        Log("MODO LAB. Puedes ver 8 entradas si mantienes los 4 dispositivos antiguos.");
        Log("Este motor usa VID F7A0 de laboratorio y PID 2201..2208, diferentes del VHF anterior.");
        Log("No modifica tus archivos FutJoy.sys, FutJoy.cat ni los controles anteriores.");
        Log("Se necesita Windows 10/11 x64 y permisos elevados para preparar el motor.");
        Log("AVISO: la instalacion firma localmente un controlador UMDF2 y agrega confianza a Windows.");
        Log("Pulsa PREPARAR solo si aceptas instalar ese controlador de terceros.");
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
            MessageBox.Show(this, "Cierra esta ventana y abre FUTUREO_NOMBRES_REALES.exe con clic derecho > Ejecutar como administrador.",
                            "UAC necesario", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        if (MessageBox.Show(this,
            "Esto INSTALA un controlador UMDF2 de HIDMaestro (terceros) y confia temporalmente "
          + "en su certificado local. SOLO EN EQUIPO SECUNDARIO.\n\n"
          + "No elimina FUTJOY ni cambia TESTSIGNING. ¿Continuar?",
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
            Log("Motor preparado; ahora puedes CREAR 1..8 mandos con nombres distintos.");
        }
        catch (Exception ex) { Error(ex); }
        finally { SetBusy(false); }
    }

    private static HMProfile Perfil(int n)
    {
        // PIDs 2201..2208 NO coinciden con los originales de VHF, 2101..2108.
        var nombre = $"FUTUREO VJOY{n}";
        return new HMProfileBuilder()
            .Id($"futureo-lab-v061-p{n}")
            .Name(nombre)
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

    private async Task CrearAsync()
    {
        if (ocupado || !preparado || motor is null || mandos.Count > 0) return;
        var n = (int)total.Value;
        if (MessageBox.Show(this,
            $"Crear P1..P{n} con IDENTIDAD HID PROPIA?\n\n"
          + "No elimina ni deshabilita los controles antiguos. Si aun siguen visibles, "
          + "joy.cpl mostrara entradas duplicadas hasta retirarlos manualmente.",
            "FUTUREO - CREAR NUEVO MOTOR", MessageBoxButtons.YesNo,
            MessageBoxIcon.Question) != DialogResult.Yes) return;
        SetBusy(true);
        try
        {
            var dispositivos = await Task.Run(() =>
            {
                var resultado = new Dictionary<int, HMController>();
                try
                {
                    for (int slot = 1; slot <= n; slot++)
                    {
                        resultado[slot] = motor.CreateController(
                            Perfil(slot), $"futureo-v061-slot-{slot}", HMBackend.Umdf2);
                    }
                    return resultado;
                }
                catch
                {
                    foreach (var item in resultado.Values) item.Dispose();
                    throw;
                }
            });
            foreach (var entry in dispositivos) mandos.Add(entry.Key, entry.Value);
            elegido.Maximum = n;
            Log($"CREADOS: {mandos.Count} mandos. Abre joy.cpl y revisa FUTUREO VJOY1...VJOY{n}.");
            for (int i = 1; i <= n; i++)
                Log($"P{i}: VID F7A0 / PID {0x2200+i:X4} / FUTUREO VJOY{i}");
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
        Log("Mandos creados en esta sesion retirados. FutJoy anterior permanece intacto.");
        SetBusy(false);
    }
}
