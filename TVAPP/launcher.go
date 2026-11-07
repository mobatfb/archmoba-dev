//go:build windows

// ARCHMOBA TVAPP: instalador/iniciador ligero para Windows.
// Compilacion: GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w -H=windowsgui" -o TVAPP_Launcher.exe launcher.go
package main

import (
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net/http"
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "sync"
    "syscall"
    "time"
    "unsafe"
)

const (
    appURL       = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/TVAPP/app.py"
    appCommitsURL = "https://api.github.com/repos/mobatfb/archmoba-dev/commits?path=TVAPP%2Fapp.py&per_page=1"
    title        = "ARCHMOBA | TVAPP"
    windowClass  = "ARCHMOBA_TVAPP_Launcher_Window"
    wmDestroy    = 0x0002
    wmClose      = 0x0010
    wmSetFont    = 0x0030
    wmApp        = 0x8000
    wmAppStatus  = wmApp + 1
    wmAppSuccess = wmApp + 2
    wmAppFailure = wmApp + 3
    wsOverlappedWindow = 0x00CF0000
    wsChild      = 0x40000000
    wsVisible    = 0x10000000
    ssLeft       = 0x00000000
    swShow       = 5
    mbOK         = 0x0
    mbIconError  = 0x10
)

type wndClassEx struct {
    Size       uint32
    Style      uint32
    WndProc    uintptr
    ClsExtra   int32
    WndExtra   int32
    Instance   uintptr
    Icon       uintptr
    Cursor     uintptr
    Background uintptr
    MenuName   *uint16
    ClassName  *uint16
    IconSmall  uintptr
}

type point struct { X, Y int32 }
type message struct {
    Hwnd uintptr
    Msg uint32
    WParam uintptr
    LParam uintptr
    Time uint32
    Pt point
    Private uint32
}

var (
    user32 = syscall.NewLazyDLL("user32.dll")
    kernel32 = syscall.NewLazyDLL("kernel32.dll")
    gdi32 = syscall.NewLazyDLL("gdi32.dll")
    procCreateWindowEx = user32.NewProc("CreateWindowExW")
    procDefWindowProc = user32.NewProc("DefWindowProcW")
    procRegisterClass = user32.NewProc("RegisterClassExW")
    procDestroyWindow = user32.NewProc("DestroyWindow")
    procPostQuitMessage = user32.NewProc("PostQuitMessage")
    procGetMessage = user32.NewProc("GetMessageW")
    procTranslateMessage = user32.NewProc("TranslateMessage")
    procDispatchMessage = user32.NewProc("DispatchMessageW")
    procShowWindow = user32.NewProc("ShowWindow")
    procUpdateWindow = user32.NewProc("UpdateWindow")
    procSetWindowText = user32.NewProc("SetWindowTextW")
    procPostMessage = user32.NewProc("PostMessageW")
    procMessageBox = user32.NewProc("MessageBoxW")
    procSendMessage = user32.NewProc("SendMessageW")
    procLoadCursor = user32.NewProc("LoadCursorW")
    procGetModuleHandle = kernel32.NewProc("GetModuleHandleW")
    procGetStockObject = gdi32.NewProc("GetStockObject")
    window uintptr
    statusLabel uintptr
    lastText string
    lastError string
    stateMu sync.Mutex
)

func utf16(s string) *uint16 { p, _ := syscall.UTF16PtrFromString(s); return p }

func setStatus(msg string) {
    stateMu.Lock(); lastText = msg; stateMu.Unlock()
    if window != 0 { procPostMessage.Call(window, wmAppStatus, 0, 0) }
}

func fail(err error) {
    stateMu.Lock(); lastError = err.Error(); stateMu.Unlock()
    if window != 0 { procPostMessage.Call(window, wmAppFailure, 0, 0) }
}

func newControl(class, text string, x, y, w, h int32) uintptr {
    hwnd, _, _ := procCreateWindowEx.Call(
        0, uintptr(unsafe.Pointer(utf16(class))), uintptr(unsafe.Pointer(utf16(text))),
        wsChild | wsVisible | ssLeft, uintptr(x), uintptr(y), uintptr(w), uintptr(h),
        window, 0, 0, 0,
    )
    font, _, _ := procGetStockObject.Call(17) // DEFAULT_GUI_FONT
    procSendMessage.Call(hwnd, wmSetFont, font, 1)
    return hwnd
}

func windowProc(hwnd uintptr, msg uint32, wParam, lParam uintptr) uintptr {
    switch msg {
    case wmAppStatus:
        stateMu.Lock(); msg := lastText; stateMu.Unlock()
        procSetWindowText.Call(statusLabel, uintptr(unsafe.Pointer(utf16(msg))))
        return 0
    case wmAppSuccess:
        procDestroyWindow.Call(hwnd)
        return 0
    case wmAppFailure:
        stateMu.Lock(); detail := lastError; stateMu.Unlock()
        procMessageBox.Call(hwnd,
            uintptr(unsafe.Pointer(utf16(detail + "\n\nVerifica la conexion a Internet, Python 3 y vuelve a ejecutar el iniciador."))),
            uintptr(unsafe.Pointer(utf16("TVAPP: no se pudo iniciar"))), mbOK|mbIconError,
        )
        procDestroyWindow.Call(hwnd)
        return 0
    case wmClose:
        procDestroyWindow.Call(hwnd)
        return 0
    case wmDestroy:
        procPostQuitMessage.Call(0)
        return 0
    }
    result, _, _ := procDefWindowProc.Call(hwnd, uintptr(msg), wParam, lParam)
    return result
}

func makeWindow() error {
    instance, _, _ := procGetModuleHandle.Call(0)
    className := utf16(windowClass)
    cursor, _, _ := procLoadCursor.Call(0, 32512) // IDC_ARROW
    cls := wndClassEx{
        Size: uint32(unsafe.Sizeof(wndClassEx{})),
        WndProc: syscall.NewCallback(windowProc),
        Instance: instance,
        Cursor: cursor,
        Background: 6, // COLOR_WINDOW + 1
        ClassName: className,
    }
    atom, _, err := procRegisterClass.Call(uintptr(unsafe.Pointer(&cls)))
    if atom == 0 { return fmt.Errorf("no se registro la ventana: %v", err) }
    window, _, err = procCreateWindowEx.Call(
        0, uintptr(unsafe.Pointer(className)), uintptr(unsafe.Pointer(utf16(title))),
        wsOverlappedWindow, 0x80000000, 0x80000000, 540, 205,
        0, 0, instance, 0,
    )
    if window == 0 { return fmt.Errorf("no se creo la ventana: %v", err) }
    newControl("STATIC", "ARCHMOBA  |  TVAPP", 30, 26, 470, 30)
    statusLabel = newControl("STATIC", "Preparando iniciador...", 30, 74, 475, 60)
    procShowWindow.Call(window, swShow)
    procUpdateWindow.Call(window)
    return nil
}

func localDir() (string, error) {
    base := os.Getenv("LOCALAPPDATA")
    if base == "" {
        configDir, err := os.UserConfigDir()
        if err != nil { return "", err }
        base = configDir
    }
    dest := filepath.Join(base, "ARCHMOBA", "TVAPP")
    if err := os.MkdirAll(dest, 0700); err != nil { return "", err }
    return dest, nil
}

func resolvedAppURL(client *http.Client, ctx context.Context) (string, string) {
    requestURL := fmt.Sprintf("%s&cache_bust=%d", appCommitsURL, time.Now().UnixNano())
    req, err := http.NewRequestWithContext(ctx, "GET", requestURL, nil)
    if err != nil { return appURL, "" }
    req.Header.Set("User-Agent", "ARCHMOBA-TVAPP-Launcher/1.1")
    req.Header.Set("Accept", "application/vnd.github+json")
    req.Header.Set("Cache-Control", "no-cache, no-store, max-age=0")
    resp, err := client.Do(req)
    if err != nil { return appURL, "" }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK { return appURL, "" }
    body, err := io.ReadAll(io.LimitReader(resp.Body, 256*1024))
    if err != nil { return appURL, "" }
    var commits []struct { SHA string `json:"sha"` }
    if json.Unmarshal(body, &commits) != nil || len(commits) == 0 { return appURL, "" }
    sha := commits[0].SHA
    if len(sha) != 40 { return appURL, "" }
    for _, ch := range sha {
        if !strings.ContainsRune("0123456789abcdef", ch) { return appURL, "" }
    }
    return fmt.Sprintf("https://raw.githubusercontent.com/mobatfb/archmoba-dev/%s/TVAPP/app.py", sha), sha
}

func downloadApp(target string) error {
    ctx, cancel := context.WithTimeout(context.Background(), 35*time.Second)
    defer cancel()
    client := &http.Client{Timeout: 35*time.Second}
    setStatus("Comprobando ultimo commit de app.py...")
    downloadURL, sha := resolvedAppURL(client, ctx)
    if sha != "" {
        setStatus("Descargando app.py del commit " + sha[:8] + "...")
    } else {
        setStatus("Descargando app.py directamente (sin cache)...")
        downloadURL = fmt.Sprintf("%s?cache_bust=%d", appURL, time.Now().UnixNano())
    }
    req, err := http.NewRequestWithContext(ctx, "GET", downloadURL, nil)
    if err != nil { return err }
    req.Header.Set("User-Agent", "ARCHMOBA-TVAPP-Launcher/1.0")
    req.Header.Set("Cache-Control", "no-cache")
    resp, err := client.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK { return fmt.Errorf("GitHub devolvio HTTP %d", resp.StatusCode) }
    bytes, err := io.ReadAll(io.LimitReader(resp.Body, 2*1024*1024+1))
    if err != nil { return err }
    if len(bytes) > 2*1024*1024 { return errors.New("app.py excede 2 MB") }
    body := string(bytes)
    if !strings.Contains(body, "def main(") || !strings.Contains(body, "__name__") {
        return errors.New("el archivo descargado no parece ser app.py de TVAPP")
    }
    temp := target + ".download"
    if err := os.WriteFile(temp, bytes, 0600); err != nil { return err }
    if err := os.Rename(temp, target); err != nil {
        os.Remove(temp)
        return err
    }
    return nil
}

func runOutput(timeout time.Duration, program string, args ...string) (string, error) {
    ctx, cancel := context.WithTimeout(context.Background(), timeout)
    defer cancel()
    cmd := exec.CommandContext(ctx, program, args...)
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000} // CREATE_NO_WINDOW
    data, err := cmd.CombinedOutput()
    if ctx.Err() != nil { return "", ctx.Err() }
    return strings.TrimSpace(string(data)), err
}

func probePython(program string, prefix ...string) string {
    args := append(append([]string{}, prefix...), "-c", "import sys,tkinter; assert sys.version_info >= (3,10); print(sys.executable)")
    output, err := runOutput(9*time.Second, program, args...)
    if err != nil { return "" }
    lines := strings.Split(output, "\n")
    exePath := strings.TrimSpace(lines[len(lines)-1])
    if exePath != "" && strings.EqualFold(filepath.Ext(exePath), ".exe") {
        if _, err := os.Stat(exePath); err == nil { return exePath }
    }
    return ""
}

func findPython() string {
    if p := probePython("py", "-3"); p != "" { return p }
    if p := probePython("python"); p != "" { return p }
    if p := probePython("python3"); p != "" { return p }
    user := os.Getenv("LOCALAPPDATA")
    for _, ver := range []string{"Python313", "Python314", "Python312", "Python311", "Python310"} {
        path := filepath.Join(user, "Programs", "Python", ver, "python.exe")
        if p := probePython(path); p != "" { return p }
    }
    pf := os.Getenv("ProgramFiles")
    for _, ver := range []string{"Python313", "Python314", "Python312", "Python311", "Python310"} {
        path := filepath.Join(pf, ver, "python.exe")
        if p := probePython(path); p != "" { return p }
    }
    return ""
}

func installPython() error {
    setStatus("Python 3 no disponible. Instalando con winget...")
    if _, err := exec.LookPath("winget"); err != nil {
        return errors.New("Python 3.10+ con tkinter no encontrado. winget no esta disponible; instala Python desde https://www.python.org/downloads/windows/")
    }
    output, err := runOutput(5*time.Minute, "winget", "install", "--id", "Python.Python.3.13", "--exact", "--source", "winget", "--scope", "user", "--silent", "--accept-package-agreements", "--accept-source-agreements")
    if err != nil {
        trimmed := output
        if len(trimmed) > 500 { trimmed = trimmed[len(trimmed)-500:] }
        return fmt.Errorf("no se pudo instalar Python: %s: %v", trimmed, err)
    }
    return nil
}

func startPython(pythonExe, script, directory string) error {
    // pythonw.exe abre la interfaz tkinter sin ventana de consola.
    guiExe := filepath.Join(filepath.Dir(pythonExe), "pythonw.exe")
    if _, err := os.Stat(guiExe); err == nil { pythonExe = guiExe }
    cmd := exec.Command(pythonExe, script)
    cmd.Dir = directory
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
    if err := cmd.Start(); err != nil { return err }
    return cmd.Process.Release()
}

func work() {
    dir, err := localDir()
    if err != nil { fail(err); return }
    script := filepath.Join(dir, "app.py")
    setStatus("Descargando app.py desde GitHub...")
    if err := downloadApp(script); err != nil {
        if file, statErr := os.Stat(script); statErr != nil || file.Size() == 0 {
            fail(fmt.Errorf("no se pudo descargar app.py: %w", err))
            return
        }
        setStatus("Sin conexion; iniciando version local guardada...")
    } else {
        setStatus("app.py descargado correctamente.")
    }
    python := findPython()
    if python == "" {
        if err := installPython(); err != nil { fail(err); return }
        setStatus("Python instalado. Preparando ejecucion...")
        python = findPython()
        if python == "" {
            fail(errors.New("Python se instalo pero no se pudo localizar con tkinter. Reinicia Windows o instala Python desde python.org"))
            return
        }
    }
    setStatus("Abriendo TVAPP...")
    if err := startPython(python, script, dir); err != nil { fail(fmt.Errorf("no se pudo ejecutar app.py: %w", err)); return }
    procPostMessage.Call(window, wmAppSuccess, 0, 0)
}

func main() {
    if err := makeWindow(); err != nil {
        procMessageBox.Call(0, uintptr(unsafe.Pointer(utf16(err.Error()))), uintptr(unsafe.Pointer(utf16(title))), mbOK|mbIconError)
        return
    }
    go work()
    var msg message
    for {
        result, _, _ := procGetMessage.Call(uintptr(unsafe.Pointer(&msg)), 0, 0, 0)
        if int32(result) <= 0 { break }
        procTranslateMessage.Call(uintptr(unsafe.Pointer(&msg)))
        procDispatchMessage.Call(uintptr(unsafe.Pointer(&msg)))
    }
}
