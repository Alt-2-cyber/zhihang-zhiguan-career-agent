param(
    [switch]$SkipContainers
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$ruff = Join-Path $backend ".venv\Scripts\ruff.exe"

if (-not (Test-Path $python)) {
    throw "Backend virtual environment is missing. Run: cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[dev]'"
}

Push-Location $backend
try {
    & $ruff check app tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Push-Location $frontend
try {
    npm run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm test -- --run
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

if (-not $SkipContainers) {
    Push-Location $root
    try {
        docker compose up --build -d
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $ready = $false
        for ($attempt = 0; $attempt -lt 36; $attempt++) {
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8080" -UseBasicParsing -TimeoutSec 3
                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            }
            catch {
                Start-Sleep -Seconds 5
            }
        }
        if (-not $ready) {
            docker compose ps
            docker compose logs --tail 100
            throw "Container smoke test did not become ready within 180 seconds."
        }
        Push-Location $frontend
        try {
            $env:E2E_BASE_URL = "http://localhost:8080"
            npm run e2e
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        finally {
            Remove-Item Env:E2E_BASE_URL -ErrorAction SilentlyContinue
            Pop-Location
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "All configured verification checks passed."
