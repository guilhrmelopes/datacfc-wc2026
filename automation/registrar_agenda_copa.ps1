#Requires -Version 5.1
<#
.SYNOPSIS
  DEPRECATED — projeto arquivado; não registre tarefas locais.

.DESCRIPTION
  Remove qualquer tarefa DataCFC residual. Workflows de Copa estão sem cron.
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
Write-Host "OK — sem agenda local. Projeto arquivado."
