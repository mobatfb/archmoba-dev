"""ISTPNCHAT: aplicación de escritorio con ventana Python nativa.
Ejecutar: python app.py   |   python app.py --cli
No inicia servidores ni necesita navegador, API externa o paquetes pip.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
import webbrowser
from collections import Counter
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




def ejecutar_escritorio():
    """Abre una ventana de escritorio REAL (Tkinter), sin HTTP ni navegador."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError as exc:
        raise RuntimeError('Python necesita el componente estándar Tkinter para mostrar la ventana.') from exc

    AZUL_OSCURO = '#002F6C'
    AZUL = '#0757AF'
    FONDO = '#F0F4F8'
    BLANCO = '#FFFFFF'
    TEXTO = '#1A2A42'
    GRIS = '#6B7788'
    BORDE = '#D8E2EE'
    BURBUJA_BOT = '#EAF1F9'

    motor = Motor()
    root = tk.Tk()
    root.title('ISTPNCHAT | Asistente institucional')
    root.configure(bg=FONDO)
    root.geometry('840x700')
    root.minsize(520, 480)

    header = tk.Frame(root, bg=AZUL_OSCURO, padx=23, pady=17)
    header.pack(fill='x')
    tk.Label(header, text='ISTPNCHAT', bg=AZUL_OSCURO, fg=BLANCO,
             font=('Segoe UI', 18, 'bold'), anchor='w').pack(anchor='w')
    tk.Label(header, text='Instituto Superior Tecnológico Policía Nacional  •  Asistente local sin API',
             bg=AZUL_OSCURO, fg='#C9DDF6', font=('Segoe UI', 9), anchor='w').pack(anchor='w', pady=(3, 0))

    toolbar = tk.Frame(root, bg=FONDO, padx=20, pady=10)
    toolbar.pack(fill='x')
    info = tk.StringVar()

    def estado_base():
        registros = motor.registros
        formulaciones = sum(len(r.get('preguntas', [])) for r in registros)
        info.set(f'Base local: {len(registros)} respuestas · {formulaciones} formas de preguntar  •  Tokens: 0')

    estado_base()
    tk.Label(toolbar, textvariable=info, fg=GRIS, bg=FONDO,
             font=('Segoe UI', 9), anchor='w').pack(side='left', fill='x', expand=True)

    area = tk.Frame(root, bg=BLANCO, highlightbackground=BORDE, highlightthickness=1)
    area.pack(fill='both', expand=True, padx=16, pady=(0, 8))
    scroll = tk.Scrollbar(area)
    scroll.pack(side='right', fill='y')
    canvas = tk.Canvas(area, bg=BLANCO, bd=0, highlightthickness=0,
                       yscrollcommand=scroll.set)
    canvas.pack(side='left', fill='both', expand=True)
    scroll.configure(command=canvas.yview)
    interior = tk.Frame(canvas, bg=BLANCO)
    interior_id = canvas.create_window((0, 0), window=interior, anchor='nw')
    etiquetas = []

    def actualizar_scroll(_evento=None):
        canvas.configure(scrollregion=canvas.bbox('all'))

    def ajustar_ancho(evento):
        canvas.itemconfigure(interior_id, width=evento.width)
        largo = max(240, int(evento.width * 0.71))
        for etiqueta in etiquetas:
            etiqueta.configure(wraplength=largo)
        actualizar_scroll()

    interior.bind('<Configure>', actualizar_scroll)
    canvas.bind('<Configure>', ajustar_ancho)

    def rueda(evento):
        if evento.num == 4:
            desplazamiento = -3
        elif evento.num == 5:
            desplazamiento = 3
        else:
            desplazamiento = -int(evento.delta / 120) * 3
        canvas.yview_scroll(desplazamiento, 'units')

    canvas.bind_all('<MouseWheel>', rueda)
    canvas.bind_all('<Button-4>', rueda)
    canvas.bind_all('<Button-5>', rueda)

    def ir_final():
        root.update_idletasks()
        canvas.yview_moveto(1.0)

    def enlace_valido(url):
        try:
            p = urlsplit(str(url))
            return p.scheme == 'https' and p.hostname == 'home.isupol.edu.ec'
        except ValueError:
            return False

    def mensaje(texto, emisor='bot', enlaces=None):
        fila = tk.Frame(interior, bg=BLANCO)
        fila.pack(fill='x', padx=16, pady=7)
        usuario = emisor == 'usuario'
        fondo = AZUL if usuario else BURBUJA_BOT
        color = BLANCO if usuario else TEXTO
        tarjeta = tk.Frame(fila, bg=fondo, padx=13, pady=11)
        tarjeta.pack(side='right' if usuario else 'left', anchor='e' if usuario else 'w')
        lbl = tk.Label(tarjeta, text=texto, bg=fondo, fg=color,
                       font=('Segoe UI', 10), justify='left', anchor='w',
                       wraplength=max(240, int(canvas.winfo_width() * .71)))
        lbl.pack(anchor='w')
        etiquetas.append(lbl)
        enlaces_mostrados = set()
        for fuente in enlaces or []:
            if not isinstance(fuente, dict):
                continue
            url = fuente.get('url', '')
            if not enlace_valido(url) or url in enlaces_mostrados:
                continue
            enlaces_mostrados.add(url)
            titulo = fuente.get('titulo') or url
            tk.Button(tarjeta, text='↗ ' + titulo, bg=fondo, fg='#0757AF',
                      activebackground=fondo, activeforeground='#003A78',
                      relief='flat', bd=0, padx=0, pady=3,
                      cursor='hand2', anchor='w', justify='left',
                      font=('Segoe UI', 9, 'underline'),
                      command=lambda u=url: webbrowser.open(u, new=2)).pack(anchor='w', fill='x')
        root.after_idle(ir_final)

    def recargar():
        try:
            motor.mtime = -1
            motor.reload()
            estado_base()
            messagebox.showinfo('ISTPNCHAT', 'Base de conocimientos recargada correctamente.')
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror('No se pudo recargar', str(exc))

    tk.Button(toolbar, text='↻ Recargar JSON', bg=BLANCO, fg=AZUL_OSCURO,
              bd=1, relief='solid', padx=10, pady=6, cursor='hand2',
              font=('Segoe UI', 9), command=recargar).pack(side='right')

    sugerencias = tk.Frame(root, bg=FONDO, padx=16, pady=6)
    sugerencias.pack(fill='x')

    entrada_bar = tk.Frame(root, bg=BLANCO, padx=15, pady=12)
    entrada_bar.pack(fill='x', padx=16, pady=(0, 16))
    entrada = tk.Entry(entrada_bar, font=('Segoe UI', 11), bg=BLANCO,
                       fg=TEXTO, relief='flat', highlightthickness=0)
    entrada.pack(side='left', fill='x', expand=True, padx=(4, 10), ipady=7)
    enviar_boton = tk.Button(entrada_bar, text='Enviar', bg=AZUL, fg=BLANCO,
                             activebackground=AZUL_OSCURO, activeforeground=BLANCO,
                             relief='flat', bd=0, padx=20, pady=9,
                             font=('Segoe UI', 10, 'bold'), cursor='hand2')
    enviar_boton.pack(side='right')

    def preguntar(pregunta=None):
        consulta = (pregunta if pregunta is not None else entrada.get()).strip()
        if not consulta:
            return
        entrada.delete(0, 'end')
        mensaje(consulta, 'usuario')
        enviar_boton.configure(state='disabled')
        try:
            resultado = motor.responder(consulta)
            mensaje(resultado.get('respuesta', 'No se obtuvo respuesta.'),
                    'bot', resultado.get('fuentes', []))
            estado_base()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            mensaje('No pude leer respuestas.json. Verifica que esté en la misma carpeta que app.py.\n'
                    + str(exc), 'bot')
        finally:
            enviar_boton.configure(state='normal')
            entrada.focus_set()

    enviar_boton.configure(command=preguntar)
    entrada.bind('<Return>', lambda _e: preguntar())

    for nombre, consulta in [
        ('Carreras', '¿Qué carreras y modalidades ofrece el ISTPN?'),
        ('Admisiones', '¿Dónde encuentro información de admisiones?'),
        ('Normativa', '¿Dónde está la normativa del ISTPN?'),
        ('Contacto', '¿Cómo contacto al ISTPN?'),
    ]:
        tk.Button(sugerencias, text=nombre, fg=AZUL_OSCURO, bg='#DCE9F8',
                  relief='flat', bd=0, padx=12, pady=6, cursor='hand2',
                  font=('Segoe UI', 9),
                  command=lambda q=consulta: preguntar(q)).pack(side='left', padx=(0, 7))

    mensaje('¡Hola! Soy ISTPNCHAT. Pregúntame por las carreras, modalidades, admisiones, normativa o servicios publicados del ISTPN.\n\nMis respuestas provienen del archivo respuestas.json y no consumen tokens.', 'bot')
    entrada.focus_set()
    root.mainloop()


def main():
    p = argparse.ArgumentParser(description='ISTPNCHAT de escritorio, sin servidor ni API')
    p.add_argument('--cli', action='store_true', help='Usar únicamente consola de texto')
    p.add_argument('--test', type=str, help='Probar una pregunta y finalizar')
    args = p.parse_args()
    motor = Motor()
    if args.test is not None:
        print(json.dumps(motor.responder(args.test), ensure_ascii=False, indent=2))
    elif args.cli:
        print('ISTPNCHAT - escribe salir para cerrar')
        while True:
            try:
                pregunta = input('Tú> ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if norm(pregunta) in ('salir', 'exit', 'quit'):
                break
            resultado = motor.responder(pregunta)
            print('ISTPNCHAT>', resultado['respuesta'])
            for fuente in resultado.get('fuentes', []):
                print('Fuente:', fuente['url'])
    else:
        ejecutar_escritorio()


if __name__ == '__main__':
    main()
