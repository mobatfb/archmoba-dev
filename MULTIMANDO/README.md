# MULTIMANDO v5.7 + Anfitrión Python v1.2 — Protocolo de 2 bytes

Parche incremental para la palanca web y el anfitrión de Windows.
No toca Laravel ni MySQL, el servidor PHP solo consulta `/api/geturlmultimando`.

## Diseño de botones

- Arriba: **X · Y · L**; abajo: **A · B · R**.
- `X`, `Y`, `L`, `A`, `B`, `R` se conectan a Xbox X, Y, LB, A, B, RB respectivamente.
- Teclas predeterminadas: U/I/O para X/Y/L; J/K/L para A/B/R; WASD en la palanca.
- START = Enter, SELECT = Retroceso. La personalización guardada sigue vigente.

## Protocolo compacto WebSocket

Cada pulsación es un frame WebSocket de texto de **2 bytes UTF-8**:
`<codigo>1` significa presionar, `<codigo>0` significa soltar.
No se envía un JSON por cada pulsación. La sobrecarga de WebSocket/TLS es adicional.

| Visible | Código | Pulsar | Soltar | Acción Python |
|---|---|---|---|---|
| X | x | `x1` | `x0` | button_x |
| Y | y | `y1` | `y0` | button_y |
| L | l | `l1` | `l0` | button_lb |
| A | a | `a1` | `a0` | button_a |
| B | b | `b1` | `b0` | button_b |
| R | r | `r1` | `r0` | button_rb |
| Arriba | u | `u1` | `u0` | ar |
| Abajo | d | `d1` | `d0` | ab |
| Izquierda | i | `i1` | `i0` | iz |
| Derecha | e | `e1` | `e0` | de |
| START | t | `t1` | `t0` | start |
| SELECT | s | `s1` | `s0` | select |

Conexión/identificación (`hello`) y mensajes de servidor (welcome/state/notice/error) siguen siendo JSON.
Los mensajes JSON de entrada del protocolo anterior se toleran de forma temporal para evitar fallos durante la actualización.

## Consola Python

En REGISTRO DE EVENTOS se muestra el puesto asignado, nombre y botón lógico:

`CONTROL P1 | Bryan | X (x1) | PRESIONADO`
`CONTROL P1 | Bryan | X (x0) | SOLTADO`

La tecla física personalizable no se transmite. No se registran pulsaciones duplicadas.

## Instalación

1. En el hosting sustituye sólo `MULTIMANDO/palanca.php`, `MULTIMANDO/assets/palanca.css` y `MULTIMANDO/private/palanca.enc`.
2. En Windows sustituye sólo `MULTIMANDO/ANFITRION/MULTIMANDO_Anfitrion.py` y reinicia el anfitrión/sala.
3. Conserva `MULTIMANDO/private/FRASE_CIFRADO.php`; el nuevo `.enc` usa exactamente la misma frase privada. **No está incluido en el parche.**
4. En el navegador actualiza con Ctrl+F5. La casilla AUTO sigue consultando la API sin cambios.

**Sin cambios:** P1/P2, cola FIFO, 10 minutos solo cuando haya espera, Cloudflare, publicación API ni seguridad de `control.php`.

Para verificar la lógica local sin mandos reales: `py MULTIMANDO_Anfitrion.py --selftest`.
Para uso en Windows: `py -m pip install websockets vgamepad` y controlador ViGEmBus.
