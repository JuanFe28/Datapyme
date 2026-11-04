FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home studio
COPY --chown=studio:studio . .
USER studio
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; req=urllib.request.Request('http://127.0.0.1:'+os.getenv('PORT','8000')+'/ready',headers={'Host':os.getenv('ALLOWED_HOSTS','127.0.0.1').split(',')[0]}); urllib.request.urlopen(req,timeout=4)"
CMD ["sh","-c","exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
