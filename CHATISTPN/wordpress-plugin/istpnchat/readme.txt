=== ISTPNCHAT ===
Contributors: istpn
Tags: assistant, chat, faq, institutional, education
Requires at least: 6.0
Requires PHP: 7.4
Stable tag: 2.0.2
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Asistente institucional sin API de pago. Utiliza un archivo JSON curado, vinculado a la web oficial del ISTPN.

== Description ==

ISTPNCHAT es un chat flotante especializado que busca respuestas en la base oficial alojada en GitHub y muestra enlaces institucionales verificables. No utiliza un servicio de inteligencia artificial generativa. Incluye respaldo de respuestas, sincronizacion automatica y administracion de visibilidad.

== Installation ==

1. Instale el archivo ZIP desde Plugins > Anadir plugin > Subir plugin.
2. Active ISTPNCHAT y abra el menu ISTPNCHAT del panel de administracion.
3. Pulse Actualizar respuestas desde GitHub y compruebe las respuestas.
4. Cuando la prueba funcione, marque Mostrar a todos los visitantes.

== Changelog ==

= 2.0.0 =
* Respuestas locales a partir de CHATISTPN/respuestas.json 0.4.1.
* Elimina por completo llamadas a OpenAI y consumo de tokens.
* Corrige los nombres de las ocho carreras y sus enlaces.
* Sincronizacion cron y manual, panel de prueba, fallback y rate limit.

== Version 2.0.1 ==
- Comprende seguimiento conversacional corto, por ejemplo «otras» después de hablar de Criminalística.

== Version 2.0.2 ==
- Mejora el mensaje cuando no se encuentra una respuesta.
- Reconoce preguntas sobre duracion con variantes y errores frecuentes de escritura (criminalisitca).
- Elimina el pie del chat sobre API y tokens.
