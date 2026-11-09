# Himnos Policiales para Android — v1.3.0

Proyecto Android nativo, independiente de TVAPP. Compilado con APKBDEV y `MediaPlayer`.

## Interfaz
- **Fondo completo:** `assets/fondo.webp`, construido a partir del último boceto aprobado.
- **Botón Ecuador:** `assets/ecuador.webp`, bandera completa amarillo/azul/rojo con su escudo, esquinas tipo app redondeadas y brillo azul.
- **Botón Policía:** `assets/policia.webp`, blanco/azul tipo bandera con escudo policial completo, esquinas redondeadas y brillo azul.
- **Botón STOP:** `assets/stop.webp`, círculo rojo con cuadrado blanco.
- **Barra inferior:** solo informativa, muestra tiempo transcurrido y duración, no se puede arrastrar.

## Comportamiento
- Tocar **Ecuador** reproduce el Himno Nacional (2:22) desde cero.
- Tocar **Policía** reproduce el Himno de la Policía (1:34) desde cero.
- Inicio con aumento gradual de volumen durante 2 segundos.
- **STOP detiene inmediatamente** el audio y reinicia el contador a 00:00.
- Si se selecciona otro himno, detiene el anterior y comienza el nuevo.
- Música local: los dos archivos MP3 originales vienen incluidos. No necesita Internet.
- La imagen personalizada del lanzador enviada previamente por el usuario se conserva.

## Compilación automatizada
```bash
python3 apkbdev/projects/himnos-policiales/unpack_resources.py
python3 apkbdev/tools/build_apk.py --project himnos-policiales
```

`.github/workflows/apkbdev-build.yml` compila y publica el APK en GitHub Releases.
Los cuatro recursos WEBP aprobados y los audios se verifican mediante SHA-256 durante la compilación.
