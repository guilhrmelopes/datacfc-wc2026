#Requires -Version 5.1
<#
.SYNOPSIS
  Configura analytics privado (GA4 + Vercel) para o mídia kit.

.DESCRIPTION
  1. Cria config/analytics.local.env e frontend/.env.local
  2. Valida formato do Measurement ID (G-XXXX)
  3. Exibe passos para Vercel e (opcional) service account do relatório

  Execute uma vez:
    powershell -ExecutionPolicy Bypass -File automation\configurar_analytics.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ConfigDir = Join-Path $Raiz "config"
$EnvLocal = Join-Path $ConfigDir "analytics.local.env"
$FrontendEnv = Join-Path $Raiz "frontend\.env.local"
$Exemplo = Join-Path $ConfigDir "analytics.local.env.example"

Write-Host ""
Write-Host "=== Data CFC — Configurar analytics (privado) ===" -ForegroundColor Cyan
Write-Host "Coleta a partir de: 14/06/2026 (config/analytics.json)"
Write-Host ""

Write-Host "Passo 1 — Google Analytics 4" -ForegroundColor Yellow
Write-Host "  1. Abra https://analytics.google.com/"
Write-Host "  2. Admin -> Criar propriedade -> Web"
Write-Host "  3. URL do site: seu dominio Vercel (ex. datacfc-wc2026.vercel.app)"
Write-Host "  4. Admin -> Fluxos de dados -> copie o ID de medicao (G-XXXXXXXXXX)"
Write-Host "  5. Admin -> Detalhes da propriedade -> ID numerico (ex. 512345678)"
Write-Host ""

$mid = Read-Host "Cole o Measurement ID (G-XXXXXXXXXX)"
$mid = $mid.Trim()
if ($mid -notmatch '^G-[A-Z0-9]+$') {
    throw "Measurement ID invalido. Esperado formato G-XXXXXXXXXX"
}

$prop = Read-Host "Cole o Property ID numerico GA4 (opcional, Enter para pular)"
$prop = $prop.Trim()

$cred = Read-Host "Caminho do JSON da service account (opcional, Enter para pular)"
$cred = $cred.Trim()
if ($cred -and -not (Test-Path $cred)) {
    throw "Arquivo nao encontrado: $cred"
}

$linhas = @(
    "VITE_GA_MEASUREMENT_ID=$mid"
)
if ($prop) { $linhas += "GA4_PROPERTY_ID=$prop" }
if ($cred) { $linhas += "GOOGLE_APPLICATION_CREDENTIALS=$cred" }

$conteudo = ($linhas -join "`n") + "`n"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
Set-Content -Path $EnvLocal -Value $conteudo -Encoding UTF8
Copy-Item -Path $EnvLocal -Destination $FrontendEnv -Force

Write-Host ""
Write-Host "Salvo:" -ForegroundColor Green
Write-Host "  $EnvLocal"
Write-Host "  $FrontendEnv"
Write-Host ""

Write-Host "Passo 2 — Vercel (producao)" -ForegroundColor Yellow
Write-Host "  1. https://vercel.com -> seu projeto Data CFC"
Write-Host "  2. Settings -> Environment Variables"
Write-Host "  3. Adicione:"
Write-Host "       Nome:  VITE_GA_MEASUREMENT_ID"
Write-Host "       Valor: $mid"
Write-Host "       Ambientes: Production (e Preview se quiser)"
Write-Host "  4. Deployments -> Redeploy ultimo deploy"
Write-Host "  5. Analytics -> Web Analytics -> Enable (complementar ao GA4)"
Write-Host ""

Write-Host "Passo 3 — Teste local" -ForegroundColor Yellow
Write-Host "  cd frontend"
Write-Host "  npm run dev"
Write-Host "  GA4 -> Relatorios -> Tempo real (aguarde ~1 min apos abrir o site)"
Write-Host ""

if (-not $prop -or -not $cred) {
    Write-Host "Relatorio completo (fim da Copa):" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements-analytics.txt"
    Write-Host "  Defina GA4_PROPERTY_ID + GOOGLE_APPLICATION_CREDENTIALS em config/analytics.local.env"
    Write-Host "  python automation/relatorio_analytics.py"
    Write-Host ""
}

Write-Host "Concluido." -ForegroundColor Green
