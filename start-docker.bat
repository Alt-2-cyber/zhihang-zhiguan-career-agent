@echo off
setlocal EnableExtensions

cd /d "%~dp0"
title Career Agent - Docker Launcher

echo [1/4] Checking Docker...
where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker was not found. Install and start Docker Desktop, then try again.
    goto :failed
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose is unavailable. Update Docker Desktop and try again.
    goto :failed
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: The Docker engine is not running. Start Docker Desktop and try again.
    goto :failed
)

if not exist ".env" (
    echo [2/4] Creating .env from .env.example...
    copy /Y ".env.example" ".env" >nul
    if errorlevel 1 goto :command_failed
) else (
    echo [2/4] Existing .env will be used.
)

echo [3/4] Building and starting containers...
docker compose up --build -d
if errorlevel 1 goto :docker_failed

echo [4/4] Waiting for container health checks...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(180); while ((Get-Date) -lt $deadline) { try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080' -TimeoutSec 3; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 5 }; exit 1"
if errorlevel 1 goto :health_failed

docker compose ps
start "" "http://127.0.0.1:8080"
echo.
echo Docker application started successfully: http://127.0.0.1:8080
echo To stop it, run: docker compose down
powershell -NoProfile -Command "Start-Sleep -Seconds 5"
exit /b 0

:health_failed
echo.
echo ERROR: The application did not become ready in 180 seconds.
docker compose ps
docker compose logs --tail 100
goto :failed

:docker_failed
echo.
echo ERROR: Docker Compose could not start the application.
docker compose ps
docker compose logs --tail 100
goto :failed

:command_failed
echo.
echo ERROR: A setup command failed. Review the output above.

:failed
echo.
pause
exit /b 1
