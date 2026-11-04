import hashlib
from datetime import date
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response as Download
from .models import Task,Company,Response,Evidence,EvidenceBlob,CanvasVersion,FinancialScenario,ResearchNote,utcnow
from .security import auth,admin,csrf,audit
from .web import render,redirect,flash
from .file_validation import validate_file
from .finance import parse_inputs,calculate_scenario

router=APIRouter()
CANVAS_BLOCKS={'segments':'Segmentos de clientes','value':'Propuesta de valor','channels':'Canales','relationships':'Relaciones con clientes','revenue':'Fuentes de ingresos','resources':'Recursos clave','activities':'Actividades clave','partners':'Socios clave','costs':'Estructura de costos'}
NOTE_TYPES={'competencia':'Competencia','organizacion':'Organización y procesos','ambiental':'Evaluación ambiental','financiacion':'Fuentes de financiación','metodologia':'Método, muestra y limitaciones','cotizacion':'Costos y cotizaciones'}

def evidence_allowed(evidence,user): return evidence and (user['role']=='admin' or evidence.uploader==user['name'])
def visible_evidence(db,user):
    query=db.query(Evidence)
    if user['role']!='admin': query=query.filter_by(uploader=user['name'])
    return query.order_by(Evidence.id.desc()).all()

def optional_id(form,key):
    value=str(form.get(key,'')).strip()
    if not value: return None
    if not value.isdigit(): raise HTTPException(422,'Asociación inválida: '+key)
    return int(value)

@router.get('/tareas')
def tasks_get(request:Request):
    auth(request)
    with request.app.state.Session() as db:
        return render(request,'tasks.html',title='Plan de trabajo',active='tareas',tasks=db.query(Task).order_by(Task.id).all())

@router.post('/tareas/{task_id}')
async def task_update(request:Request,task_id:int):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    status=str(form.get('status','completada' if form.get('completed')=='yes' else 'planificada'))
    assignee=str(form.get('assignee','')).strip(); evidence=str(form.get('evidence','')).strip()
    if status not in ('planificada','en_ejecucion','completada') or len(assignee)>120 or len(evidence)>300: raise HTTPException(422,'Estado o campos inválidos.')
    if status=='completada' and (not evidence or not assignee): raise HTTPException(422,'Una actividad completada requiere responsable y referencia a la evidencia.')
    try: due=date.fromisoformat(str(form.get('due_date'))) if form.get('due_date') else None
    except ValueError: raise HTTPException(422,'Fecha inválida.')
    with request.app.state.Session() as db:
        task=db.get(Task,task_id)
        if not task: raise HTTPException(404)
        task.status=status; task.completed=status=='completada'; task.assignee=assignee; task.evidence=evidence; task.due_date=due; task.updated_at=utcnow()
        audit(db,user['name'],'actualizar','task',task_id,{'estado':status,'responsable':assignee}); db.commit()
    flash(request,'Actividad actualizada.'); return redirect('/tareas')

@router.get('/evidencias')
def evidence_get(request:Request):
    user=auth(request)
    with request.app.state.Session() as db:
        return render(request,'evidence.html',title='Evidencias y archivos',active='evidencias',files=visible_evidence(db,user),companies=db.query(Company).order_by(Company.name).all(),responses=db.query(Response).order_by(Response.id.desc()).all(),tasks=db.query(Task).all())

@router.post('/evidencias')
async def evidence_upload(request:Request):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    if form.get('authorized')!='yes': raise HTTPException(422,'Confirma la autorización de carga y tratamiento de este archivo.')
    title=str(form.get('title','')).strip(); notes=str(form.get('notes','')).strip()
    if not title or len(title)>180 or len(notes)>4000: raise HTTPException(422,'Completa un título válido (máximo 180 caracteres).')
    upload=form.get('file')
    if not upload or not hasattr(upload,'read'): raise HTTPException(422,'Selecciona un archivo.')
    content=await upload.read(request.app.state.settings.max_upload+1); await upload.close()
    filename,mime=validate_file(upload.filename or '',content,request.app.state.settings.max_upload)
    links={key:optional_id(form,key) for key in ('company_id','response_id','task_id')}
    with request.app.state.Session() as db:
        for key,model in [('company_id',Company),('response_id',Response),('task_id',Task)]:
            if links[key] is not None and not db.get(model,links[key]): raise HTTPException(422,'El registro asociado ya no existe.')
        if links['response_id'] and links['company_id'] and db.get(Response,links['response_id']).company_id!=links['company_id']: raise HTTPException(422,'La respuesta no corresponde a la empresa seleccionada.')
        record=Evidence(title=title,filename=filename,mime_type=mime,size=len(content),sha256=hashlib.sha256(content).hexdigest(),uploader=user['name'],notes=notes,**links)
        db.add(record); db.flush(); db.add(EvidenceBlob(evidence_id=record.id,content=content))
        audit(db,user['name'],'adjuntar','evidence',record.id,{'sha256':record.sha256,'bytes':record.size}); db.commit()
    flash(request,'Archivo almacenado en la base persistente, con acceso privado.'); return redirect('/evidencias')

@router.get('/evidencias/{evidence_id}/descargar')
def evidence_download(request:Request,evidence_id:int):
    user=auth(request)
    with request.app.state.Session() as db:
        record=db.get(Evidence,evidence_id)
        if not record: raise HTTPException(404)
        if not evidence_allowed(record,user): raise HTTPException(403,'Archivo privado de otro investigador.')
        content=record.blob.content
        audit(db,user['name'],'descargar','evidence',record.id); db.commit()
        from urllib.parse import quote
        return Download(content,media_type=record.mime_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(record.filename),'Content-Security-Policy':"sandbox; default-src 'none'",'X-Content-Type-Options':'nosniff'})

@router.get('/canvas')
def canvas_get(request:Request,version:int|None=None,compare:int|None=None):
    user=auth(request)
    with request.app.state.Session() as db:
        versions=db.query(CanvasVersion).order_by(CanvasVersion.id.desc()).all()
        selected=db.get(CanvasVersion,version) if version else (versions[0] if versions else None)
        comparison=db.get(CanvasVersion,compare) if compare else None
        if (version and not selected) or (compare and not comparison): raise HTTPException(404)
        return render(request,'canvas.html',title='Modelo de negocio',active='canvas',versions=versions,selected=selected,comparison=comparison,blocks=CANVAS_BLOCKS,evidences=visible_evidence(db,user))

@router.post('/canvas')
async def canvas_save(request:Request):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    title=str(form.get('title','')).strip(); blocks={k:str(form.get(k,'')).strip() for k in CANVAS_BLOCKS}
    status=str(form.get('hypothesis_status','pendiente')); conclusion=str(form.get('conclusion','')).strip(); evidence_id=optional_id(form,'evidence_id')
    if not title or len(title)>180 or any(not v or len(v)>4000 for v in blocks.values()) or len(conclusion)>4000: raise HTTPException(422,'Completa título y los nueve componentes (máximo 4000 caracteres cada uno).')
    if status not in ('pendiente','contrastada','validada','descartada'): raise HTTPException(422,'Estado de hipótesis inválido.')
    with request.app.state.Session() as db:
        if evidence_id and not evidence_allowed(db.get(Evidence,evidence_id),user): raise HTTPException(403,'Evidencia no disponible.')
        if status!='pendiente' and (not conclusion or not evidence_id): raise HTTPException(422,'Contrastar o validar requiere evidencia adjunta y una conclusión explícita.')
        record=CanvasVersion(title=title,blocks=blocks,hypothesis_status=status,evidence_id=evidence_id,conclusion=conclusion,author=user['name']); db.add(record); db.flush()
        audit(db,user['name'],'versionar','canvas',record.id,{'estado':status}); db.commit()
    flash(request,'Nueva versión del Canvas guardada. Las versiones anteriores se conservan.'); return redirect('/canvas')

@router.get('/finanzas')
def finance_get(request:Request,scenario:int|None=None,compare:int|None=None):
    auth(request)
    with request.app.state.Session() as db:
        scenarios=db.query(FinancialScenario).order_by(FinancialScenario.id.desc()).all()
        selected=db.get(FinancialScenario,scenario) if scenario else (scenarios[0] if scenarios else None)
        comparison=db.get(FinancialScenario,compare) if compare else None
        if (scenario and not selected) or (compare and not comparison): raise HTTPException(404)
        return render(request,'finance.html',title='Viabilidad financiera',active='finanzas',scenarios=scenarios,selected=selected,result=calculate_scenario(selected.inputs) if selected else None,comparison=comparison,comparison_result=calculate_scenario(comparison.inputs) if comparison else None)

@router.post('/finanzas')
async def finance_save(request:Request):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    inputs=parse_inputs(form); name=str(form.get('name','')).strip(); source=str(form.get('source','')).strip(); assumptions=str(form.get('assumptions','')).strip()
    if not name or not source or not assumptions or len(name)>180 or len(source)>4000 or len(assumptions)>4000: raise HTTPException(422,'Registra nombre, fuentes y supuestos explícitos.')
    with request.app.state.Session() as db:
        scenario=FinancialScenario(name=name,inputs=inputs,source=source,assumptions=assumptions,author=user['name']); db.add(scenario); db.flush()
        audit(db,user['name'],'crear','finance',scenario.id); db.commit()
    flash(request,'Escenario calculado y guardado con sus supuestos.'); return redirect('/finanzas')

@router.get('/api/finanzas/{scenario_id}')
def finance_api(request:Request,scenario_id:int):
    auth(request)
    with request.app.state.Session() as db:
        record=db.get(FinancialScenario,scenario_id)
        if not record: raise HTTPException(404)
        return {**calculate_scenario(record.inputs),'name':record.name,'source':record.source,'assumptions':record.assumptions}

@router.get('/notas')
def notes_get(request:Request,kind:str=''):
    auth(request)
    with request.app.state.Session() as db:
        records=db.query(ResearchNote).order_by(ResearchNote.id.desc())
        if kind: records=records.filter_by(kind=kind)
        return render(request,'notes.html',title='Estudios y fuentes',active='notas',records=records.all(),kinds=NOTE_TYPES,kind=kind)

@router.post('/notas')
async def notes_save(request:Request):
    user=auth(request); form=await request.form(); csrf(request,form.get('csrf_token'))
    values={k:str(form.get(k,'')).strip() for k in ('kind','title','content','source')}
    if values['kind'] not in NOTE_TYPES or any(not v for v in values.values()) or len(values['title'])>180 or any(len(values[k])>10000 for k in ('content','source')): raise HTTPException(422,'Completa tipo, título, contenido y fuente verificable.')
    with request.app.state.Session() as db:
        record=ResearchNote(**values,author=user['name']); db.add(record); db.flush(); audit(db,user['name'],'crear','note',record.id); db.commit()
    flash(request,'Nota guardada con su fuente.'); return redirect('/notas')
