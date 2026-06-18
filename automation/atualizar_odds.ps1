#Requires -Version 5.1

<#

.SYNOPSIS

  Sincroniza mercado, raspa odds GA%/SG% e commita/push se houver mudanças válidas.



.DESCRIPTION

  Pensado para Agendador de Tarefas do Windows (6×/dia) ou após atualização manual.

  Ordem: git pull → Cartola + FotMob (ADV/proximo jogo) → odds → validação → commit.

  Requer: Python 3.12+, git com push configurado, playwright chromium instalado.

#>



Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"



$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$LogDir = Join-Path $Raiz "logs\atualizar_odds"

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
    "frontend/public/data/odds_eventos_armazenados.json",
    "frontend/public/data/mapeamento_jogadores_odds.json",
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

        [string]$Script

    )

    $env:PYTHONPATH = Join-Path $Raiz "src"

    $out = & $Python $Script 2>&1

    $exit = $LASTEXITCODE

    $out | ForEach-Object { Write-Log "$_" }

    if ($exit -ne 0) { throw "Script falhou: $Script (exit $exit)" }

}



try {

    Write-Log "=== Início atualização odds ==="

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



    Write-Log "--- [1/3] API oficial Cartola Copa (/copa/) ---"

    Invoke-PythonScript -Python $python -Script (Join-Path $Raiz "automation\atualizar_cartola_copa.py")



    Write-Log "--- [2/3] Mercado + proximo adversario (FotMob/Cartola) ---"

    Invoke-PythonScript -Python $python -Script (Join-Path $Raiz "automation\preparar_mercado_odds.py")



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

    $env:ODDSNOTIFIER_HEADLESS = "true"

    $env:ODDS_SKIP_WARMUP = "0"



    Write-Log "Executando scraper + validacao..."

    $scrapeOut = & $python (Join-Path $Raiz "automation\executar_odds.py") 2>&1

    $scrapeExit = $LASTEXITCODE

    $scrapeOut | ForEach-Object { Write-Log "$_" }

    if ($scrapeExit -ne 0) {

        throw "Scraper ou validacao falhou (exit $scrapeExit) — commit abortado"

    }



    Push-Location $Raiz

    try {

        git add @ArquivosCommit

        git diff --cached --quiet

        if ($LASTEXITCODE -eq 0) {

            Write-Log "Nenhuma mudança para commitar."

        } else {

            $msg = @"

bot: atualizar mercado e odds GA%/SG% [skip ci]



Cartola + FotMob (proximo adversario) e odds vigentes do proximo jogo.

"@

            git commit -m $msg

            if ($LASTEXITCODE -ne 0) { throw "git commit falhou" }

            Write-Log "git push"

            git push

            if ($LASTEXITCODE -ne 0) { throw "git push falhou" }

            Write-Log "Commit e push concluídos."

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

