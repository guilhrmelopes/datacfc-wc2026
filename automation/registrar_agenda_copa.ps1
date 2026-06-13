#Requires -Version 5.1
<#
.SYNOPSIS
  Registra tarefa agendada para atualizar a Copa a cada 30 minutos.

.DESCRIPTION
  Execute uma vez como administrador. A tarefa chama automation/atualizar_copa.ps1,
  que roda Cartola (/copa/), FotMob, odds GA%/SG% e push (deploy Vercel).

  Para agenda completa (status jogadores + 6×/dia), use registrar_agenda_completa.ps1.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Raiz "automation\atualizar_copa.ps1"
$NomeTarefa = "DataCFC_AtualizarCopa_30min"

if (-not (Test-Path $Script)) {
    throw "Script não encontrado: $Script"
}

$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 60)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $NomeTarefa -Action $acao -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Tarefa '$NomeTarefa' registrada — a cada 30 min por 60 dias."
Write-Host "Fluxo: Cartola + FotMob + odds + commit/push."
Write-Host "Para remover: Unregister-ScheduledTask -TaskName '$NomeTarefa' -Confirm:`$false"
