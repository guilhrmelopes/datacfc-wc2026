#Requires -Version 5.1
<#
.SYNOPSIS
  Atualiza dados da Copa (FotMob) e commita/push se houver mudanças.

.DESCRIPTION
  Pensado para Agendador de Tarefas do Windows — executar a cada 30 min
  durante a fase de grupos (ou após cada jogo + ~2h).
  Processa apenas partidas finalizadas ainda não registradas em copa_estado.json.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogDir = Join-Path $Raiz "logs\atualizar_copa"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("{0:yyyy-MM-dd_HH-mm-ss}.log" -f (Get-Date))

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

$ArquivosCommit = @(
    "frontend/public/data/copa_estado.json",
    "frontend/public/data/grupos_wc2026.json",
    "frontend/public/data/classificacao_grupos.json",
    "frontend/public/data/pontuacao_cedida.json",
    "frontend/public/data/selecoes.json",
    "frontend/public/data/jogadores_mercado.json"
)

try {
    Write-Log "=== Início atualização Copa ==="
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

    Write-Log "Executando pipeline FotMob..."
    $env:PYTHONPATH = Join-Path $Raiz "src"
    $pipeOut = & $python (Join-Path $Raiz "automation\atualizar_copa_fotmob.py") 2>&1
    $pipeExit = $LASTEXITCODE
    $pipeOut | ForEach-Object { Write-Log "$_" }
    if ($pipeExit -ne 0) { throw "Pipeline falhou (exit $pipeExit)" }

    Push-Location $Raiz
    try {
        git add @ArquivosCommit
        git diff --cached --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Nenhuma mudança para commitar."
        } else {
            $msg = "bot: atualizar dados Copa (recorrência, hub, classificação) [skip ci]"
            git commit -m $msg
            if ($LASTEXITCODE -ne 0) { throw "git commit falhou" }
            Write-Log "git push"
            git push
            if ($LASTEXITCODE -ne 0) { throw "git push falhou" }
            Write-Log "Commit e push concluídos — deploy Vercel disparado."
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
