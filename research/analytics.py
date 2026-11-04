from collections import Counter
from datetime import date,datetime,time,timedelta,timezone
from urllib.parse import urlencode
from fastapi import HTTPException
from .models import Company,Response,Task
from questions import Q_MAP

FILTER_KEYS=('q','size','activity','eligibility','company_id','from_date','to_date','sort')

def parse_filters(params):
    result={k:str(params.get(k,''))[:180] for k in FILTER_KEYS}
    for key in ('from_date','to_date'):
        if result[key]:
            try: date.fromisoformat(result[key])
            except ValueError: raise HTTPException(422,'Fecha inválida. Usa AAAA-MM-DD.')
    if result['from_date'] and result['to_date'] and result['from_date']>result['to_date']: raise HTTPException(422,'La fecha inicial debe ser anterior a la final.')
    if result['company_id'] and not result['company_id'].isdigit(): raise HTTPException(422,'Código de empresa inválido.')
    return result

def in_period(value,filters):
    if not value: return not filters['from_date'] and not filters['to_date']
    # Los filtros corresponden a fechas de campo de Colombia, almacenadas en UTC.
    from zoneinfo import ZoneInfo
    if value.tzinfo is None: value=value.replace(tzinfo=timezone.utc)
    day=value.astimezone(ZoneInfo('America/Bogota')).date().isoformat()
    return (not filters['from_date'] or day>=filters['from_date']) and (not filters['to_date'] or day<=filters['to_date'])

def filtered_records(db,params):
    f=parse_filters(params)
    companies=db.query(Company).all()
    if f['q']:
        term=f['q'].casefold(); companies=[c for c in companies if term in f'{c.name} {c.barrio} {c.code}'.casefold()]
    if f['size']: companies=[c for c in companies if c.size==f['size'] or (f['size']=='Pequeña' and c.size=='Microempresa')]
    if f['activity']: companies=[c for c in companies if c.activity==f['activity']]
    if f['eligibility']: companies=[c for c in companies if c.eligibility_status==f['eligibility']]
    if f['company_id']: companies=[c for c in companies if c.id==int(f['company_id'])]
    ids={c.id for c in companies}
    responses=[r for r in db.query(Response).all() if r.company_id in ids and in_period(r.created_at,f)]
    # Fechas filtran la fecha propia del registro, no excluyen respuestas de empresas antiguas.
    visible_companies=[c for c in companies if in_period(c.created_at,f)]
    key={'name':lambda c:c.name.casefold(),'size':lambda c:c.size,'recent':lambda c:-c.id}.get(f['sort'],lambda c:-c.id)
    visible_companies.sort(key=key)
    return visible_companies,responses,f

def is_valid(response):
    return response.status=='complete' and response.consent_id is not None and response.company.eligible

def distribution(responses,code):
    q=Q_MAP['mercado'][code]
    values=[r.data.get(code) for r in responses]
    if q['kind']=='multi': values=[v for v in values if isinstance(v,list) and v and len(v)==len(set(v)) and all(x in q['choices'] for x in v)]
    elif q['kind']=='select': values=[v for v in values if isinstance(v,str) and v in q['choices']]
    elif q['kind']=='scale': values=[v for v in values if type(v) is int and 1<=v<=5]
    else: values=[v for v in values if v is not None and v!='']
    n=len(values)
    counts=Counter(x for v in values for x in v) if q['kind']=='multi' else Counter(str(v) for v in values)
    return {'code':code,'label':q['label'],'multiple':q['kind']=='multi','unit':'participantes','scope':'surveys','n':n,'rows':[{'label':k,'count':v,'percent':round(100*v/n,1)} for k,v in counts.most_common()]}

def build_analysis(db,companies,responses):
    valid=[r for r in responses if is_valid(r)]
    surveys=[r for r in valid if r.category=='mercado']
    codes=[code for code,q in Q_MAP['mercado'].items() if q['kind'] in ('select','multi','scale')]
    stats={'companies':len(companies),'eligible':sum(c.eligible for c in companies),'pending':sum(c.eligibility_status=='pendiente' for c in companies),'survey':sum(r.category=='mercado' for r in responses),'valid_surveys':len(surveys),'interviews':sum(r.category=='entrevista' for r in valid),'tests':sum(r.category=='prototipo' for r in valid),'drafts':sum(r.status=='draft' for r in responses),'legacy':sum(r.status=='legacy_pending' for r in responses),'progress':db.query(Task).filter_by(completed=True).count(),'tasks':db.query(Task).count()}
    prices=[r.data['M20'] for r in surveys if type(r.data.get('M20')) is int and r.data['M20']>=0]
    distributions={}
    for code,label,values in [('company_size','Tamaño empresarial de las candidatas',[('Pequeña' if c.size=='Microempresa' else c.size) for c in companies]),('company_activity','Actividad económica de las candidatas',[c.activity for c in companies])]:
        n=len(values)
        distributions[code]={'code':code,'label':label,'multiple':False,'scope':'companies','unit':'empresas','n':n,'rows':[{'label':k,'count':v,'percent':round(100*v/n,1)} for k,v in Counter(values).most_common()]}
    distributions.update({code:distribution(surveys,code) for code in codes})
    return {'stats':stats,'distributions':distributions,'sizes':dict(Counter(('Pequeña' if c.size=='Microempresa' else c.size) for c in companies)),'activities':dict(Counter(c.activity for c in companies)),'price':{'n':len(prices),'mean':round(sum(prices)/len(prices),2) if prices else None},'limitations':'Análisis descriptivo. Las distribuciones de candidatas incluyen todas las empresas filtradas. Las de encuestas excluyen borradores, históricos pendientes y empresas no elegibles. Una muestra por conveniencia no permite generalizar a Bucaramanga. En selección múltiple los porcentajes pueden sumar más del 100 %.'}

def query_string(filters): return urlencode({k:v for k,v in filters.items() if v})
