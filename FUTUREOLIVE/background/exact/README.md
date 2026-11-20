# FUTUREO LIVE — reconstruccion exacta a partir de la imagen enviada

**Fuente:** imagen adjunta de 815 x 286 pixeles, sin ampliarla ni redibujarla.
La composicion de las 12 capas PNG transparentes recupera exactamente el
RGBA de la imagen original (**0 pixeles diferentes**) a su resolucion nativa.

Las capas agrupan pixeles por regiones y color; la imagen original no contiene
objetos editables ni la informacion que estaba oculta detras del humo.
Por eso, ocultar una capa muestra la parte retirada de la imagen; no revela
un fondo original que nunca estuvo disponible.

## Archivos
- `fondo1.bg`: manifest remoto con el orden y los recursos.
- `index.html`: visor; solo conoce la URL de `fondo1.bg`.
- `exact/referencia_original.png`: archivo original intacto.
- `exact/layer0_fondo.png` hasta `exact/layer11_particulas.png`: capas.
- `exact/integridad.json`: resultado de comparacion exacta.

**IMPORTANTE:** se conserva la relacion de aspecto original de 815:286.
Una pantalla 16:9 mostrara barras vacias para no estirar ni recortar.
Los recursos PNG son estaticos: introducir animacion a capas los cambiara
intencionalmente respecto de la foto original.
