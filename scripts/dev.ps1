param(
  [int]$BackendPort = 5001,
  [int]$StreamlitPort = 8501,
  [int]$NextPort = 3000,
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($msg) {
  Write-Host "[dev] $msg"
}

if (-not (Test-Path $ProjectRoot)) {
  throw "ProjectRoot não existe: $ProjectRoot"
}

Set-Location $ProjectRoot
Info "Projeto: $ProjectRoot"

if (-not (Test-Path "venv")) {
  Info "Criando venv..."
  python -m venv venv
}

Info "Ativando venv..."
& "$ProjectRoot\venv\Scripts\Activate.ps1"

Info "Instalando deps Python (backend + Streamlit)..."
pip install fastapi uvicorn pandas numpy
pip install -r requirements.txt

if (-not (Test-Path "node_modules")) {
  Info "Instalando deps Node..."
  npm i
}

if (-not (Test-Path ".streamlit")) {
  New-Item -ItemType Directory -Path ".streamlit" | Out-Null
}

if (-not (Test-Path ".streamlit\secrets.toml")) {
  Info "Criando .streamlit\secrets.toml..."
  @"
BACKEND_URL = "http://localhost:$BackendPort"
"@ | Set-Content -Path ".streamlit\secrets.toml" -Encoding UTF8
}

if (-not (Test-Path ".env.local") -and -not (Test-Path "src\.env.local")) {
  Info "Criando .env.local..."
  @"
PY_BACKEND_URL=http://localhost:$BackendPort
"@ | Set-Content -Path ".env.local" -Encoding UTF8
}

Info "Iniciando backend FastAPI..."
Start-Process -WorkingDirectory $ProjectRoot -WindowStyle Normal -FilePath "uvicorn" -ArgumentList "backend.main:app --reload --port $BackendPort"

Info "Iniciando Streamlit..."
Start-Process -WorkingDirectory $ProjectRoot -WindowStyle Normal -FilePath "streamlit" -ArgumentList "run app.py --server.port $StreamlitPort"

Info "Iniciando Next dev server..."
Start-Process -WorkingDirectory $ProjectRoot -WindowStyle Normal -FilePath "npm" -ArgumentList "run dev -- --port $NextPort"

Info "URLs:"
Info "Backend:   http://localhost:$BackendPort/"
Info "Streamlit: http://localhost:$StreamlitPort/"
Info "Next:      http://localhost:$NextPort/"
