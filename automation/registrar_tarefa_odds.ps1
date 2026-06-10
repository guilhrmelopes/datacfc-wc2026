#Requires -Version 5.1
<#
.SYNOPSIS
  Registra tarefas no Agendador do Windows para atualizar odds 6×/dia (hora local).

  powershell -ExecutionPolicy Bypass -File automation\registrar_tarefa_odds.ps1
#>

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Raiz "automation\atualizar_odds.ps1"

if (-not (Test-Path $Script)) {
    throw "Script não encontrado: $Script"
}

$TaskPrefix = "DataCFC-AtualizarOdds"
$Horarios = @("06:00", "09:00", "12:00", "15:00", "18:00", "21:00")
$Action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""

foreach ($h in $Horarios) {
    $suffix = $h.Replace(":", "")
    $name = if ($h -eq "06:00") { $TaskPrefix } else { "$TaskPrefix-$suffix" }
    schtasks /Create /TN $name /TR $Action /SC DAILY /ST $h /F | Out-Null
    Write-Host "Tarefa registrada: $name ($h)"
}

Write-Host ""
Write-Host "Testar agora:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$Script`""
