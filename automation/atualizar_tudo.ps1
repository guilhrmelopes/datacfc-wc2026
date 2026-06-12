#Requires -Version 5.1
<#
.SYNOPSIS
  Atualiza todos os dados do dashboard: Copa (FotMob), status/fotos, odds — e faz deploy.

.DESCRIPTION
  Ordem: git pull → pipeline Copa → status jogadores → odds → commit único → push (Vercel).

  Uso manual:
    powershell -ExecutionPolicy Bypass -File automation\atualizar_tudo.ps1

  Agendar (uma vez):
    powershell -ExecutionPolicy Bypass -File automation\registrar_agenda_completa.ps1
#>

param(
    [switch]$SkipOdds,
    [switch]$SkipPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogDir = Join-Path $Raiz "logs\atualizar_tudo"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("{0:yyyy-MM-dd_HH-mm-ss}.log" -f (Get-Date))

$ArquivosCommit = @(
    "frontend/public/data/copa_estado.json",
    "frontend/public/data/grupos_wc2026.json",
    "frontend/public/data/classificacao_grupos.json",
    "frontend/public/data/pontuacao_cedida.json",
    "frontend/public/data/selecoes.json",
    "frontend/public/data/jogadores_mercado.json",
    "frontend/public/data/odds_jogadores.json",
    "frontend/public/data/eventos_odds_rodada1.json"
)

function Write-Log {
    param([string]$Message)
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Invoke-Git {
    param([string[]]$Args)
    Push-Location $Raiz
    try {
        & git @Args
        if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') falhou (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}

function Find-Python {
    foreach ($cmd in @("py -3", "py -3.12", "python")) {
        $parts = $cmd -split " "
        $exe = $parts[0]
        $pyArgs = @()
        if ($parts.Length -gt 1) { $pyArgs = $parts[1..($parts.Length - 1)] }
        try {
            & $exe @pyArgs -c "import sys; print(sys.executable)" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return @{ Exe = $exe; Args = $pyArgs } }
        } catch { }
    }
    throw "Python não encontrado. Instale Python 3.12+."
}

function Invoke-PythonScript {
    param(
        [string]$Python,
        [string]$Script,
        [hashtable]$ExtraEnv = @{}
    )
    $env:PYTHONPATH = Join-Path $Raiz "src"
    foreach ($k in $ExtraEnv.Keys) { Set-Item -Path "env:$k" -Value $ExtraEnv[$k] }
    $out = & $Python $Script 2>&1
    $exit = $LASTEXITCODE
    $out | ForEach-Object { Write-Log "$_" }
    if ($exit -ne 0) { throw "Script falhou: $Script (exit $exit)" }
}

try {
    Write-Log "=== Início atualização completa ==="
    Write-Log "Repo: $Raiz"

    $py = Find-Python
    $venv = Join-Path $Raiz ".venv\Scripts\python.exe"
    if (Test-Path $venv) {
        $python = $venv
        Write-Log "Usando venv: $python"
    } else {
        $python = & $py.Exe @($py.Args + @("-c", "import sys; print(sys.executable)"))
        Write-Log "Usando Python: $python"
    }

    Write-Log "git pull --rebase"
    Invoke-Git @("pull", "--rebase", "--autostash")

    Write-Log "--- [1/3] Pipeline Copa (FotMob) ---"
    Invoke-PythonScript -Python $python -Script (Join-Path $Raiz "automation\atualizar_copa_fotmob.py")

    Write-Log "--- [2/3] Status e fotos dos jogadores ---"
    Invoke-PythonScript -Python $python -Script (Join-Path $Raiz "automation\atualizar_status_jogadores.py")

    if (-not $SkipOdds) {
        Write-Log "--- [3/3] Odds GA% / SG% ---"
        $req = Join-Path $Raiz "requirements-odds.txt"
        Write-Log "pip install -r requirements-odds.txt"
        & $python -m pip install -q -r $req
        if ($LASTEXITCODE -ne 0) { throw "pip install falhou" }

        $playwrightMarker = Join-Path $Raiz ".playwright\chromium_installed"
        if (-not (Test-Path $playwrightMarker)) {
            Write-Log "playwright install chromium (primeira execução)"
            & $python -m playwright install chromium
            if ($LASTEXITCODE -ne 0) { throw "playwright install falhou" }
            New-Item -ItemType File -Force -Path $playwrightMarker | Out-Null
        }

        $env:PYTHONPATH = $Raiz
        $env:ODDS_MERGE = "1"
        $env:ODDS_SKIP_WARMUP = "1"
        $env:ODDSNOTIFIER_HEADLESS = "true"

        $scrapeOut = & $python -m src.scrapers.scraper_odds_jogadores 2>&1
        $scrapeExit = $LASTEXITCODE
        $scrapeOut | ForEach-Object { Write-Log "$_" }

        $validOut = & $python (Join-Path $Raiz "automation\validar_odds.py") 2>&1
        $validExit = $LASTEXITCODE
        $validOut | ForEach-Object { Write-Log "$_" }
        if ($validExit -ne 0) {
            throw "Validação de odds falhou (scrape exit=$scrapeExit) — commit abortado"
        }
        if ($scrapeExit -ne 0) {
            Write-Log "AVISO: scraper de odds exit $scrapeExit, mas validação OK."
        }
    } else {
        Write-Log "--- [3/3] Odds ignoradas (-SkipOdds) ---"
    }

    if ($SkipPush) {
        Write-Log "SkipPush — alterações locais apenas, sem commit."
        Write-Log "=== Concluído (sem deploy) ==="
        exit 0
    }

    Push-Location $Raiz
    try {
        git add @ArquivosCommit
        git diff --cached --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Nenhuma mudança para commitar."
        } else {
            $msg = @"
bot: atualizar Copa, scouts, pontuações e odds [skip ci]

Pipeline FotMob (classificação, hub, cedido/conquistado), status Cartola e odds GA%/SG%.
"@
            git commit -m $msg
            if ($LASTEXITCODE -ne 0) { throw "git commit falhou" }
            Write-Log "git push"
            git push
            if ($LASTEXITCODE -ne 0) { throw "git push falhou" }
            Write-Log "Deploy Vercel disparado via push."
        }
    } finally {
        Pop-Location
    }

    Write-Log "=== Concluído com sucesso ==="
    exit 0
} catch {
    Write-Log "ERRO: $($_.Exception.Message)"
    exit 1
}
