using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;
using HIDMaestro;

namespace FutureoVJoyV080;

internal sealed class RuntimePad
{
    public int Slot { get; }
    public HMController Controller { get; }
    public HMButton Buttons = HMButton.None;
    public HMHat Hat = HMHat.None;
    public float X = .5f, Y = .5f;
    public long Transmissions;
    public DateTime LastAnalogEvent = DateTime.MinValue;
    public readonly List<string> Events = new();

    public RuntimePad(int slot, HMController controller)
    {
        Slot = slot;
        Controller = controller;
    }
}

internal sealed class FutureoForm : Form
{
    private HMContext? context;
    private readonly Dictionary<int, RuntimePad> pads = new();
    private readonly HashSet<int> overridden = new();

    private readonly Panel iniciarPage = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Panel probarPage = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Panel monitorPage = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Panel pages = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Button[] navigation = new Button[3];

    private readonly NumericUpDown quantity = new()
    {
        Minimum = 1, Maximum = 8, Value = 4, Width = 74,
        BackColor = Ui.PanelLight, ForeColor = Ui.White,
        Font = new Font("Segoe UI", 14, FontStyle.Bold)
    };
    private readonly Button start = Ui.Button("INSTALAR Y CREAR MANDOS", true);
    private readonly Button stop = Ui.Button("DETENER TODOS");
    private readonly Button joy = Ui.Button("ABRIR JOY.CPL");
    private readonly Button browser = Ui.Button("PROBAR NAVEGADOR");
    private readonly Button identify = Ui.Button("IDENTIFICAR SELECCIONADO", true);
    private readonly Button monitorAuto = Ui.Button("AUTO PRUEBA: BOTONES / ANALOGICO / CRUCETA", true);
    private readonly Button monitorRelease = Ui.Button("SOLTAR TODAS LAS ENTRADAS");
    private readonly Button release = Ui.Button("SOLTAR TODAS LAS ENTRADAS");
    private readonly Label systemStatus = Ui.Label("Motor no iniciado.", 12, true);
    private readonly ListBox deviceList = new()
    {
        Dock = DockStyle.Fill, BackColor = Ui.Panel, ForeColor = Ui.White,
        Font = new Font("Consolas", 11), BorderStyle = BorderStyle.FixedSingle
    };
    private readonly TextBox startupLog = new()
    {
        ReadOnly = true, Multiline = true, WordWrap = true,
        ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill,
        BackColor = Ui.Panel, ForeColor = Ui.White,
        Font = new Font("Consolas", 9.5f)
    };

    private readonly FlowLayoutPanel testSelectors = CreateSelector();
    private readonly FlowLayoutPanel monitorSelectors = CreateSelector();
    private readonly FlowLayoutPanel movement = new()
    {
        Dock = DockStyle.Fill, WrapContents = true, AutoScroll = true,
        BackColor = Ui.Panel
    };
    private readonly VirtualStick testStick = new();
    private readonly VirtualDpad testDpad = new();
    private readonly VirtualStick monitorStick = new() { Interactive = false, Size = new Size(190, 190) };
    private readonly VirtualDpad monitorDpad = new() { Interactive = false, Size = new Size(190, 190) };
    private readonly Dictionary<int, PadFaceButton> testButtons = new();
    private readonly Dictionary<int, Label> monitorButtons = new();

    private readonly CheckBox hold = new()
    {
        Text = "MANTENER BOTONES (activar/desactivar con clic)",
        ForeColor = Ui.White, AutoSize = true, Margin = new Padding(12, 15, 8, 4)
    };
    private readonly Label testInfo = Ui.Label("Inicia los mandos en la seccion 1.", 9);
    private readonly Label monitorInfo = Ui.Label("Sin mandos activos.", 10, true);
    private readonly Label analogInfo = Ui.Label("ANALOGICO X: 0%   Y: 0%", 11, true);
    private readonly Label dpadInfo = Ui.Label("D-PAD: CENTRO", 11, true);
    private readonly ListBox monitorEvents = new()
    {
        Dock = DockStyle.Fill, BackColor = Ui.Panel,
        ForeColor = Ui.White, Font = new Font("Consolas", 9.5f),
        HorizontalScrollbar = true, BorderStyle = BorderStyle.FixedSingle
    };
    private readonly Label footStatus = Ui.Label("v0.8.0 | Motor HIDMaestro UMDF2 | Portable | Windows x64", 9);
    private readonly Button[] modes = new Button[3];

    private int selectedSlot;
    private int monitorRenderedSlot = -1;
    private int currentSection;
    private int movementMode = 2; // 0=analogico, 1=cruceta, 2=mixto
    private bool busy;
    private bool identifying;
    private bool updating;
    private readonly System.Windows.Forms.Timer monitorTimer = new() { Interval = 60 };

    public FutureoForm()
    {
        Text = "FUTUREO VJOY v0.8.0 - PORTABLE | INICIAR / PROBAR / MONITOR";
        StartPosition = FormStartPosition.CenterScreen;
        Size = new Size(1250, 880);
        MinimumSize = new Size(1010, 725);
        BackColor = Ui.Background;
        ForeColor = Ui.White;
        Font = new Font("Segoe UI", 10f);
        AutoScaleMode = AutoScaleMode.Dpi;

        BuildRoot();
        BuildStartPage();
        BuildTestPage();
        BuildMonitorPage();
        SwitchSection(0);
        RefreshAll();

        start.Click += async (_, _) => await StartAsync();
        stop.Click += (_, _) => StopAll();
        joy.Click += (_, _) => OpenLink("control.exe", "joy.cpl");
        browser.Click += (_, _) => OpenLink("https://hardwaretester.com/gamepad");
        identify.Click += async (_, _) => await IdentifyAsync();
        monitorAuto.Click += async (_, _) => await IdentifyAsync();
        monitorRelease.Click += (_, _) => ReleaseSelected();
        release.Click += (_, _) => ReleaseSelected();
        testStick.Changed += OnAnalog;
        testDpad.Changed += OnDpad;
        monitorTimer.Tick += (_, _) => UpdateMonitor();
        monitorTimer.Start();
        FormClosing += OnClosing;

        Log("FUTUREO v0.8.0: 16 botones + joystick izquierdo X/Y + D-Pad 8 vias.");
        Log("INICIAR: instalar driver UMDF2 con consentimiento y crear 1 a 8 mandos.");
        Log("PROBAR: pulsa con el mouse para enviar entradas reales al mando seleccionado.");
        Log("MONITOR: muestra lo ENVIADO por FUTUREO, no una lectura independiente de Windows.");
        Log("Importante: cierra las versiones anteriores y juegos antes de iniciar.");
    }

    private static FlowLayoutPanel CreateSelector()
    {
        return new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false, AutoScroll = true, BackColor = Ui.Panel,
            Padding = new Padding(5, 3, 5, 3), Margin = new Padding(0)
        };
    }

    private static TableLayoutPanel Table(int rows, int cols, Color? background = null)
    {
        return new TableLayoutPanel
        {
            Dock = DockStyle.Fill, RowCount = rows, ColumnCount = cols,
            BackColor = background ?? Ui.Background, Margin = new Padding(0),
            Padding = new Padding(0)
        };
    }

    private void BuildRoot()
    {
        var root = Table(4, 1);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 83));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 56));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));
        Controls.Add(root);

        var header = new Panel { Dock = DockStyle.Fill, BackColor = Ui.Panel };
        var headline = new Label
        {
            Text = "FUTUREO  VJOY",
            Dock = DockStyle.Left, Width = 365,
            ForeColor = Ui.Cyan, Font = new Font("Segoe UI", 24, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(20, 0, 0, 0)
        };
        var headerRight = new Label
        {
            Text = "PORTABLE v0.8.0  |  16 BOTONES  /  D-PAD  /  ANALOGICO IZQUIERDO",
            Dock = DockStyle.Fill, ForeColor = Ui.White,
            TextAlign = ContentAlignment.MiddleRight, Padding = new Padding(0, 0, 22, 0),
            Font = new Font("Segoe UI", 10, FontStyle.Bold)
        };
        header.Controls.Add(headerRight);
        header.Controls.Add(headline);
        root.Controls.Add(header, 0, 0);

        var tabs = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, Padding = new Padding(16, 4, 4, 4),
            BackColor = Ui.PanelLight
        };
        string[] captions = { "01  INICIAR", "02  PROBAR", "03  MONITOR" };
        for (int i = 0; i < 3; i++)
        {
            var idx = i;
            var button = Ui.Button(captions[i]);
            button.Width = 175;
            button.Click += (_, _) => SwitchSection(idx);
            navigation[i] = button;
            tabs.Controls.Add(button);
        }
        root.Controls.Add(tabs, 0, 1);

        pages.Controls.Add(monitorPage);
        pages.Controls.Add(probarPage);
        pages.Controls.Add(iniciarPage);
        root.Controls.Add(pages, 0, 2);

        var bottom = new Panel { Dock = DockStyle.Fill, BackColor = Ui.Panel };
        footStatus.Dock = DockStyle.Fill;
        footStatus.TextAlign = ContentAlignment.MiddleLeft;
        footStatus.Padding = new Padding(12, 0, 0, 0);
        bottom.Controls.Add(footStatus);
        root.Controls.Add(bottom, 0, 3);
    }

    private void BuildStartPage()
    {
        var root = Table(5, 1);
        root.Padding = new Padding(18, 12, 18, 14);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 54));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 72));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 60));
        iniciarPage.Controls.Add(root);

        var title = Ui.Label("SECCION 1 - INICIAR MANDOS", 16, true);
        title.ForeColor = Ui.Cyan;
        title.Dock = DockStyle.Fill;
        root.Controls.Add(title, 0, 0);

        var toolbar = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, AutoScroll = true, WrapContents = false,
            BackColor = Ui.Panel, Padding = new Padding(10, 8, 10, 3)
        };
        var countLabel = Ui.Label("Cantidad de mandos:", 11, true);
        countLabel.Margin = new Padding(4, 14, 12, 4);
        quantity.Margin = new Padding(0, 7, 18, 3);
        start.Width = 285;
        stop.Width = 170;
        joy.Width = 162;
        toolbar.Controls.Add(countLabel);
        toolbar.Controls.Add(quantity);
        toolbar.Controls.Add(start);
        toolbar.Controls.Add(stop);
        toolbar.Controls.Add(joy);
        root.Controls.Add(toolbar, 0, 1);

        systemStatus.Dock = DockStyle.Fill;
        systemStatus.ForeColor = Ui.Green;
        systemStatus.TextAlign = ContentAlignment.MiddleLeft;
        root.Controls.Add(systemStatus, 0, 2);

        var body = Table(1, 2);
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 43));
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 57));
        root.Controls.Add(body, 0, 3);
        var devColumn = Table(2, 1, Ui.Panel);
        devColumn.RowStyles.Add(new RowStyle(SizeType.Absolute, 37));
        devColumn.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        devColumn.Padding = new Padding(8);
        devColumn.Controls.Add(Ui.Label("DISPOSITIVOS ACTIVOS", 12, true), 0, 0);
        devColumn.Controls.Add(deviceList, 0, 1);
        body.Controls.Add(devColumn, 0, 0);

        var logColumn = Table(2, 1, Ui.Panel);
        logColumn.RowStyles.Add(new RowStyle(SizeType.Absolute, 37));
        logColumn.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        logColumn.Padding = new Padding(8);
        logColumn.Controls.Add(Ui.Label("REGISTRO DE INICIO Y MOTOR", 12, true), 0, 0);
        logColumn.Controls.Add(startupLog, 0, 1);
        body.Controls.Add(logColumn, 1, 0);

        var note = Ui.Label(
            "El EXE es portable, pero el controlador HIDMaestro se instala en Windows con UAC. "
            + "Los mandos solo permanecen activos mientras el programa esta abierto. "
            + "La version v0.7.0 sigue disponible como respaldo.", 9);
        note.Dock = DockStyle.Fill;
        note.ForeColor = Ui.Gray;
        note.MaximumSize = new Size(1200, 0);
        root.Controls.Add(note, 0, 4);
    }

    private void BuildTestPage()
    {
        var root = Table(5, 1);
        root.Padding = new Padding(15, 10, 15, 11);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 45));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 54));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        probarPage.Controls.Add(root);

        root.Controls.Add(testSelectors, 0, 0);
        var toolbar = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Ui.PanelLight,
            WrapContents = false, AutoScroll = true, Padding = new Padding(4, 0, 0, 0)
        };
        string[] opts = { "ANALOGICO", "CRUCETA", "MIXTO" };
        for (int i = 0; i < 3; i++)
        {
            var idx = i;
            modes[i] = Ui.Button(opts[i]);
            modes[i].Width = 120;
            modes[i].Height = 39;
            modes[i].Click += (_, _) => SetMovementMode(idx);
            toolbar.Controls.Add(modes[i]);
        }
        toolbar.Controls.Add(hold);
        root.Controls.Add(toolbar, 0, 1);

        var main = Table(1, 2);
        main.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 39));
        main.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 61));
        root.Controls.Add(main, 0, 2);

        var left = Table(2, 1, Ui.Panel);
        left.RowStyles.Add(new RowStyle(SizeType.Absolute, 35));
        left.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        left.Padding = new Padding(7);
        left.Controls.Add(Ui.Label("MOVIMIENTO - JOYSTICK IZQUIERDO Y D-PAD", 10, true), 0, 0);
        left.Controls.Add(movement, 0, 1);
        main.Controls.Add(left, 0, 0);

        testStick.Margin = new Padding(10, 10, 10, 10);
        testDpad.Margin = new Padding(10, 10, 10, 10);
        movement.Controls.Add(testStick);
        movement.Controls.Add(testDpad);

        var right = Table(4, 1, Ui.Panel);
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 35));
        right.RowStyles.Add(new RowStyle(SizeType.Percent, 56));
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 57));
        right.RowStyles.Add(new RowStyle(SizeType.Percent, 44));
        right.Padding = new Padding(7);
        right.Controls.Add(Ui.Label("ACCIONES - 16 BOTONES", 12, true), 0, 0);

        var large = Table(2, 3, Ui.Panel);
        for (int c = 0; c < 3; c++) large.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / 3));
        for (int r = 0; r < 2; r++) large.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
        for (int i = 0; i < 6; i++)
        {
            var b = MakePadButton(i, true);
            large.Controls.Add(b, i % 3, i / 3);
        }
        right.Controls.Add(large, 0, 1);

        var smallPair = Table(1, 2, Ui.Panel);
        smallPair.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        smallPair.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        for (int i = 6; i < 8; i++) smallPair.Controls.Add(MakePadButton(i, false), i - 6, 0);
        right.Controls.Add(smallPair, 0, 2);

        var extra = Table(2, 4, Ui.Panel);
        for (int c = 0; c < 4; c++) extra.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
        extra.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
        extra.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
        for (int i = 8; i < 16; i++) extra.Controls.Add(MakePadButton(i, false), (i - 8) % 4, (i - 8) / 4);
        right.Controls.Add(extra, 0, 3);

        main.Controls.Add(right, 1, 0);

        var controls = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Ui.PanelLight,
            AutoScroll = true, WrapContents = false, Padding = new Padding(6, 2, 0, 1)
        };
        identify.Width = 270;
        release.Width = 270;
        browser.Width = 210;
        controls.Controls.Add(identify);
        controls.Controls.Add(release);
        controls.Controls.Add(browser);
        root.Controls.Add(controls, 0, 3);

        testInfo.Dock = DockStyle.Fill;
        testInfo.ForeColor = Ui.Gray;
        testInfo.TextAlign = ContentAlignment.MiddleLeft;
        root.Controls.Add(testInfo, 0, 4);
        SetMovementMode(2);
    }

    private PadFaceButton MakePadButton(int i, bool large)
    {
        var b = new PadFaceButton(PadButtonSpec.All[i], large)
        {
            Dock = DockStyle.Fill, Margin = new Padding(3),
            MinimumSize = new Size(26, 32)
        };
        b.Changed += OnButton;
        testButtons[i] = b;
        return b;
    }

    private void BuildMonitorPage()
    {
        var root = Table(4, 1);
        root.Padding = new Padding(15, 12, 15, 12);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 51));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 55));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        monitorPage.Controls.Add(root);
        root.Controls.Add(monitorSelectors, 0, 0);
        monitorInfo.Dock = DockStyle.Fill;
        monitorInfo.ForeColor = Ui.Cyan;
        monitorInfo.TextAlign = ContentAlignment.MiddleLeft;
        root.Controls.Add(monitorInfo, 0, 1);
        var monitorActions = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Ui.PanelLight,
            AutoScroll = true, WrapContents = false, Padding = new Padding(4, 2, 0, 2)
        };
        monitorAuto.Width = 360;
        monitorRelease.Width = 275;
        monitorActions.Controls.Add(monitorAuto);
        monitorActions.Controls.Add(monitorRelease);
        root.Controls.Add(monitorActions, 0, 2);

        var columns = Table(1, 2);
        columns.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 57));
        columns.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 43));
        root.Controls.Add(columns, 0, 3);

        var left = Table(4, 1, Ui.Panel);
        left.Padding = new Padding(10);
        left.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        left.RowStyles.Add(new RowStyle(SizeType.Percent, 46));
        left.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        left.RowStyles.Add(new RowStyle(SizeType.Percent, 54));
        left.Controls.Add(Ui.Label("SENALES ENVIADAS POR LA APLICACION", 11, true), 0, 0);
        columns.Controls.Add(left, 0, 0);

        var figures = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Ui.Panel,
            WrapContents = false, AutoScroll = true
        };
        monitorStick.Margin = new Padding(5);
        monitorDpad.Margin = new Padding(5);
        figures.Controls.Add(monitorStick);
        figures.Controls.Add(monitorDpad);
        var labels = new Panel { Width = 160, Height = 130, BackColor = Ui.Panel };
        analogInfo.Location = new Point(2, 20);
        analogInfo.AutoSize = false;
        analogInfo.Width = 157;
        analogInfo.Height = 45;
        dpadInfo.Location = new Point(2, 79);
        dpadInfo.AutoSize = false;
        dpadInfo.Width = 157;
        labels.Controls.Add(analogInfo);
        labels.Controls.Add(dpadInfo);
        figures.Controls.Add(labels);
        left.Controls.Add(figures, 0, 1);
        left.Controls.Add(Ui.Label("ESTADO DE LOS 16 BOTONES  |  VERDE = PRESIONADO", 10, true), 0, 2);

        var ledGrid = Table(4, 4, Ui.Panel);
        for (int i = 0; i < 4; i++)
        {
            ledGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
            ledGrid.RowStyles.Add(new RowStyle(SizeType.Percent, 25));
        }
        for (int i = 0; i < 16; i++)
        {
            var spec = PadButtonSpec.All[i];
            var label = new Label
            {
                Text = $"{spec.Index + 1:00}  {spec.Label}",
                ForeColor = Ui.White, BackColor = Ui.PanelLight,
                Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
                Margin = new Padding(4),
                Font = new Font("Segoe UI", 10, FontStyle.Bold)
            };
            monitorButtons[i] = label;
            ledGrid.Controls.Add(label, i % 4, i / 4);
        }
        left.Controls.Add(ledGrid, 0, 3);

        var right = Table(3, 1, Ui.Panel);
        right.Padding = new Padding(10);
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));
        right.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));
        right.Controls.Add(Ui.Label("REGISTRO CRONOLOGICO DE EVENTOS", 11, true), 0, 0);
        right.Controls.Add(monitorEvents, 0, 1);
        var note = Ui.Label("Este monitor registra lo que FUTUREO envia al mando virtual. "
            + "No es una lectura USB/HID independiente ni confirma que un juego lo haya recibido.", 9);
        note.Dock = DockStyle.Fill;
        note.ForeColor = Ui.Gray;
        right.Controls.Add(note, 0, 2);
        columns.Controls.Add(right, 1, 0);
    }

    private void SwitchSection(int section)
    {
        if (!identifying && currentSection == 1 && section != 1 &&
            pads.ContainsKey(selectedSlot))
            ReleaseSelected();
        currentSection = section;
        iniciarPage.Visible = section == 0;
        probarPage.Visible = section == 1;
        monitorPage.Visible = section == 2;
        for (int i = 0; i < navigation.Length; i++)
        {
            if (navigation[i] is null) continue;
            navigation[i].BackColor = i == section ? Color.FromArgb(26, 125, 174) : Ui.Panel;
        }
        RefreshAll();
    }

    private static void OpenLink(string executableOrUrl, string? argument = null)
    {
        try
        {
            Process.Start(new ProcessStartInfo(executableOrUrl, argument ?? string.Empty)
            {
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            MessageBox.Show("No se pudo abrir: " + ex.Message, "FUTUREO VJOY",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private static HMProfile Profile(int slot)
    {
        var name = $"FUTUREO_VJOY{slot}";
        return new HMProfileBuilder()
            .Id($"futureo-portable-v080-p{slot}")
            .Name(name).DeviceDescription(name).ProductString(name)
            .ManufacturerString("FUTUREO LAB").Vendor("FUTUREO LAB")
            .Vid(0xF7A0).Pid((ushort)(0x2200 + slot))
            .Type("gamepad").Connection("usb")
            .FromDescriptorBuilder(new HidDescriptorBuilder()
                .Gamepad()
                .AddStick("Left", bits: 16)
                .AddButtons(16)
                .AddHat(8))
            .Build();
    }

    private void Log(string message)
    {
        if (IsDisposed) return;
        startupLog.AppendText($"[{DateTime.Now:HH:mm:ss}] {message}{Environment.NewLine}");
    }

    private void SetBusy(bool value)
    {
        busy = value;
        start.Enabled = !busy && pads.Count == 0;
        stop.Enabled = !busy && !identifying && pads.Count > 0;
        quantity.Enabled = !busy && pads.Count == 0;
        probarPage.Enabled = !busy && pads.Count > 0;
        for (int i = 0; i < navigation.Length; i++)
            if (navigation[i] is not null) navigation[i].Enabled = !busy;
    }

    private async Task StartAsync()
    {
        if (busy || pads.Count > 0) return;
        int total = (int)quantity.Value;
        if (MessageBox.Show(this,
                $"FUTUREO VJOY PORTABLE v0.8.0\n\n"
                + $"Instalar el controlador UMDF2 de HIDMaestro y crear {total} mandos.\n"
                + "Cada mando tendra 16 botones, 1 joystick analogico izquierdo y D-Pad de 8 vias.\n\n"
                + "Se instalaran componentes y un certificado local de terceros en Windows.\n"
                + "La aplicacion NO cambia TESTSIGNING ni elimina mandos VHF antiguos.\n"
                + "Cierra las otras versiones de FUTUREO antes de continuar.\n\n"
                + "¿Autorizas la instalacion y creacion?",
                "CONSENTIMIENTO PARA CONTROLADOR HID",
                MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;

        SetBusy(true);
        systemStatus.Text = "Preparando controlador y creando mandos...";
        Log("Instalacion UMDF2 autorizada. Creando hasta " + total + " mandos.");
        try
        {
            var result = await Task.Run(() =>
            {
                HMContext ctx = context ?? new HMContext(HMBackend.Umdf2);
                var created = new Dictionary<int, HMController>();
                var claimed = new List<int>();
                try
                {
                    ctx.InstallDriver();
                    for (int slot = 1; slot <= total; slot++)
                    {
                        var controller = ctx.CreateController(
                            Profile(slot), $"futureo-portable-v080-slot-{slot}", HMBackend.Umdf2);
                        created.Add(slot, controller);
                        // HIDMaestro backs up all three OEM name values before changing them.
                        HMOemNameOverride.Set(0xF7A0, (ushort)(0x2200 + slot),
                            $"FUTUREO_VJOY{slot}");
                        claimed.Add(slot);
                    }
                    return (Context: ctx, Created: created, Claimed: claimed);
                }
                catch
                {
                    foreach (var item in created.Values)
                    {
                        try { item.Dispose(); } catch { }
                    }
                    foreach (int slot in claimed)
                    {
                        try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
                        catch { }
                    }
                    if (context is null)
                    {
                        try { ctx.Dispose(); } catch { }
                    }
                    throw;
                }
            });
            context = result.Context;
            foreach (var item in result.Created)
                pads.Add(item.Key, new RuntimePad(item.Key, item.Value));
            foreach (var slot in result.Claimed)
                overridden.Add(slot);
            selectedSlot = 1;
            ReloadMonitorEvents();
            systemStatus.Text = $"Motor activo: {pads.Count} mandos independientes.";
            Log($"OK: {pads.Count} mandos HID creados con nombres FUTUREO_VJOY1..FUTUREO_VJOY{total}.");
            Record(pads[1], "MANDO INICIADO - listo para recibir entradas");
            SwitchSection(1);
        }
        catch (Exception ex)
        {
            systemStatus.Text = "Error al instalar o crear mandos. Revisa el registro.";
            Log("ERROR: " + ex.Message);
            MessageBox.Show(this, ex.Message, "FUTUREO - INSTALACION",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            SetBusy(false);
            RefreshAll();
        }
    }

    private void StopAll()
    {
        if (busy || pads.Count == 0) return;
        ReleaseSelected();
        foreach (var pad in pads.Values)
        {
            try
            {
                pad.Controller.SubmitState(new HMGamepadState
                {
                    Axes = new Dictionary<HMAxis, float>
                    {
                        [HMAxis.X] = .5f, [HMAxis.Y] = .5f
                    },
                    Buttons = HMButton.None, Hat = HMHat.None
                });
                pad.Controller.Dispose();
            }
            catch (Exception ex) { Log($"P{pad.Slot}: error al retirar: {ex.Message}"); }
        }
        pads.Clear();
        foreach (var slot in overridden.OrderByDescending(x => x))
        {
            try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
            catch (Exception ex) { Log($"P{slot}: pendiente de restaurar OEM: {ex.Message}"); }
        }
        overridden.Clear();
        selectedSlot = 0;
        ReloadMonitorEvents();
        systemStatus.Text = "Mandos retirados. Motor instalado en Windows permanece disponible.";
        Log("Mandos de FUTUREO retirados; nombre OEM restaurado cuando fue posible.");
        RefreshAll();
    }

    private void OnClosing(object? sender, FormClosingEventArgs e)
    {
        if (busy || identifying)
        {
            e.Cancel = true;
            Log("Operacion en curso. Espera a que termine antes de cerrar.");
            return;
        }
        monitorTimer.Stop();
        StopAll();
        try { context?.Dispose(); } catch (Exception ex) { Log(ex.Message); }
        context = null;
    }

    private void RefreshAll()
    {
        RefreshSelectors();
        deviceList.BeginUpdate();
        deviceList.Items.Clear();
        foreach (var pad in pads.Values.OrderBy(p => p.Slot))
        {
            deviceList.Items.Add(
                $"P{pad.Slot}  FUTUREO_VJOY{pad.Slot}  |  VID F7A0 PID {0x2200 + pad.Slot:X4}"
                + "  |  16 botones + X/Y + D-Pad");
        }
        deviceList.EndUpdate();
        if (pads.Count == 0) deviceList.Items.Add("Sin mandos activos.");

        start.Enabled = !busy && pads.Count == 0;
        stop.Enabled = !busy && !identifying && pads.Count > 0;
        identify.Enabled = !busy && !identifying && pads.ContainsKey(selectedSlot);
        monitorAuto.Enabled = !busy && !identifying && pads.ContainsKey(selectedSlot);
        monitorRelease.Enabled = !busy && !identifying && pads.ContainsKey(selectedSlot);
        release.Enabled = !busy && !identifying && pads.ContainsKey(selectedSlot);
        probarPage.Enabled = !busy && pads.Count > 0;
        RefreshTestButtons();
        UpdateMonitor();
        footStatus.Text = $"FUTUREO v0.8.0  |  {pads.Count} mando(s) activo(s)  |  "
            + (pads.ContainsKey(selectedSlot) ? $"Seleccionado: FUTUREO_VJOY{selectedSlot}" : "Sin seleccion")
            + "  |  Monitor de senales ENVIADAS";
    }

    private void RefreshSelectors()
    {
        UpdateSelector(testSelectors);
        UpdateSelector(monitorSelectors);
    }

    private void UpdateSelector(FlowLayoutPanel strip)
    {
        strip.SuspendLayout();
        while (strip.Controls.Count > 0)
        {
            var item = strip.Controls[0];
            strip.Controls.RemoveAt(0);
            item.Dispose();
        }
        if (pads.Count == 0)
        {
            strip.Controls.Add(Ui.Label("Sin mandos activos. Abre INICIAR y crea los mandos.", 10, true));
        }
        else
        {
            foreach (int slot in pads.Keys.OrderBy(x => x))
            {
                int capturedSlot = slot;
                var button = Ui.Button($"FUTUREO_VJOY{slot}");
                button.Height = 34;
                button.Width = 155;
                button.BackColor = slot == selectedSlot ? Color.FromArgb(27, 129, 177) : Ui.PanelLight;
                button.Click += (_, _) => SelectPad(capturedSlot);
                strip.Controls.Add(button);
            }
        }
        strip.ResumeLayout();
    }

    private void SelectPad(int slot)
    {
        if (busy || identifying || !pads.ContainsKey(slot) || selectedSlot == slot) return;
        if (pads.ContainsKey(selectedSlot)) ReleaseSelected();
        selectedSlot = slot;
        ReloadMonitorEvents();
        RefreshAll();
        Record(pads[slot], $"SELECCIONADO FUTUREO_VJOY{slot}");
    }

    private void SetMovementMode(int mode)
    {
        if (mode < 0 || mode > 2) return;
        if (pads.ContainsKey(selectedSlot) && movementMode != mode)
            ReleaseSelected();
        movementMode = mode;
        testStick.Visible = mode != 1;
        testDpad.Visible = mode != 0;
        var mixed = mode == 2;
        testStick.Size = mixed ? new Size(190, 190) : new Size(324, 324);
        testDpad.Size = mixed ? new Size(190, 190) : new Size(324, 324);
        for (int i = 0; i < modes.Length; i++)
            if (modes[i] is not null)
                modes[i].BackColor = mode == i ? Color.FromArgb(27, 129, 177) : Ui.PanelLight;
    }

    private void OnButton(int index, bool pressed)
    {
        if (updating || busy || identifying || !pads.TryGetValue(selectedSlot, out var pad)) return;
        var spec = PadButtonSpec.All[index];
        var wasPressed = (pad.Buttons & spec.Code) != 0;
        bool next;
        if (hold.Checked)
        {
            if (!pressed) return;
            next = !wasPressed;
        }
        else next = pressed;
        if (next == wasPressed) return;
        if (next) pad.Buttons |= spec.Code;
        else pad.Buttons &= ~spec.Code;
        Send(pad);
        Record(pad, $"BOTON {index + 1:00} {spec.Label}: {(next ? "PRESIONADO" : "LIBERADO")}");
        RefreshTestButtons();
    }

    private void OnAnalog(float x, float y)
    {
        if (updating || busy || identifying || movementMode == 1 ||
            !pads.TryGetValue(selectedSlot, out var pad)) return;
        if (MathF.Abs(pad.X - x) < .003f && MathF.Abs(pad.Y - y) < .003f) return;
        pad.X = x;
        pad.Y = y;
        Send(pad);
        if ((DateTime.UtcNow - pad.LastAnalogEvent).TotalMilliseconds > 160 ||
            MathF.Abs(x - .5f) < .005f && MathF.Abs(y - .5f) < .005f)
        {
            Record(pad, $"ANALOG X: {MathF.Round((x - .5f) * 200):+0;-0;0}%"
                + $"  Y: {MathF.Round((y - .5f) * 200):+0;-0;0}%");
            pad.LastAnalogEvent = DateTime.UtcNow;
        }
    }

    private void OnDpad(HMHat direction)
    {
        if (updating || busy || identifying || movementMode == 0 ||
            !pads.TryGetValue(selectedSlot, out var pad)) return;
        if (pad.Hat == direction) return;
        pad.Hat = direction;
        Send(pad);
        Record(pad, $"D-PAD: {direction}");
    }

    private void ReleaseSelected()
    {
        if (!pads.TryGetValue(selectedSlot, out var pad)) return;
        var changed = pad.Buttons != HMButton.None || pad.Hat != HMHat.None ||
            MathF.Abs(pad.X - .5f) > .003f || MathF.Abs(pad.Y - .5f) > .003f;
        pad.Buttons = HMButton.None;
        pad.Hat = HMHat.None;
        pad.X = pad.Y = .5f;
        Send(pad);
        if (changed) Record(pad, "ENTRADAS LIBERADAS / CENTRO");
        RefreshTestButtons();
    }

    private void RefreshTestButtons()
    {
        updating = true;
        try
        {
            var active = pads.TryGetValue(selectedSlot, out var pad);
            foreach (var (index, control) in testButtons)
            {
                control.Active = active && (pad!.Buttons & PadButtonSpec.All[index].Code) != 0;
                control.Enabled = active && !busy && !identifying;
                control.Invalidate();
            }
            testStick.Interactive = active && !busy && !identifying;
            testDpad.Interactive = active && !busy && !identifying;
            testStick.Display(active ? pad!.X : .5f, active ? pad!.Y : .5f);
            testDpad.Display(active ? pad!.Hat : HMHat.None);
            testInfo.Text = active
                ? $"ENVIANDO A FUTUREO_VJOY{selectedSlot} | "
                    + "Mantén pulsado con el mouse o activa MANTENER para combinar botones."
                : "Para probar, primero crea mandos en INICIAR.";
        }
        finally { updating = false; }
    }

    private bool Send(RuntimePad pad)
    {
        try
        {
            pad.Controller.SubmitState(new HMGamepadState
            {
                Buttons = pad.Buttons,
                Hat = pad.Hat,
                Axes = new Dictionary<HMAxis, float>
                {
                    [HMAxis.X] = pad.X,
                    [HMAxis.Y] = pad.Y
                }
            });
            pad.Transmissions++;
            return true;
        }
        catch (Exception ex)
        {
            systemStatus.Text = $"ERROR: No se pudo enviar entrada a P{pad.Slot}.";
            Log($"ERROR P{pad.Slot} de transmision: {ex.Message}");
            return false;
        }
    }

    private void Record(RuntimePad pad, string description)
    {
        var line = $"[{DateTime.Now:HH:mm:ss.fff}] P{pad.Slot}: {description}";
        pad.Events.Insert(0, line);
        if (pad.Events.Count > 250) pad.Events.RemoveAt(pad.Events.Count - 1);
        if (currentSection == 2 && selectedSlot == pad.Slot)
        {
            monitorEvents.Items.Insert(0, line);
            if (monitorEvents.Items.Count > 250)
                monitorEvents.Items.RemoveAt(monitorEvents.Items.Count - 1);
        }
    }

    private void ReloadMonitorEvents()
    {
        monitorRenderedSlot = selectedSlot;
        monitorEvents.BeginUpdate();
        try
        {
            monitorEvents.Items.Clear();
            if (pads.TryGetValue(selectedSlot, out var pad))
                foreach (var item in pad.Events)
                    monitorEvents.Items.Add(item);
        }
        finally { monitorEvents.EndUpdate(); }
    }

    private void UpdateMonitor()
    {
        if (IsDisposed || updating) return;
        if (monitorRenderedSlot != selectedSlot) ReloadMonitorEvents();
        var active = pads.TryGetValue(selectedSlot, out var pad);
        monitorInfo.Text = active
            ? $"FUTUREO_VJOY{selectedSlot} | TRANSMISIONES: {pad!.Transmissions} | "
                + $"BOTONES PULSADOS: {PadButtonSpec.All.Count(s => (pad.Buttons & s.Code) != 0)}"
            : "SIN MANDOS ACTIVOS. Entra en la seccion INICIAR.";
        monitorStick.Display(active ? pad!.X : .5f, active ? pad!.Y : .5f);
        monitorDpad.Display(active ? pad!.Hat : HMHat.None);
        analogInfo.Text = active
            ? $"X {MathF.Round((pad!.X - .5f) * 200):+0;-0;0}%\n"
                + $"Y {MathF.Round((pad.Y - .5f) * 200):+0;-0;0}%"
            : "X 0%\nY 0%";
        dpadInfo.Text = active ? $"D-PAD:\n{pad!.Hat}" : "D-PAD:\nCENTRO";
        foreach (var (index, label) in monitorButtons)
        {
            bool on = active && (pad!.Buttons & PadButtonSpec.All[index].Code) != 0;
            var wanted = on ? Color.FromArgb(22, 126, 98) : Ui.PanelLight;
            if (label.BackColor != wanted) label.BackColor = wanted;
        }
    }

    private async Task IdentifyAsync()
    {
        if (busy || identifying || !pads.TryGetValue(selectedSlot, out var pad)) return;
        identifying = true;
        RefreshAll();
        RefreshTestButtons();
        identify.Enabled = false;
        monitorAuto.Enabled = false;
        monitorRelease.Enabled = false;
        Record(pad, "IDENTIFICAR: comienza en 3 segundos - abre joy.cpl.");
        try
        {
            await Task.Delay(3000);
            for (int i = 0; i < 3; i++)
            {
                pad.X = .92f; pad.Y = .5f; pad.Buttons = HMButton.A; pad.Hat = HMHat.North;
                Send(pad);
                Record(pad, "IDENTIFICAR: X + boton A + D-Pad NORTE");
                await Task.Delay(420);
                pad.X = .5f; pad.Y = .5f; pad.Buttons = HMButton.None; pad.Hat = HMHat.None;
                Send(pad);
                Record(pad, "IDENTIFICAR: centro y botones libres");
                await Task.Delay(320);
            }
        }
        catch (Exception ex) { Log("Identificacion: " + ex.Message); }
        finally
        {
            pad.X = pad.Y = .5f; pad.Buttons = HMButton.None; pad.Hat = HMHat.None;
            Send(pad);
            identifying = false;
            RefreshAll();
        }
    }
}
