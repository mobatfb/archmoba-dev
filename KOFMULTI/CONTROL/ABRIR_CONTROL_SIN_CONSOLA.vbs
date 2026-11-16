' KOFMULTI CONTROL v.0.0.2 — inicio oculto, sin consola
Option Explicit
Dim shell, fso, ruta, comando
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ruta = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = ruta
comando = "pyw -3 -B """ & fso.BuildPath(ruta, "KOF_Control.pyw") & """"
On Error Resume Next
shell.Run comando, 0, False
If Err.Number <> 0 Then
    MsgBox "No se pudo iniciar KOFMULTI CONTROL sin consola." & vbCrLf & _
           "Revisa que Python y PySide6 esten instalados.", vbCritical, "KOFMULTI v.0.0.2"
End If
On Error GoTo 0
