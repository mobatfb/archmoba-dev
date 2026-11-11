# ISTPNCHAT 2.0.0 — WordPress, sin API de pago

Plugin institucional para **home.isupol.edu.ec**, creado a partir de la base pública de preguntas y respuestas de `CHATISTPN`.

## Qué hace

- Chat flotante en WordPress, compatible con computadora y móvil.
- Responde mediante búsqueda **local** en una copia de `respuestas.json`.
- Muestra los nombres y enlaces **individuales** de las 8 carreras de la oferta registrada.
- Incorpora inicialmente **221 respuestas y 964 formulaciones** (base JSON 0.4.1).
- Descarga las actualizaciones del JSON desde GitHub automáticamente mediante WP-Cron (una vez por hora, cuando WordPress ejecute tareas programadas), o manualmente desde el panel.
- Si GitHub no está disponible, sigue utilizando la última base válida. También incluye una copia de inicio dentro del plugin.
- Sin clave de OpenAI, sin IA generativa, sin compras de tokens y sin servicios de inferencia externa.
- No guarda historial de conversaciones. Aplica límite básico de solicitudes mediante un identificador temporal derivado de la IP.

**IMPORTANTE:** al no usar un modelo de IA, el asistente solo puede responder lo que esté representado en el JSON. El sitio puede incorporar información nueva o modificar convocatorias. El JSON debe mantenerse revisado; no se garantiza que todo el portal o cada PDF haya sido examinado.

## Instalación y actualización

1. Crea copia de seguridad de WordPress.
2. Entra en **WordPress → Plugins → Añadir plugin → Subir plugin**.
3. Selecciona `ISTPNCHAT-WordPress-v2.0.0.zip`.
4. Si ya tienes ISTPNCHAT 1.0.x instalado, utiliza **Reemplazar el actual con el subido**. **No desinstales** antes.
5. Entra en **ISTPNCHAT**, pulsa **Actualizar respuestas desde GitHub** y revisa la versión y las cantidades.
6. Abre tu portal iniciando sesión como administrador y prueba estas preguntas:
   - `¿Cuántas carreras tiene el ISTPN?`
   - `¿Qué carreras ofrece el ISTPN?`
   - `¿Cuáles son las carreras en línea?`
   - `¿Dónde encuentro el Reglamento de Bienestar Estudiantil?`
   - `Créame un programa en Python` (debe indicar que solo atiende información institucional).
7. Al comprobar su funcionamiento, activa **Mostrar a todos los visitantes** en el panel y guarda.
8. Si el navegador guarda CSS/JS antiguos, limpia la caché del hosting/CDN y pulsa `Ctrl + F5`.

La instalación mantiene el **slug `istpnchat` y el archivo principal `istpnchat.php`** de versiones anteriores, por lo que es un reemplazo del mismo plugin. El chat nuevo arranca en modo de prueba (administradores) aunque el anterior se hubiese habilitado al público. Se pueden conservar el color y el saludo previos si estaban definidos. La clave API antigua, si la hubiera, **no es utilizada ni enviada a ninguna parte** por esta versión; para eliminarla de la base de datos necesitarás realizar una limpieza específica controlada.

## Administración

- **ISTPNCHAT → Base de conocimientos:** versión, total de registros, origen y última sincronización.
- **Actualizar respuestas desde GitHub:** solicitud inmediata al repositorio.
- **Visibilidad:** prueba solo administradores o chat público.
- **Auto sincronización:** usa tareas de WordPress, no realiza una descarga por cada mensaje o visitante.
- **Saludo, color y límite de consultas:** personalización sin cambiar código.
- **Probar una pregunta:** muestra respuesta y enlaces desde el mismo panel.

Fuente de datos autorizada: `https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/CHATISTPN/respuestas.json`.

## Arquitectura

```
Visitante -> Chat JavaScript -> REST de WordPress (POST /wp-json/istpnchat/v2/chat)
                                   |
                                   v
                           Motor de búsqueda PHP
                                   |
                                   v
                 JSON validado almacenado en WordPress
                                   ^
                                   |
                      GitHub / Copia del ZIP
```

Las consultas de visitantes **no se envían a GitHub**. GitHub solo suministra el JSON al servidor de WordPress cuando el administrador pulsa sincronizar o cuando se ejecuta la tarea programada.

## Seguridad y privacidad

- El endpoint solo admite preguntas y entrega texto y URLs autorizadas en `*.isupol.edu.ec`.
- La interfaz construye mensajes con `textContent` y valida los enlaces antes de mostrarlos.
- Sin herramientas ejecutables, sin acceso administrativo mediante el chat y sin solicitudes a modelos generativos.
- Límite de consultas por IP anonimizada durante 10 minutos; si la web utiliza proxy o CDN, revisar el límite para redes compartidas.
- La sincronización usa la API HTTP segura de WordPress, tamaño máximo 4 MB y validación estructural del JSON.
- WordPress no controla si una respuesta curada en el JSON está desactualizada: debe revisarse el contenido institucional y la validez de los enlaces.

## Restricciones y pruebas pendientes

- **No se ha instalado aún en `home.isupol.edu.ec`.** Se requiere validar la integración en el tema y los sistemas de caché y seguridad del sitio.
- Requiere que el tema ejecute los hooks WordPress estándar `wp_enqueue_scripts` y `wp_footer`.
- El hosting debe permitir leer `raw.githubusercontent.com` para actualizar automáticamente. Si está bloqueado, el plugin continúa con la copia incluida.
- WordPress REST API debe estar accesible para el frontend o debe permitirse la ruta `istpnchat/v2/chat` en el cortafuegos.
- Si la web usa WP-Cron desactivado, configurar una tarea de cron real o actualizar desde el panel.
- Los filtros de preguntas no constituyen un clasificador semántico perfecto: se trata de búsqueda documental por similitud léxica, no de IA generativa.

## Validación local

Para revisión por desarrolladores:

```bash
php -l istpnchat.php
php -l includes/class-istpnchat-admin.php
php -l includes/class-istpnchat-knowledge.php
php -l includes/class-istpnchat-search.php
node --check assets/widget.js
```

La carpeta de desarrollo contiene `tests/test_engine.php` para verificar consultas habituales sin necesitar instalar WordPress; los tests no van incluidos en el ZIP de producción.
