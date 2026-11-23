using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace FutureoVJoyV084;

/// <summary>
/// Local read-only gamepad snapshots. No login, pairing code or per-site setup.
/// Only 127.0.0.1 is bound. Browser pages are not allowed to read directly:
/// the HTTP endpoint has no CORS headers and rejects web page Origin headers.
/// The Chrome/Edge extension's worker reads and relays gamepad state.
/// </summary>
internal sealed class BrowserBridge : IDisposable
{
    public const int Port = 38471;
    private const int MaxRequestBytes = 8192;
    private readonly CancellationTokenSource cancellation = new();
    private readonly SemaphoreSlim capacity = new(8, 8);
    private TcpListener? listener;
    private string snapshot = "{\"version\":1,\"pads\":[],\"timestamp\":0}";
    private bool disposed;
    public string Status { get; private set; } = "DETENIDO";
    public bool Active => listener is not null;
    public string Address => $"http://127.0.0.1:{Port}/state";

    public bool Start()
    {
        if (disposed) throw new ObjectDisposedException(nameof(BrowserBridge));
        if (listener is not null) return true;
        try
        {
            var tcp = new TcpListener(IPAddress.Loopback, Port);
            tcp.Start(16);
            listener = tcp;
            Status = "AUTOMATICO 127.0.0.1:" + Port;
            _ = Task.Run(() => ServeAsync(tcp, cancellation.Token));
            return true;
        }
        catch (Exception ex)
        {
            Status = "ERROR: " + ex.Message;
            return false;
        }
    }

    public void UpdateJson(string json)
    {
        if (disposed) return;
        Volatile.Write(ref snapshot, json);
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

            if (!await capacity.WaitAsync(0))
            {
                client.Dispose();
                continue;
            }

            _ = Task.Run(async () =>
            {
                try { await HandleAsync(client, ct); }
                catch (Exception) { /* one remote request cannot stop the service */ }
                finally
                {
                    client.Dispose();
                    try { capacity.Release(); } catch (ObjectDisposedException) { }
                }
            }, CancellationToken.None);
        }
    }

    private async Task HandleAsync(TcpClient client, CancellationToken ct)
    {
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(ct);
        deadline.CancelAfter(TimeSpan.FromSeconds(2));
        using var stream = client.GetStream();
        using var reader = new StreamReader(stream, new UTF8Encoding(false),
            detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);

        var first = await reader.ReadLineAsync(deadline.Token);
        if (first is null || first.Length > 1024)
        {
            await RespondAsync(stream, 400, "{\"error\":\"bad request\"}", deadline.Token);
            return;
        }

        string? host = null, origin = null;
        var bytes = first.Length;
        var count = 0;
        while (true)
        {
            var line = await reader.ReadLineAsync(deadline.Token);
            if (line is null || line.Length == 0) break;
            bytes += line.Length;
            if (bytes > MaxRequestBytes || ++count > 30)
            {
                await RespondAsync(stream, 431, "{\"error\":\"too many headers\"}", deadline.Token);
                return;
            }
            var colon = line.IndexOf(':');
            if (colon <= 0) continue;
            var name = line[..colon].Trim();
            if (name.Equals("Host", StringComparison.OrdinalIgnoreCase))
                host = line[(colon + 1)..].Trim();
            if (name.Equals("Origin", StringComparison.OrdinalIgnoreCase))
                origin = line[(colon + 1)..].Trim();
        }

        // Exact Host blocks DNS rebinding to arbitrary web hostnames.
        if (host != $"127.0.0.1:{Port}")
        {
            await RespondAsync(stream, 403, "{\"error\":\"invalid host\"}", deadline.Token);
            return;
        }

        // Direct website fetches never receive a permissive CORS response.
        // Extension workers can send the chrome-extension:// origin, if present.
        if (origin is not null &&
            !origin.StartsWith("chrome-extension://", StringComparison.OrdinalIgnoreCase))
        {
            await RespondAsync(stream, 403, "{\"error\":\"web origins blocked\"}", deadline.Token);
            return;
        }

        if (first != "GET /state HTTP/1.1" && first != "GET /state HTTP/1.0")
        {
            await RespondAsync(stream, 404, "{\"error\":\"not found\"}", deadline.Token);
            return;
        }

        await RespondAsync(stream, 200, Volatile.Read(ref snapshot), deadline.Token);
    }

    private static async Task RespondAsync(NetworkStream stream, int status,
        string json, CancellationToken ct)
    {
        var body = Encoding.UTF8.GetBytes(json);
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
            + $"Content-Length: {body.Length}\r\n\r\n");
        await stream.WriteAsync(header, ct);
        await stream.WriteAsync(body, ct);
        await stream.FlushAsync(ct);
    }

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        cancellation.Cancel();
        listener?.Stop();
        listener = null;
        Status = "DETENIDO";
        // Do not dispose the semaphore while client handlers may release it.
        cancellation.Dispose();
    }

    // GitHub Actions: verifies zero-config access from localhost, denies
    // hostile Host/Origin values, and checks there is no wildcard CORS.
    public static async Task<string> SmokeTestAsync()
    {
        using var bridge = new BrowserBridge();
        bridge.UpdateJson("{\"version\":1,\"pads\":[{\"slot\":1,\"name\":\"FUTUREO_VJOY1\"}],\"timestamp\":123}");
        if (!bridge.Start()) return "ERROR: " + bridge.Status;

        using var client = new System.Net.Http.HttpClient(
            new System.Net.Http.HttpClientHandler { UseProxy = false })
        { Timeout = TimeSpan.FromSeconds(4) };
        var standard = await client.GetAsync(bridge.Address);
        var value = await standard.Content.ReadAsStringAsync();

        using var webOrigin = new System.Net.Http.HttpRequestMessage(
            System.Net.Http.HttpMethod.Get, bridge.Address);
        webOrigin.Headers.TryAddWithoutValidation("Origin", "https://example.com");
        var webResponse = await client.SendAsync(webOrigin);

        using var hostSpoof = new System.Net.Http.HttpRequestMessage(
            System.Net.Http.HttpMethod.Get, bridge.Address);
        hostSpoof.Headers.Host = "example.com";
        var hostResponse = await client.SendAsync(hostSpoof);

        using var extensionOrigin = new System.Net.Http.HttpRequestMessage(
            System.Net.Http.HttpMethod.Get, bridge.Address);
        extensionOrigin.Headers.TryAddWithoutValidation(
            "Origin", "chrome-extension://abcdefghijklmnopabcdefghijklmnop");
        var extensionResponse = await client.SendAsync(extensionOrigin);

        if ((int)standard.StatusCode != 200
            || !value.Contains("FUTUREO_VJOY1")
            || standard.Headers.Contains("Access-Control-Allow-Origin")
            || (int)webResponse.StatusCode != 403
            || (int)hostResponse.StatusCode != 403
            || (int)extensionResponse.StatusCode != 200)
            throw new InvalidOperationException(
                $"Zero-config bridge failed: localhost={standard.StatusCode}, "
                + $"web={webResponse.StatusCode}, dns={hostResponse.StatusCode}, "
                + $"extension={extensionResponse.StatusCode}");
        return "BRIDGE smoke OK: automatic localhost JSON, CORS off, web Origin and DNS rebinding blocked";
    }
}
