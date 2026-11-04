from fastapi import HTTPException
from questions import Q_MAP

VERSION='2026-10-22.1'
CONSENT_STATEMENT='Participación voluntaria para el Plan de Negocios Datapyme UTS; se informó propósito, uso académico, confidencialidad, posibilidad de no responder y retiro mediante el equipo investigador. No se solicitan datos sensibles.'
EXCLUSIVE={'M07':['No hay registro organizado'],'M08':['No lleva control sistemático'],'M10':['No enfrenta dificultades relevantes'],'M15':['Ninguno']}

# Delimitación poblacional F-DC-124 (Sarmiento Suárez et al., 2024; Taborda Blandón et al., 2024):
# El estudio se orienta a mipymes comerciales en Bucaramanga. Los microcomercios autocalificados
# se homologan dentro del segmento 'Pequeña' para evitar exclusión inadvertida.
TARGET_COMPANY_SIZES = ('Pequeña', 'Mediana', 'Microempresa')

def normalize_company_size(size: str) -> str:
    s = (size or '').strip()
    return 'Pequeña' if s == 'Microempresa' else s

def applicable(category,code,values):
    if category=='mercado' and code=='M14': return values.get('M13')=='Sí'
    if category=='mercado' and code=='M20': return values.get('M19') in ('Suscripción mensual','Suscripción anual')
    if category=='prototipo' and code=='V11': return values.get('V10')=='Sí'
    return True

def validate_answers(category,form,complete):
    result={}; errors={}
    for code,q in Q_MAP[category].items():
        if not applicable(category,code,form):
            result[code]=None if q['kind']=='number' else ''; continue
        value=form.getlist(code) if q['kind']=='multi' else str(form.get(code,'')).strip()
        required=q['required'] or (category=='mercado' and code=='M14') or (category=='prototipo' and code=='V11')
        if complete and required and not value: errors[code]='Completa esta respuesta.'
        if q['kind'] in ('select','multi'):
            selected=value if isinstance(value,list) else ([value] if value else [])
            if any(x not in q['choices'] for x in selected): errors[code]='Selecciona una opción permitida.'
            if len(set(selected))!=len(selected): errors[code]='No repitas opciones.'
            if q['maximum'] and len(selected)>q['maximum']: errors[code]=f'Máximo {q["maximum"]} opciones.'
            if len(selected)>1 and any(x in selected for x in EXCLUSIVE.get(code,[])): errors[code]='La opción de ausencia de dificultades no se combina con otras.'
        if q['kind']=='scale' and value:
            if value not in ('1','2','3','4','5'): errors[code]='Selecciona un valor entre 1 y 5.'
            else: value=int(value)
        if q['kind']=='number':
            if value:
                if not str(value).isdigit() or len(value)>12: errors[code]='Usa un entero positivo en COP, sin separadores.'
                else: value=int(value)
            else: value=None
        if isinstance(value,str) and len(value)>4000: errors[code]='Máximo 4000 caracteres.'
        result[code]=value
    return result,errors
