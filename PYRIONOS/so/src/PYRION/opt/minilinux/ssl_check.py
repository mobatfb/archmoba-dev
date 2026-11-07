#!/usr/bin/python3
import os
import socket
import ssl
import tempfile
import urllib.request
import urllib.error

HOST = "api.github.com"
URL = "https://api.github.com"
CAFILE = "/etc/ssl/certs/ca-certificates.crt"


def one_line_name(name):
    out = []
    for group in name or ():
        for key, value in group:
            out.append(f"{key}={value}")
    return ", ".join(out) if out else "(unknown)"


def peer_info_unverified():
    try:
        raw = socket.create_connection((HOST, 443), timeout=8)
        ctx = ssl._create_unverified_context()
        with ctx.wrap_socket(raw, server_hostname=HOST) as s:
            der = s.getpeercert(binary_form=True)
        pem = ssl.DER_cert_to_PEM_cert(der)
        fd, path = tempfile.mkstemp(prefix="peer-", suffix=".pem")
        try:
            os.write(fd, pem.encode("ascii"))
            os.close(fd)
            cert = ssl._ssl._test_decode_cert(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        print("TLS peer subject :", one_line_name(cert.get("subject")))
        print("TLS peer issuer  :", one_line_name(cert.get("issuer")))
        print("TLS peer expires :", cert.get("notAfter", "?"))
    except Exception as exc:
        print("TLS peer inspect : FAIL", repr(exc))


def try_url(label, context=None):
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "MiniLinux-AMDEV-SSLCheck/1.12"})
        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            print(f"{label}: OK HTTP {response.status}")
            return True
    except Exception as exc:
        print(f"{label}: FAIL {type(exc).__name__}: {exc}")
        return False


print("=== MiniLinux SSL diagnostic 1.12 ===")
print("OpenSSL:", ssl.OPENSSL_VERSION)
print("SSL_CERT_FILE:", os.environ.get("SSL_CERT_FILE", "(unset)"))
print("SSL_CERT_DIR :", os.environ.get("SSL_CERT_DIR", "(unset)"))
print("Default paths:", ssl.get_default_verify_paths())
try:
    ctx0 = ssl.create_default_context()
    print("Loaded CA certificates:", len(ctx0.get_ca_certs()))
except Exception as exc:
    print("CA load: FAIL", repr(exc))

try:
    ips = sorted({x[4][0] for x in socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)})
    print("DNS:", HOST, "->", ", ".join(ips))
except Exception as exc:
    print("DNS: FAIL", repr(exc))

ok_default = try_url("HTTPS default")
try:
    explicit = ssl.create_default_context(cafile=CAFILE)
    ok_explicit = try_url("HTTPS explicit CA", explicit)
except Exception as exc:
    ok_explicit = False
    print("HTTPS explicit CA: FAIL creating context:", repr(exc))

if ok_default or ok_explicit:
    print("RESULT: SSL_OK")
else:
    print("RESULT: SSL_VERIFY_FAILED")
    peer_info_unverified()
    print("NOTE: verification stays enabled; no insecure download fallback is used.")
