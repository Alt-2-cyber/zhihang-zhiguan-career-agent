@echo off
setlocal EnableExtensions

cd /d "%~dp0"
title Career Agent - Local Launcher

set "ROOT=%CD%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV_PYTHON=%BACKEND%\.venv\Scripts\python.exe"
set "BACKEND_ENV=%BACKEND%\.env"

rem Keep local development independent from Docker-only hostnames in the root .env.
if not exist "%BACKEND_ENV%" (
    > "%BACKEND_ENV%" echo # Local launcher overrides. Shared provider keys remain in the project root .env.
    >> "%BACKEND_ENV%" echo DATABASE_URL=sqlite:///./career.db
    >> "%BACKEND_ENV%" echo STORAGE_BACKEND=local
    >> "%BACKEND_ENV%" echo UPLOAD_DIR=./uploads
    >> "%BACKEND_ENV%" echo CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
    >> "%BACKEND_ENV%" echo EMBEDDING_SERVICE_URL=http://127.0.0.1:8101
    >> "%BACKEND_ENV%" echo OCR_SERVICE_URL=http://127.0.0.1:8102
    >> "%BACKEND_ENV%" echo SPEECH_SERVICE_URL=http://127.0.0.1:8103
    >> "%BACKEND_ENV%" echo EMOTION_SERVICE_URL=http://127.0.0.1:8104
    >> "%BACKEND_ENV%" echo ENABLE_SCHEDULER=false
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$path='%BACKEND_ENV%'; $required=[ordered]@{ 'DATABASE_URL'='sqlite:///./career.db'; 'STORAGE_BACKEND'='local'; 'UPLOAD_DIR'='./uploads'; 'CORS_ORIGINS'='http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080'; 'EMBEDDING_SERVICE_URL'='http://127.0.0.1:8101'; 'OCR_SERVICE_URL'='http://127.0.0.1:8102'; 'SPEECH_SERVICE_URL'='http://127.0.0.1:8103'; 'EMOTION_SERVICE_URL'='http://127.0.0.1:8104'; 'ENABLE_SCHEDULER'='false' }; $lines=Get-Content -LiteralPath $path -ErrorAction SilentlyContinue; foreach ($key in $required.Keys) { $value=$required[$key]; $escaped=[regex]::Escape($key); $matched=$false; $next=@(); foreach ($line in $lines) { if ($line -match ('^[ ]*'+$escaped+'[ ]*=')) { $next += ($key+'='+$value); $matched=$true } else { $next += $line } }; if (-not $matched) { $next += ($key+'='+$value) }; $lines=$next }; Set-Content -LiteralPath $path -Value $lines -Encoding UTF8"
if errorlevel 1 goto :command_failed

echo [1/5] Checking local development tools...
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm was not found. Install Node.js 22 or later and try again.
    goto :failed
)

if not exist "%VENV_PYTHON%" (
    echo [2/5] Creating the Python virtual environment...
    where python >nul 2>&1
    if not errorlevel 1 (
        python -m venv "%BACKEND%\.venv"
    ) else (
        where py >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Python was not found. Install Python 3.13 and try again.
            goto :failed
        )
        py -3 -m venv "%BACKEND%\.venv"
    )
    if errorlevel 1 goto :command_failed
) else (
    echo [2/5] Python virtual environment is ready.
)

pushd "%BACKEND%"
"%VENV_PYTHON%" -c "import alembic, fastapi, sqlalchemy, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [3/5] Installing backend dependencies...
    "%VENV_PYTHON%" -m pip install -e ".[dev]"
    if errorlevel 1 (
        popd
        goto :command_failed
    )
) else (
    echo [3/5] Backend dependencies are ready.
)

echo [4/5] Preparing the local database...
"%VENV_PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    popd
    goto :command_failed
)
"%VENV_PYTHON%" -m app.core.seed
if errorlevel 1 (
    popd
    goto :command_failed
)
popd

pushd "%FRONTEND%"
call npm ls --depth=0 >nul 2>&1
if errorlevel 1 (
    echo [5/5] Installing frontend dependencies...
    call npm ci
    if errorlevel 1 (
        popd
        goto :command_failed
    )
) else (
    echo [5/5] Frontend dependencies are ready.
)
popd

echo.
echo Starting backend and frontend in separate windows...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($response.status -eq 'ok') { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
    echo Backend is already running; using the existing service.
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) { exit 0 }; exit 1" >nul 2>&1
    if not errorlevel 1 (
        echo ERROR: Port 8000 is already used by another application.
        goto :failed
    )
    start "Career Agent Backend" /D "%BACKEND%" cmd /k ""%VENV_PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2; if ($response.StatusCode -eq 200 -and $response.Content -match '/src/main.tsx') { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
    echo Frontend is already running; using the existing service.
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue) { exit 0 }; exit 1" >nul 2>&1
    if not errorlevel 1 (
        echo ERROR: Port 5173 is already used by another application.
        goto :failed
    )
    start "Career Agent Frontend" /D "%FRONTEND%" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"
)

echo Waiting for the application at http://127.0.0.1:5173 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(60); while ((Get-Date) -lt $deadline) { try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 (
    echo WARNING: The browser was not opened because the app did not become ready in 60 seconds.
    echo Check the Backend and Frontend windows for details.
    goto :done
)

start "" "http://127.0.0.1:5173"
echo Application started successfully.
echo Backend API: http://127.0.0.1:8000/api/health
echo Frontend:    http://127.0.0.1:5173

:done
powershell -NoProfile -Command "Start-Sleep -Seconds 3"
exit /b 0

:command_failed
echo.
echo ERROR: A setup command failed. Review the output above.

:failed
echo.
pause
exit /b 1
