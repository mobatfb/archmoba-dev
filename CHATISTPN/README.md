# CHATISTPN — prototipo Python gratuito

Asistente local de información institucional de **https://home.isupol.edu.ec/**.

- **Costo de API: USD 0.** No utiliza OpenAI, Cloudflare ni otra IA remota.
- Solo responde con **datos contenidos en `respuestas.json`** y enlaces públicos al portal.
- La primera base incluye **44 respuestas revisadas / 200 formulaciones de pregunta / 21 URL de referencia principales**.
- Incluye un **rastreador** que añade fragmentos localizables de páginas, publicaciones y (opcionalmente) PDF del portal.
- A diferencia de un modelo generativo, esta primera versión es un buscador conversacional: no improvisa respuestas ni razona sobre documentos extensos.

## Archivos

| Archivo | Función |
|---|---|
| `app.py` | Chat en ventana nativa de Python (Tkinter), sin navegador ni servidor. |
| `respuestas.json` | Respuestas, formas de preguntar, URL de origen y estado de cobertura. |
| `crawler.py` | Recorrido de sitemap, REST WordPress y enlaces públicos; enriquece el JSON. |
| `README.md` | Instalación y uso. |

## 1. Ejecutar el chat en Windows

1. Instala **Python 3.10+** si aún no lo tienes.
2. Descarga la carpeta `CHATISTPN` completa.
3. Abre una consola dentro de la carpeta.
4. Ejecuta:

```bash
python app.py
```

Se abrirá **una ventana directamente en Windows**. No se inicia un servidor, no se monta una página web y no se abre un navegador. El programa lee `respuestas.json` desde la misma carpeta y muestra enlaces oficiales clicables.

Otras pruebas:

```bash
python app.py --cli
python app.py --test "¿Qué carreras y modalidades ofrece el ISTPN?"
```

Cierra la ventana para terminar. También puedes abrir `app.py` con doble clic en Windows, siempre que Python esté asociado con archivos `.py`. Requiere Python con **Tkinter**, que viene normalmente con las instalaciones oficiales de Windows.

## 2. Actualizar la base de conocimientos desde la web

La primera base está precargada, pero **no equivale a un escaneo absoluto**. El entorno desde el cual se elaboró no consiguió acceder al sitemap/REST del WordPress. Ejecuta el crawler desde tu PC o servidor si tienes conectividad al portal:

```bash
python crawler.py --max-pages 600
```

Para incluir PDF descargables (solo documentos públicos y con texto extraíble):

```bash
python -m pip install pypdf
python crawler.py --max-pages 0 --pdf --delay 1
```

`--max-pages 0` significa sin límite de páginas; **puede tardar y generar tráfico al sitio**. Emplea una demora de cortesía (al menos 0,5 segundos) y ejecuta el rastreo fuera de horas de mayor uso. `--pdf` puede consumir memoria y tiempo según el volumen de documentos. Algunos PDF escaneados necesitan OCR, que este prototipo no incluye.

El rastreador intenta localizar:

- `wp-sitemap.xml`, `sitemap_index.xml` y `sitemap.xml`.
- Entradas publicadas desde `/wp-json/wp/v2/pages` y `/wp-json/wp/v2/posts`, si están accesibles.
- Enlaces internos de cada página pública, con comprobación de `robots.txt`.
- PDF públicos, si `--pdf` está activado y `pypdf` está instalado.

**Genera `cobertura.json`** con cantidades, errores y páginas pendientes. Si algunas áreas requieren inicio de sesión, están bloqueadas o no se vinculan desde páginas públicas, **no pueden considerarse rastreadas**. No recoge contenidos privados ni intenta saltarse restricciones.

Al actualizar, conserva las respuestas manualmente verificadas y sustituye los fragmentos del rastreo anterior. El chat recarga el JSON cuando cambia el archivo. Haz copia del JSON antes de cambios masivos.

## 3. Ejemplos

- «¿Qué carreras y modalidades ofrece el ISTPN?»
- «¿Cuánto dura Criminalística?»
- «¿Dónde está el Reglamento de Bienestar Estudiantil?»
- «¿Cómo presento un oficio en línea?»
- «¿Cómo consultar mis notas en el SGA?»
- «¿Dónde encuentro las noticias?»

## Límites y seguridad

Este es un **prototipo de escritorio** y **no debe publicarse directamente como endpoint WordPress**. No abre ningún puerto ni recibe conexiones, no guarda conversaciones, rechaza instrucciones evidentemente ajenas al ISTPN y valida los enlaces antes de mostrarlos. El filtrado por vocabulario puede equivocarse; no sustituye una moderación exhaustiva.

El contenido del portal puede estar desactualizado (por ejemplo, convocatorias 2024/2025). Las fuentes se enlazan para contrastarlas; las respuestas de admisiones históricas incluyen advertencias. El rastreador no determina jurídicamente vigencias de reglamentos ni garantiza precisión de extracción en páginas complejas.

**Cobertura inicial:** ver `respuestas.json → cobertura`. Después de ejecutar `crawler.py`, revisar `cobertura.json` y las páginas pendientes antes de afirmar que el corpus está completo.
