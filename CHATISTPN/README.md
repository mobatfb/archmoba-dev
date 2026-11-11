# CHATISTPN v0.4 — prototipo Python sin consumo de tokens

Asistente de escritorio para consultar información pública del [Instituto Superior Tecnológico Policía Nacional](https://home.isupol.edu.ec/), usando solamente datos revisados y enlaces oficiales.

**No utiliza OpenAI ni otra API de inteligencia artificial**. Es un buscador local de preguntas y respuestas: no genera explicaciones nuevas a partir de una IA, y no accede a datos privados de estudiantes o docentes.

## Ejecución (un solo archivo)

El único archivo necesario en la PC para abrir la interfaz es `app.py`. Necesitas Python 3.10+ con Tkinter (normalmente instalado en Windows):

```powershell
python app.py
```

Abre directamente una ventana del escritorio **sin navegador ni servidor HTTP**. Al iniciar, `app.py` descarga el archivo `CHATISTPN/respuestas.json` de la rama `main` del repositorio `mobatfb/archmoba-dev` y guarda una copia de respaldo en el equipo. Puedes pulsar **Actualizar desde GitHub** para obtener cambios nuevos. Si no hay conexión, usa la última copia descargada previamente.

Para probar preguntas sin abrir ventana:

```powershell
python app.py --test "¿Cuáles son las líneas de investigación del ISTPN?"
```

## Contenido de la edición 0.4

- **220 fichas de respuestas** y **949 formulaciones de preguntas**; estos números corresponden a la base preparada el 11/11/2026, antes de rastreos posteriores.
- 40 direcciones de origen o navegación (incluyendo páginas de carreras y sistemas del dominio institucional).
- Oferta académica, modalidades, admisiones, requisitos publicados, carreras y datos de contacto.
- Bienestar Estudiantil, biblioteca, guías EVA/SGA/SIG/DOCPOL, trámites y servicios institucionales.
- Siete líneas y principios de investigación, noticias fechadas, rendiciones de cuentas, actividades institucionales.
- **74 documentos normativos localizables**: se verificó su **título en el índice**, pero **no se analizaron sus PDF** ni se confirmó su vigencia jurídica.

La base incluye `cobertura` con los límites del muestreo y cada registro incluye URL de origen. Nunca debe anunciarse una convocatoria de 2024/2025 como abierta en 2026.

## ¿Se ha examinado toda la web?

**No.** La consulta programática desde el entorno de preparación no consiguió resolver/acceder por HTTP a `home.isupol.edu.ec`; las fichas se basan en páginas públicas examinadas mediante el índice web, no en una descarga completa de WordPress. No se revisaron todos los PDF, archivos no enlazados, páginas privadas ni los contenidos de plataformas protegidas. El número real de URLs públicas pendientes no puede confirmarse sin ejecutar el rastreador sobre la conexión del portal.

El archivo `crawler.py` ofrece un recorrido adicional de las páginas públicas: sitemaps, entradas de WordPress REST cuando están abiertas y enlaces internos, respetando `robots.txt` y una pausa entre peticiones. Se debe ejecutar desde una computadora con acceso al dominio:

```powershell
python crawler.py --max-pages 600 --delay 1
```

Si quieres seguir los enlaces públicos sin un límite fijo de páginas (sigue existiendo el límite conservador de fragmentos para no sobrepasar la capacidad del cliente):

```powershell
python crawler.py --max-pages 0 --delay 1
```

Para indexar PDF descargables con texto (opcional):

```powershell
python -m pip install pypdf
python crawler.py --max-pages 0 --pdf --delay 1
```

Generará `cobertura.json` con URLs visitadas, errores, páginas pendientes, contenidos excluidos y cantidad de fragmentos. Lee ese informe antes de declarar que el rastreo se ha completado.

## Protección de calidad de las respuestas

En la revisión se detectó **contenido publicitario ajeno a la institución** en determinadas páginas públicas. El rastreador actualizado aparta páginas con indicadores conocidos de contenido no institucional para revisión humana, en lugar de incorporarlas automáticamente a la base. Este filtro es básico y **no sustituye una auditoría de seguridad del sitio** ni garantiza encontrar todas las formas de contaminación.

Recomendación para el administrador WordPress: revisar las páginas afectadas y sus revisiones, usuarios, plugins, archivos y registros de seguridad, respaldar el sitio y eliminar únicamente contenido confirmado como no autorizado. No publicar respuestas basadas en esos fragmentos hasta resolver el problema.

Las respuestas de documentos normativos solo confirman que el archivo aparece enlazado; no sustituyen una interpretación legal ni la lectura de la última versión aprobada. La información de personas, ofertas y procesos puede cambiar sin que el JSON se actualice automáticamente.

## Archivos del repositorio

| Archivo | Uso |
|---|---|
| `app.py` | Programa de escritorio; descarga el JSON del repositorio. |
| `respuestas.json` | Base institucional de respuestas y enlaces. |
| `crawler.py` | Rastreo público opcional, con informe de cobertura y controles de calidad. |
| `test_chat.py` | Pruebas sin red ni pagos. |
| `README.md` | Documentación del proyecto. |

Ejecuta las pruebas desde la carpeta `CHATISTPN`:

```powershell
python -m unittest -v test_chat.py
```

**Uso previsto:** prototipo local. No exponer el proceso como servicio público de WordPress sin un diseño adicional de seguridad, escalabilidad y administración de fuentes.
