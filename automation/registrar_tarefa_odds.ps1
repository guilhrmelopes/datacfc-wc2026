#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Registra tarefa no Agendador do Windows para atualizar odds 6×/dia (horário local).

  Execute como Administrador:
    powershell -ExecutionPolicy Bypass -File automation\registrar_tarefa_odds.ps1
#>

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Raiz "automation\atualizar_odds.ps1"
$TaskName = "DataCFC-AtualizarOdds"

if (-not (Test-Path $Script)) {
    throw "Script não encontrado: $Script"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`"" `
    -WorkingDirectory $Raiz

# Horários locais (ajuste se não estiver em BRT)
$Horarios = @("06:00", "09:00", "12:00", "15:00", "18:00", "21:00")
$Triggers = foreach ($h in $Horarios) {
    New-ScheduledTaskTrigger -Daily -At $h
}

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Triggers `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Raspa odds GA%/SG% do hub.oddsnotifier.io e commita no repo Data CFC WC 2026." `
    -Force | Out-Null

Write-Host "Tarefa '$TaskName' registrada."
Write-Host "Horários diários: $($Horarios -join ', ')"
Write-Host "Script: $Script"
Write-Host ""
Write-Host "Testar agora:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$Script`""
