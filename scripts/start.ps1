param([int]$Port=8000,[switch]$NoBrowser)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$localPython=Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $localPython)) { throw 'Crea .venv e instala requirements.txt siguiendo el README.' }
try {
    $studioStatus=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/ready" -TimeoutSec 2
    if ($studioStatus.status -eq 'ok' -and $studioStatus.schema -eq '20261022_01') {
        Write-Output "Datapyme ya esta disponible en http://127.0.0.1:$Port"
        if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
        exit 0
    }
} catch { }
& $localPython manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$studioLocal=Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Force -Path $studioLocal | Out-Null
$studioProcess=Start-Process -FilePath $localPython -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $studioLocal 'server-out.log') -RedirectStandardError (Join-Path $studioLocal 'server-error.log') -PassThru
$studioProcess.Id | Set-Content -LiteralPath (Join-Path $studioLocal 'server.pid')
for ($studioAttempt=0;$studioAttempt -lt 20;$studioAttempt++) {
    try {
        $studioStatus=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/ready" -TimeoutSec 2
        if ($studioStatus.status -eq 'ok') {
            Write-Output "Datapyme esta disponible en http://127.0.0.1:$Port"
            if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 1
}
throw 'No se confirmo el inicio. Consultar .local/server-error.log.'
