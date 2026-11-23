using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace FutureoVJoyV082;

/// <summary>
/// Only an authenticated JSON snapshot service. It NEVER accepts commands
/// from browser pages and never changes Windows device or driver settings.
/// Binds to 127.0.0.1 only; no Access-Control-Allow-Origin header.
/// </summary>
internal sealed class BrowserBridge : IDisposable
{
    public const int Port = 38471;
    private const int MaxRequestBytes = 8192;
    private const string TokenHeader = "x-futureo-token";
    private readonly CancellationTokenSource cancel = new();
    private readonly SemaphoreSlim clients = new(8, 8);
    private TcpListener? listener;
    private Task? loop;
    private string snapshot = "{\"version\":1,\"pads\":[],\"timestamp\":0}";
    private bool disposed;
    public string Token { get; }
    public string Status { get; private set; } = "DETENIDO";
    public bool Active => listener is not null;
    public string Address => $"http://127.0.0.1:{Port}/state";

    public BrowserBridge()
    {
        Token = LoadOrCreateSecret();
    }

    private static string LoadOrCreateSecret()
    {
        var folder = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FUTUREO_VJOY");
        Directory.CreateDirectory(folder);
        var path = Path.Combine(folder, "browser_bridge_token.txt");
        try
        {
            if (File.Exists(path))
            {
                var existing = File.ReadAllText(path).Trim();
                if (existing.Length == 64 && existing.All(Uri.IsHexDigit))
                    return existing;
            }
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        var value = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
        try
        {
            File.WriteAllText(path, value + Environment.NewLine, Encoding.ASCII);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        return value;
    }

    public bool Start()
    {
        if (disposed) throw new ObjectDisposedException(nameof(BrowserBridge));
        if (listener is not null) return true;
        try
        {
            var tcp = new TcpListener(IPAddress.Loopback, Port);
            tcp.Start(16);
            listener = tcp;
            Status = "ACTIVO 127.0.0.1:" + Port;
            loop = Task.Run(() => ServeAsync(tcp, cancel.Token));
            return true;
        }
        catch (Exception ex)
        {
            Status = "ERROR: " + ex.Message;
            return false;
        }
    }

    public void UpdateJson(string data)
    {
        if (disposed) return;
        Volatile.Write(ref snapshot, data);
    }

    private bool GoodToken(string? supplied)
    {
        if (supplied is null || supplied.Length != Token.Length)
            return false;
        var got = Encoding.ASCII.GetBytes(supplied);
        var expected = Encoding.ASCII.GetBytes(Token);
        return CryptographicOperations.FixedTimeEquals(got, expected);
    }

    private async Task ServeAsync(TcpListener tcp, CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            TcpClient client;
            try { client = await tcp.AcceptTcpClientAsync(ct); }
            catch (OperationCanceledException) { break; }
            catch (ObjectDisposedException) { break; }
            catch (SocketException) when (ct.IsCancellationRequested) { break; }
            catch (SocketException) { continue; }

            if (!await clients.WaitAsync(0))
            {
                client.Dispose();
                continue;
            }
            _ = Task.Run(async () =>
            {
                try { await HandleAsync(client, ct); }
                catch (Exception) { /* isolated per-client errors must not stop the bridge */ }
                finally
                {
                    client.Dispose();
                    try { clients.Release(); } catch (ObjectDisposedException) { }
                }
            }, CancellationToken.None);
        }
    }

    private async Task HandleAsync(TcpClient client, CancellationToken ct)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(TimeSpan.FromSeconds(2));
        using var stream = client.GetStream();
        using var reader = new StreamReader(stream, new UTF8Encoding(false),
            detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);

        string? first = await reader.ReadLineAsync(cts.Token);
        if (first is null || first.Length > 1024)
        {
            await ReplyAsync(stream, 400, "{\"error\":\"bad request\"}", cts.Token);
            return;
        }
        string? token = null;
        var length = first.Length;
        var headers = 0;
        while (true)
        {
            var line = await reader.ReadLineAsync(cts.Token);
            if (line is null || line.Length == 0) break;
            length += line.Length;
            if (length > MaxRequestBytes || ++headers > 30)
            {
                await ReplyAsync(stream, 431, "{\"error\":\"too many headers\"}", cts.Token);
                return;
            }
            var pos = line.IndexOf(':');
            if (pos > 0 && line[..pos].Trim().Equals(TokenHeader, StringComparison.OrdinalIgnoreCase))
                token = line[(pos + 1)..].Trim();
        }

        if (first != "GET /state HTTP/1.1" && first != "GET /state HTTP/1.0")
        {
            await ReplyAsync(stream, 404, "{\"error\":\"not found\"}", cts.Token);
            return;
        }
        if (!GoodToken(token))
        {
            await ReplyAsync(stream, 403, "{\"error\":\"pairing required\"}", cts.Token);
            return;
        }

        await ReplyAsync(stream, 200, Volatile.Read(ref snapshot), cts.Token);
    }

    private static async Task ReplyAsync(NetworkStream stream, int status, string json,
        CancellationToken ct)
    {
        var data = Encoding.UTF8.GetBytes(json);
        var reason = status switch
        {
            200 => "OK", 403 => "Forbidden", 404 => "Not Found",
            431 => "Request Header Fields Too Large", _ => "Bad Request"
        };
        var header = Encoding.ASCII.GetBytes(
            $"HTTP/1.1 {status} {reason}\r\n"
            + "Content-Type: application/json; charset=utf-8\r\n"
            + "X-Content-Type-Options: nosniff\r\n"
            + "Cache-Control: no-store\r\n"
            + "Connection: close\r\n"
            + $"Content-Length: {data.Length}\r\n\r\n");
        await stream.WriteAsync(header, ct);
        await stream.WriteAsync(data, ct);
        await stream.FlushAsync(ct);
    }

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        cancel.Cancel();
        listener?.Stop();
        listener = null;
        Status = "DETENIDO";
        // Let in-flight request handlers release their semaphore naturally.
        // Do not dispose the SemaphoreSlim before they finish.
        cancel.Dispose();
    }

    // Used by GitHub Actions without creating HID devices or opening WinForms.
    public static async Task<string> SmokeTestAsync()
    {
        using var bridge = new BrowserBridge();
        bridge.UpdateJson("{\"version\":1,\"pads\":[{\"slot\":1,\"name\":\"FUTUREO_VJOY1\"}],\"timestamp\":123}");
        if (!bridge.Start()) return "ERROR: " + bridge.Status;

        using var http = new System.Net.Http.HttpClient(
            new System.Net.Http.HttpClientHandler { UseProxy = false })
        { Timeout = TimeSpan.FromSeconds(3) };
        var unauthenticated = await http.GetAsync(bridge.Address);
        using var msg = new System.Net.Http.HttpRequestMessage(
            System.Net.Http.HttpMethod.Get, bridge.Address);
        msg.Headers.Add("X-Futureo-Token", bridge.Token);
        var authenticated = await http.SendAsync(msg);
        var body = await authenticated.Content.ReadAsStringAsync();
        if ((int)unauthenticated.StatusCode != 403
            || (int)authenticated.StatusCode != 200
            || !body.Contains("FUTUREO_VJOY1"))
            throw new InvalidOperationException(
                $"Bridge self-test failed: bad={unauthenticated.StatusCode}, "
                + $"good={authenticated.StatusCode}, body={body}");
        return "BRIDGE smoke OK: localhost only, token required, JSON state available";
    }
}
