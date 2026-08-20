#Requires -Version 5.1
<#
.SYNOPSIS
  DEPRECATED — projeto arquivado; não registre agenda local.

.DESCRIPTION
  Remove qualquer tarefa DataCFC residual no Agendador do Windows.
  GitHub Actions de Copa/status estão sem cron (só workflow_dispatch).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like "DataCFC*" -or $_.TaskPath -eq '\DataCFC\' } |
    ForEach-Object {
        Write-Host "Removendo tarefa local: $($_.TaskPath)$($_.TaskName)"
        Stop-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath -Confirm:$false -ErrorAction SilentlyContinue
    }

Write-Host ""
Write-Host "Agenda local desativada. Projeto arquivado — sem atualizacao automatica."
