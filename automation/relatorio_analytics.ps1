#Requires -Version 5.1
<#
.SYNOPSIS
  Gera relatorio privado de mídia kit (exports/relatorio_midia_kit.md).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvFile = Join-Path $Raiz "config\analytics.local.env"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $nome = $matches[1].Trim()
            $valor = $matches[2].Trim()
            Set-Item -Path "env:$nome" -Value $valor
        }
    }
}

$python = "py"
try {
    & py -3 -c "import sys" 2>$null
    if ($LASTEXITCODE -ne 0) { $python = "python" }
} catch {
    $python = "python"
}

& $python (Join-Path $Raiz "automation\relatorio_analytics.py")
exit $LASTEXITCODE
