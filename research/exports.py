import csv
import io
import os
import textwrap
from datetime import datetime,timezone
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response as Download
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle,KeepTogether,Image as PDFImage
from PIL import Image,ImageDraw,ImageFont
import reportlab
import xlsxwriter
from .models import Company,Response,Task,CanvasVersion,FinancialScenario,ResearchNote,Evidence
from .security import admin,audit
from .web import render
from .analytics import filtered_records,build_analysis,is_valid,query_string
from .finance import calculate_scenario,INPUT_LABELS,FORMULA_LABELS
from .project_routes import CANVAS_BLOCKS
from questions import Q_MAP

router=APIRouter()
FONT_PATH=Path(reportlab.__file__).parent/'fonts'/'Vera.ttf'
pdfmetrics.registerFont(TTFont('ResearchSans',str(FONT_PATH)))

def download(content,filename,mime):
    if os.getenv('APP_ENV')=='review': filename='REVISION_NO_USAR_EN_INVESTIGACION_'+filename
    return Download(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})

def excel_safe(value):
    text='' if value is None else str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text

def response_row(record):
    result={'Respuesta ID':record.id,'Empresa código':record.company.code,'Participante código':record.participant_code or 'Histórico sin código','Tipo':record.category,'Estado':record.status,'Válida para análisis':'Sí' if is_valid(record) else 'No','Fecha UTC':record.created_at.isoformat() if record.created_at else '', 'Investigador':record.author,'Versión instrumento':record.instrument_version or 'Sin revisar'}
    for code,question in Q_MAP.get(record.category,{}).items():
        value=record.data.get(code)
        result[code+' · '+question['label']]=' | '.join(value) if isinstance(value,list) else value
    return result

def company_row(c):
    return {'Código':c.code,'Empresa':c.name,'Barrio':c.barrio,'Municipio':c.city,'Actividad':c.activity,'CIIU':c.ciiu,'Tamaño':c.size,'Verificación':c.verification_status,'Fuente':c.source,'Estado de actividad':c.operating_status,'Registros de ventas e inventarios':c.has_records,'Informante rol':c.respondent_role,'Participación':c.willing,'Elegibilidad':c.eligibility_status,'Investigador':c.owner}

def task_row(t): return {'Objetivo':t.phase,'Actividad':t.title,'Estado':t.status,'Responsable':t.assignee,'Fecha límite':str(t.due_date or ''),'Evidencia':t.evidence}

def workbook_bytes(sheets):
    if os.getenv('APP_ENV')=='review': sheets=[('SOLO REVISION',[{'Advertencia':'SOLO PRUEBAS. Copia de revisión; no incorporar estas cifras a los resultados del proyecto.'}])]+sheets
    output=io.BytesIO(); book=xlsxwriter.Workbook(output,{'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
    head=book.add_format({'bold':True,'bg_color':'#14334B','font_color':'white','text_wrap':True,'valign':'vcenter'})
    for name,rows in sheets:
        sheet=book.add_worksheet(name[:31]); keys=list(dict.fromkeys(key for row in rows for key in row)) or ['Sin registros']
        for j,key in enumerate(keys): sheet.write_string(0,j,key,head); sheet.set_column(j,j,26)
        sheet.set_row(0,48); sheet.freeze_panes(1,0)
        for i,row in enumerate(rows,1):
            for j,key in enumerate(keys):
                value=row.get(key,'')
                if isinstance(value,(int,float)) and not isinstance(value,bool): sheet.write_number(i,j,value)
                else: sheet.write_string(i,j,excel_safe(value))
        if rows: sheet.autofilter(0,0,len(rows),len(keys)-1)
    book.close(); return output.getvalue()

def csv_bytes(rows):
    if os.getenv('APP_ENV')=='review': rows=[{'Origen del archivo':'SOLO PRUEBAS — NO ES INVESTIGACIÓN REAL',**row} for row in rows]
    stream=io.StringIO(); writer=csv.writer(stream)
    keys=list(dict.fromkeys(k for row in rows for k in row)) or ['Sin registros']
    writer.writerow(keys)
    for row in rows: writer.writerow(excel_safe(row.get(k,'')) for k in keys)
    return stream.getvalue().encode('utf-8-sig')

def pdf_styles():
    styles=getSampleStyleSheet()
    for name in ('Normal','Heading1','Heading2','Heading3'):
        styles[name].fontName='ResearchSans'
    styles['Normal'].fontSize=9; styles['Normal'].leading=14
    styles['Heading1'].fontSize=20; styles['Heading1'].leading=26; styles['Heading1'].textColor=colors.HexColor('#14334b')
    styles['Heading2'].spaceBefore=16; styles['Heading2'].spaceAfter=10; styles['Heading2'].fontSize=13
    return styles

def paragraph(value,style): return Paragraph(escape(str(value)).replace('\n','<br/>'),style)
def table(rows,widths,styles):
    body=[[paragraph(value,styles['Normal']) for value in row] for row in rows]
    t=LongTable(body,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF3F4')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#DCE5E9'))]))
    return t

def pdf_document(flow,landscape_page=False):
    output=io.BytesIO(); page=landscape(A4) if landscape_page else A4
    review=os.getenv('APP_ENV')=='review'
    if review: flow=[paragraph('REVISIÓN — DATOS DE PRUEBA. No utilizar como resultado de investigación.',pdf_styles()['Heading2']),Spacer(1,12)]+flow
    def footer(canvas,document):
        canvas.setFont('ResearchSans',8); canvas.setFillColor(colors.HexColor('#627887'))
        canvas.drawString(40,24,'SOLO REVISIÓN · Datos de prueba · No son resultados' if review else 'Datapyme Research Studio · UTS · Uso académico privado')
        canvas.drawRightString(page[0]-40,24,f'Página {document.page}')
    SimpleDocTemplate(output,pagesize=page,leftMargin=40,rightMargin=40,topMargin=40,bottomMargin=44,title='Datapyme Research Studio').build(flow,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()

def chart_png(distribution,filter_text='Todos los registros válidos'):
    if not distribution['n']: raise HTTPException(422,'No hay respuestas válidas para generar este gráfico.')
    width=1800; rows=distribution['rows']; height=240+len(rows)*88
    image=Image.new('RGB',(width,height),'white'); draw=ImageDraw.Draw(image)
    regular=ImageFont.truetype(str(FONT_PATH),24); bold=ImageFont.truetype(str(FONT_PATH),30); small=ImageFont.truetype(str(FONT_PATH),20)
    title_lines=textwrap.wrap(distribution['label'],78)
    for i,line in enumerate(title_lines[:2]): draw.text((45,28+i*38),line,font=bold,fill='#14334B')
    draw.text((45,116),f"n = {distribution['n']} {distribution.get('unit','participantes')} · Frecuencia y porcentaje",font=regular,fill='#496475')
    for index,row in enumerate(rows):
        y=182+index*88
        label_lines=textwrap.wrap(row['label'],42)
        draw.multiline_text((45,y), '\n'.join(label_lines[:2]),font=small,fill='#14334B',spacing=4)
        draw.rounded_rectangle((650,y,1570,y+43),radius=7,fill='#EEF4F6')
        if row['percent']>0: draw.rounded_rectangle((650,y,650+max(1,int(920*row['percent']/100)),y+43),radius=7,fill='#159D8A')
        draw.text((1590,y+8),f"{row['count']} · {row['percent']:.1f}%",font=regular,fill='#14334B')
    note=('Cada empresa candidata cuenta una vez; se incluyen clasificaciones pendientes.' if distribution.get('scope')=='companies' else ('Selección múltiple: los porcentajes pueden sumar más de 100 %.' if distribution['multiple'] else 'Cada participante aporta una respuesta a esta pregunta.'))
    draw.text((45,height-52),note,font=small,fill='#496475')
    draw.text((45,height-27),('Filtros: '+filter_text)[:145],font=small,fill='#496475')
    if os.getenv('APP_ENV')=='review':
        framed=Image.new('RGB',(width,height+56),'white');framed.paste(image,(0,56))
        badge=ImageDraw.Draw(framed);badge.rectangle((0,0,width,56),fill='#FFF2CA')
        badge.text((45,16),'REVISIÓN — DATOS DE PRUEBA · No incorporar al informe de resultados',font=small,fill='#644A0D')
        image=framed
    output=io.BytesIO(); image.save(output,format='PNG',dpi=(180,180)); return output.getvalue()

def report_pdf(analysis,filters):
    styles=pdf_styles(); s=styles; flow=[paragraph('Datapyme Informe descriptivo de investigación',s['Heading1']),paragraph('Corte UTC: '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),s['Normal']),paragraph('Filtros: '+(', '.join(k+'='+v for k,v in filters.items() if v) or 'Sin restricciones'),s['Normal'])]
    facts=[['Indicador','Registros']]+[[label,analysis['stats'][key]] for label,key in [('Empresas registradas','companies'),('Empresas elegibles','eligible'),('Pendientes de verificación','pending'),('Encuestas almacenadas','survey'),('Encuestas válidas','valid_surveys'),('Entrevistas completas válidas','interviews'),('Sesiones de prototipo completas válidas','tests'),('Borradores','drafts'),('Históricos pendientes','legacy')]]
    flow.extend([Spacer(1,16),table(facts,[380,130],s),Spacer(1,14),paragraph(analysis['limitations'],s['Normal'])])
    for code in ('company_size','company_activity','M07','M10','M15','M17','M19','M21'):
        dist=analysis['distributions'][code]
        section=[paragraph(dist['label'],s['Heading2']),paragraph(f"Base del gráfico: n = {dist['n']} {dist.get('unit','participantes')}",s['Normal'])]
        if dist['n']:
            png=chart_png(dist,query_string(filters) or 'Sin restricciones')
            with Image.open(io.BytesIO(png)) as graphic: height=graphic.height
            section.append(PDFImage(io.BytesIO(png),width=510,height=510*height/1800))
            section.append(table([['Respuesta','Frecuencia','% de n']]+[[r['label'],r['count'],str(r['percent'])+' %'] for r in dist['rows']],[325,80,105],s))
        else: section.append(paragraph('Sin observaciones válidas. No se infieren resultados.',s['Normal']))
        flow.append(KeepTogether(section))
    return pdf_document(flow)

def financial_sheets(record):
    result=calculate_scenario(record.inputs)
    return [('Supuestos',[{'Variable':INPUT_LABELS.get(key,key),'Valor':value} for key,value in record.inputs.items()]),('Flujo de caja',[{'Mes':r['month'],'Clientes':r['customers'],'Ingresos COP':float(r['revenue']),'Costos variables COP':float(r['variable']),'Costos fijos COP':float(r['fixed']),'Flujo neto COP':float(r['net']),'Saldo acumulado COP':float(r['balance'])} for r in result['cash_flow']]),('Fórmulas',[{'Indicador':FORMULA_LABELS.get(k,k),'Fórmula':v} for k,v in result['formulas'].items()]),('Indicadores',[{'Contribución COP':result['contribution'],'Clientes de equilibrio':result['break_even_customers'],'Limitaciones':result['limitations']}]),('Fuentes',[{'Escenario':record.name,'Fuente':record.source,'Supuestos':record.assumptions}])]

@router.get('/reportes')
def reports(request:Request):
    admin(request)
    with request.app.state.Session() as db:
        companies,responses,filters=filtered_records(db,request.query_params)
        return render(request,'reports.html',title='Exportar informes',active='reportes',analysis=build_analysis(db,companies,responses),filters=filters,filter_query=query_string(filters))

@router.get('/exportar/grafico/{code}.png')
def png_export(request:Request,code:str):
    user=admin(request)
    with request.app.state.Session() as db:
        companies,responses,filters=filtered_records(db,request.query_params); analysis=build_analysis(db,companies,responses)
        if code not in analysis['distributions']: raise HTTPException(404)
        content=chart_png(analysis['distributions'][code],query_string(filters) or 'Sin restricciones')
        audit(db,user['name'],'exportar','chart',changes={'pregunta':code,'filtros':filters}); db.commit()
        return download(content,'datapyme_'+code+'.png','image/png')

@router.get('/exportar/canvas/{version_id}.pdf')
def canvas_pdf(request:Request,version_id:int):
    admin(request)
    with request.app.state.Session() as db:
        record=db.get(CanvasVersion,version_id)
        if not record: raise HTTPException(404)
        s=pdf_styles(); flow=[paragraph('Datapyme Business Model Canvas',s['Heading1']),paragraph(f'Versión {record.id}: {record.title} · Estado: {record.hypothesis_status}',s['Normal'])]
        for key,label in CANVAS_BLOCKS.items(): flow.extend([paragraph(label,s['Heading2']),paragraph(record.blocks.get(key,''),s['Normal'])])
        flow.extend([paragraph('Evidencia y conclusión',s['Heading2']),paragraph(f'Referencia interna de evidencia: {record.evidence_id or "Sin asociar"}. {record.conclusion}',s['Normal'])])
        return download(pdf_document(flow),'datapyme_canvas_'+str(record.id)+'.pdf','application/pdf')

@router.get('/exportar/finanzas/{scenario_id}.{kind}')
def finance_export(request:Request,scenario_id:int,kind:str):
    admin(request)
    with request.app.state.Session() as db:
        record=db.get(FinancialScenario,scenario_id)
        if not record: raise HTTPException(404)
        sheets=financial_sheets(record)
        if kind=='xlsx': return download(workbook_bytes(sheets),f'datapyme_escenario_{record.id}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        if kind=='pdf':
            s=pdf_styles(); flow=[paragraph('Datapyme Escenario financiero',s['Heading1']),paragraph(record.name,s['Heading2']),paragraph('Fuentes: '+record.source,s['Normal']),paragraph('Supuestos: '+record.assumptions,s['Normal'])]
            for title,rows in sheets:
                if title=='Fuentes': continue
                flow.append(paragraph(title,s['Heading2']))
                if title=='Supuestos': flow.append(table([['Variable','Valor']]+[[r['Variable'],r['Valor']] for r in rows],[350,160],s))
                elif title=='Flujo de caja': flow.append(table([['Mes','Clientes','Ingresos COP','Flujo neto COP','Saldo COP']]+[[r['Mes'],r['Clientes'],r['Ingresos COP'],r['Flujo neto COP'],r['Saldo acumulado COP']] for r in rows],[40,55,135,135,145],s))
                else:
                    for row in rows: flow.append(paragraph(' · '.join(k+': '+str(v) for k,v in row.items()),s['Normal']))
            return download(pdf_document(flow),f'datapyme_escenario_{record.id}.pdf','application/pdf')
        raise HTTPException(404)

@router.get('/exportar/{kind}')
def export(request:Request,kind:str):
    user=admin(request)
    with request.app.state.Session() as db:
        companies,responses,filters=filtered_records(db,request.query_params); analysis=build_analysis(db,companies,responses)
        if kind=='pdf': content=report_pdf(analysis,filters); filename='datapyme_informe.pdf'; mime='application/pdf'
        elif kind=='xlsx':
            sheets=[('Empresas',[company_row(c) for c in companies])]+[(category.title(),[response_row(r) for r in responses if r.category==category]) for category in Q_MAP]
            sheets+=[('Actividades',[task_row(t) for t in db.query(Task).all()]),('Análisis',[{'Pregunta':d['label'],'n válido':d['n'],'Unidad':d['unit'],'Opción':row['label'],'Frecuencia':row['count'],'% de n':row['percent']} for d in analysis['distributions'].values() for row in d['rows']]),('Contexto',[{'Corte UTC':datetime.now(timezone.utc).isoformat(),'Filtros':query_string(filters),'Limitaciones':analysis['limitations']}]),('Canvas',[{'Versión':c.id,'Título':c.title,'Estado':c.hypothesis_status,'Conclusión':c.conclusion,**{CANVAS_BLOCKS[k]:v for k,v in c.blocks.items()}} for c in db.query(CanvasVersion)]),('Escenarios',[{'ID':r.id,'Nombre':r.name,'Fuente':r.source,'Supuestos':r.assumptions,**{INPUT_LABELS.get(k,k):v for k,v in r.inputs.items()}} for r in db.query(FinancialScenario)]),('Estudios y fuentes',[{'Tipo':n.kind,'Título':n.title,'Contenido':n.content,'Fuente':n.source} for n in db.query(ResearchNote)])]
            content=workbook_bytes(sheets); filename='datapyme_investigacion.xlsx'; mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif kind in ('empresas','mercado','entrevista','prototipo','actividades'):
            rows=[company_row(c) for c in companies] if kind=='empresas' else ([task_row(t) for t in db.query(Task)] if kind=='actividades' else [response_row(r) for r in responses if r.category==kind])
            content=csv_bytes(rows); filename='datapyme_'+kind+'.csv'; mime='text/csv; charset=utf-8'
        else: raise HTTPException(404)
        audit(db,user['name'],'exportar','dataset',changes={'tipo':kind,'filtros':filters}); db.commit()
        return download(content,filename,mime)
