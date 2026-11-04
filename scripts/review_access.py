"""Acceso temporal HTTPS a una copia de revisión; nunca publica la base real.

Windows: python scripts/review_access.py start|status|stop
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DIRECTORY=ROOT/'.local'/'review'
PORT=8002
NO_WINDOW=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0

def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare_review(directory=DIRECTORY):
    from sqlalchemy.orm import Session
    from research.database import make_engine,upgrade_database
    from research.models import Company,User,normalized
    from research.security import create_user,audit
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    config_path=directory/'private-config.json'
    if config_path.exists(): config=json.loads(config_path.read_text(encoding='utf-8'))
    else:
        config={'secret':secrets.token_urlsafe(48),'admin_password':secrets.token_urlsafe(20),'field_password':secrets.token_urlsafe(20)}
        write_json(config_path,config)
    # Ruta fija derivada de la carpeta de revisión. No se acepta la base de producción.
    config['database_url']='sqlite:///'+(directory/'revision.db').as_posix()
    engine=make_engine(config['database_url'])
    try:
        upgrade_database(engine)
        with Session(engine) as db:
            for username,password,role in [('revision_admin',config['admin_password'],'admin'),('revision_campo',config['field_password'],'campo')]:
                if not db.query(User).filter_by(username=username).first(): create_user(db,username,password,role)
            if not db.query(Company).count():
                name='PRUEBA DE REVISIÓN — NO ES UNA EMPRESA REAL';barrio='Caso sintético'
                key=hashlib.sha256((normalized(name)+'|'+normalized(barrio)).encode()).hexdigest()
                db.add(Company(name=name,barrio=barrio,city='Bucaramanga',activity='Comercio minorista',size='Pequeña',source='CASO SINTÉTICO de revisión; no constituye verificación empresarial real',verification_status='verificada',operating_status='activa',has_records='Sí, ambos',respondent_role='Propietario',willing='Sí',owner='entorno_revision',notes='Solo permite probar los formularios. No usar este registro como evidencia académica.',duplicate_key=key))
            audit(db,'entorno_revision','preparar','review',changes={'base_aislada':True});db.commit()
    finally: engine.dispose()
    return config

def cloudflared():
    directory=ROOT/'.local'/'tools';directory.mkdir(parents=True,exist_ok=True)
    binary=directory/'cloudflared.exe';metadata=directory/'cloudflared.json'
    if binary.exists() and metadata.exists():
        data=json.loads(metadata.read_text(encoding='utf-8'))
        with binary.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest==data.get('sha256'): return binary
        raise RuntimeError('El ejecutable local no coincide con su SHA-256 verificado.')
    request=urllib.request.Request('https://api.github.com/repos/cloudflare/cloudflared/releases/latest',headers={'User-Agent':'Datapyme-Private-Review'})
    with urllib.request.urlopen(request,timeout=30) as response: release=json.load(response)
    asset=next(x for x in release['assets'] if x['name']=='cloudflared-windows-amd64.exe')
    expected=asset.get('digest','')
    if not expected.startswith('sha256:') or not asset['browser_download_url'].startswith('https://github.com/cloudflare/cloudflared/releases/download/'):
        raise RuntimeError('No se encontró una descarga oficial con checksum verificable.')
    temporary=directory/'cloudflared.download'
    with urllib.request.urlopen(asset['browser_download_url'],timeout=90) as response,temporary.open('wb') as output:
        while chunk:=response.read(1024*1024): output.write(chunk)
    with temporary.open('rb') as stream: actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected.split(':',1)[1]: raise RuntimeError('La descarga no coincide con el checksum oficial; no se ejecutó.')
    temporary.replace(binary)
    write_json(metadata,{'version':release['tag_name'],'url':asset['browser_download_url'],'sha256':actual})
    return binary

def request_json(url,timeout=5):
    with urllib.request.urlopen(url,timeout=timeout) as response: return json.load(response)

def owned_process(pid,kind):
    """Verificar ejecutable y comando antes de actuar sobre un PID guardado."""
    if os.name!='nt': return False
    pid=int(pid)
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    command=f'Get-CimInstance Win32_Process -Filter "ProcessId={pid}" | Select-Object ExecutablePath,CommandLine | ConvertTo-Json -Compress'
    result=subprocess.run([str(powershell),'-NoProfile','-Command',command],capture_output=True,text=True,creationflags=NO_WINDOW)
    if not result.stdout.strip(): return False
    info=json.loads(result.stdout)
    expected=ROOT/'.local/tools/cloudflared.exe' if kind=='tunnel' else ROOT/'.venv/Scripts/python.exe'
    actual=Path(info.get('ExecutablePath') or '').resolve()
    text=info.get('CommandLine') or ''
    return actual==expected.resolve() and ('tunnel' in text if kind=='tunnel' else 'uvicorn app:app' in text and f'--port {PORT}' in text)

def read_state():
    path=DIRECTORY/'state.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def access_block(config,url):
    return ('--- ACCESO_REVISION_INICIO ---\n'
        'ENLACE DE REVISIÓN ACTUAL: '+url+'\n'
        'Administrador SOLO de la copia de revisión: revision_admin\n'
        'Contraseña de revisión: '+config['admin_password']+'\n'
        'Investigador SOLO de la copia de revisión: revision_campo\n'
        'Contraseña de investigador de revisión: '+config['field_password']+'\n'
        'Estas credenciales no abren la base real. Archivo privado para los dos autores.\n'
        'La URL es temporal y requiere este computador encendido, conectado y sin suspensión.\n'
        'No recopilar empresas, contactos ni respuestas reales en esta copia.\n'
        '--- ACCESO_REVISION_FIN ---')

def update_access(config,url):
    block=access_block(config,url)
    (DIRECTORY/'ACCESO_REVISION.txt').write_text(block+'\n',encoding='utf-8-sig')
    guide=ROOT/'USO_PRIVADO_EQUIPO.txt'
    if guide.exists():
        text=guide.read_text(encoding='utf-8-sig')
        pattern=r'--- ACCESO_REVISION_INICIO ---.*?--- ACCESO_REVISION_FIN ---'
        text=re.sub(pattern,lambda _:block,text,flags=re.S) if re.search(pattern,text,re.S) else text+'\n\n'+block+'\n'
        guide.write_text(text,encoding='utf-8-sig')

def status():
    state=read_state()
    running=bool(state.get('server_pid') and owned_process(state['server_pid'],'server') and state.get('tunnel_pid') and owned_process(state['tunnel_pid'],'tunnel'))
    ready=False
    if running:
        try: ready=request_json(state['url']+'/ready',10).get('status')=='ok'
        except Exception: pass
    return {'running':running,'public_ready':ready,'url':state.get('url',''),'database':'COPIA DE REVISIÓN, sin investigación real'}

def stop():
    state=read_state()
    for key,kind in [('tunnel_pid','tunnel'),('server_pid','server')]:
        if state.get(key) and owned_process(state[key],kind): os.kill(int(state[key]),signal.SIGTERM)
    if state:
        state['stopped']=True;write_json(DIRECTORY/'state.json',state)
    config_path=DIRECTORY/'private-config.json'
    if config_path.exists():
        config=json.loads(config_path.read_text(encoding='utf-8'));update_access(config,'DETENIDO. Ejecutar REVISAR_POR_INTERNET.cmd para generar un enlace nuevo.')

def review_environment(config):
    env={**os.environ,'APP_ENV':'review','DATABASE_URL':config['database_url'],'SESSION_SECRET':config['secret'],'ALLOWED_HOSTS':'127.0.0.1,localhost'}
    # Vacíos explícitos bloquean también la carga de bootstrap desde el .env real.
    for key in ('ADMIN_PASSWORD','FIELD_PASSWORD','ADMIN_USER','FIELD_USER'): env[key]=''
    return env

def start():
    current=status()
    if current['running'] and current['public_ready']:
        print('Acceso de revisión ya disponible: '+current['url']);return
    if current['running']: stop()
    config=prepare_review()
    # No ocupar ni detener un servicio ajeno.
    with socket.socket() as check:
        try: check.bind(('127.0.0.1',PORT))
        except OSError: raise RuntimeError(f'El puerto {PORT} está ocupado. No se detuvo ese servicio.')
    binary=cloudflared()
    help_result=subprocess.run([str(binary),'tunnel','--help'],capture_output=True,text=True,creationflags=NO_WINDOW)
    if '--http-host-header' not in help_result.stdout: raise RuntimeError('La versión de cloudflared no ofrece la opción requerida de origen.')
    env=review_environment(config)
    server_log=(DIRECTORY/'server.log').open('a',encoding='utf-8')
    server=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(PORT)],cwd=ROOT,env=env,stdout=server_log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
    tunnel=None
    try:
        for _ in range(30):
            if server.poll() is not None: raise RuntimeError('No inició el servidor de revisión. Consultar .local/review/server.log.')
            try:
                if request_json(f'http://127.0.0.1:{PORT}/ready',1).get('status')=='ok': break
            except Exception: time.sleep(.5)
        else: raise RuntimeError('El servidor de revisión no respondió a tiempo.')
        log_path=DIRECTORY/'tunnel.log'
        with log_path.open('w',encoding='utf-8') as output:
            tunnel=subprocess.Popen([str(binary),'tunnel','--url',f'http://127.0.0.1:{PORT}','--http-host-header','127.0.0.1','--protocol','http2','--no-autoupdate'],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
        url=None
        for _ in range(100):
            if tunnel.poll() is not None: raise RuntimeError('Cloudflare no pudo abrir la revisión. Consultar .local/review/tunnel.log.')
            match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',log_path.read_text(encoding='utf-8',errors='replace'))
            if match: url=match.group(0);break
            time.sleep(.5)
        if not url: raise RuntimeError('No se recibió una URL pública de revisión.')
        write_json(DIRECTORY/'state.json',{'server_pid':server.pid,'tunnel_pid':tunnel.pid,'url':url,'port':PORT})
        for _ in range(24):
            try:
                if request_json(url+'/ready',4).get('status')=='ok': break
            except Exception: time.sleep(1)
        else: raise RuntimeError('El enlace no superó la comprobación HTTPS; no se declara publicado.')
        update_access(config,url)
        print('REVISIÓN HTTPS VERIFICADA: '+url)
        print('Acceso privado en .local/review/ACCESO_REVISION.txt y USO_PRIVADO_EQUIPO.txt, si existe.')
        print('Es una copia de prueba. No recopilar investigación real aquí.')
    except Exception:
        if tunnel and tunnel.poll() is None: tunnel.terminate()
        if server.poll() is None: server.terminate()
        raise
    finally: server_log.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['start','status','stop'])
    command=parser.parse_args().command
    if command=='start': start()
    elif command=='stop': stop();print('Revisión detenida. La base de investigación no se modificó.')
    else: print(json.dumps(status(),ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except Exception as error: raise SystemExit(str(error))
