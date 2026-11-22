using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Security.Principal;
using System.Text;
using System.Windows.Forms;

namespace FutureoLimpiador;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new CleanupForm());
    }
}

internal record ProcessResult(int ExitCode, string StandardOutput, string StandardError);

internal sealed class CleanupForm : Form
{
    private readonly CheckBox limpiarVhf = new()
    {
        Text = "Eliminar FUTJOY / VHF (ROOT\\FUTJOY01..08, FutJoy.inf, certificado LAB, alias FUTUREO)",
        Checked = true, AutoSize = true, ForeColor = Color.White
    };
    private readonly CheckBox limpiarMaestro = new()
    {
        Text = "Eliminar HIDMaestro completo (incluidos controladores de OTRAS aplicaciones que lo utilicen)",
        Checked = true, AutoSize = true, ForeColor = Color.White
    };
    private readonly Button scan = MakeButton("1. ESCANEAR SIN BORRAR");
    private readonly Button clean = MakeButton("2. LIMPIAR DISPOSITIVOS SELECCIONADOS");
    private readonly Button openLog = MakeButton("ABRIR CARPETA DE REGISTROS");
    private readonly Button original = MakeButton("ABRIR VERSION QUE FUNCIONO (v0.6.0)");
    private readonly TextBox output = new()
    {
        ReadOnly = true, Multiline = true, WordWrap = false,
        ScrollBars = ScrollBars.Both, Dock = DockStyle.Fill,
        BackColor = Color.FromArgb(9, 24, 40), ForeColor = Color.LightGreen,
        Font = new Font("Consolas", 9.5f)
    };
    private readonly Label state = new()
    {
        Text = "No se ha realizado el escaneo. Nada se elimina automaticamente.",
        ForeColor = Color.LightCyan, Dock = DockStyle.Fill,
        TextAlign = ContentAlignment.MiddleLeft
    };
    private readonly string folder =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FUTUREO_VJOY", "cleanup_logs");
    private readonly string logFile;
    private readonly string basePath = AppContext.BaseDirectory;
    private bool scanned, busy;

    private static Button MakeButton(string title) => new()
    {
        Text = title, AutoSize = true, Height = 40, Padding = new Padding(9, 5, 9, 5),
        Margin = new Padding(5), FlatStyle = FlatStyle.System
    };

    public CleanupForm()
    {
        logFile = Path.Combine(folder, $"limpieza_{DateTime.Now:yyyyMMdd_HHmmss}.txt");
        Text = "FUTUREO VJOY - LIMPIADOR TOTAL DE LABORATORIO v1.0";
        Size = new Size(1000, 770);
        MinimumSize = new Size(820, 630);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(14, 30, 53);
        ForeColor = Color.White;
        Font = new Font("Segoe UI", 10);
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 6,
            Padding = new Padding(15)
        };
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 82));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 45));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 112));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        panel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        Controls.Add(panel);
        panel.Controls.Add(new Label
        {
            Text = "FUTUREO VJOY | LIMPIADOR TOTAL\n"
                + "Solo motores virtuales del laboratorio. No borra dispositivos fisicos.",
            Dock = DockStyle.Fill, Font = new Font("Segoe UI", 17, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleCenter, ForeColor = Color.LightCyan
        }, 0, 0);
        panel.Controls.Add(limpiarVhf, 0, 1);
        panel.Controls.Add(limpiarMaestro, 0, 2);
        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = true };
        actions.Controls.Add(scan);
        actions.Controls.Add(clean);
        actions.Controls.Add(openLog);
        actions.Controls.Add(original);
        panel.Controls.Add(actions, 0, 3);
        panel.Controls.Add(state, 0, 4);
        panel.Controls.Add(output, 0, 5);
        clean.Enabled = false;
        scan.Click += async (_, _) => await ScanAsync();
        clean.Click += async (_, _) => await CleanAsync();
        openLog.Click += (_, _) =>
        {
            try
            {
                Directory.CreateDirectory(folder);
                Process.Start(new ProcessStartInfo("explorer.exe", folder) { UseShellExecute = true });
            }
            catch (Exception ex) { ShowError(ex.Message); }
        };
        original.Click += (_, _) =>
        {
            try
            {
                Process.Start(new ProcessStartInfo(
                    "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/MULTIMANDO/FUTUREO_VJOY/instalador_windows/FUTUREO_VJOY_v0_6_0_LAB_NOMBRES_REALES_UMDF2.zip")
                { UseShellExecute = true });
            }
            catch (Exception ex) { ShowError(ex.Message); }
        };
        limpiarVhf.CheckedChanged += (_, _) => InvalidateScan();
        limpiarMaestro.CheckedChanged += (_, _) => InvalidateScan();
        FormClosing += (_, e) =>
        {
            if (!busy) return;
            e.Cancel = true;
            Write("Hay una operacion en curso. No cerrar durante la limpieza.");
        };

        Write("ATENCION: SOLO PC SECUNDARIA DE LABORATORIO. Ejecutar como administrador.");
        Write("Cierra FUTUREO VJOY v0.6.x, Steam y joy.cpl antes de escanear.");
        Write("Se eliminaran TODOS los dispositivos y driver de HIDMaestro si seleccionas esa opcion.");
        Write("NO se eliminan dispositivos fisicos, dispositivos USB ajenos ni USB/IP de terceros.");
        Write("TESTSIGNING y configuracion de arranque no se modifican.");
        Write("La eliminacion es irreversible sin reinstalar. Primero ESCANEAR.");
        Write($"Log local: {logFile}");
        if (!IsAdmin())
        {
            state.Text = "Ejecuta como administrador. El manifiesto solicita UAC.";
            scan.Enabled = false;
        }
    }

    private static bool IsAdmin()
    {
        using var id = WindowsIdentity.GetCurrent();
        return new WindowsPrincipal(id).IsInRole(WindowsBuiltInRole.Administrator);
    }

    private void Write(string value)
    {
        var line = $"[{DateTime.Now:HH:mm:ss}] {value}{Environment.NewLine}";
        output.AppendText(line);
        try
        {
            Directory.CreateDirectory(folder);
            File.AppendAllText(logFile, line, Encoding.UTF8);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private void ShowError(string message)
    {
        Write("ERROR: " + message);
        MessageBox.Show(this, message, "FUTUREO LIMPIADOR",
            MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private void InvalidateScan()
    {
        scanned = false;
        clean.Enabled = false;
        if (!busy) state.Text = "Opciones modificadas: vuelve a ESCANEAR.";
    }

    private void SetBusy(bool value)
    {
        busy = value;
        scan.Enabled = !value && IsAdmin();
        clean.Enabled = !value && scanned;
        limpiarVhf.Enabled = !value;
        limpiarMaestro.Enabled = !value;
    }

    private static async Task<ProcessResult> RunProcessAsync(
        string file, IEnumerable<string> args, int timeoutSeconds)
    {
        var start = new ProcessStartInfo(file)
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        foreach (var arg in args) start.ArgumentList.Add(arg);
        using var process = new Process { StartInfo = start };
        if (!process.Start()) throw new InvalidOperationException("No se pudo iniciar " + file);
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(timeoutSeconds));
        try
        {
            await process.WaitForExitAsync(cts.Token);
        }
        catch (OperationCanceledException)
        {
            try { process.Kill(entireProcessTree: true); } catch { }
            throw new TimeoutException("Operacion excedio el tiempo permitido: " + Path.GetFileName(file));
        }
        return new ProcessResult(process.ExitCode, await stdout, await stderr);
    }

    private static string VhfScript =>
        Path.Combine(AppContext.BaseDirectory, "FUTUREO_LIMPIAR_VHF.ps1");

    private static string MaestroUninstall =>
        Path.Combine(AppContext.BaseDirectory, "HIDMaestroUninstall.exe");

    private static Task<ProcessResult> RunVhf(string mode) =>
        RunProcessAsync(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", VhfScript, "-Modo", mode }, 180);

    private static Task<ProcessResult> RunMaestro(string option) =>
        RunProcessAsync(MaestroUninstall, new[] { option }, 300);

    private void PrintProcess(string label, ProcessResult result)
    {
        Write($"---- {label} (codigo {result.ExitCode}) ----");
        if (!string.IsNullOrWhiteSpace(result.StandardOutput))
            Write(result.StandardOutput.Trim());
        if (!string.IsNullOrWhiteSpace(result.StandardError))
            Write("STDERR: " + result.StandardError.Trim());
    }

    private bool Ready()
    {
        if (!limpiarVhf.Checked && !limpiarMaestro.Checked)
        {
            ShowError("Selecciona por lo menos un motor virtual.");
            return false;
        }
        if (limpiarVhf.Checked && !File.Exists(VhfScript))
        {
            ShowError("Falta FUTUREO_LIMPIAR_VHF.ps1: extrae el ZIP completo.");
            return false;
        }
        if (limpiarMaestro.Checked && !File.Exists(MaestroUninstall))
        {
            ShowError("Falta el desinstalador oficial HIDMaestroUninstall.exe: extrae el ZIP completo.");
            return false;
        }
        return true;
    }

    private async Task ScanAsync()
    {
        if (busy || !Ready()) return;
        scanned = false;
        SetBusy(true);
        state.Text = "Escaneando sin modificar dispositivos...";
        try
        {
            if (limpiarMaestro.Checked)
            {
                var r = await RunMaestro("--preview");
                PrintProcess("HIDMaestro: vista previa oficial", r);
                if (r.ExitCode != 0)
                    throw new InvalidOperationException(
                        $"HIDMaestro no permite continuar (codigo {r.ExitCode}). "
                        + "Cierra programas que lo esten usando, revisa el log y vuelve a escanear.");
            }
            if (limpiarVhf.Checked)
            {
                var r = await RunVhf("VistaPrevia");
                PrintProcess("FUTJOY VHF: vista previa", r);
                if (r.ExitCode != 0)
                    throw new InvalidOperationException("Inventario FUTJOY fallido. No eliminar.");
            }
            scanned = true;
            state.Text = "Vista previa correcta. Para eliminar se necesita confirmacion manual.";
            Write("ESCANEO COMPLETADO. Todavia no se ha borrado ningun controlador.");
        }
        catch (Exception ex)
        {
            state.Text = "Escaneo fallido. No se habilito la eliminacion.";
            ShowError(ex.Message);
        }
        finally { SetBusy(false); }
    }

    private async Task CleanAsync()
    {
        if (busy || !scanned || !Ready()) return;
        if (MessageBox.Show(this,
            "AVISO IMPORTANTE:\n\n"
            + "Esta operacion ELIMINARA los dispositivos virtuales seleccionados, "
            + "sus paquetes de controladores y certificados asociados.\n\n"
            + "HIDMaestro es un motor compartido: su desinstalacion afecta "
            + "tambien a otras aplicaciones que lo usan.\n\n"
            + "NO se desactiva TESTSIGNING. NO se borran mandos fisicos.\n"
            + "Para empezar de nuevo, despues reinstala FUTUREO v0.6.0.\n\n"
            + "¿Continuar al ultimo control?",
            "CONFIRMAR LIMPIEZA DE LABORATORIO", MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning) != DialogResult.Yes) return;

        using var dialog = new Form
        {
            Text = "Confirmacion final FUTUREO", Size = new Size(570, 235),
            StartPosition = FormStartPosition.CenterParent,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            MaximizeBox = false, MinimizeBox = false
        };
        var text = new Label
        {
            Text = "Escribe exactamente LIMPIAR FUTUREO para autorizar la eliminacion.\n"
                + "Esta accion no se puede deshacer sin reinstalar los controladores.",
            AutoSize = true, Location = new Point(18, 17)
        };
        var entry = new TextBox { Location = new Point(18, 87), Width = 520 };
        var confirm = new Button
        {
            Text = "ELIMINAR", Enabled = false, DialogResult = DialogResult.OK,
            Location = new Point(310, 130), Width = 110
        };
        var cancel = new Button
        {
            Text = "CANCELAR", DialogResult = DialogResult.Cancel,
            Location = new Point(430, 130), Width = 110
        };
        entry.TextChanged += (_, _) => confirm.Enabled =
            string.Equals(entry.Text.Trim(), "LIMPIAR FUTUREO", StringComparison.Ordinal);
        dialog.Controls.AddRange(new Control[] { text, entry, confirm, cancel });
        dialog.AcceptButton = confirm;
        dialog.CancelButton = cancel;
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        scanned = false;
        SetBusy(true);
        state.Text = "Eliminando. No cerrar la aplicacion...";
        var needsRestart = false;
        var errors = false;
        try
        {
            if (limpiarMaestro.Checked)
            {
                Write("Eliminando HIDMaestro usando su desinstalador oficial (sin --include-usbip)...");
                var result = await RunMaestro("--yes");
                PrintProcess("HIDMaestro: desinstalacion oficial", result);
                if (result.ExitCode == 3)
                {
                    needsRestart = true;
                    Write("HIDMaestro: hay operaciones pendientes para el siguiente reinicio.");
                }
                else if (result.ExitCode != 0)
                {
                    throw new InvalidOperationException(
                        $"HIDMaestro se detuvo (codigo {result.ExitCode}). "
                        + "Consulta el log; no se ejecutara limpieza VHF.");
                }
            }
            if (limpiarVhf.Checked)
            {
                Write("Retirando exclusivamente ROOT\\FUTJOY01..08 y sus paquetes FUTUREO...");
                var result = await RunVhf("Eliminar");
                PrintProcess("FUTJOY VHF: eliminacion", result);
                if (result.ExitCode != 0)
                    throw new InvalidOperationException(
                        "Algunas partes de FUTJOY no se pudieron eliminar. "
                        + "Revisa el log y vuelve a escanear.");
            }
            Write("FIN. Cierra la GUI y reinicia Windows antes de reinstalar.");
            state.Text = needsRestart
                ? "Limpieza ejecutada. Reinicio necesario para finalizar."
                : "Limpieza ejecutada. Recomendado reiniciar antes de reinstalar.";
            MessageBox.Show(this,
                "Limpieza ejecutada. Revisa el registro y reinicia Windows "
                + "antes de instalar FUTUREO v0.6.0.\n\n"
                + "TESTSIGNING permanece sin cambios.",
                "FUTUREO - RESULTADO", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            errors = true;
            state.Text = "Limpieza incompleta. No reinstales sin revisar el registro.";
            ShowError(ex.Message);
        }
        finally
        {
            Write(errors ? "RESULTADO: revisar incidencias y volver a escanear." :
                "RESULTADO: limpieza finalizada.");
            SetBusy(false);
        }
    }
}
