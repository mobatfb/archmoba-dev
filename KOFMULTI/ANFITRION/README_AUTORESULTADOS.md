# KOFMULTI · Marcador leído del juego (v1.16.5)

**Objetivo:** que la tabla Ganados / Perdidos / Perfecto / Puntaje se actualice a partir de lo que muestra KOF 2002 en la ventana local de MAME, nunca por las teclas enviadas desde un control remoto.

## Qué hace actualmente

- `KOF_Anfitrion.py` ejecuta el MAME antiguo y abre `KOF_AutoResultados.py` en un hilo independiente.
- El detector captura temporalmente **la ventana local de MAME en memoria** y procesa el texto con OCR, sin enviar imágenes ni guardar capturas.
- Si ve repetidamente un resultado inequívoco como `1P WINS`, `P2 WINNER` o `WINNER PLAYER 2`, y los dos jugadores siguen siendo los mismos, registra:
  - **Ganados:** +1 al ganador
  - **Perdidos:** +1 al rival
  - **Perfecto:** +1 extra al ganador si aparece `PERFECT` en el resultado
  - **Puntaje:** Ganados + Perfecto (ambos valen 1 punto)
- Tiene protección contra duplicados para que un rótulo que permanezca en pantalla no cuente más de una vez.
- La tabla es **solo lectura**: ya no admite doble clic ni clic derecho para modificar números.
- Desconectar un jugador no añade ni resta victorias; desconectar al último ganador solicita reiniciar MAME como antes.

## Preparación del equipo Windows (anfitrión)

Los dos Python deben estar en la **misma carpeta**:
```
KOFMULTI/ANFITRION/
  KOF_Anfitrion.py
  KOF_AutoResultados.py
```

En el anfitrión instala una sola vez Pillow:
```powershell
py -m pip install --no-cache-dir Pillow
```
También necesitas **Tesseract OCR para Windows** con idioma inglés `eng`.
Puede estar en `PATH`, en `C:\Program Files\Tesseract-OCR\tesseract.exe`
o en `ANFITRION\Tesseract-OCR\tesseract.exe`, con sus archivos de idioma.
No es necesario instalar OCR en la computadora del jugador.

Abre la sala e inicia MAME. En **ACTIVIDAD DEL SERVIDOR** aparecerá:
`AUTO MARCADOR: lectura local de MAME activa` o un aviso si falta una dependencia.

Para validar la lógica de texto sin abrir MAME:
```powershell
py -B KOF_AutoResultados.py
```

## Limitaciones que debemos validar antes de usarlo en torneos

El archivo original `KOF2022GAME.zip` trae una versión de MAME anterior a la interfaz Lua moderna. Este prototipo no lee variables internas de la ROM: interpreta imágenes **solo en el PC anfitrión**.

**No se ha probado todavía en la partida real de la modificación `kf2k2mp2`.** Si el juego no muestra claramente `P1/1P` o `P2/2P` junto al ganador, el detector **no registrará ningún resultado** para evitar asignar puntos a la persona equivocada. También puede fallar si DirectDraw no permite capturar la ventana. En ese caso necesitaremos identificar los indicadores reales (pantallas o direcciones de RAM), y ajustar el detector.

Un `PERFECT` se reconoce por el rótulo en pantalla y se vincula al ganador correspondiente; no debe contarse por separado si no hay resultado confirmado. El resultado registrado puede referirse a un combate/round, dependiendo de qué escena presente el juego. Este comportamiento requiere validación con partidos reales.

**No se realiza transmisión de video ni audio, y no se almacenan capturas de pantalla.** El OCR utiliza CPU del anfitrión; si observas tirones, primero valida el consumo de recursos en la máquina Windows.
