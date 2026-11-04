"""Empaquetar únicamente código y documentación; excluir datos y secretos."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib

ROOT=Path(__file__).resolve().parents[1]
FILES=['app.py','questions.py','manage.py','README.md','requirements.txt','requirements-dev.txt','constraints.txt','alembic.ini','pytest.ini','.python-version','Procfile','render.yaml','Dockerfile','.dockerignore','.gitignore','.env.example','INICIAR_DATAPYME.cmd','REVISAR_POR_INTERNET.cmd','DETENER_REVISION.cmd']
DIRS=['research','migrations','templates','static','scripts','tests','docs','.github']

def main():
    output=ROOT/'dist'; output.mkdir(exist_ok=True)
    archive=output/'datapyme-research-studio.zip'
    paths=[ROOT/name for name in FILES if (ROOT/name).is_file()]
    for directory in DIRS:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.db','.sqlite','.dump') and p.name!='.env')
    with ZipFile(archive,'w',ZIP_DEFLATED) as package:
        for path in sorted(set(paths)): package.write(path,path.relative_to(ROOT).as_posix())
    with archive.open('rb') as source: digest=hashlib.file_digest(source,'sha256').hexdigest()
    (output/'SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(f'Entrega: {archive.name} · {len(set(paths))} archivos · SHA-256 {digest}')

if __name__=='__main__': main()
