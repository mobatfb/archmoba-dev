using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Linq;
using System.Windows.Forms;
using HIDMaestro;

namespace FutureoVJoyV085;

internal static class Ui
{
    public static readonly Color Background = Color.FromArgb(8, 24, 42);
    public static readonly Color Panel = Color.FromArgb(15, 38, 64);
    public static readonly Color PanelLight = Color.FromArgb(23, 50, 78);
    public static readonly Color Stroke = Color.FromArgb(64, 115, 153);
    public static readonly Color Cyan = Color.FromArgb(92, 224, 242);
    public static readonly Color White = Color.FromArgb(228, 242, 252);
    public static readonly Color Gray = Color.FromArgb(152, 177, 198);
    public static readonly Color Green = Color.FromArgb(80, 218, 160);
    public static readonly Color Amber = Color.FromArgb(235, 188, 91);

    public static Button Button(string title, bool primary = false)
    {
        return new Button
        {
            Text = title,
            Height = 30,
            AutoSize = false,
            BackColor = primary ? Color.FromArgb(24, 113, 160) : PanelLight,
            ForeColor = White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            Margin = new Padding(2),
            Padding = new Padding(3, 1, 3, 1),
            Cursor = Cursors.Hand,
            UseVisualStyleBackColor = false
        }.WithFlatBorder();
    }

    private static Button WithFlatBorder(this Button button)
    {
        button.FlatAppearance.BorderSize = 1;
        button.FlatAppearance.BorderColor = Stroke;
        return button;
    }

    public static Label Label(string text, float size = 10f, bool bold = false)
    {
        return new Label
        {
            Text = text, ForeColor = White,
            Font = new Font("Segoe UI", Math.Max(8f, size * .85f), bold ? FontStyle.Bold : FontStyle.Regular),
            AutoSize = true, Margin = new Padding(5)
        };
    }

    public static void Rounded(Graphics g, Brush brush, RectangleF r, float radius)
    {
        using var p = new GraphicsPath();
        var d = radius * 2;
        if (r.Width <= d || r.Height <= d)
        {
            g.FillRectangle(brush, r);
            return;
        }
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        g.FillPath(brush, p);
    }
}

internal sealed record PadButtonSpec(int Index, string Label, HMButton Code, Color Tint)
{
    public static readonly PadButtonSpec[] All =
    {
        new(0, "X", HMButton.X, Color.FromArgb(53, 144, 226)),
        new(1, "Y", HMButton.Y, Color.FromArgb(221, 172, 65)),
        new(2, "L", HMButton.LeftBumper, Color.FromArgb(114, 132, 153)),
        new(3, "A", HMButton.A, Color.FromArgb(55, 170, 127)),
        new(4, "B", HMButton.B, Color.FromArgb(210, 69, 93)),
        new(5, "R", HMButton.RightBumper, Color.FromArgb(114, 132, 153)),
        new(6, "SELECT", HMButton.Back, Color.FromArgb(41, 89, 129)),
        new(7, "START", HMButton.Start, Color.FromArgb(53, 175, 202)),
        new(8, "L3", HMButton.LeftStick, Color.FromArgb(86, 108, 145)),
        new(9, "R3", HMButton.RightStick, Color.FromArgb(86, 108, 145)),
        new(10, "HOME", HMButton.Guide, Color.FromArgb(86, 108, 145)),
        new(11, "TOUCH", HMButton.Touchpad, Color.FromArgb(86, 108, 145)),
        new(12, "SHARE", HMButton.Share, Color.FromArgb(86, 108, 145)),
        new(13, "P1", HMButton.RightPaddle, Color.FromArgb(86, 108, 145)),
        new(14, "P2", HMButton.LeftPaddle, Color.FromArgb(86, 108, 145)),
        new(15, "EXTRA", HMButton.Misc1, Color.FromArgb(86, 108, 145))
    };
}

internal sealed class PadFaceButton : Control
{
    public PadButtonSpec Spec { get; }
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public bool Active { get; set; }
    public bool Large { get; }
    public event Action<int, bool>? Changed;
    private bool mousePressed;

    public PadFaceButton(PadButtonSpec spec, bool large = true)
    {
        Spec = spec;
        Large = large;
        Text = spec.Label;
        BackColor = Ui.Panel;
        ForeColor = Ui.White;
        Font = new Font("Segoe UI", large ? 16f : 9f, FontStyle.Bold);
        Cursor = Cursors.Hand;
        AccessibleName = "Boton " + spec.Label;
        AccessibleDescription = "Mantener pulsado para enviar entrada al mando virtual";
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button != MouseButtons.Left || !Enabled) return;
        mousePressed = true;
        Capture = true;
        Changed?.Invoke(Spec.Index, true);
        Invalidate();
    }

    private void EndPress()
    {
        if (!mousePressed) return;
        mousePressed = false;
        Changed?.Invoke(Spec.Index, false);
        Invalidate();
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        EndPress();
        Capture = false;
    }

    protected override void OnMouseCaptureChanged(EventArgs e)
    {
        base.OnMouseCaptureChanged(e);
        EndPress();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.Clear(BackColor);
        var bounds = new RectangleF(4, 4, Math.Max(4, Width - 8), Math.Max(4, Height - 8));
        using var shadow = new SolidBrush(Color.FromArgb(9, 20, 37));
        using var baseFill = new SolidBrush(Active ? ControlPaint.Light(Spec.Tint, .15f) : Spec.Tint);
        using var ring = new Pen(Active ? Ui.Cyan : Color.FromArgb(73, 108, 151), Active ? 5 : 4);
        using var textBrush = new SolidBrush(Ui.White);
        if (Large)
        {
            bounds.Inflate(-4, -4);
            g.FillEllipse(shadow, new RectangleF(bounds.X + 2, bounds.Y + 7, bounds.Width, bounds.Height));
            g.FillEllipse(baseFill, bounds);
            g.DrawEllipse(ring, bounds);
        }
        else
        {
            Ui.Rounded(g, shadow, new RectangleF(bounds.X, bounds.Y + 3, bounds.Width, bounds.Height), 18);
            Ui.Rounded(g, baseFill, bounds, 18);
            g.DrawRectangle(ring, bounds.X, bounds.Y, bounds.Width, bounds.Height);
        }
        using var center = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
        g.DrawString(Text, Font, textBrush, bounds, center);
    }
}

internal sealed class VirtualStick : Control
{
    private bool dragging;
    private float x = 0.5f, y = 0.5f;
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public bool Interactive { get; set; } = true;
    public float X => x;
    public float Y => y;
    public event Action<float, float>? Changed;

    public VirtualStick()
    {
        BackColor = Ui.Panel;
        Size = new Size(210, 210);
        Cursor = Cursors.Cross;
        AccessibleName = "Analogico izquierdo. Arrastrar con el mouse para mover X e Y.";
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
    }

    public void Display(float nx, float ny)
    {
        x = Math.Clamp(nx, 0f, 1f);
        y = Math.Clamp(ny, 0f, 1f);
        Invalidate();
    }

    private void SetFromPoint(Point location)
    {
        var cx = Width / 2f;
        var cy = Height / 2f;
        var radius = Math.Max(10, Math.Min(Width, Height) * 0.36f);
        var dx = (location.X - cx) / radius;
        var dy = (location.Y - cy) / radius;
        var dist = MathF.Sqrt(dx * dx + dy * dy);
        if (dist > 1)
        {
            dx /= dist;
            dy /= dist;
        }
        var nx = Math.Clamp((dx + 1) * .5f, 0f, 1f);
        var ny = Math.Clamp((dy + 1) * .5f, 0f, 1f);
        if (MathF.Abs(nx - x) < .003f && MathF.Abs(ny - y) < .003f) return;
        Display(nx, ny);
        Changed?.Invoke(nx, ny);
    }

    private void Reset()
    {
        Display(0.5f, 0.5f);
        Changed?.Invoke(0.5f, 0.5f);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (!Interactive || e.Button != MouseButtons.Left) return;
        dragging = true;
        Capture = true;
        SetFromPoint(e.Location);
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (dragging && Interactive) SetFromPoint(e.Location);
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (!dragging) return;
        dragging = false;
        Capture = false;
        Reset();
    }

    protected override void OnMouseCaptureChanged(EventArgs e)
    {
        base.OnMouseCaptureChanged(e);
        if (!dragging) return;
        dragging = false;
        Reset();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.Clear(BackColor);
        float cX = Width / 2f, cY = Height / 2f;
        float radius = Math.Min(Width, Height) * .43f;
        using var outer = new SolidBrush(Color.FromArgb(9, 29, 50));
        using var inner = new SolidBrush(Color.FromArgb(13, 42, 70));
        using var knob = new SolidBrush(Color.FromArgb(54, 102, 151));
        using var outline = new Pen(Ui.Stroke, 2);
        using var cross = new Pen(Color.FromArgb(39, 82, 119), 1);
        g.FillEllipse(outer, cX - radius, cY - radius, radius * 2, radius * 2);
        g.DrawEllipse(outline, cX - radius, cY - radius, radius * 2, radius * 2);
        g.FillEllipse(inner, cX - radius * .84f, cY - radius * .84f,
            radius * 1.68f, radius * 1.68f);
        g.DrawLine(cross, cX - radius * .7f, cY, cX + radius * .7f, cY);
        g.DrawLine(cross, cX, cY - radius * .7f, cX, cY + radius * .7f);
        float knobR = radius * .29f;
        float knobX = cX + (x - .5f) * 2 * radius * .75f;
        float knobY = cY + (y - .5f) * 2 * radius * .75f;
        g.FillEllipse(knob, knobX - knobR, knobY - knobR, knobR * 2, knobR * 2);
        g.DrawEllipse(outline, knobX - knobR, knobY - knobR, knobR * 2, knobR * 2);
        g.FillEllipse(inner, knobX - 8, knobY - 8, 16, 16);
        using var small = new Font("Segoe UI", 9, FontStyle.Bold);
        using var ink = new SolidBrush(Ui.Gray);
        g.DrawString("L", small, ink, 9, 8);
    }
}

internal sealed class VirtualDpad : Control
{
    private bool dragging;
    private HMHat direction = HMHat.None;
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public bool Interactive { get; set; } = true;
    public HMHat Direction => direction;
    public event Action<HMHat>? Changed;
    public VirtualDpad()
    {
        BackColor = Ui.Panel;
        Size = new Size(205, 205);
        Cursor = Cursors.Hand;
        AccessibleName = "Cruceta DPad de 8 direcciones";
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
    }

    public void Display(HMHat value)
    {
        direction = value;
        Invalidate();
    }

    private void UpdateFromPoint(Point pos)
    {
        var dx = pos.X - Width / 2f;
        var dy = pos.Y - Height / 2f;
        if (MathF.Sqrt(dx * dx + dy * dy) < Math.Min(Width, Height) * .095f)
        {
            Set(HMHat.None);
            return;
        }
        var angle = MathF.Atan2(dx, -dy) * 180f / MathF.PI;
        var sector = ((int)MathF.Round(angle / 45f) + 8) % 8;
        Set((HMHat)(sector + 1));
    }

    private void Set(HMHat value)
    {
        if (direction == value) return;
        Display(value);
        Changed?.Invoke(value);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (!Interactive || e.Button != MouseButtons.Left) return;
        dragging = true;
        Capture = true;
        UpdateFromPoint(e.Location);
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (dragging && Interactive) UpdateFromPoint(e.Location);
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (!dragging) return;
        dragging = false;
        Capture = false;
        Set(HMHat.None);
    }

    protected override void OnMouseCaptureChanged(EventArgs e)
    {
        base.OnMouseCaptureChanged(e);
        if (!dragging) return;
        dragging = false;
        Set(HMHat.None);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.Clear(BackColor);
        float unit = Math.Min(Width, Height) / 5.1f;
        float cx = Width / 2f, cy = Height / 2f;
        using var neutral = new SolidBrush(Color.FromArgb(42, 78, 110));
        using var selected = new SolidBrush(Ui.Cyan);
        using var baseBrush = new SolidBrush(Color.FromArgb(23, 48, 72));
        Ui.Rounded(g, baseBrush, new RectangleF(cx - unit * .65f, cy - unit * 1.68f,
            unit * 1.3f, unit * 3.36f), unit * .22f);
        Ui.Rounded(g, baseBrush, new RectangleF(cx - unit * 1.68f, cy - unit * .65f,
            unit * 3.36f, unit * 1.3f), unit * .22f);
        var sectors = new (HMHat Hat, float Dx, float Dy, string Label)[]
        {
            (HMHat.North, 0, -1.12f, "N"),
            (HMHat.NorthEast, .88f, -.88f, "NE"),
            (HMHat.East, 1.12f, 0, "E"),
            (HMHat.SouthEast, .88f, .88f, "SE"),
            (HMHat.South, 0, 1.12f, "S"),
            (HMHat.SouthWest, -.88f, .88f, "SO"),
            (HMHat.West, -1.12f, 0, "O"),
            (HMHat.NorthWest, -.88f, -.88f, "NO")
        };
        using var font = new Font("Segoe UI", Math.Max(8, unit * .19f), FontStyle.Bold);
        using var fmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
        foreach (var item in sectors)
        {
            var r = new RectangleF(cx + item.Dx * unit - unit * .42f,
                cy + item.Dy * unit - unit * .42f, unit * .84f, unit * .84f);
            g.FillEllipse(direction == item.Hat ? selected : neutral, r);
            using var text = new SolidBrush(direction == item.Hat ? Ui.Background : Ui.White);
            g.DrawString(item.Label, font, text, r, fmt);
        }
        g.FillEllipse(direction == HMHat.None ? neutral : selected,
            cx - unit * .34f, cy - unit * .34f, unit * .68f, unit * .68f);
    }
}
