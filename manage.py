"""Administración local: migrar, crear usuarios y respaldar sin exponer claves."""
import argparse
import getpass
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
from research.config import Settings,ROOT
from research.database import make_engine,upgrade_database
from research.models import User
from research.security import create_user,hash_password,audit

def backup(settings,destination):
    destination=Path(destination).resolve()
    if destination.exists(): raise ValueError('La copia de destino ya existe; elige un nombre nuevo.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    url=make_url(settings.database_url)
    if url.drivername.startswith('sqlite'):
        source=Path(url.database).resolve()
        if not source.exists(): raise ValueError('La base de origen no existe.')
        if source==destination: raise ValueError('El destino debe ser una copia independiente.')
        with sqlite3.connect(source) as db,sqlite3.connect(destination) as target: db.backup(target)
        with sqlite3.connect(destination) as target:
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Falló la comprobación de la copia.')
    else:
        executable=shutil.which('pg_dump')
        if not executable: raise ValueError('Instala pg_dump compatible con el servidor PostgreSQL.')
        env={**os.environ,'PGPASSWORD':url.password or '', 'PGSSLMODE':url.query.get('sslmode','require')}
        command=[executable,'--host',url.host,'--port',str(url.port or 5432),'--username',url.username,'--dbname',url.database,'--format=custom','--no-owner','--no-acl','--file',str(destination)]
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        if result.returncode: raise ValueError('pg_dump falló. Revisa conectividad y permisos; la copia no está confirmada.')
    with destination.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'file':destination.name,'sha256':digest,'engine':url.get_backend_name(),'includes':'Usuarios, consentimientos, investigación, auditoría y binarios de evidencias'}
    destination.with_suffix(destination.suffix+'.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Copia creada y manifiesto SHA-256 guardado. Protege ambos archivos.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate')
    user=sub.add_parser('create-user'); user.add_argument('--username',required=True); user.add_argument('--role',choices=['admin','campo'],default='campo')
    change=sub.add_parser('reset-password'); change.add_argument('--username',required=True)
    copy=sub.add_parser('backup'); copy.add_argument('--output',required=True)
    sub.add_parser('check')
    sub.add_parser('seed-demo')
    clear_p = sub.add_parser('clear-demo')
    clear_p.add_argument('--all', action='store_true', help='Limpia todas las entidades de investigación, no solo las demo.')
    args=parser.parse_args(); settings=Settings.from_env()
    if args.command=='backup': backup(settings,args.output); return
    engine=make_engine(settings.database_url)
    try:
        upgrade_database(engine)
        if args.command=='migrate': print('Esquema actualizado mediante Alembic, sin borrar registros.'); return
        if args.command=='check':
            from sqlalchemy import text
            with engine.connect() as db: print('Esquema: '+db.execute(text('SELECT version_num FROM alembic_version')).scalar())
            print('Conexión de base de datos: correcta.'); return
        if args.command in ('seed-demo', 'clear-demo'):
            from research.demo_data import seed_demo_data, clear_demo_data, clear_all_research_data
            with Session(engine) as db:
                if args.command == 'seed-demo':
                    res = seed_demo_data(db)
                    print(f"Datos demo sembrados con éxito: {res['companies']} empresas, {res['surveys']} encuestas, {res['canvas']} canvas, {res['finance']} finanzas, {res['notes']} notas.")
                elif args.command == 'clear-demo':
                    if args.all:
                        res = clear_all_research_data(db)
                        print(f"Limpieza completa de datos de investigación: {res}")
                    else:
                        res = clear_demo_data(db)
                        print(f"Datos de demostración eliminados: {res}")
            return
        password=getpass.getpass('Contraseña (mínimo 12 caracteres): ')
        if password!=getpass.getpass('Confirma la contraseña: '): raise ValueError('Las contraseñas no coinciden.')
        with Session(engine) as db:
            if args.command=='create-user':
                if db.query(User).filter_by(username=args.username.strip().casefold()).first(): raise ValueError('Ya existe ese usuario.')
                user=create_user(db,args.username,password,args.role)
            else:
                from research.models import LoginSession
                user=db.query(User).filter_by(username=args.username.strip().casefold()).first()
                if not user: raise ValueError('Usuario no encontrado.')
                user.password_hash=hash_password(password)
                db.query(LoginSession).filter_by(user_id=user.id).delete()
            audit(db,'CLI','administrar','user',user.id,{'usuario':user.username,'operación':args.command}); db.commit()
        print('Cuenta actualizada. La contraseña no se guardó en texto plano.')
    finally: engine.dispose()

if __name__=='__main__':
    try: main()
    except ValueError as error: raise SystemExit(str(error))
