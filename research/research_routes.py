import hashlib
import secrets
from datetime import date
from fastapi import APIRouter,Request,HTTPException
from sqlalchemy.exc import IntegrityError
from .models import Company,CompanyContact,Response,Consent,Answer,AuditLog,utcnow,normalized
from .security import auth,admin,csrf,audit
from .web import render,redirect,flash
from .instruments import VERSION,CONSENT_STATEMENT,validate_answers
from .analytics import filtered_records,build_analysis,query_string
from questions import QUESTION_SETS,Q_MAP

router=APIRouter()
CHOICES={'city':['Bucaramanga','Otro / por verificar'],'activity':['Comercio minorista','Comercio mayorista','Servicios','Manufactura','Otra / verificar'],'size':['Microempresa','Pequeña','Mediana','Grande','Desconocida'],'has_records':['Sí, ambos','Solo ventas','Solo inventarios','No / no sabe'],'willing':['Sí','Tal vez','No','No contactado'],'verification_status':['pendiente','verificada'],'operating_status':['activa','inactiva','pendiente'],'respondent_role':['No contactado','Propietario','Propietario o socio','Gerente o administrador','Administrador','Responsable de ventas','Responsable de inventarios','Otro']}

def company_values(form):
    fields={'name':180,'barrio':120,'city':60,'activity':90,'ciiu':20,'size':30,'source':90,'has_records':40,'respondent_role':90,'willing':30,'notes':4000,'verification_status':20,'operating_status':20}
    values={k:str(form.get(k,'' )).strip() for k in fields}
    values['verification_status']=values['verification_status'] or 'pendiente'
    values['operating_status']=values['operating_status'] or 'pendiente'
    for key,limit in fields.items():
        if len(values[key])>limit: raise HTTPException(422,f'{key}: máximo {limit} caracteres.')
    if len(values['name'])<2 or not values['barrio']: raise HTTPException(422,'Completa nombre comercial y barrio.')
    for key,options in CHOICES.items():
        if values[key] not in options: raise HTTPException(422,'Opción inválida: '+key)
    values['duplicate_key']=hashlib.sha256((normalized(values['name'])+'|'+normalized(values['barrio'])).encode()).hexdigest()
    return values

def find_duplicate(db,values,exclude=None):
    return next((c for c in db.query(Company).all() if c.id!=exclude and normalized(c.name)==normalized(values['name']) and normalized(c.barrio)==normalized(values['barrio'])),None)

@router.get('/')
def dashboard(request:Request):
    auth(request)
    with request.app.state.Session() as db:
        companies,responses,filters=filtered_records(db,request.query_params)
        analysis=build_analysis(db,companies,responses)
        return render(request,'dashboard.html',title='Vista general',active='inicio',analysis=analysis,stats=analysis['stats'],filters=filters,filter_query=query_string(filters),recent=sorted(responses,key=lambda r:r.id,reverse=True)[:5])

@router.get('/analisis')
def analysis_page(request:Request):
    auth(request)
    with request.app.state.Session() as db:
        companies,responses,filters=filtered_records(db,request.query_params)
        return render(request,'analytics.html',title='Análisis estadístico',active='analisis',analysis=build_analysis(db,companies,responses),filters=filters,filter_query=query_string(filters))

@router.get('/api/analisis')
def analysis_api(request:Request):
    auth(request)
    with request.app.state.Session() as db:
        companies,responses,filters=filtered_records(db,request.query_params)
        return {**build_analysis(db,companies,responses),'filters':filters}

def get_registration_share(request: Request):
    base_url = str(request.base_url).rstrip('/')
    url = f"{base_url}/registro-empresa"
    message = (
        "Estimado(a) empresario(a),\n\n"
        "Un cordial saludo del equipo de investigación de las Unidades Tecnológicas de Santander (UTS) para el proyecto Datapyme.\n\n"
        "Le invitamos a inscribir su empresa o negocio en el estudio sobre gestión de ventas e inventarios para el comercio de Bucaramanga. "
        "Puede registrarse fácilmente a través del siguiente enlace:\n\n"
        f"{url}\n\n"
        "Una vez inscrito(a), podrá responder el breve diagnóstico comercial de 3 a 5 minutos. "
        "¡Agradecemos mucho su valiosa colaboración!"
    )
    return url, message

@router.get('/empresas')
def companies_get(request:Request):
    auth(request)
    with request.app.state.Session() as db:
        companies,_,filters=filtered_records(db,request.query_params)
        reg_url, reg_msg = get_registration_share(request)
        return render(request,'companies.html',title='Empresas',active='empresas',companies=companies,filters=filters,filter_query=query_string(filters),query=filters['q'],registration_url=reg_url,whatsapp_reg_message=reg_msg)

@router.get('/empresas/nueva')
def company_new(request:Request):
    auth(request)
    reg_url, reg_msg = get_registration_share(request)
    return render(request,'company_form.html',title='Registrar empresa',active='empresas',choices=CHOICES,registration_url=reg_url,whatsapp_reg_message=reg_msg)

def contact_values(db,company,form,user):
    if user['role']!='admin': return
    name=str(form.get('contact_name','')).strip(); detail=str(form.get('contact_detail','')).strip()
    if len(name)>120 or len(detail)>250: raise HTTPException(422,'Contacto demasiado extenso.')
    if name or detail or company.contact:
        if not company.contact: company.contact=CompanyContact()
        company.contact.name=name; company.contact.detail=detail

@router.post('/empresas/nueva')
async def company_create(request:Request):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    values=company_values(form)
    with request.app.state.Session() as db:
        if find_duplicate(db,values): raise HTTPException(409,'Ya existe una empresa con el mismo nombre y barrio.')
        company=Company(**values,owner=user['name']); db.add(company)
        try:
            db.flush(); contact_values(db,company,form,user)
            audit(db,user['name'],'crear','company',company.id,{'code':company.code}); db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'Ya existe una empresa con el mismo nombre y barrio.')
    flash(request,'Empresa registrada. Verifica los criterios antes de aplicar instrumentos.'); return redirect('/empresas')

@router.get('/empresas/{company_id}/editar')
def company_edit(request:Request,company_id:int):
    user=auth(request)
    with request.app.state.Session() as db:
        company=db.get(Company,company_id)
        if not company: raise HTTPException(404,'Empresa no encontrada.')
        history=db.query(AuditLog).filter_by(entity_type='company',entity_id=company_id).order_by(AuditLog.id.desc()).limit(20).all()
        existing_survey=db.query(Response).filter_by(company_id=company_id,category='mercado',status='complete').first()
        from .tokens import generate_survey_token
        token=generate_survey_token(request.app.state.settings.secret,company_id)
        base_url=str(request.base_url).rstrip('/')
        survey_url=f"{base_url}/encuesta/{token}"
        whatsapp_message=(
            f"Estimado(a) representante de {company.name},\n\n"
            f"Un cordial saludo del equipo de investigación de las Unidades Tecnológicas de Santander (UTS) para el proyecto Datapyme.\n\n"
            f"Le compartimos el enlace para responder la breve encuesta académica sobre gestión de ventas e inventarios (toma de 3 a 5 minutos):\n\n"
            f"{survey_url}\n\n"
            f"Sus respuestas son confidenciales y con fines estrictamente académicos. ¡Agradecemos mucho su valiosa colaboración!"
        )
        return render(request,'company_form.html',title='Editar empresa',active='empresas',company=company,choices=CHOICES,history=history,survey_url=survey_url,existing_survey=existing_survey,whatsapp_message=whatsapp_message)

@router.post('/empresas/{company_id}/editar')
async def company_update(request:Request,company_id:int):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token')); values=company_values(form)
    with request.app.state.Session() as db:
        company=db.get(Company,company_id)
        if not company: raise HTTPException(404,'Empresa no encontrada.')
        if find_duplicate(db,values,company_id): raise HTTPException(409,'Ya existe otra empresa con ese nombre y barrio.')
        changes={k:{'antes':getattr(company,k),'después':v} for k,v in values.items() if k!='duplicate_key' and getattr(company,k)!=v}
        for key,value in values.items(): setattr(company,key,value)
        contact_values(db,company,form,user); company.updated_at=utcnow()
        audit(db,user['name'],'editar','company',company.id,changes)
        try: db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'Conflicto de duplicidad. No se guardaron cambios.')
    flash(request,'Ficha actualizada; los análisis reflejan la elegibilidad actual.'); return redirect('/empresas')

@router.post('/empresas/{company_id}/eliminar')
async def no_company_delete(request:Request,company_id:int):
    admin(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    raise HTTPException(409,'Se conserva el registro y su historial. Cambia su estado de actividad si corresponde.')

def instrument_context(request,db,category,record=None,values=None,errors=None,status_code=200):
    companies=[c for c in db.query(Company).order_by(Company.name) if c.eligible]
    if category=='mercado':
        done={r.company_id for r in db.query(Response).filter_by(category='mercado',status='complete') if not record or r.id!=record.id}
        companies=[c for c in companies if c.id not in done]
    titles={'mercado':'Encuesta de mercado','entrevista':'Entrevista empresarial','prototipo':'Validación del prototipo'}
    return render(request,'instrument.html',status_code=status_code,title=titles[category],active=category,category=category,sections=QUESTION_SETS[category],companies=companies,record=record,values=values or (record.data if record else {}),errors=errors or {},consent_statement=CONSENT_STATEMENT)

@router.get('/instrumentos/{category}')
def instrument_get(request:Request,category:str,response_id:int|None=None):
    user=auth(request)
    if category not in QUESTION_SETS: raise HTTPException(404)
    with request.app.state.Session() as db:
        record=db.get(Response,response_id) if response_id else None
        if response_id and (not record or record.category!=category): raise HTTPException(404)
        if record and record.author!=user['name'] and user['role']!='admin': raise HTTPException(403)
        if record and record.status=='withdrawn' and user['role']!='admin': raise HTTPException(403,'Solo el administrador puede revisar una respuesta retirada.')
        return instrument_context(request,db,category,record)

@router.post('/instrumentos/{category}')
async def instrument_post(request:Request,category:str):
    user=auth(request)
    if category not in QUESTION_SETS: raise HTTPException(404)
    form=await request.form(); csrf(request,form.get('csrf_token'))
    try: company_id=int(form.get('company_id','0')); response_id=int(form.get('response_id') or '0')
    except ValueError: raise HTTPException(422,'Empresa o respuesta inválida.')
    complete=form.get('action','complete')=='complete'
    payload,errors=validate_answers(category,form,complete)
    if complete and form.get('consent')!='yes': errors['consent']='Confirma el consentimiento informado antes de guardar.'
    reference=str(form.get('prototype_reference','')).strip()
    if complete and category=='prototipo' and not reference: errors['prototype_reference']='Registra la URL o referencia de la versión que realmente se evaluó.'
    if len(reference)>500: errors['prototype_reference']='Máximo 500 caracteres.'
    with request.app.state.Session() as db:
        company=db.get(Company,company_id)
        if not company or not company.eligible: raise HTTPException(422,'La empresa debe cumplir todos los criterios de elegibilidad.')
        record=db.get(Response,response_id) if response_id else None
        if response_id and (not record or record.company_id!=company_id or record.category!=category): raise HTTPException(404)
        if record and record.author!=user['name'] and user['role']!='admin': raise HTTPException(403)
        if record and record.status in ('complete','withdrawn') and user['role']!='admin': raise HTTPException(403,'Solo el administrador puede corregir o reactivar una respuesta final o retirada.')
        if category=='mercado' and complete and db.query(Response).filter(Response.category=='mercado',Response.company_id==company_id,Response.status=='complete',Response.id!=(response_id or -1)).first(): raise HTTPException(409,'Ya existe una encuesta final de esta empresa.')
        if record and record.status=='complete' and not complete: raise HTTPException(409,'Una respuesta final no se convierte en borrador. Corrígela como final o documenta su retiro.')
        if errors: return instrument_context(request,db,category,record,{**payload,'company_id':str(company_id),'consent':form.get('consent',''),'prototype_reference':reference},errors,422)
        if not record:
            record=Response(company_id=company_id,category=category,author=user['name'],data={},participant_code='P-'+secrets.token_hex(5).upper()); db.add(record)
        old_status=record.status
        record.participant_code=record.participant_code or 'P-'+secrets.token_hex(5).upper()
        record.data=payload; record.status='complete' if complete else 'draft'; record.updated_at=utcnow(); record.instrument_version=VERSION; record.prototype_reference=reference
        record.survey_key=f'mercado:{company_id}' if category=='mercado' and complete else None
        if complete:
            consent=Consent(company_id=company_id,participant_code=record.participant_code,instrument=category,version=VERSION,statement=CONSENT_STATEMENT,recorded_by=user['name']); db.add(consent); db.flush(); record.consent_id=consent.id
        try:
            db.flush(); record.answers.clear(); db.flush()
            record.answers=[Answer(question_code=k,value=v) for k,v in payload.items() if v is not None]
            audit(db,user['name'],'finalizar' if complete else 'borrador','response',record.id,{'anterior':old_status,'estado':record.status,'instrumento':category})
            db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'Ya existe una encuesta final o hubo una actualización simultánea. Recarga el registro.')
        flash(request,'Respuesta final guardada con consentimiento.' if complete else 'Borrador guardado. No se incluye en estadísticas.')
        return redirect(f'/respuestas/{record.id}')

@router.get('/respuestas')
def responses_get(request:Request,tipo:str='',status:str=''):
    auth(request)
    with request.app.state.Session() as db:
        _,records,filters=filtered_records(db,request.query_params)
        if tipo in QUESTION_SETS: records=[r for r in records if r.category==tipo]
        if status: records=[r for r in records if r.status==status]
        return render(request,'responses.html',title='Respuestas registradas',active='respuestas',records=sorted(records,key=lambda r:-r.id),tipo=tipo,questions=Q_MAP,filters=filters)

@router.get('/respuestas/{response_id}')
def response_detail(request:Request,response_id:int):
    auth(request)
    with request.app.state.Session() as db:
        record=db.get(Response,response_id)
        if not record: raise HTTPException(404)
        return render(request,'response_detail.html',title='Detalle de respuesta',active='respuestas',record=record,labels=Q_MAP.get(record.category,{}))

@router.post('/respuestas/{response_id}/eliminar')
async def response_withdraw(request:Request,response_id:int):
    user=admin(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    with request.app.state.Session() as db:
        record=db.get(Response,response_id)
        if not record: raise HTTPException(404)
        record.status='withdrawn'; record.survey_key=None
        audit(db,user['name'],'retirar','response',record.id,{'motivo':str(form.get('reason','Retiro documentado por administrador'))[:300]}); db.commit()
    flash(request,'Respuesta retirada del análisis; se conserva el historial.'); return redirect('/respuestas')

@router.get('/guia')
def guide(request:Request):
    auth(request); return render(request,'guide.html',title='Guía de campo',active='guia')
