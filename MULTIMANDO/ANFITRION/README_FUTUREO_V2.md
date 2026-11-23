MULTIMANDO ANFITRION FUTUREO v2.0.0
================================
Windows 10/11 x64. Usa el motor FUTUREO v0.8.4 y NO necesita vJoy antiguo ni pyvjoystick.

CAMBIAR CAPACIDAD EN VIVO (1..8)
--------------------------------
1. Abre FUTUREO VJOY v0.8.4, crea al menos un mando en INICIAR.
2. Abre MULTIMANDO_FUTUREO_Anfitrion_v2_0_0.py.
3. Configura puestos REMOTO/CONTROLADO y pulsa ABRIR SALA.
4. Si hay visitantes, el enlace publico y la sala NO se interrumpen.
5. Cambia el selector Jugadores (1..8) y pulsa APLICAR EN VIVO.
6. Si aumentas: se agregan solo los mandos nuevos y se atiende la cola FIFO.
7. Si reduces: suelta mandos de numeros altos, y sus jugadores pasan a la cola
   detras de quienes ya esperaban, preservando su tiempo restante de juego.
8. Los puestos que permanecen no se recrean ni pierden su turno.
9. Si hay jugadores afectados, el programa pide confirmacion.
10. El ID de sala, WebSocket y enlace Cloudflare permanecen activos.

CONTROLADORES
-------------
FUTUREO_VJOY1..8; hasta 16 botones, analogico izquierdo X/Y
y D-Pad HID de 8 direcciones. Los clientes PHP existentes siguen
enviando WASD/UIOJKL, A/B/X/Y/L/R, SELECT y START por WebSocket.
El programa utiliza un puente HTTP localhost con FUTUREO.

PUERTOS
-------
8766: servidor de visitantes (WebSocket), publicable con Cloudflare.
38471: puente de solo lectura de la extension Chrome/Edge.
38472: puente local de entradas del anfitrion, solo 127.0.0.1.
       GET /health, POST /input, POST /capacity.
El puerto 38472 no se publica por Cloudflare y NO ejecuta comandos
arbitrarios; valida el Host, Origin, tipo/tamano de JSON y cabecera
X-Futureo-Client, sin clave segun la preferencia del usuario.
Procesos locales de terceros podrian imitar esa cabecera: utiliza
solo software de confianza en tu computadora.

TURNOS
------
- 600 segundos por jugador, consumidos solo mientras exista cola.
- Cuenta atras 3 segundos y ventana de activacion de 10 segundos.
- Hasta 64 visitantes y hasta 8 mandos ocupados.
- Reconexion hasta 35 segundos; liberacion segura de pulsaciones.
- FIFO para rotaciones por tiempo o administracion.
- Al reducir, los desplazados no pierden su sesion y conservan
  los segundos de juego que les quedaban.

INSTALACION PYTHON
------------------
Ejecuta: py MULTIMANDO_FUTUREO_Anfitrion_v2_0_0.py
Si faltan, se instalan websockets y pygame. No pyvjoystick.
Para pruebas sin hardware: py MULTIMANDO_FUTUREO_Anfitrion_v2_0_0.py --selftest

NOTAS
-----
El driver HIDMaestro requiere UAC al instalarse la primera vez.
FUTUREO debe permanecer abierto. No ejecutes simultaneamente
dos anfitriones para controlar los mismos mandos.
