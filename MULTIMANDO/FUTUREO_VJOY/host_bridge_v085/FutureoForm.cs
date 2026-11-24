using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using System.Text.Json;
using System.Windows.Forms;
using HIDMaestro;

namespace FutureoVJoyV085;

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
    public string RemoteSession = "";
    public long RemoteSequence;
    public DateTime RemoteTouched = DateTime.MinValue;
    public DateTime RemoteLogAt = DateTime.MinValue;
    public DateTime RemoteLastSubmit = DateTime.MinValue;

    public RuntimePad(int slot, HMController controller)
    {
        Slot = slot;
        Controller = controller;
    }
}

internal sealed class FutureoForm : Form
{
    private HMContext? context;
    private readonly BrowserBridge browserBridge = new();
    private readonly HostInputBridge hostInput = new();
    private readonly ConcurrentDictionary<int, HostPadInput> remoteLatest = new();
    private int[] hostPadSlots = Array.Empty<int>();
    private bool hostClosing;
    private readonly Label browserIndicator = Ui.Label("WEB AUTOMATICO", 9, true);
    private readonly Dictionary<int, RuntimePad> pads = new();
    private readonly HashSet<int> overridden = new();

    private readonly Panel iniciarPage = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Panel probarPage = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Panel monitorPage = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Panel pages = new() { Dock = DockStyle.Fill, BackColor = Ui.Background };
    private readonly Button[] navigation = new Button[3];
    private readonly Button miniButton = Ui.Button("VISTA AMPLIADA");
    private readonly Button foldStartList = Ui.Button("PLEGAR LISTA");
    private readonly Button foldStartLog = Ui.Button("PLEGAR LOG");
    private readonly Button foldTestMotion = Ui.Button("PLEGAR MOV.");
    private readonly Button foldTestButtons = Ui.Button("PLEGAR BOT.");
    private readonly Button foldMonitorVisual = Ui.Button("PLEGAR VISTA");
    private readonly Button foldMonitorLog = Ui.Button("PLEGAR HIST.");
    private TableLayoutPanel? startColumns, testColumns, monitorColumns;
    private Control? startListPanel, startLogPanel;
    private Control? testMotionPanel, testButtonsPanel;
    private Control? monitorVisualPanel, monitorLogPanel;
    private bool startListFolded, startLogFolded, testMotionFolded, testButtonsFolded;
    private bool monitorVisualFolded, monitorLogFolded;
    private bool miniView = true;

    private readonly NumericUpDown quantity = new()
    {
        Minimum = 1, Maximum = 8, Value = 4, Width = 54,
        BackColor = Ui.PanelLight, ForeColor = Ui.White,
        Font = new Font("Segoe UI", 11, FontStyle.Bold)
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
        Font = new Font("Consolas", 9), BorderStyle = BorderStyle.FixedSingle
    };
    private readonly TextBox startupLog = new()
    {
        ReadOnly = true, Multiline = true, WordWrap = true,
        ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill,
        BackColor = Ui.Panel, ForeColor = Ui.White,
        Font = new Font("Consolas", 8.5f)
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
    private readonly VirtualStick monitorStick = new() { Interactive = false, Size = new Size(125, 125) };
    private readonly VirtualDpad monitorDpad = new() { Interactive = false, Size = new Size(125, 125) };
    private readonly Dictionary<int, PadFaceButton> testButtons = new();
    private readonly Dictionary<int, Label> monitorButtons = new();

    private readonly CheckBox hold = new()
    {
        Text = "MANTENER BOTONES",
        ForeColor = Ui.White, AutoSize = true, Margin = new Padding(7, 8, 4, 1),
        Font = new Font("Segoe UI", 8.5f)
    };
    private readonly Label testInfo = Ui.Label("Inicia los mandos en la seccion 1.", 9);
    private readonly Label monitorInfo = Ui.Label("Sin mandos activos.", 10, true);
    private readonly Label analogInfo = Ui.Label("ANALOGICO X: 0%   Y: 0%", 11, true);
    private readonly Label dpadInfo = Ui.Label("D-PAD: CENTRO", 11, true);
    private readonly ListBox monitorEvents = new()
    {
        Dock = DockStyle.Fill, BackColor = Ui.Panel,
        ForeColor = Ui.White, Font = new Font("Consolas", 8.5f),
        HorizontalScrollbar = true, BorderStyle = BorderStyle.FixedSingle
    };
    private readonly Label footStatus = Ui.Label("v0.8.5 | Motor HIDMaestro UMDF2 | Portable | Windows x64", 9);
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
        Text = "FUTUREO VJOY v0.8.5 - PORTABLE | INICIAR / PROBAR / MONITOR";
        StartPosition = FormStartPosition.CenterScreen;
        Size = new Size(930, 650);
        MinimumSize = new Size(715, 510);
        BackColor = Ui.Background;
        ForeColor = Ui.White;
        Font = new Font("Segoe UI", 9f);
        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScroll = false;

        BuildRoot();
        BuildStartPage();
        BuildTestPage();
        BuildMonitorPage();
        WireFoldButtons();
        ApplyFoldLayouts();
        SwitchSection(0);
        RefreshAll();

        start.Click += async (_, _) => await StartAsync();
        stop.Click += (_, _) => StopAll();
        joy.Click += (_, _) => OpenLink("control.exe", "joy.cpl");
        browser.Click += (_, _) => OpenLink("https://hardwaretester.com/gamepad");
        if (browserBridge.Start())
        {
            browserIndicator.ForeColor = Ui.Green;
            Log("NAVEGADOR AUTOMATICO activo en 127.0.0.1:38471. Sin claves ni autorizacion por pagina.");
        }
        else
        {
            browserIndicator.ForeColor = Color.OrangeRed;
            browserIndicator.Text = "WEB SIN CONEXION";
            Log("NAVEGADOR AUTOMATICO no disponible: " + browserBridge.Status
                + ". Cierra otras versiones de FUTUREO que utilicen el puerto.");
        }
        hostInput.GetSlots = () => System.Threading.Volatile.Read(ref hostPadSlots);
        hostInput.ApplyInput = QueueHostInput;
        hostInput.ApplyCapacity = ResizeForHostAsync;
        if (hostInput.Start())
            Log("MULTIMANDO anfitrion listo en 127.0.0.1:38472; permite 1-8 jugadores sin cerrar la sala.");
        else
            Log("MULTIMANDO anfitrion: puerto ocupado o no disponible: " + hostInput.Status);
        identify.Click += async (_, _) => await IdentifyAsync();
        monitorAuto.Click += async (_, _) => await IdentifyAsync();
        monitorRelease.Click += (_, _) => ReleaseSelected();
        release.Click += (_, _) => ReleaseSelected();
        testStick.Changed += OnAnalog;
        testDpad.Changed += OnDpad;
        monitorTimer.Tick += (_, _) =>
        {
            DrainHostInput();
            UpdateMonitor();
        };
        monitorTimer.Start();
        FormClosing += OnClosing;

        Log("FUTUREO v0.8.5: 16 botones + joystick izquierdo X/Y + D-Pad 8 vias.");
        Log("ANTI-DERIVA: reenvio HID de estado cada 450 ms y reintento en errores.");
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
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 57));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 43));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 26));
        Controls.Add(root);

        var header = new Panel { Dock = DockStyle.Fill, BackColor = Ui.Panel };
        var headline = new Label
        {
            Text = "FUTUREO  VJOY",
            Dock = DockStyle.Left, Width = 249,
            ForeColor = Ui.Cyan, Font = new Font("Segoe UI", 18, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(12, 0, 0, 0)
        };
        var headerRight = new Label
        {
            Text = "16 BOTONES  |  D-PAD  |  ANALOGICO IZQUIERDO",
            Dock = DockStyle.Fill, ForeColor = Ui.White,
            TextAlign = ContentAlignment.MiddleRight, Padding = new Padding(0, 0, 12, 0),
            Font = new Font("Segoe UI", 8, FontStyle.Bold)
        };
        header.Controls.Add(headerRight);
        header.Controls.Add(headline);
        root.Controls.Add(header, 0, 0);

        var tabs = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, Padding = new Padding(7, 3, 4, 2),
            AutoScroll = true, WrapContents = false, BackColor = Ui.PanelLight
        };
        string[] captions = { "01  INICIAR", "02  PROBAR", "03  MONITOR" };
        for (int i = 0; i < 3; i++)
        {
            var idx = i;
            var button = Ui.Button(captions[i]);
            button.Width = 119;
            button.Height = 31;
            button.Click += (_, _) => SwitchSection(idx);
            navigation[i] = button;
            tabs.Controls.Add(button);
        }
        miniButton.Width = 129;
        miniButton.Height = 31;
        miniButton.Click += (_, _) => ToggleWindowSize();
        tabs.Controls.Add(miniButton);
        root.Controls.Add(tabs, 0, 1);

        pages.Controls.Add(monitorPage);
        pages.Controls.Add(probarPage);
        pages.Controls.Add(iniciarPage);
        root.Controls.Add(pages, 0, 2);

        var bottom = new Panel { Dock = DockStyle.Fill, BackColor = Ui.Panel };
        footStatus.Dock = DockStyle.Fill;
        footStatus.TextAlign = ContentAlignment.MiddleLeft;
        footStatus.Padding = new Padding(7, 0, 0, 0);
        bottom.Controls.Add(footStatus);
        root.Controls.Add(bottom, 0, 3);
    }

    private void BuildStartPage()
    {
        var root = Table(5, 1);
        root.Padding = new Padding(8, 5, 8, 5);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 31));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 41));
        iniciarPage.Controls.Add(root);

        var title = Ui.Label("SECCION 1 - INICIAR MANDOS", 16, true);
        title.ForeColor = Ui.Cyan;
        title.Dock = DockStyle.Fill;
        root.Controls.Add(title, 0, 0);

        var toolbar = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, AutoScroll = true, WrapContents = false,
            BackColor = Ui.Panel, Padding = new Padding(5, 5, 5, 0)
        };
        var countLabel = Ui.Label("Cantidad de mandos:", 11, true);
        countLabel.Margin = new Padding(3, 9, 4, 0);
        quantity.Margin = new Padding(0, 3, 7, 0);
        start.Width = 184;
        stop.Width = 103;
        joy.Width = 108;
        browserIndicator.Margin = new Padding(7, 8, 5, 0);
        foldStartList.Width = 104;
        foldStartLog.Width = 94;
        toolbar.Controls.Add(countLabel);
        toolbar.Controls.Add(quantity);
        toolbar.Controls.Add(start);
        toolbar.Controls.Add(stop);
        toolbar.Controls.Add(joy);
        toolbar.Controls.Add(browserIndicator);
        toolbar.Controls.Add(foldStartList);
        toolbar.Controls.Add(foldStartLog);
        root.Controls.Add(toolbar, 0, 1);

        systemStatus.Dock = DockStyle.Fill;
        systemStatus.ForeColor = Ui.Green;
        systemStatus.TextAlign = ContentAlignment.MiddleLeft;
        root.Controls.Add(systemStatus, 0, 2);

        var body = Table(1, 2);
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 43));
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 57));
        startColumns = body;
        root.Controls.Add(body, 0, 3);
        var devColumn = Table(2, 1, Ui.Panel);
        devColumn.RowStyles.Add(new RowStyle(SizeType.Absolute, 26));
        devColumn.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        devColumn.Padding = new Padding(4);
        devColumn.Controls.Add(Ui.Label("DISPOSITIVOS ACTIVOS", 12, true), 0, 0);
        devColumn.Controls.Add(deviceList, 0, 1);
        body.Controls.Add(devColumn, 0, 0);
        startListPanel = devColumn;

        var logColumn = Table(2, 1, Ui.Panel);
        logColumn.RowStyles.Add(new RowStyle(SizeType.Absolute, 26));
        logColumn.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        logColumn.Padding = new Padding(4);
        logColumn.Controls.Add(Ui.Label("REGISTRO DE INICIO Y MOTOR", 12, true), 0, 0);
        logColumn.Controls.Add(startupLog, 0, 1);
        body.Controls.Add(logColumn, 1, 0);
        startLogPanel = logColumn;

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
        root.Padding = new Padding(7, 5, 7, 5);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 35));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 39));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 39));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));
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
            modes[i].Width = 87;
            modes[i].Height = 30;
            modes[i].Click += (_, _) => SetMovementMode(idx);
            toolbar.Controls.Add(modes[i]);
        }
        toolbar.Controls.Add(hold);
        foldTestMotion.Width = 106;
        foldTestButtons.Width = 94;
        toolbar.Controls.Add(foldTestMotion);
        toolbar.Controls.Add(foldTestButtons);
        root.Controls.Add(toolbar, 0, 1);

        var main = Table(1, 2);
        main.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 39));
        main.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 61));
        testColumns = main;
        root.Controls.Add(main, 0, 2);

        var left = Table(2, 1, Ui.Panel);
        left.RowStyles.Add(new RowStyle(SizeType.Absolute, 25));
        left.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        left.Padding = new Padding(3);
        left.Controls.Add(Ui.Label("MOVIMIENTO - JOYSTICK IZQUIERDO Y D-PAD", 10, true), 0, 0);
        left.Controls.Add(movement, 0, 1);
        main.Controls.Add(left, 0, 0);
        testMotionPanel = left;

        testStick.Margin = new Padding(4);
        testDpad.Margin = new Padding(4);
        movement.Controls.Add(testStick);
        movement.Controls.Add(testDpad);

        var right = Table(4, 1, Ui.Panel);
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 25));
        right.RowStyles.Add(new RowStyle(SizeType.Percent, 56));
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 37));
        right.RowStyles.Add(new RowStyle(SizeType.Percent, 44));
        right.Padding = new Padding(3);
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
        testButtonsPanel = right;

        var controls = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Ui.PanelLight,
            AutoScroll = true, WrapContents = false, Padding = new Padding(6, 2, 0, 1)
        };
        identify.Width = 209;
        release.Width = 182;
        browser.Width = 151;
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
            Dock = DockStyle.Fill, Margin = new Padding(1),
            MinimumSize = new Size(22, 27)
        };
        b.Changed += OnButton;
        testButtons[i] = b;
        return b;
    }

    private void BuildMonitorPage()
    {
        var root = Table(4, 1);
        root.Padding = new Padding(7, 5, 7, 5);
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 35));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 33));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
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
        monitorAuto.Text = "AUTO PRUEBA";
        monitorRelease.Text = "SOLTAR TODO";
        monitorAuto.Width = 151;
        monitorRelease.Width = 122;
        foldMonitorVisual.Width = 115;
        foldMonitorLog.Width = 102;
        monitorActions.Controls.Add(monitorAuto);
        monitorActions.Controls.Add(monitorRelease);
        monitorActions.Controls.Add(foldMonitorVisual);
        monitorActions.Controls.Add(foldMonitorLog);
        root.Controls.Add(monitorActions, 0, 2);

        var columns = Table(1, 2);
        columns.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 57));
        columns.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 43));
        monitorColumns = columns;
        root.Controls.Add(columns, 0, 3);

        var left = Table(4, 1, Ui.Panel);
        left.Padding = new Padding(4);
        left.RowStyles.Add(new RowStyle(SizeType.Absolute, 23));
        left.RowStyles.Add(new RowStyle(SizeType.Percent, 46));
        left.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
        left.RowStyles.Add(new RowStyle(SizeType.Percent, 54));
        left.Controls.Add(Ui.Label("SENALES ENVIADAS POR LA APLICACION", 11, true), 0, 0);
        columns.Controls.Add(left, 0, 0);
        monitorVisualPanel = left;

        var figures = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Ui.Panel,
            WrapContents = false, AutoScroll = true
        };
        monitorStick.Margin = new Padding(5);
        monitorDpad.Margin = new Padding(5);
        figures.Controls.Add(monitorStick);
        figures.Controls.Add(monitorDpad);
        var labels = new Panel { Width = 111, Height = 125, BackColor = Ui.Panel };
        analogInfo.Location = new Point(2, 12);
        analogInfo.AutoSize = false;
        analogInfo.Width = 107;
        analogInfo.Height = 42;
        dpadInfo.Location = new Point(2, 66);
        dpadInfo.AutoSize = false;
        dpadInfo.Width = 107;
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
                Margin = new Padding(2),
                Font = new Font("Segoe UI", 8.5f, FontStyle.Bold)
            };
            monitorButtons[i] = label;
            ledGrid.Controls.Add(label, i % 4, i / 4);
        }
        left.Controls.Add(ledGrid, 0, 3);

        var right = Table(3, 1, Ui.Panel);
        right.Padding = new Padding(4);
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 26));
        right.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        right.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        right.Controls.Add(Ui.Label("REGISTRO CRONOLOGICO DE EVENTOS", 11, true), 0, 0);
        right.Controls.Add(monitorEvents, 0, 1);
        var note = Ui.Label("Este monitor registra lo que FUTUREO envia al mando virtual. "
            + "No es una lectura USB/HID independiente ni confirma que un juego lo haya recibido.", 9);
        note.Dock = DockStyle.Fill;
        note.ForeColor = Ui.Gray;
        right.Controls.Add(note, 0, 2);
        columns.Controls.Add(right, 1, 0);
        monitorLogPanel = right;
    }


    // Smoke-test of the actual WinForms layout: no HIDMaestro context is
    // created, no driver installed, and no admin rights are required.
    internal void RunUiSmoke()
    {
        CreateControl();
        SwitchSection(0);
        startListFolded = true;
        ApplyFoldLayouts();
        if (startColumns!.ColumnStyles[0].Width != 0)
            throw new InvalidOperationException("No se pliega el inventario");
        startListFolded = false;
        startLogFolded = true;
        ApplyFoldLayouts();
        if (startColumns.ColumnStyles[1].Width != 0)
            throw new InvalidOperationException("No se pliega el log");
        startLogFolded = false;

        SwitchSection(1);
        testMotionFolded = true;
        ApplyFoldLayouts();
        if (testColumns!.ColumnStyles[0].Width != 0)
            throw new InvalidOperationException("No se pliega movimiento");
        testMotionFolded = false;
        testButtonsFolded = true;
        ApplyFoldLayouts();
        if (testColumns.ColumnStyles[1].Width != 0)
            throw new InvalidOperationException("No se pliegan botones");
        testButtonsFolded = false;

        SwitchSection(2);
        monitorVisualFolded = true;
        ApplyFoldLayouts();
        if (monitorColumns!.ColumnStyles[0].Width != 0)
            throw new InvalidOperationException("No se pliega vista de monitor");
        monitorVisualFolded = false;
        monitorLogFolded = true;
        ApplyFoldLayouts();
        if (monitorColumns.ColumnStyles[1].Width != 0)
            throw new InvalidOperationException("No se pliega historial");
        monitorLogFolded = false;

        ApplyFoldLayouts();
        ToggleWindowSize();
        ToggleWindowSize();
        PerformLayout();
        if (!miniView || testButtons.Count != 16 || monitorButtons.Count != 16)
            throw new InvalidOperationException("Faltan controles de la vista mini");
    }

    private void ToggleWindowSize()
    {
        miniView = !miniView;
        if (WindowState != FormWindowState.Normal)
            WindowState = FormWindowState.Normal;
        Size = miniView ? new Size(930, 650) : new Size(1240, 840);
        miniButton.Text = miniView ? "VISTA AMPLIADA" : "VISTA MINI";
    }

    private void WireFoldButtons()
    {
        foldStartList.Click += (_, _) =>
        {
            startListFolded = !startListFolded;
            if (startListFolded) startLogFolded = false;
            ApplyFoldLayouts();
        };
        foldStartLog.Click += (_, _) =>
        {
            startLogFolded = !startLogFolded;
            if (startLogFolded) startListFolded = false;
            ApplyFoldLayouts();
        };
        foldTestMotion.Click += (_, _) =>
        {
            if (pads.ContainsKey(selectedSlot) && !testMotionFolded)
                ReleaseSelected(); // no dejar una direccion o boton oculto en estado pulsado
            testMotionFolded = !testMotionFolded;
            if (testMotionFolded) testButtonsFolded = false;
            ApplyFoldLayouts();
        };
        foldTestButtons.Click += (_, _) =>
        {
            if (pads.ContainsKey(selectedSlot) && !testButtonsFolded)
                ReleaseSelected();
            testButtonsFolded = !testButtonsFolded;
            if (testButtonsFolded) testMotionFolded = false;
            ApplyFoldLayouts();
        };
        foldMonitorVisual.Click += (_, _) =>
        {
            monitorVisualFolded = !monitorVisualFolded;
            if (monitorVisualFolded) monitorLogFolded = false;
            ApplyFoldLayouts();
        };
        foldMonitorLog.Click += (_, _) =>
        {
            monitorLogFolded = !monitorLogFolded;
            if (monitorLogFolded) monitorVisualFolded = false;
            ApplyFoldLayouts();
        };
    }

    // Cada seccion tiene dos paneles. Permitir ocultar cualquiera de ellos
    // pero nunca los dos a la vez mantiene el mando accesible en ventana mini.
    private static void FitColumns(
        TableLayoutPanel? columns, Control? left, Control? right,
        bool leftFolded, bool rightFolded, float normalLeftPercent)
    {
        if (columns is null || left is null || right is null) return;
        columns.SuspendLayout();
        try
        {
            left.Visible = !leftFolded;
            right.Visible = !rightFolded;
            columns.ColumnStyles[0].SizeType = SizeType.Percent;
            columns.ColumnStyles[1].SizeType = SizeType.Percent;
            columns.ColumnStyles[0].Width =
                leftFolded ? 0 : rightFolded ? 100 : normalLeftPercent;
            columns.ColumnStyles[1].Width =
                rightFolded ? 0 : leftFolded ? 100 : 100 - normalLeftPercent;
        }
        finally
        {
            columns.ResumeLayout(true);
        }
    }

    private void ApplyFoldLayouts()
    {
        FitColumns(startColumns, startListPanel, startLogPanel,
            startListFolded, startLogFolded, 43f);
        FitColumns(testColumns, testMotionPanel, testButtonsPanel,
            testMotionFolded, testButtonsFolded, 39f);
        FitColumns(monitorColumns, monitorVisualPanel, monitorLogPanel,
            monitorVisualFolded, monitorLogFolded, 57f);

        foldStartList.Text = startListFolded ? "VER LISTA" : "PLEGAR LISTA";
        foldStartLog.Text = startLogFolded ? "VER LOG" : "PLEGAR LOG";
        foldTestMotion.Text = testMotionFolded ? "VER MOV." : "PLEGAR MOV.";
        foldTestButtons.Text = testButtonsFolded ? "VER BOT." : "PLEGAR BOT.";
        foldMonitorVisual.Text = monitorVisualFolded ? "VER VISTA" : "PLEGAR VISTA";
        foldMonitorLog.Text = monitorLogFolded ? "VER HIST." : "PLEGAR HIST.";
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
                $"FUTUREO VJOY PORTABLE v0.8.5\n\n"
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
            PublishHostSlots();
            selectedSlot = 1;
            ReloadMonitorEvents();
            systemStatus.Text = $"Motor activo: {pads.Count} mandos independientes.";
            Log($"OK: {pads.Count} mandos HID creados con nombres FUTUREO_VJOY1..FUTUREO_VJOY{total}.");
            UpdateBrowserSnapshot();
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
            }
            catch (Exception ex) { Log($"P{pad.Slot}: error al liberar entradas: {ex.Message}"); }
            // Dispose must still run when a last neutral packet fails.
            try { pad.Controller.Dispose(); }
            catch (Exception ex) { Log($"P{pad.Slot}: error al retirar: {ex.Message}"); }
        }
        pads.Clear();
        remoteLatest.Clear();
        PublishHostSlots();
        foreach (var slot in overridden.OrderByDescending(x => x))
        {
            try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
            catch (Exception ex) { Log($"P{slot}: pendiente de restaurar OEM: {ex.Message}"); }
        }
        overridden.Clear();
        UpdateBrowserSnapshot();
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
        hostClosing = true;
        monitorTimer.Stop();
        StopAll();
        hostInput.Dispose();
        browserBridge.Dispose();
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
        footStatus.Text = $"FUTUREO v0.8.5  |  {pads.Count} mando(s) activo(s)  |  "
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
                button.Height = 29;
                button.Width = 131;
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
        testStick.Size = mixed ? new Size(145, 145) : new Size(240, 240);
        testDpad.Size = mixed ? new Size(145, 145) : new Size(240, 240);
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

    // Serializacion en el hilo de WinForms. El servicio localhost solo
    // comparte un snapshot inmutable; nunca accede a los objetos HID.

    private void PublishHostSlots()
    {
        System.Threading.Volatile.Write(ref hostPadSlots,
            pads.Keys.OrderBy(k => k).ToArray());
    }

    private bool QueueHostInput(HostPadInput packet)
    {
        if (hostClosing ||
            !System.Threading.Volatile.Read(ref hostPadSlots).Contains(packet.Slot))
            return false;
        remoteLatest[packet.Slot] = packet;
        return true;
    }

    private Task<bool> ResizeForHostAsync(int requested)
    {
        var finished = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        if (hostClosing || IsDisposed || Disposing || !IsHandleCreated)
            return Task.FromResult(false);
        try
        {
            BeginInvoke(new Action(() =>
            {
                bool result = false;
                try { result = ResizePadsInPlace(requested); }
                catch (Exception ex) { Log("Redimensionar: " + ex.Message); }
                finished.TrySetResult(result);
            }));
        }
        catch (ObjectDisposedException) { finished.TrySetResult(false); }
        catch (InvalidOperationException) { finished.TrySetResult(false); }
        return finished.Task;
    }

    // Preserve the first N controllers. Only suffix devices are added/removed.
    // The user can keep Steam, MAME, the browser and the MULTIMANDO room open.
    private bool ResizePadsInPlace(int count)
    {
        if (count is < 1 or > 8 || hostClosing || busy || identifying ||
            context is null || pads.Count == 0) return false;
        int current = pads.Count;
        if (current == count) return true;
        busy = true;
        SetBusy(true);
        try
        {
            if (count > current)
            {
                var created = new Dictionary<int, HMController>();
                var oemClaimed = new List<int>();
                try
                {
                    for (int slot = current + 1; slot <= count; slot++)
                    {
                        var controller = context.CreateController(
                            Profile(slot), $"futureo-portable-v080-slot-{slot}", HMBackend.Umdf2);
                        created.Add(slot, controller);
                        HMOemNameOverride.Set(0xF7A0, (ushort)(0x2200 + slot),
                            $"FUTUREO_VJOY{slot}");
                        oemClaimed.Add(slot);
                    }
                }
                catch
                {
                    foreach (var controller in created.Values)
                    {
                        try { controller.Dispose(); } catch { }
                    }
                    foreach (var slot in oemClaimed)
                    {
                        try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
                        catch { }
                    }
                    throw;
                }
                foreach (var item in created)
                    pads[item.Key] = new RuntimePad(item.Key, item.Value);
                foreach (var slot in oemClaimed) overridden.Add(slot);
            }
            else
            {
                // Removing highest-numbered slots first does not re-number
                // ongoing players on lower-numbered slots.
                foreach (var slot in pads.Keys.Where(n => n > count).OrderByDescending(x => x).ToArray())
                {
                    remoteLatest.TryRemove(slot, out _);
                    var pad = pads[slot];
                    pad.Buttons = HMButton.None;
                    pad.Hat = HMHat.None;
                    pad.X = pad.Y = .5f;
                    Send(pad);
                    try { pad.Controller.Dispose(); }
                    catch (Exception ex) { Log($"P{slot}: Dispose: {ex.Message}"); }
                    pads.Remove(slot);
                    if (overridden.Remove(slot))
                    {
                        try { HMOemNameOverride.Clear(0xF7A0, (ushort)(0x2200 + slot)); }
                        catch (Exception ex) { Log($"P{slot}: OEM restore: {ex.Message}"); }
                    }
                }
                if (!pads.ContainsKey(selectedSlot))
                    selectedSlot = Math.Min(count, 1);
            }
            PublishHostSlots();
            quantity.Value = count;
            UpdateBrowserSnapshot();
            ReloadMonitorEvents();
            systemStatus.Text = $"Motor FUTUREO: {count} mandos (capacidad actualizada sin reiniciar)";
            Log($"MULTIMANDO: capacidad {current} -> {count}, sala y jugadores activos conservados.");
            return true;
        }
        catch (Exception ex)
        {
            Log("MULTIMANDO: no se pudo cambiar la cantidad de mandos: " + ex.Message);
            PublishHostSlots();
            UpdateBrowserSnapshot();
            return false;
        }
        finally
        {
            busy = false;
            SetBusy(false);
            RefreshAll();
        }
    }

    // Process coalesced Python states on the UI thread. The watchdog ensures
    // a crashed Python process never leaves a virtual button held forever.
    private void DrainHostInput()
    {
        if (busy || identifying || hostClosing || pads.Count == 0) return;
        var now = DateTime.UtcNow;
        foreach (var pad in pads.Values)
        {
            if (remoteLatest.TryRemove(pad.Slot, out var packet))
            {
                if (pad.RemoteSession == packet.Session &&
                    packet.Seq <= pad.RemoteSequence) continue;
                var buttons = HMButton.None;
                for (var i = 0; i < Math.Min(packet.Buttons.Length, PadButtonSpec.All.Length); i++)
                    if (packet.Buttons[i] == 1) buttons |= PadButtonSpec.All[i].Code;

                var oldButtons = pad.Buttons;
                var oldHat = pad.Hat;
                var oldX = pad.X;
                var oldY = pad.Y;
                pad.Buttons = buttons;
                pad.Hat = (HMHat)packet.Hat;
                pad.X = Math.Clamp((packet.Axes[0] + 1f) / 2f, 0f, 1f);
                pad.Y = Math.Clamp((packet.Axes[1] + 1f) / 2f, 0f, 1f);
                pad.RemoteSession = packet.Session;
                pad.RemoteSequence = packet.Seq;
                pad.RemoteTouched = now;
                // La API /input confirma que se ENCOLO la orden, no que el
                // driver HID la recibio. Reafirmar periodicamente el estado
                // incluso si no cambia: un "soltar derecha" perdido no debe
                // dejar el juego caminando a la derecha indefinidamente.
                var changed = oldButtons != pad.Buttons || oldHat != pad.Hat ||
                    Math.Abs(oldX - pad.X) > .003f ||
                    Math.Abs(oldY - pad.Y) > .003f;
                var resubmit = (now - pad.RemoteLastSubmit).TotalMilliseconds >= 450;
                if (changed || resubmit)
                {
                    if (Send(pad))
                    {
                        pad.RemoteLastSubmit = now;
                        if (changed && (now - pad.RemoteLogAt).TotalMilliseconds >= 150)
                        {
                            Record(pad,
                                $"HOST: {PadButtonSpec.All.Count(x => (buttons & x.Code) != 0)} botones; " +
                                $"Hat={pad.Hat} X={packet.Axes[0]:F2} Y={packet.Axes[1]:F2}");
                            pad.RemoteLogAt = now;
                        }
                    }
                    else
                    {
                        // Si SubmitState falla, no dar por aplicado el cambio
                        // y permitir que el proximo heartbeat vuelva a probar.
                        pad.Buttons = oldButtons;
                        pad.Hat = oldHat;
                        pad.X = oldX;
                        pad.Y = oldY;
                        pad.RemoteLastSubmit = DateTime.MinValue;
                    }
                }
            }
            else if (pad.RemoteTouched != DateTime.MinValue &&
                (now - pad.RemoteTouched).TotalSeconds > 2)
            {
                pad.RemoteSession = "";
                pad.RemoteSequence = 0;
                pad.Buttons = HMButton.None;
                pad.Hat = HMHat.None;
                pad.X = pad.Y = .5f;
                if (Send(pad))
                {
                    pad.RemoteTouched = DateTime.MinValue;
                    pad.RemoteLastSubmit = now;
                    Record(pad, "ANFITRION: sin senal; controles liberados por seguridad");
                }
                else
                {
                    // Mantener el watchdog armado para reintentar neutralizacion.
                    pad.RemoteTouched = now.AddMilliseconds(-1800);
                    pad.RemoteLastSubmit = DateTime.MinValue;
                }
            }
        }
    }

    private void UpdateBrowserSnapshot()
    {
        if (!browserBridge.Active) return;
        var samples = pads.Values.OrderBy(p => p.Slot).Select(p => new
        {
            slot = p.Slot,
            name = $"FUTUREO_VJOY{p.Slot}",
            buttons = PadButtonSpec.All.Select(spec =>
                (p.Buttons & spec.Code) != 0 ? 1 : 0).ToArray(),
            axes = new[]
            {
                Math.Clamp((p.X - .5f) * 2f, -1f, 1f),
                Math.Clamp((p.Y - .5f) * 2f, -1f, 1f)
            },
            hat = (int)p.Hat
        }).ToArray();

        try
        {
            browserBridge.UpdateJson(JsonSerializer.Serialize(new
            {
                version = 1,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                pads = samples
            }));
        }
        catch (Exception ex)
        {
            Log("Error preparando snapshot para extension: " + ex.Message);
        }
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
            UpdateBrowserSnapshot();
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
        // El historial se acumula incluso mientras el usuario esta en PROBAR:
        // al cambiar a MONITOR se ven los eventos anteriores del mismo mando.
        if (monitorRenderedSlot == pad.Slot && selectedSlot == pad.Slot)
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
