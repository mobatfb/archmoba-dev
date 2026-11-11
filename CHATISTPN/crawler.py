"""Rastreador PUBLICO de home.isupol.edu.ec para respuestas.json.
No utiliza ninguna API de IA. Requiere conexion a internet en el equipo que lo ejecuta.
Opcional para leer PDF: pip install pypdf
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

BASE = 'https://home.isupol.edu.ec/'
HOST = 'home.isupol.edu.ec'
HERE = Path(__file__).resolve().parent
DB = HERE / 'respuestas.json'
AGENT = 'ISTPNCHAT/0.1 (+rastreador institucional de contenido publico; sin autenticacion)'
SEEDS = ['/', '/acerca/', '/admisiones/', '/normativa/', '/noticias/', '/nuestras_autoridades/', '/guias-para-usuarios/', '/tramites/', '/organigrama/', '/vincula/']
SKIP_EXT = ('.jpg','.png','.jpeg','.gif','.webp','.svg','.ico','.css','.js','.mp3','.mp4','.webm','.zip','.7z','.doc','.docx','.xls','.xlsx','.ppt','.pptx')


def safe_url(raw, base=BASE):
    try:
        u=urllib.parse.urljoin(base,unescape(str(raw)).strip())
        p=urllib.parse.urlsplit(u)
        if p.scheme!='https' or p.hostname!=HOST or p.username or p.password:return None
        path=re.sub(r'/+','/',p.path or '/')
        if any(x in path.lower() for x in ('/wp-admin/','/wp-login','/xmlrpc.php','/wp-json/','/feed/','/comments/','/wp-content/plugins/')):return None
        if path.lower().endswith(SKIP_EXT):return None
        # Evitar duplicados por parametros de analitica y paginacion de WordPress.
        query=urllib.parse.parse_qs(p.query)
        query={k:v for k,v in query.items() if k in ('paged','page')}
        return urllib.parse.urlunsplit(('https',HOST,path,urllib.parse.urlencode(query,doseq=True),''))
    except Exception:return None


class Extractor(HTMLParser):
    BLOCKS = {'h1','h2','h3','h4','h5','h6','p','li','td','th','blockquote','figcaption','dt','dd'}
    SKIP={'script','style','noscript','nav','footer','header','form','svg'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.active=[];self.parts=[];self.links=[];self.title=[];self.in_title=False
    def skipping(self):return any(x in self.SKIP for x in self.stack)
    def handle_starttag(self,tag,attrs):
        if tag in ('br','hr','img','input','source','meta','link'):return
        if tag=='a' and not self.skipping():
            for k,v in attrs:
                if k=='href' and v:self.links.append(v)
        if tag=='title':self.in_title=True
        if tag in self.BLOCKS and not self.skipping():
            self.active.append([tag,[]])
        self.stack.append(tag)
    def handle_endtag(self,tag):
        if self.active and self.active[-1][0]==tag:
            name,content=self.active.pop()
            val=' '.join(' '.join(content).split())
            if len(val)>=8:
                self.parts.append((name,val))
        if tag=='title':self.in_title=False
        if tag in self.stack:
            idx=len(self.stack)-1-self.stack[::-1].index(tag)
            self.stack=self.stack[:idx]
    def handle_data(self,data):
        s=' '.join(data.split())
        if not s or self.skipping():return
        if self.in_title:self.title.append(s)
        if self.active:self.active[-1][1].append(s)


def http_get(url, delay, timeout, max_bytes=12_000_000):
    time.sleep(delay)
    req=urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'text/html,application/json,application/xml,text/xml,application/pdf,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        code=r.status
        content=r.read(max_bytes+1)
        if len(content)>max_bytes:raise ValueError('archivo demasiado grande')
        return code,dict(r.headers),content


def html_entries(url,raw):
    raw_text=raw.decode('utf-8','replace')
    parser=Extractor();parser.feed(raw_text)
    title=' '.join(parser.title).strip() or urllib.parse.urlparse(url).path.strip('/').replace('-',' ').title() or 'Inicio ISTPN'
    unique=set();blocks=[]
    for tag,text in parser.parts:
        key=text.casefold()
        if key not in unique and len(text)<5000:
            unique.add(key);blocks.append((tag,text))
    # Si no hay bloques legibles, no inventar respuestas.
    if not blocks:return title,[],parser.links
    lines=[];heading=title;chunks=[]
    def save():
        if not lines:return
        snippet=' '.join(lines).strip()[:900]
        if len(snippet)<45:return
        section=heading if heading else title
        uid=hashlib.sha256((url+'|'+section+'|'+snippet[:70]).encode()).hexdigest()[:16]
        chunks.append({'id':'web-'+uid,'tema':'Contenido web','titulo':section,'preguntas':[f'¿Qué información hay sobre {section}?',f'¿Dónde encuentro {section}?'], 'respuesta':snippet, 'fuente':url,'origen':'rastreo'})
    for tag,text in blocks:
        if tag.startswith('h') and tag[1:].isdigit() and len(text)<170:
            if lines:save();lines=[]
            heading=text
        elif len(text)>=26:
            if len(' '.join(lines))+len(text)>800:
                save();lines=[]
            lines.append(text)
        if len(chunks)>=55:break
    if lines and len(chunks)<55:save()
    return title,chunks,parser.links


def pdf_entries(url, raw, max_pdf_pages=150):
    try:from pypdf import PdfReader
    except ImportError:return [],'pypdf no instalado; PDF omitido (pip install pypdf)'
    try:
        pdf=PdfReader(io.BytesIO(raw))
        chunks=[]
        for page,pg in enumerate(pdf.pages[:max_pdf_pages],1):
            text=' '.join((pg.extract_text() or '').split())
            for i in range(0,min(len(text),18000),850):
                fragment=text[i:i+950].strip()
                if len(fragment)<80:continue
                uid=hashlib.sha256(f'{url}:{page}:{i}'.encode()).hexdigest()[:16]
                title=urllib.parse.unquote(url.split('/')[-1])+' · página '+str(page)
                chunks.append({'id':'pdf-'+uid,'tema':'Documento PDF','titulo':title,'preguntas':[f'¿Qué contiene {title}?'], 'respuesta':fragment, 'fuente':url,'pagina_pdf':page,'origen':'rastreo'})
        return chunks,None
    except Exception as e:return [],'PDF no legible: '+str(e)[:130]


def find_sitemap_urls(xml):
    try:root=ET.fromstring(xml)
    except ET.ParseError:return []
    return [el.text.strip() for el in root.iter() if el.tag.endswith('loc') and el.text]


def discover_api(fetch, add):
    for typ in ('pages','posts'):
        for page in range(1,31):
            url=BASE+f'wp-json/wp/v2/{typ}?per_page=100&page={page}&_fields=link,status'
            try:_,hdr,raw=fetch(url)
            except Exception:break
            try:records=json.loads(raw)
            except ValueError:break
            if not isinstance(records,list) or not records:break
            for item in records:
                if item.get('status')=='publish':add(item.get('link'))
            if len(records)<100:break


def run(max_pages, delay, timeout, include_pdf):
    data=json.loads(DB.read_text(encoding='utf-8'))
    manual=[x for x in data.get('respuestas',[]) if x.get('origen')!='rastreo']
    found=set();pending=deque();visited=set();failures=[];records=[];sitemaps=deque([BASE+'wp-sitemap.xml',BASE+'sitemap_index.xml',BASE+'sitemap.xml']);seen_maps=set()
    def add(u):
        u=safe_url(u)
        if u and u not in found:
            found.add(u);pending.append(u)
    def fetch(u):return http_get(u,delay,timeout)
    for seed in SEEDS:add(urllib.parse.urljoin(BASE,seed))
    for item in manual:
        for u in item.get('fuentes',[]) or ([item['fuente']] if item.get('fuente') else []):add(u)
    robots=urllib.robotparser.RobotFileParser()
    try:
        robots.set_url(BASE+'robots.txt');robots.read();robot_ok=True
    except Exception as e:
        robot_ok=False;failures.append({'url':BASE+'robots.txt','error':'Robots no disponible: '+str(e)[:100]})
    while sitemaps and len(seen_maps)<90:
        link=sitemaps.popleft()
        if link in seen_maps:continue
        seen_maps.add(link)
        try:_,_,raw=fetch(link)
        except Exception as e:failures.append({'url':link,'error':str(e)[:150]});continue
        for url in find_sitemap_urls(raw):
            if url.endswith('.xml') and urllib.parse.urlparse(url).hostname==HOST:sitemaps.append(url)
            else:add(url)
    try:discover_api(fetch,add)
    except Exception as e:failures.append({'url':'wp-json','error':str(e)[:150]})
    print(f'URLs descubiertas inicialmente: {len(pending)}')
    while pending and (max_pages==0 or len(visited)<max_pages):
        url=pending.popleft()
        if url in visited:continue
        visited.add(url)
        if robot_ok and not robots.can_fetch(AGENT,url):
            failures.append({'url':url,'error':'Bloqueado por robots.txt'});continue
        if url.lower().endswith('.pdf') and not include_pdf:continue
        try:code,headers,raw=fetch(url)
        except Exception as e:
            failures.append({'url':url,'error':str(e)[:170]});continue
        typ=headers.get('Content-Type','').lower()
        if 'pdf' in typ or raw[:5]==b'%PDF-':
            if include_pdf:
                chunks,err=pdf_entries(url,raw)
                records.extend(chunks)
                if err:failures.append({'url':url,'error':err})
        elif 'html' in typ or raw.lstrip()[:15].lower().startswith((b'<!doctype html',b'<html')):
            title,chunks,links=html_entries(url,raw)
            records.extend(chunks)
            for link in links:add(urllib.parse.urljoin(url,link))
        if len(visited)%25==0:print(f'Visitadas: {len(visited)} | indexadas: {len(records)} | pendientes: {len(pending)}')
    # ids duplicados: quedarse con una entrada por fragmento.
    unique={r['id']:r for r in records}
    data['respuestas']=manual+list(unique.values())
    data['ultima_sincronizacion']=datetime.now(timezone.utc).isoformat()
    data['cobertura']={'metodo':'Sitemaps + WP REST + enlaces internos públicos; no accede a contenido privado', 'urls_descubiertas':len(found),'urls_visitadas':len(visited),'fragmentos_generados':len(unique),'limite_alcanzado':bool(pending),'urls_pendientes':len(pending),'errores':len(failures),'pdf_incluido':include_pdf,'exhaustivo_confirmado':bool(not pending and not failures)}
    tmp=DB.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(DB)
    report={'fecha':data['ultima_sincronizacion'],'cobertura':data['cobertura'],'errores':failures[:500],'pendientes':list(pending)[:500]}
    (HERE/'cobertura.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Escaneo finalizado. Repuestas verificadas:',len(manual),'Fragmentos web:',len(unique))
    print('Informe:',HERE/'cobertura.json')
    if failures:print('Advertencia: hay errores o archivos no leidos; no equivale a escaneo absoluto.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Indexa WordPress publico en respuestas.json, sin IA pagada')
    p.add_argument('--max-pages',type=int,default=600,help='0 sin limite; respeta robots.txt y retardo')
    p.add_argument('--delay',type=float,default=0.6,help='Segundos entre solicitudes; minimo 0.5')
    p.add_argument('--timeout',type=float,default=16)
    p.add_argument('--pdf',action='store_true',help='Agregar archivos PDF (requiere pypdf)')
    a=p.parse_args()
    run(max(0,a.max_pages),max(.5,a.delay),max(5,a.timeout),a.pdf)
