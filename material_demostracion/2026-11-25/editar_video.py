"""Montaje reproducible de las fuentes de demostración, sin voz ni datos nuevos."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / '2026-11-24' / 'EDICION' / 'completo'
CHAPTERS = [
 ('El negocio, en una sola vista',14,['Inventario, ventas e indicadores conectados en una misma aplicación.','Recorrido de una ferretería con datos sintéticos de demostración.']),
 ('Acceso y primeros pasos',24,['La cuenta de la empresa permite entrar a su espacio de trabajo.','Una clave temporal se cambia por una contraseña privada al activar la cuenta.','El recorrido guiado ayuda a ubicar Inventarios, Ventas, Proyección y Mis Datos.']),
 ('Preparar la información',30,['Revise códigos, unidades, costos, precios y existencias antes de operar.','La condición de IVA de la empresa y la tarifa del artículo afectan el cálculo.','Confirme esos datos antes de registrar operaciones reales.']),
 ('Inventario bajo control',38,['Registre el producto con su código, unidad, costo, precio y cantidad inicial.','Ejemplo del catálogo: base $10.000 + IVA $1.900 = precio final $11.900.','Revise la vista previa y compruebe que el producto quedó en el catálogo.','Para corregir cantidades físicas, registre un ajuste con su motivo.']),
 ('Una venta, de principio a fin',50,['Seleccione el producto, confirme la cantidad y el medio de pago.','Ejemplo: base $115.000 + IVA $21.850 = total a cobrar $136.850.','Después de confirmar, revise el comprobante y las existencias.','En el ejemplo se vende un par: el inventario pasa de 12 a 11 pares.','Base $115.000 − costo $78.000 = utilidad bruta $37.000.','El comprobante es un registro interno; no sustituye una factura electrónica DIAN.']),
 ('Validar y corregir',30,['Una cantidad superior a las existencias bloquea la confirmación.','Corrija y revise el total antes de continuar con la operación.','La anulación del ejemplo devuelve el par al inventario: de 11 a 12.','Si se pierde la conexión, revise el historial antes de repetir la venta.']),
 ('Importar con revisión previa',40,['Revise el archivo de Excel antes de guardar información en el catálogo.','Compruebe las columnas, códigos, unidades, costos, precios y cantidades.','Si aparece un dato inválido, corríjalo en el archivo y vuelva a revisarlo.','Las ventas actuales descuentan existencias; el historial conserva operaciones anteriores.','Elija el tipo de importación adecuado y verifique el resultado final.']),
 ('Indicadores que se pueden explicar',32,['Seleccione el periodo y revise los ingresos sin IVA y la utilidad bruta.','La utilidad bruta todavía no descuenta arriendo, servicios ni otros gastos.','Consulte el inventario al costo y los artículos con poco movimiento.','Estos indicadores apoyan la revisión del negocio; no garantizan mejoras económicas.']),
 ('Proyectar sin crear falsas expectativas',30,['La proyección necesita al menos tres meses completos y consecutivos con datos suficientes.','Una cuenta nueva muestra datos insuficientes hasta contar con ese historial.','El ajuste estadístico describe el pasado; no garantiza las ventas futuras.']),
 ('Cuenta y cuidado de la información',24,['La persona propietaria entra al espacio de su comercio; la administración es un acceso aparte.','Mis Datos permite revisar opciones de seguridad y exportar información.','Proteja las copias exportadas y cierre sesión cuando use un equipo compartido.']),
 ('Continuidad desde el celular',24,['La interfaz móvil permite recorrer las secciones principales desde el navegador.','Antes de operar, pruebe con pocos productos y una venta de demostración.','Compare importes y existencias con sus registros en el dispositivo que utilizará.']),
 ('Qué proponemos revisar juntos',14,['Revisar la claridad de los datos, la utilidad de los indicadores y el flujo de trabajo.','Identificar mejoras con profesionales antes de incorporar información de empresas.']),
]
SHORT = [
 ('Una vista compartida del negocio',12,['Inventario, ventas e indicadores conectados para revisar el comercio.','Pantallas de la aplicación con datos sintéticos de demostración.']),
 ('Del producto al registro de venta',18,['Organice el catálogo y revise cantidades, precios e IVA antes de confirmar.','Consulte el comprobante y compruebe el cambio de existencias.']),
 ('Información para revisar decisiones',20,['Consulte ingresos sin IVA, utilidad bruta e inventario al costo.','La utilidad bruta no equivale a la ganancia neta del negocio.','Una proyección necesita historial suficiente y no garantiza ventas futuras.']),
 ('Empezar con una prueba controlada',15,['Active su cuenta y recorra las funciones con datos de práctica.','Revise el archivo importado y contraste los resultados antes de operar.']),
 ('Una revisión con profesionales',10,['Evaluemos claridad, utilidad y flujo de trabajo antes de incorporar datos de empresas.']),
]

def stamp(seconds, srt=False):
    ms=round(seconds*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02}{"," if srt else "."}{ms:03}'

def run(ff,args):
    subprocess.run([ff,'-hide_banner','-loglevel','error','-y',*args],check=True,cwd=HERE)

def card(title,lines,path):
    im=Image.new('RGB',(1920,1080),'#092c36'); d=ImageDraw.Draw(im)
    fonts='C:/Windows/Fonts/'
    d.rounded_rectangle((100,105,1820,975),radius=32,fill='#103c46',outline='#257a80',width=2)
    d.text((170,165),'DATAPYME',font=ImageFont.truetype(fonts+'segoeuib.ttf',36),fill='#64dfcb')
    y=300
    for line in textwrap.wrap(title,38):
        d.text((170,y),line,font=ImageFont.truetype(fonts+'segoeuib.ttf',64),fill='white'); y+=90
    y+=35
    for line in lines:
        d.text((170,y),line,font=ImageFont.truetype(fonts+'segoeui.ttf',32),fill='#d3e6e9'); y+=62
    d.text((170,875),'DEMOSTRACIÓN DEL PROTOTIPO · DATOS SINTÉTICOS',font=ImageFont.truetype(fonts+'segoeuib.ttf',24),fill='#64dfcb')
    im.save(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--ffmpeg',required=True);p.add_argument('--resumen',action='store_true');a=p.parse_args()
    chapters=SHORT if a.resumen else CHAPTERS
    source=SOURCE.parent/'breve' if a.resumen else SOURCE
    name='DATAPYME_RESUMEN_PROFESIONAL' if a.resumen else 'DATAPYME_PRESENTACION_PROFESIONAL'
    suffix='_RESUMEN' if a.resumen else ''
    work=HERE/('trabajo_resumen' if a.resumen else 'trabajo');work.mkdir(exist_ok=True)
    out=HERE/(name+'_1080P.mp4')
    total=8+sum(c[1] for c in chapters)+12
    cursor=8; cues=[]; manifest=[]; parts=[]; subtitle_lines=[]
    intro=work/'intro.png'; outro=work/'cierre.png'
    card('Del registro a la decisión',['Inventario · ventas · indicadores para revisar el negocio','Presentación para revisión con profesionales'],intro)
    card('Revisemos su utilidad en la práctica',['Claridad de la información · flujo de trabajo · mejoras por priorizar','Alvino Camacho Bonna · Juan Felipe','Demostración académica; validación con empresas pendiente.'],outro)
    for card_name,duration,img in [('intro',8,intro),('cierre',12,outro)]:
        dest=work/f'{card_name}.mp4'
        run(a.ffmpeg,['-loop','1','-i',str(img),'-t',str(duration),'-vf','fps=25,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','19','-an',str(dest)])
    parts.append(work/'intro.mp4')
    for i,(title,duration,texts) in enumerate(chapters,1):
        src=source/f'{i:02}.mp4'; dest=work/f'{i:02}.mp4'
        # Los encabezados/pies del montaje anterior se reemplazan fuera del área de la aplicación.
        import cv2
        capture=cv2.VideoCapture(str(src)); old=capture.get(cv2.CAP_PROP_FRAME_COUNT)/capture.get(cv2.CAP_PROP_FPS); capture.release()
        header=work/f'titulo-{i}.txt'; header.write_text(title,encoding='utf-8')
        ass=work/f'{i:02}.ass'
        head='[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Segoe UI,34,&H00FFFFFF,&H00FFFFFF,&H0020190C,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,100,100,30,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
        def ass_time(t):
            return stamp(t)[:-1].lstrip('0') if t>=3600 else f'0:{int(t)//60:02}:{t%60:05.2f}'
        # Duración proporcional al texto: frases completas y un máximo de 17 caracteres/s.
        weights=[len(t) for t in texts]; unit=(duration-1)/sum(weights); local=.3
        for text,w in zip(texts,weights):
            end=local+w*unit
            assert len(text)/(end-local)<=17.5
            wrapped=r'\N'.join(textwrap.wrap(text,92))
            head+=f'Dialogue: 0,{ass_time(local)},{ass_time(end)},Default,,0,0,0,,{wrapped}\n'
            subtitle_lines.append(f'{len(subtitle_lines)+1}\n{stamp(cursor+local,True)} --> {stamp(cursor+end,True)}\n'+ '\n'.join(textwrap.wrap(text,82))+'\n')
            cues.append({'chapter':i,'start':round(cursor+local,3),'end':round(cursor+end,3),'text':text,'cps':round(len(text)/(end-local),2)})
            local=end
        ass.write_text(head,encoding='utf-8')
        # Usar rutas relativas para que libass no interprete el ':' de Windows.
        relass=f'{work.name}/{i:02}.ass'; reltitle=f'{work.name}/titulo-{i}.txt'
        vf=(f'setpts={duration/old:.9f}*PTS,fps=25,'
            'drawbox=x=0:y=0:w=iw:h=108:color=0x092c36:t=fill,'
            'drawbox=x=0:y=930:w=iw:h=150:color=0x092c36:t=fill,'
            "drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='DATAPYME':x=42:y=16:fontsize=22:fontcolor=0x64dfcb,"
            f"drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':textfile='{reltitle}':x=42:y=48:fontsize=33:fontcolor=white,"
            f"drawtext=fontfile='C\\:/Windows/Fonts/segoeui.ttf':text='{i:02} / {len(chapters)}   DATOS DE DEMOSTRACIÓN':x=w-tw-42:y=38:fontsize=22:fontcolor=0xbedde2,"
            f"drawbox=x=0:y=105:w={round(1920*i/len(chapters))}:h=3:color=0x64dfcb:t=fill,ass='{relass}',format=yuv420p")
        run(a.ffmpeg,['-i',str(src),'-vf',vf,'-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','19','-an',str(dest)])
        manifest.append({'chapter':i,'title':title,'source':str(src.relative_to(HERE.parent)),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_duration':old,'start':cursor,'duration':duration})
        parts.append(dest);cursor+=duration
        print(f'Capítulo {i}/{len(chapters)} listo',flush=True)
    parts.append(work/'cierre.mp4')
    concat=work/'montaje.ffconcat';concat.write_text('ffconcat version 1.0\n'+''.join(f"file '{p.name}'\n" for p in parts),encoding='utf-8')
    joined=work/'montaje.mp4'
    run(a.ffmpeg,['-safe','0','-f','concat','-i',str(concat),'-c','copy',str(joined)])
    metadata=work/'capitulos.ffmetadata'
    entries=[(0,8,'Presentación')]+[(m['start'],m['start']+m['duration'],m['title']) for m in manifest]+[(cursor,total,'Revisión con profesionales')]
    metadata.write_text(';FFMETADATA1\n'+''.join(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={start*1000}\nEND={end*1000}\ntitle={title}\n' for start,end,title in entries),encoding='utf-8')
    run(a.ffmpeg,['-i',str(joined),'-f','ffmetadata','-i',str(metadata),'-map','0:v:0','-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',str(out)])
    (HERE/(name+'.srt')).write_text('\n'.join(subtitle_lines),encoding='utf-8')
    (HERE/('CAPITULOS'+suffix+'.txt')).write_text('00:00:00 Presentación\n'+'\n'.join(stamp(m['start']).split('.')[0]+' '+m['title'] for m in manifest)+'\n'+stamp(cursor).split('.')[0]+' Revisión con profesionales\n',encoding='utf-8')
    (HERE/('MONTAJE'+suffix+'.json')).write_text(json.dumps({'source_revision':'a95aac66825bfab5334c5843eb57ce07b1758fab','duration':total,'chapters':manifest,'subtitles':cues,'audio':False},ensure_ascii=False,indent=2),encoding='utf-8')
    print(out,flush=True)

if __name__=='__main__': main()
