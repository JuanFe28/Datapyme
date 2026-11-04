import secrets
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from .config import ROOT
from .security import account

templates=Jinja2Templates(directory=str(ROOT/'templates'))

def local_date(value):
    from datetime import timezone
    from zoneinfo import ZoneInfo
    if value.tzinfo is None: value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo('America/Bogota')).strftime('%d/%m/%Y')
templates.env.filters['localdate']=local_date

def render(request,name,status_code=200,**kwargs):
    request.session.setdefault('csrf',secrets.token_hex(24))
    context={'request':request,'user':account(request),'csrf':request.session['csrf'],'flash':request.session.pop('flash',None),'active':'','title':'Datapyme','environment':request.app.state.settings.environment,**kwargs}
    return templates.TemplateResponse(request=request,name=name,context=context,status_code=status_code)

def flash(request,text,kind='ok'): request.session['flash']={'text':text,'kind':kind}
def redirect(path): return RedirectResponse(path,status_code=303)
def fail(message,status=422): raise HTTPException(status,message)
