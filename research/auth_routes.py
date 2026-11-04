import secrets
from fastapi import APIRouter,Request,HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from .models import User,LoginSession,AuditLog
from .security import account,admin,auth,csrf,authenticate,token_digest,create_user,hash_password,audit
from .web import render,redirect,flash

router=APIRouter()

@router.get('/login')
def login_get(request:Request):
    if account(request): return redirect('/')
    return render(request,'login.html',title='Acceso seguro')

@router.post('/login')
async def login_post(request:Request):
    form=await request.form(); csrf(request,form.get('csrf_token'))
    username=str(form.get('username','')); password=str(form.get('password',''))
    if len(username)>60 or len(password)>512: raise HTTPException(422,'Credenciales inválidas.')
    with request.app.state.Session() as db:
        token=authenticate(request,db,username,password)
    if not token:
        flash(request,'Usuario o contraseña incorrectos.','error'); return redirect('/login')
    request.session.clear(); request.session.update(token=token,csrf=secrets.token_hex(24))
    return redirect('/')

@router.post('/logout')
async def logout(request:Request):
    form=await request.form(); csrf(request,form.get('csrf_token'))
    with request.app.state.Session() as db:
        db.execute(delete(LoginSession).where(LoginSession.token_hash==token_digest(request.session.get('token','')))); db.commit()
    request.session.clear(); return redirect('/login')

@router.get('/usuarios')
def users_get(request:Request):
    admin(request)
    with request.app.state.Session() as db:
        return render(request,'users.html',title='Usuarios y acceso',active='usuarios',users=db.query(User).order_by(User.username).all())

@router.post('/usuarios')
async def users_create(request:Request):
    actor=admin(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    with request.app.state.Session() as db:
        try:
            user=create_user(db,str(form.get('username','')),str(form.get('password','')),str(form.get('role','')))
            audit(db,actor['name'],'crear','user',user.id,{'usuario':user.username,'rol':user.role}); db.commit()
        except ValueError as error: raise HTTPException(422,str(error))
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'Ya existe ese usuario.')
    flash(request,'Cuenta individual creada. Comparte sus credenciales por un canal privado.'); return redirect('/usuarios')

@router.post('/usuarios/{user_id}')
async def user_update(request:Request,user_id:int):
    actor=admin(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    with request.app.state.Session() as db:
        user=db.get(User,user_id)
        if not user: raise HTTPException(404)
        active=form.get('active')=='yes'; role=str(form.get('role',''))
        if role not in ('admin','campo'): raise HTTPException(422,'Rol inválido.')
        if user.id==actor['id'] and (not active or role!='admin'): raise HTTPException(422,'No puedes retirar tu propio acceso de administrador.')
        user.active=active; user.role=role
        password=str(form.get('password',''))
        if password:
            try: user.password_hash=hash_password(password)
            except ValueError as error: raise HTTPException(422,str(error))
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id))
        audit(db,actor['name'],'acceso','user',user.id,{'activo':active,'rol':role,'clave_cambiada':bool(password)}); db.commit()
    flash(request,'Acceso actualizado y sesiones anteriores revocadas.'); return redirect('/usuarios')

@router.get('/auditoria')
def audit_get(request:Request):
    admin(request)
    with request.app.state.Session() as db:
        return render(request,'audit.html',title='Historial de cambios',active='auditoria',records=db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all())
