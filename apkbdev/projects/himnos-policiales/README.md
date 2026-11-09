# Himnos Policiales para Android — v1.3.5

Proyecto Android nativo, independiente de TVAPP. Compilado con APKBDEV y `MediaPlayer`.

## Interfaz
- **Fondo completo:** `assets/fondo.webp`, construido a partir del último boceto aprobado.
- **Botón Ecuador:** `assets/ecuador.webp`, bandera completa amarillo/azul/rojo con su escudo, esquinas tipo app redondeadas y brillo azul.
- **Botón Policía:** `assets/policia.webp`, blanco/azul tipo bandera con escudo policial completo, esquinas redondeadas y brillo azul.
- **Botón STOP:** `assets/stop.webp`, círculo rojo con cuadrado blanco.
- **Borde integrado de selección:** no se dibujan rectángulos adicionales ni márgenes artificiales. El color dorado (Ecuador) o celeste (Policía) ilumina el contorno exacto del propio botón redondeado; permanece durante la reproducción y desaparece con STOP, al terminar o ante un error. El recurso seleccionado se genera desde los WEBP originales con Pillow en APKBDEV.
- **Barra inferior:** solo informativa, muestra tiempo transcurrido y duración, no se puede arrastrar.

## Comportamiento
- Tocar **Ecuador** reproduce el Himno Nacional (2:22) desde cero.
- Tocar **Policía** reproduce el Himno de la Policía (1:34) desde cero.
- Inicio con aumento gradual de volumen durante 2 segundos.
- **STOP detiene inmediatamente** el audio y reinicia el contador a 00:00.
- Si se selecciona otro himno, detiene el anterior y comienza el nuevo.
- Música local: los dos archivos MP3 originales vienen incluidos. No necesita Internet.
- Ícono del lanzador optimizado sin bordes negros: conserva el diseño mitad Ecuador/mitad Policía e incorpora el escudo policial exacto de referencia entregado por el usuario.
- Android usa un ícono adaptativo en `res/mipmap-anydpi-v26/ic_launcher.xml`, con colores que llenan la forma de cada lanzador. No se modifica el diseño interno de la pantalla.


## Publicidad dinámica (pub.pub)
- El recuadro publicitario aparece en el extremo inferior derecho, sobre la cinta tricolor, como en la captura de referencia.
- Muestra la miniatura del anuncio, su `description` y el botón naranja `button_text`. Solo el botón abre `button_url` en el navegador.
- En `pub.pub` del repositorio, el campo numérico `selected_id` selecciona qué objeto del arreglo `ads` mostrar. Todos los nombres están en inglés: `id`, `image`, `description`, `button_text`, `button_url`.
- La aplicación consulta el JSON público de GitHub al abrirse o al volver al primer plano; modificar `selected_id`, imágenes, texto o URL no exige recompilar la APK.
- **Sin publicidad offline ni caché:** no se empaqueta `pub.pub` ni miniaturas de anuncios dentro del APK. Tampoco se leen anuncios de `SharedPreferences` ni archivos locales.
- En cada apertura o regreso a la app se oculta inmediatamente cualquier anuncio previo, se consulta `pub.pub` exclusivamente por HTTPS y se descarga la imagen de la publicación seleccionada.
- Si falla la red, el JSON, la imagen o el `selected_id`, no se muestra absolutamente ningún anuncio.
- Las imágenes de anuncios se conservan solo en `public/` del repositorio (servidas desde Internet), **fuera de los assets del APK**.
- Los himnos siguen disponibles completamente sin conexión. El permiso de Internet se usa para descargar anuncios/imágenes.

## Compilación automatizada
```bash
python3 apkbdev/projects/himnos-policiales/unpack_resources.py
python3 apkbdev/tools/build_apk.py --project himnos-policiales
```

`.github/workflows/apkbdev-build.yml` compila y publica el APK en GitHub Releases.
Los cuatro recursos WEBP aprobados y los audios se verifican mediante SHA-256 durante la compilación.
