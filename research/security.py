import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import timedelta, timezone
from fastapi import HTTPException
from .models import User, LoginSession, LoginAttempt, AuditLog, utcnow

ITERATIONS=600_000
def hash_password(password):
    if not 12<=len(password)<=512: raise ValueError('La contraseña debe tener entre 12 y 512 caracteres.')
    salt=secrets.token_bytes(18)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'

def verify_password(password,encoded):
    try:
        algorithm,iterations,salt,expected=encoded.split('$')
        if algorithm!='pbkdf2_sha256' or len(password)>512: return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(iterations)).hex()
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False

def audit(db,actor,action,entity_type,entity_id=None,changes=None):
    db.add(AuditLog(actor=actor,action=action,entity_type=entity_type,entity_id=entity_id,changes=changes or {}))

def create_user(db,username,password,role):
    username=username.strip().casefold()
    if not re.fullmatch(r'[a-z0-9_.-]{3,60}',username) or role not in ('admin','campo'): raise ValueError('Usuario o rol inválido.')
    user=User(username=username,password_hash=hash_password(password),role=role,active=True)
    db.add(user); db.flush(); return user

def bootstrap(db):
    for user_key,password_key,default,role in [('ADMIN_USER','ADMIN_PASSWORD','admin','admin'),('FIELD_USER','FIELD_PASSWORD','investigador','campo')]:
        username=os.getenv(user_key,default).casefold()
        if not db.query(User).filter_by(username=username).first() and os.getenv(password_key):
            create_user(db,username,os.environ[password_key],role)

def token_digest(token): return hashlib.sha256(token.encode()).hexdigest()
def aware(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def account(request):
    if hasattr(request.state,'account'): return request.state.account
    result=None; token=request.session.get('token','')
    if token:
        with request.app.state.Session() as db:
            session=db.query(LoginSession).filter_by(token_hash=token_digest(token)).first()
            if session and aware(session.expires_at)>utcnow() and session.user.active:
                result={'id':session.user.id,'name':session.user.username,'role':session.user.role}
    request.state.account=result
    return result

def auth(request):
    user=account(request)
    if not user: raise HTTPException(303,headers={'Location':'/login'})
    return user

def admin(request):
    user=auth(request)
    if user['role']!='admin': raise HTTPException(403,'Solo el administrador puede realizar esta operación.')
    return user

def csrf(request,value):
    if not isinstance(value,str) or not value or not hmac.compare_digest(value,request.session.get('csrf','')):
        raise HTTPException(403,'El formulario venció. Recarga la página e inténtalo de nuevo.')

def attempt_key(request,username):
    ip=request.client.host if request.client else 'unknown'
    return hmac.new(request.app.state.settings.secret.encode(),(ip+'|'+username.strip().casefold()).encode(),'sha256').hexdigest()

def authenticate(request,db,username,password):
    key=attempt_key(request,username)
    attempt=db.get(LoginAttempt,key)
    if attempt and aware(attempt.since)<utcnow()-timedelta(minutes=15):
        attempt.failures=0; attempt.since=utcnow()
    if attempt and attempt.failures>=5:
        raise HTTPException(429,'Demasiados intentos. Inténtalo en 15 minutos.',headers={'Retry-After':'900'})
    user=db.query(User).filter_by(username=username.strip().casefold()).first()
    # También ejecutar el hash para usuarios inexistentes, sin revelar su existencia.
    fallback='pbkdf2_sha256$600000$'+'00'*18+'$'+'00'*32
    valid=verify_password(password,user.password_hash if user else fallback)
    if not user or not user.active or not valid:
        if not attempt:
            attempt=LoginAttempt(key=key,failures=0); db.add(attempt)
        attempt.failures+=1; db.commit(); return None
    if attempt: db.delete(attempt)
    token=secrets.token_urlsafe(40)
    db.add(LoginSession(token_hash=token_digest(token),user_id=user.id,expires_at=utcnow()+timedelta(hours=12)))
    audit(db,user.username,'login','user',user.id)
    db.commit()
    return token
