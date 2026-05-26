# SmartPark Web — Start backend + frontend
$root = Split-Path -Parent $PSScriptRoot

Write-Host "`n SmartPark MQTT Web UI" -ForegroundColor Cyan
Write-Host " ─────────────────────────────────────" -ForegroundColor DarkGray
Write-Host " Backend  →  http://localhost:8000" -ForegroundColor Green
Write-Host " Frontend →  http://localhost:5173" -ForegroundColor Green
Write-Host " ─────────────────────────────────────`n" -ForegroundColor DarkGray

# Start FastAPI backend in background
$backend = Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "web.backend.main:app", "--reload", "--port", "8000" `
    -WorkingDirectory $root `
    -PassThru -NoNewWindow

Write-Host " [1/2] Backend started (PID $($backend.Id))" -ForegroundColor Green

# Start Vite frontend
Set-Location "$PSScriptRoot\frontend"
Write-Host " [2/2] Starting frontend..." -ForegroundColor Green
npm run dev
