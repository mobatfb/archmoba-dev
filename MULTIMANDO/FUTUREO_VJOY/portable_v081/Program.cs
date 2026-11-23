using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;
using System.Windows.Forms;
using HIDMaestro;

namespace FutureoVJoyV081;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        // Test isolated EXE without touching Windows drivers/certificates.
        if (args.Length == 2 && args[0] == "--self-test")
        {
            try
            {
                var sdk = typeof(HMBuildInfo).Assembly;
                var resources = sdk.GetManifestResourceNames().Length;
                var included = HMBuildInfo.DriverArchitectures.Contains(Architecture.X64);
                var reversibleNames = typeof(HMOemNameOverride).GetMethod("Set") is not null;
                var descriptor = new HidDescriptorBuilder()
                    .Gamepad().AddStick("Left", bits: 16).AddButtons(16).AddHat(8).Build();
                var hatUsage = false;
                for (var i = 0; i < descriptor.Length - 1; i++)
                {
                    if (descriptor[i] == 0x09 && descriptor[i + 1] == 0x39)
                    {
                        hatUsage = true;
                        break;
                    }
                }

                File.WriteAllText(args[1],
                    $"UMDF2 x64 embedded: {included}\n"
                    + $"OEM API: {reversibleNames}\n"
                    + $"Resource count: {resources}\n"
                    + $"Descriptor bytes: {descriptor.Length}\n"
                    + $"HID hat present: {hatUsage}\n"
                    + "Buttons: 16\nAnalog: X+Y\nDPad: 8-way\n"
                    + "Monitor: signals submitted by this application, not physical readback\n");

                if (!included || !reversibleNames || resources < 10 ||
                    !hatUsage || descriptor.Length < 30)
                    Environment.ExitCode = 21;
            }
            catch (Exception ex)
            {
                try { File.WriteAllText(args[1], "SELFTEST ERROR: " + ex); }
                catch { }
                Environment.ExitCode = 22;
            }
            return;
        }

        // Integrated WinForms layout smoke test, no driver or privilege changes.
        if (args.Length == 2 && args[0] == "--ui-smoke")
        {
            try
            {
                ApplicationConfiguration.Initialize();
                using var smoke = new FutureoForm();
                smoke.RunUiSmoke();
                File.WriteAllText(args[1],
                    "UI smoke: OK; 3 tabs, mini view, foldable groups, 16 test buttons and LEDs.");
            }
            catch (Exception ex)
            {
                try { File.WriteAllText(args[1], "UI smoke failed: " + ex); } catch { }
                Environment.ExitCode = 23;
            }
            return;
        }

        ApplicationConfiguration.Initialize();
        using var oneInstance = new Mutex(true, @"Local\FUTUREO_VJOY_PORTABLE_V080", out var first);
        if (!first)
        {
            MessageBox.Show("FUTUREO VJOY v0.8.0 ya esta abierto. Usa esa ventana.",
                "FUTUREO VJOY", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

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
                        "La instalacion del CONTROLADOR requiere permisos de administrador.\n"
                        + "Ejecuta el EXE con clic derecho > Ejecutar como administrador.\n\n"
                        + ex.Message, "FUTUREO VJOY", MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                }
                return;
            }
        }
        Application.Run(new FutureoForm());
    }
}
