#Requires -Version 5.1
<#
.SYNOPSIS
  Registra tarefas agendadas para atualização completa do dashboard.

.DESCRIPTION
  - Copa + status: a cada 30 min (processa partidas finalizadas, push → Vercel)
  - Odds completas: 6×/dia (06h, 09h, 12h, 15h, 18h, 21h) via atualizar_tudo.ps1

  Execute uma vez (como administrador recomendado):
    powershell -ExecutionPolicy Bypass -File automation\registrar_agenda_completa.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ScriptCopa = Join-Path $Raiz "automation\atualizar_copa.ps1"
$ScriptTudo = Join-Path $Raiz "automation\atualizar_tudo.ps1"

if (-not (Test-Path $ScriptCopa)) { throw "Não encontrado: $ScriptCopa" }
if (-not (Test-Path $ScriptTudo)) { throw "Não encontrado: $ScriptTudo" }

# Copa a cada 30 min (sem odds — mais rápido pós-jogo)
$NomeCopa = "DataCFC_AtualizarCopa_30min"
$acaoCopa = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptCopa`""
$triggerCopa = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 60)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $NomeCopa -Action $acaoCopa -Trigger $triggerCopa -Settings $settings -Force | Out-Null
Write-Host "Tarefa '$NomeCopa' - a cada 30 min (Copa + deploy)."

# Odds + Copa + status 6×/dia
$TaskPrefix = "DataCFC-AtualizarTudo"
$Horarios = @("06:00", "09:00", "12:00", "15:00", "18:00", "21:00")
$ActionTudo = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptTudo`""

foreach ($h in $Horarios) {
    $suffix = $h.Replace(":", "")
    $name = if ($h -eq "06:00") { $TaskPrefix } else { "${TaskPrefix}-$suffix" }
    schtasks /Create /TN $name /TR $ActionTudo /SC DAILY /ST $h /F | Out-Null
    Write-Host "Tarefa registrada: $name ($h) - Copa + status + odds + deploy."
}

Write-Host ""
Write-Host "Testar agora:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$ScriptTudo`""
Write-Host ""
Write-Host "Remover tarefas:"
Write-Host "  Unregister-ScheduledTask -TaskName '$NomeCopa' -Confirm:`$false"
Write-Host "  schtasks /Delete /TN $TaskPrefix /F"
