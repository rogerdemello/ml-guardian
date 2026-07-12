# ML Guardian - one command runs backend + frontend (Windows PowerShell).
# Creates a venv, installs deps, opens the dashboard, and serves everything at :8000.
$ErrorActionPreference = "Stop"
$Port = 8000

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example (offline fixture mode, no keys required)."
}

# Open the dashboard once the server is up.
$url = "http://localhost:$Port"
Start-Job { Start-Sleep 3; Start-Process $using:url } | Out-Null

Write-Host "`nML Guardian running at http://localhost:$Port  (Ctrl+C to stop)`n"
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port $Port
