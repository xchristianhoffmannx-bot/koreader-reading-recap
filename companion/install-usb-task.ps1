$ErrorActionPreference = 'Stop'
$syncScript = Join-Path $PSScriptRoot 'sync.ps1'
$logFile = Join-Path $PSScriptRoot 'sync.log'
$quotedScript = $syncScript.Replace("'", "''")
$quotedLog = $logFile.Replace("'", "''")
$commandArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"& '$quotedScript' *> '$quotedLog'; exit `$LASTEXITCODE`""
$xmlArgs = [System.Security.SecurityElement]::Escape($commandArgs)
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><EventTrigger><Enabled>true</Enabled>
    <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="Microsoft-Windows-Partition/Diagnostic"&gt;&lt;Select Path="Microsoft-Windows-Partition/Diagnostic"&gt;*[System[EventID=1006]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    <Delay>PT20S</Delay>
  </EventTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>$sid</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT2H</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>powershell.exe</Command><Arguments>$xmlArgs</Arguments></Exec></Actions>
</Task>
"@
Register-ScheduledTask -TaskName 'KOReader-Reading-Recap' -Xml $xml | Out-Null
Write-Host 'Installed KOReader-Reading-Recap. Keep this folder in place. See sync.log after connecting your reader.'
