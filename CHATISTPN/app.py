"""ISTPNCHAT - prototipo local, sin APIs, tokens ni dependencias externas.
Ejecutar: python app.py   |   python app.py --cli
"""
from __future__ import annotations

import argparse
import html
import json
import re
import threading
import time
import unicodedata
import webbrowser
from collections import Counter, defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent
DB = BASE / 'respuestas.json'
STOP = set('a al algo algunas algunos ante como con cual cuales cuando de del desde donde el ella ellas ellos en entre era es esa esas ese esos esta estas este estos hacia hay la las le les lo los mas me mi mis muy no o para pero por porque que quien quienes se sea ser si sin sobre son su sus te tiene tienen tu un una unas unos y ya puedo podrian quiero saber necesito dime favor informacion instituto istpn isupol chat'.split())
ALIASES = {'carreras':'carrera', 'cursos':'curso', 'estudios':'estudio', 'modalidades':'modalidad', 'requisitos':'requisito', 'inscripciones':'inscripcion', 'matriculas':'matricula', 'admisiones':'admision', 'reglamentos':'reglamento', 'noticias':'noticia', 'telefonos':'telefono', 'contactos':'contacto', 'docentes':'docente', 'estudiantes':'estudiante', 'graduados':'graduado', 'titulaciones':'titulacion'}


def norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', text)).strip()


def tokens(text):
    return {ALIASES.get(w, w) for w in norm(text).split() if len(w) > 2 and w not in STOP}


def out_of_scope(q):
    s = norm(q)
    prohibited = [r'\b(olvida|ignora) (tus|las|todas|anteriores) (reglas|instrucciones)',
                  r'\b(actua como|eres ahora|nuevo rol|system prompt|developer prompt)',
                  r'\b(genera|crea|escribe|hazme|programa|desarrolla)\b.{0,45}\b(codigo|script|python|javascript|java|php|programa informatico|aplicacion movil|software)\b',
                  r'\b(receta|horoscopo|apuestas|pelicula|futbol mundial)\b']
    return any(re.search(p, s) for p in prohibited)


class Motor:
    def __init__(self, ruta=DB):
        self.ruta = Path(ruta)
        self.mtime = -1
        self.data = {}
        self.registros = []
        self.reload()

    def reload(self):
        stamp = self.ruta.stat().st_mtime_ns
        if stamp == self.mtime:
            return
        data = json.loads(self.ruta.read_text(encoding='utf-8'))
        records = data.get('respuestas', [])
        if not isinstance(records, list):
            raise ValueError('Formato incorrecto de respuestas.json')
        self.data, self.registros, self.mtime = data, records, stamp

    def buscar(self, pregunta, limite=4):
        self.reload()
        words = tokens(pregunta)
        if not words:
            return []
        df = Counter()
        terms = []
        for r in self.registros:
            ts = tokens(' '.join(r.get('preguntas', [])) + ' ' + r.get('titulo', '') + ' ' + ' '.join(r.get('etiquetas', [])) + ' ' + r.get('respuesta', '')[:1200])
            terms.append(ts)
            df.update(ts)
        n = max(1, len(self.registros))
        results = []
        qnorm = norm(pregunta)
        for r, ts in zip(self.registros, terms):
            common = words & ts
            if not common:
                continue
            overlap = sum(1.0 + min(2.0, (n / (1 + df[w])) ** .35) for w in common)
            coverage = len(common) / len(words)
            score = overlap / max(2.2, len(words) ** .55) + coverage * 2.6
            title_tokens = tokens(r.get('titulo', ''))
            score += len(words & title_tokens) * .65
            for q in r.get('preguntas', []):
                pn = norm(q)
                if pn == qnorm:
                    score += 30
                    break
                qt = tokens(q)
                if len(words & qt) >= 2:
                    score += len(words & qt) / max(len(words), len(qt), 1) * 3.2
                if qnorm and len(qnorm) > 9 and qnorm in pn:
                    score += 6
            if r.get('origen') == 'verificado':
                score += .6
            if score >= 2.9 and (coverage >= .33 or len(common) >= 2):
                results.append((score, r))
        results.sort(key=lambda s: (-s[0], s[1].get('id', '')))
        return results[:limite]

    def responder(self, pregunta):
        question = str(pregunta or '').strip()[:700]
        if not question:
            return {'respuesta': 'Escribe tu pregunta sobre el ISTPN.', 'fuentes': [], 'modo': 'local'}
        if out_of_scope(question):
            return {'respuesta': 'Soy ISTPNCHAT y solo atiendo consultas sobre la información institucional publicada en el portal del ISTPN.', 'fuentes': [], 'modo': 'rechazo'}
        if norm(question) in ('hola','buenas','buenos dias','buenas tardes','saludos','hey','gracias'):
            return {'respuesta': '¡Hola! Soy ISTPNCHAT. Puedes preguntarme por carreras, modalidades, admisiones, normativa, noticias, trámites y servicios del ISTPN.', 'fuentes': [], 'modo': 'local'}
        matches = self.buscar(question)
        if not matches:
            return {'respuesta': 'No encontré información verificada suficiente en mi base local. Consulta el portal oficial o actualiza respuestas.json con crawler.py.', 'fuentes': [{'titulo': 'Portal ISTPN', 'url':'https://home.isupol.edu.ec/'}], 'modo': 'sin_resultado'}
        best, item = matches[0]
        answer = item.get('respuesta', '').strip()
        related = []
        for _, other in matches[1:]:
            if other.get('fuente') != item.get('fuente') and other.get('titulo') not in related and len(related) < 2:
                related.append(other.get('titulo','Información relacionada'))
        sources = []
        seen = set()
        for record in [item] + [x[1] for x in matches[1:]]:
            urls = record.get('fuentes') or ([record['fuente']] if record.get('fuente') else [])
            for u in urls:
                if isinstance(u, str) and u.startswith('https://home.isupol.edu.ec/') and u not in seen:
                    sources.append({'titulo':record.get('titulo','Fuente oficial'), 'url':u})
                    seen.add(u)
            if len(sources) >= 3:
                break
        if item.get('historico'):
            answer += '\n\nAviso: esta información corresponde a una publicación histórica; verifica si existe una convocatoria o actualización vigente.'
        return {'respuesta': answer[:1300], 'fuentes': sources, 'modo': 'local', 'tema': item.get('tema',''), 'coincidencia': round(best,2)}


HTML = r'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISTPNCHAT · Prototipo</title><style>
:root{font-family:system-ui,-apple-system,Segoe UI,Arial;color:#172944;background:#eef3f9}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}.shell{width:min(800px,100%);height:min(800px,90vh);display:flex;flex-direction:column;background:white;border-radius:20px;overflow:hidden;box-shadow:0 14px 50px #05255226}.head{background:linear-gradient(110deg,#06285a,#1266b9);color:#fff;padding:18px 24px}.head h1{margin:0;font-size:1.18rem}.head small{opacity:.8}.messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:14px}.bub{max-width:86%;padding:12px 14px;border-radius:16px;white-space:pre-wrap;line-height:1.52;font-size:14px}.user{align-self:flex-end;background:#0865c2;color:white;border-bottom-right-radius:3px}.bot{align-self:flex-start;background:#f0f5fa;border:1px solid #e4ebf3;border-bottom-left-radius:3px}.links{margin-top:10px;display:grid;gap:6px}.links a{color:#075aa9;overflow-wrap:anywhere}.hint{color:#637287;font-size:12px;padding:0 20px 10px}form{display:flex;gap:8px;padding:16px;border-top:1px solid #e3e8ef}input{flex:1;border:1px solid #c9d5e3;border-radius:12px;padding:13px;font-size:14px;min-width:0}button{border:none;background:#0d58a8;color:white;padding:0 20px;border-radius:12px;cursor:pointer}button:disabled{opacity:.6}.qs{display:flex;flex-wrap:wrap;gap:7px;padding:0 20px 12px}.qs button{font-size:12px;padding:8px 10px;background:#e3effc;color:#11446f}
</style></head><body><main class="shell"><header class="head"><h1>💬 ISTPNCHAT</h1><small>Prototipo local · Información pública del ISTPN · Sin API de pago</small></header>
<div class="messages" id="messages" aria-live="polite"></div><div class="qs" id="qs"><button data-q="¿Qué carreras y modalidades ofrece el ISTPN?">Carreras</button><button data-q="¿Cuál es la misión del ISTPN?">Misión</button><button data-q="¿Dónde está la normativa?">Normativa</button><button data-q="¿Cómo contacto al instituto?">Contacto</button></div><div class="hint">Las respuestas provienen de respuestas.json. Pueden requerir actualización y verificación.</div><form id="form"><input id="q" maxlength="700" placeholder="Escribe una consulta institucional..." aria-label="Pregunta" autocomplete="off" required><button id="send" type="submit">Enviar</button></form></main><script>
const messages=document.getElementById('messages'),input=document.getElementById('q'),button=document.getElementById('send');
function bubble(text,who,links=[]){const el=document.createElement('div');el.className='bub '+who;el.textContent=text;if(links.length){const box=document.createElement('div');box.className='links';for(const item of links){try{const u=new URL(item.url);if(u.protocol!=='https:'||u.hostname!=='home.isupol.edu.ec')continue;const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent='↗ '+(item.titulo||u.href);box.appendChild(a)}catch{}}el.appendChild(box)}messages.appendChild(el);messages.scrollTop=messages.scrollHeight;return el}
bubble('¡Hola! Soy ISTPNCHAT. ¿Qué deseas saber sobre el Instituto Superior Tecnológico Policía Nacional?','bot');
async function ask(q){if(!q.trim())return;bubble(q,'user');input.value='';button.disabled=true;try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:q})});const data=await r.json();bubble(data.respuesta||'No se obtuvo respuesta.','bot',data.fuentes||[])}catch(e){bubble('No pude conectar con el servicio local.','bot')}finally{button.disabled=false;input.focus()}}
document.getElementById('form').addEventListener('submit',e=>{e.preventDefault();ask(input.value)});document.querySelectorAll('[data-q]').forEach(b=>b.addEventListener('click',()=>ask(b.dataset.q)));
</script></body></html>'''


def serve(host, port, browser=True):
    engine = Motor()
    hits = defaultdict(deque)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/':
                self.send_error(404); return
            b = HTML.encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'");self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_POST(self):
            if self.path != '/api/chat':
                self.send_error(404);return
            try: length=int(self.headers.get('Content-Length','0'))
            except ValueError: length=0
            if length<1 or length>4000:
                self.send_error(413);return
            now=time.monotonic();ip=self.client_address[0];recent=hits[ip]
            while recent and now-recent[0]>60:recent.popleft()
            if len(recent)>=25:
                self.send_error(429, 'Demasiadas consultas');return
            recent.append(now)
            try:
                content=json.loads(self.rfile.read(length).decode('utf-8'))
                result=engine.responder(content.get('pregunta',''))
                data=json.dumps(result,ensure_ascii=False).encode('utf-8')
                self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (json.JSONDecodeError,UnicodeDecodeError,AttributeError):self.send_error(400)
            except Exception as exc:print('Error:',str(exc));self.send_error(500)
        def log_message(self, fmt,*args):pass
    srv=ThreadingHTTPServer((host,port),Handler)
    url=f'http://{host}:{port}/'
    print(f'ISTPNCHAT funcionando en {url} (Ctrl+C para cerrar)')
    if browser:threading.Timer(.6,lambda:webbrowser.open(url)).start()
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:srv.server_close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description='ISTPNCHAT local sin consumo de tokens')
    p.add_argument('--cli',action='store_true');p.add_argument('--no-browser',action='store_true');p.add_argument('--port',type=int,default=8765)
    p.add_argument('--test',type=str,help='Prueba una consulta sin abrir ventana')
    args=p.parse_args()
    engine=Motor()
    if args.test:print(json.dumps(engine.responder(args.test),ensure_ascii=False,indent=2))
    elif args.cli:
        print('ISTPNCHAT - escribe salir para cerrar')
        while True:
            try:question=input('Tú> ').strip()
            except (EOFError,KeyboardInterrupt):break
            if norm(question) in ('salir','exit','quit'):break
            response=engine.responder(question)
            print('ISTPNCHAT>',response['respuesta'])
            for link in response.get('fuentes',[]):print('Fuente:',link['url'])
    else:serve('127.0.0.1',args.port,not args.no_browser)
