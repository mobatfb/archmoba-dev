using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace FutureoVJoyV085;

// A snapshot from the existing Python MULTIMANDO room to the exact FUTUREO
// slot already created in the Windows GUI. No vJoy/ViGEm driver is involved.
internal sealed class HostPadInput
{
    public int Slot { get; set; }
    public string Session { get; set; } = "";
    public long Seq { get; set; }
    public int[] Buttons { get; set; } = Array.Empty<int>();
    public float[] Axes { get; set; } = Array.Empty<float>();
    public int Hat { get; set; }

    public bool IsValid()
    {
        return Slot >= 1 && Slot <= 8 && Seq >= 1
            && Session.Length is >= 16 and <= 32 && Session.All(Uri.IsHexDigit)
            && Buttons is { Length: 16 } && Buttons.All(n => n is 0 or 1)
            && Axes is { Length: 2 }
            && Axes.All(x => float.IsFinite(x) && x >= -1f && x <= 1f)
            && Hat >= 0 && Hat <= 8;
    }
}

/// <summary>
/// Exposes a local input bridge for the host Python script. No passwords or
/// manual pairing are required. POST is restricted to loopback, exact Host,
/// application/json and a fixed nonsecret header; no CORS policy is granted.
/// This service accepts states only, and never executes arbitrary commands.
/// </summary>
internal sealed class HostInputBridge : IDisposable
{
    public const int Port = 38472;
    public Func<HostPadInput, bool>? ApplyInput { get; set; }
    public Func<int, Task<bool>>? ApplyCapacity { get; set; }
    public Func<int[]>? GetSlots { get; set; }
    public bool Active => listener is not null;
    public string Status { get; private set; } = "INACTIVO";
    private readonly CancellationTokenSource stop = new();
    private readonly SemaphoreSlim capacity = new(8, 8);
    private TcpListener? listener;
    private bool disposed;

    public bool Start()
    {
        if (disposed) throw new ObjectDisposedException(nameof(HostInputBridge));
        if (listener is not null) return true;
        try
        {
            var server = new TcpListener(IPAddress.Loopback, Port);
            server.Start(12);
            listener = server;
            Status = "ACTIVO 127.0.0.1:" + Port;
            _ = Task.Run(() => ServeAsync(server, stop.Token));
            return true;
        }
        catch (Exception ex)
        {
            Status = "ERROR: " + ex.Message;
            return false;
        }
    }

    private async Task ServeAsync(TcpListener server, CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            TcpClient client;
            try { client = await server.AcceptTcpClientAsync(token); }
            catch (OperationCanceledException) { break; }
            catch (ObjectDisposedException) { break; }
            catch (SocketException) when (token.IsCancellationRequested) { break; }
            catch (SocketException) { continue; }

            if (!await capacity.WaitAsync(0))
            {
                client.Dispose();
                continue;
            }

            _ = Task.Run(async () =>
            {
                try { await HandleAsync(client, token); }
                catch (Exception) { /* handle errors per request */ }
                finally
                {
                    client.Dispose();
                    try { capacity.Release(); } catch (ObjectDisposedException) { }
                }
            });
        }
    }

    private async Task HandleAsync(TcpClient client, CancellationToken token)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token);
        // Dynamic HID controller creation may take a few seconds.
        timeout.CancelAfter(TimeSpan.FromSeconds(40));
        using var stream = client.GetStream();
        using var reader = new StreamReader(stream, new UTF8Encoding(false),
            detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);

        var first = await reader.ReadLineAsync(timeout.Token);
        if (first is null || first.Length > 1024)
        {
            await ReplyAsync(stream, 400, "{\"error\":\"invalid request\"}", timeout.Token);
            return;
        }

        string? host = null, origin = null, contentType = null, sender = null;
        int? bodySize = null;
        bool duplicateSize = false, transferEncoding = false;
        int limit = first.Length, headers = 0;
        while (true)
        {
            var header = await reader.ReadLineAsync(timeout.Token);
            if (header is null || header.Length == 0) break;
            limit += header.Length;
            if (limit > 8192 || ++headers > 30)
            {
                await ReplyAsync(stream, 431, "{\"error\":\"headers too large\"}", timeout.Token);
                return;
            }
            var pos = header.IndexOf(':');
            if (pos < 1) continue;
            var key = header[..pos].Trim();
            var val = header[(pos + 1)..].Trim();
            if (key.Equals("Host", StringComparison.OrdinalIgnoreCase)) host = val;
            if (key.Equals("Origin", StringComparison.OrdinalIgnoreCase)) origin = val;
            if (key.Equals("Content-Type", StringComparison.OrdinalIgnoreCase)) contentType = val;
            if (key.Equals("X-Futureo-Client", StringComparison.OrdinalIgnoreCase)) sender = val;
            if (key.Equals("Transfer-Encoding", StringComparison.OrdinalIgnoreCase)) transferEncoding = true;
            if (key.Equals("Content-Length", StringComparison.OrdinalIgnoreCase))
            {
                if (bodySize.HasValue) duplicateSize = true;
                if (int.TryParse(val, out int num)) bodySize = num;
                else bodySize = -1;
            }
        }

        if (host != $"127.0.0.1:{Port}" || origin is not null)
        {
            await ReplyAsync(stream, 403, "{\"error\":\"localhost required\"}", timeout.Token);
            return;
        }

        if (first == "GET /health HTTP/1.1" || first == "GET /health HTTP/1.0")
        {
            int[] slots;
            try { slots = GetSlots?.Invoke() ?? Array.Empty<int>(); }
            catch { slots = Array.Empty<int>(); }
            var message = JsonSerializer.Serialize(new
            {
                engine = "FUTUREO_VJOY", version = "0.8.4",
                hostInput = true, slots
            });
            await ReplyAsync(stream, 200, message, timeout.Token);
            return;
        }

        var isInput = first == "POST /input HTTP/1.1" ||
            first == "POST /input HTTP/1.0";
        var isCapacity = first == "POST /capacity HTTP/1.1" ||
            first == "POST /capacity HTTP/1.0";
        if (!isInput && !isCapacity)
        {
            await ReplyAsync(stream, 404, "{\"error\":\"not found\"}", timeout.Token);
            return;
        }

        if (sender != "MULTIMANDO" || contentType is null ||
            !contentType.StartsWith("application/json", StringComparison.OrdinalIgnoreCase))
        {
            await ReplyAsync(stream, 403, "{\"error\":\"application client required\"}", timeout.Token);
            return;
        }
        if (transferEncoding || duplicateSize || bodySize is null or < 2 or > 2048)
        {
            await ReplyAsync(stream, 400, "{\"error\":\"invalid payload length\"}", timeout.Token);
            return;
        }

        var payload = new char[bodySize.Value];
        int read = 0;
        while (read < payload.Length)
        {
            var n = await reader.ReadAsync(payload.AsMemory(read), timeout.Token);
            if (n <= 0) break;
            read += n;
        }
        if (read != payload.Length)
        {
            await ReplyAsync(stream, 400, "{\"error\":\"incomplete payload\"}", timeout.Token);
            return;
        }

        if (isCapacity)
        {
            int count;
            try
            {
                using var doc = JsonDocument.Parse(new string(payload));
                if (!doc.RootElement.TryGetProperty("count", out var v) ||
                    !v.TryGetInt32(out count) || count is < 1 or > 8)
                {
                    await ReplyAsync(stream, 422, "{\"error\":\"capacity must be 1..8\"}", timeout.Token);
                    return;
                }
            }
            catch (JsonException)
            {
                await ReplyAsync(stream, 400, "{\"error\":\"invalid capacity json\"}", timeout.Token);
                return;
            }
            bool resized;
            try { resized = await (ApplyCapacity?.Invoke(count) ?? Task.FromResult(false)); }
            catch { resized = false; }
            await ReplyAsync(stream, resized ? 200 : 409,
                resized ? "{\"ok\":true}" : "{\"error\":\"resize failed or no FUTUREO pads\"}",
                timeout.Token);
            return;
        }

        HostPadInput? update;
        try
        {
            update = JsonSerializer.Deserialize<HostPadInput>(
                new string(payload),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        }
        catch (JsonException)
        {
            await ReplyAsync(stream, 400, "{\"error\":\"invalid json\"}", timeout.Token);
            return;
        }
        if (update is null || !update.IsValid())
        {
            await ReplyAsync(stream, 422, "{\"error\":\"invalid controller state\"}", timeout.Token);
            return;
        }

        bool accepted;
        try { accepted = ApplyInput?.Invoke(update) ?? false; }
        catch { accepted = false; }
        await ReplyAsync(stream, accepted ? 200 : 409,
            accepted ? "{\"ok\":true}" : "{\"error\":\"controller inactive\"}", timeout.Token);
    }

    private static async Task ReplyAsync(NetworkStream stream, int status,
        string payload, CancellationToken token)
    {
        var content = Encoding.UTF8.GetBytes(payload);
        var statusText = status switch
        {
            200 => "OK", 400 => "Bad Request", 403 => "Forbidden",
            404 => "Not Found", 409 => "Conflict", 422 => "Unprocessable Content",
            431 => "Request Header Fields Too Large", _ => "Error"
        };
        var header = Encoding.ASCII.GetBytes(
            $"HTTP/1.1 {status} {statusText}\r\n"
            + "Content-Type: application/json; charset=utf-8\r\n"
            + "Cache-Control: no-store\r\n"
            + "X-Content-Type-Options: nosniff\r\n"
            + "Connection: close\r\n"
            + $"Content-Length: {content.Length}\r\n\r\n");
        await stream.WriteAsync(header, token);
        await stream.WriteAsync(content, token);
        await stream.FlushAsync(token);
    }

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        stop.Cancel();
        listener?.Stop();
        listener = null;
        Status = "INACTIVO";
        stop.Dispose();
    }

    // Driver-free integration smoke test on GitHub Actions Windows runner.
    public static async Task<string> SmokeTestAsync()
    {
        HostPadInput? latest = null;
        int wantedCount = 3;
        using var bridge = new HostInputBridge
        {
            GetSlots = () => Enumerable.Range(1, wantedCount).ToArray(),
            ApplyInput = state => { latest = state; return true; },
            ApplyCapacity = count =>
            {
                wantedCount = count;
                return Task.FromResult(true);
            }
        };
        if (!bridge.Start()) throw new InvalidOperationException(bridge.Status);

        using var http = new HttpClient(new HttpClientHandler { UseProxy = false })
        { Timeout = TimeSpan.FromSeconds(4) };
        var health = await http.GetStringAsync("http://127.0.0.1:38472/health");
        if (!health.Contains("hostInput") || !health.Contains("FUTUREO_VJOY"))
            throw new InvalidOperationException("Health endpoint missing required fields");

        const string data = "{\"slot\":2,\"session\":\"1234567890abcdef\",\"seq\":1,"
            + "\"buttons\":[1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],"
            + "\"axes\":[0.8,-0.4],\"hat\":2}";

        using var missingHeader = new StringContent(data, Encoding.UTF8, "application/json");
        var forbidden = await http.PostAsync("http://127.0.0.1:38472/input", missingHeader);

        using var allowed = new HttpRequestMessage(HttpMethod.Post,
            "http://127.0.0.1:38472/input")
        {
            Content = new StringContent(data, Encoding.UTF8, "application/json")
        };
        allowed.Headers.Add("X-Futureo-Client", "MULTIMANDO");
        var response = await http.SendAsync(allowed);

        using var hostile = new HttpRequestMessage(HttpMethod.Post,
            "http://127.0.0.1:38472/input")
        {
            Content = new StringContent(data, Encoding.UTF8, "application/json")
        };
        hostile.Headers.Add("X-Futureo-Client", "MULTIMANDO");
        hostile.Headers.Add("Origin", "https://example.com");
        var blocked = await http.SendAsync(hostile);

        using var grow = new HttpRequestMessage(HttpMethod.Post,
            "http://127.0.0.1:38472/capacity")
        {
            Content = new StringContent("{\"count\":8}", Encoding.UTF8, "application/json")
        };
        grow.Headers.Add("X-Futureo-Client", "MULTIMANDO");
        var capacityResponse = await http.SendAsync(grow);
        var resizedHealth = await http.GetStringAsync("http://127.0.0.1:38472/health");

        if ((int)forbidden.StatusCode != 403 || (int)response.StatusCode != 200
            || (int)blocked.StatusCode != 403 || latest is null
            || latest.Slot != 2 || latest.Buttons[0] != 1
            || latest.Hat != 2 || Math.Abs(latest.Axes[0] - .8f) > .001f
            || (int)capacityResponse.StatusCode != 200
            || !resizedHealth.Contains("8"))
            throw new InvalidOperationException(
                $"Input smoke test failed: no-header={forbidden.StatusCode} "
                + $"good={response.StatusCode} web-origin={blocked.StatusCode}");
        return "HOST INPUT smoke OK: no pairing; local health; POST 16 buttons + DPad + analog; resize capacity 3->8; web origins blocked";
    }
}
