import io
from pathlib import PurePath
from zipfile import ZipFile, BadZipFile
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException

MIMES={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.txt':'text/plain; charset=utf-8','.csv':'text/csv; charset=utf-8','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}

def validate_file(filename,content,max_size):
    filename=PurePath(filename.replace('\\','/')).name
    suffix=PurePath(filename).suffix.lower()
    if suffix not in MIMES or not filename or len(filename)>180: raise HTTPException(422,'Formato no autorizado. Usa PDF, PNG, JPEG, TXT, CSV, DOCX o XLSX.')
    if not content or len(content)>max_size: raise HTTPException(413,'El archivo debe contener datos y pesar como máximo 10 MiB.')
    try:
        if suffix=='.pdf':
            if not content.startswith(b'%PDF-') or b'%%EOF' not in content[-2048:]: raise ValueError()
        elif suffix in ('.png','.jpg','.jpeg'):
            with Image.open(io.BytesIO(content)) as image:
                if image.format != ('PNG' if suffix=='.png' else 'JPEG') or image.width*image.height>20_000_000: raise ValueError()
                image.verify()
        elif suffix in ('.docx','.xlsx'):
            with ZipFile(io.BytesIO(content)) as archive:
                infos=archive.infolist()
                if len(infos)>2000 or sum(x.file_size for x in infos)>40*1024*1024: raise ValueError()
                if any(x.flag_bits&1 or '..' in PurePath(x.filename).parts or x.filename.startswith(('/','\\')) or 'vbaproject' in x.filename.lower() for x in infos): raise ValueError()
                required='word/document.xml' if suffix=='.docx' else 'xl/workbook.xml'
                if required not in archive.namelist() or '[Content_Types].xml' not in archive.namelist(): raise ValueError()
                if archive.testzip(): raise ValueError()
        else:
            decoded=content.decode('utf-8-sig')
            if '\x00' in decoded: raise ValueError()
    except (ValueError,UnicodeDecodeError,BadZipFile,UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'El contenido del archivo no corresponde al formato permitido o no es legible.')
    return filename,MIMES[suffix]
