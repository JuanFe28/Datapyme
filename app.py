"""Entrada ASGI. Crear instancias aisladas para pruebas y operación."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from research.config import ROOT,Settings
from research.database import make_engine,upgrade_database
from research.models import Base,Company,Response,Task,InstrumentQuestion
from research.security import bootstrap
from research.web import render
from research.instruments import VERSION
from questions import MILESTONES,Q_MAP

class BodyTooLarge(Exception): pass
class BodyLimit:
    def __init__(self,app,max_size): self.app=app; self.max_size=max_size
    async def __call__(self,scope,receive,send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        count=0
        async def limited_receive():
            nonlocal count
            message=await receive()
            count+=len(message.get('body',b''))
            if count>self.max_size: raise BodyTooLarge()
            return message
        length=dict(scope.get('headers',[])).get(b'content-length',b'0')
        if length.isdigit() and int(length)>self.max_size:
            return await JSONResponse({'detail':'La solicitud supera el límite de carga.'},413)(scope,receive,send)
        await self.app(scope,limited_receive,send)

def create_app(database_url=None,testing=False):
    settings=Settings.from_env(database_url)
    engine=make_engine(settings.database_url)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    @asynccontextmanager
    async def lifespan(application):
        upgrade_database(engine)
        with Session() as db:
            existing={t.title for t in db.query(Task)}
            db.add_all(Task(phase=p,title=t) for p,t in MILESTONES if t not in existing)
            for category,questions in Q_MAP.items():
                for code,definition in questions.items():
                    if not db.query(InstrumentQuestion).filter_by(category=category,version=VERSION,code=code).first():
                        db.add(InstrumentQuestion(category=category,version=VERSION,code=code,definition=definition))
            bootstrap(db); db.commit()
        yield
        engine.dispose()
    application=FastAPI(title='Datapyme Research Studio',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    application.state.engine=engine; application.state.Session=Session; application.state.settings=settings
    review=settings.environment=='review'
    application.add_middleware(SessionMiddleware,secret_key=settings.secret,session_cookie='datapyme_revision_session' if review else 'datapyme_session',https_only=settings.production or review,same_site='lax',max_age=43200)
    application.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.allowed_hosts)
    application.add_middleware(BodyLimit,max_size=12*1024*1024)
    @application.middleware('http')
    async def security_headers(request,call_next):
        response=await call_next(request)
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'",'Cache-Control':'no-store'})
        if settings.production or review: response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response
    @application.exception_handler(BodyTooLarge)
    async def too_large(request,error): return JSONResponse({'detail':'El archivo supera el límite permitido.'},413)
    @application.exception_handler(HTTPException)
    async def http_error(request,error):
        if error.status_code==303 or request.url.path.startswith('/api/'):
            return JSONResponse({'detail':error.detail},error.status_code,headers=error.headers)
        response=render(request,'error.html',status_code=error.status_code,title='Revisar solicitud',message=error.detail,code=error.status_code)
        if error.headers: response.headers.update(error.headers)
        return response
    @application.exception_handler(Exception)
    async def unhandled_error(request,error):
        logging.getLogger('uvicorn.error').exception(f'Error no controlado en {request.url.path}: {error}')
        if request.url.path.startswith('/api/'):
            return JSONResponse({'detail':'Ocurrió un error inesperado al procesar la solicitud.'},500)
        return render(request,'error.html',status_code=500,title='Error del servidor',message='El servidor encontró un inconveniente temporal.',code=500)
    @application.get('/health')
    def health(): return {'status':'ok'}
    @application.get('/ready')
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                revision=connection.execute(text('SELECT version_num FROM alembic_version')).scalar()
            if revision!='20261022_01': raise ValueError('schema')
            return {'status':'ok','database':'ok','schema':revision}
        except Exception:
            return JSONResponse({'status':'unavailable','database':'unavailable'},503)
    from research.auth_routes import router as auth_router
    from research.research_routes import router as research_router
    from research.project_routes import router as project_router
    from research.exports import router as export_router
    from research.public_routes import router as public_router
    for router in (auth_router,research_router,project_router,export_router,public_router): application.include_router(router)
    application.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')
    try:
        import sys
        empresarial_dir = ROOT / 'empresarial'
        if empresarial_dir.exists():
            root_app_mod = sys.modules.get('app')
            sys.modules.pop('app', None)
            emp_path_str = str(empresarial_dir.resolve())
            if emp_path_str not in sys.path:
                sys.path.insert(0, emp_path_str)
            from app.main import create_app as create_empresarial_app
            empresarial_app = create_empresarial_app()
            if root_app_mod is not None:
                sys.modules['app'] = root_app_mod
            application.mount('/empresarial', empresarial_app)
    except Exception as exc:
        logging.getLogger('uvicorn.error').warning(f'No fue posible montar Datapyme Empresarial: {exc}')
    return application

app=create_app()
