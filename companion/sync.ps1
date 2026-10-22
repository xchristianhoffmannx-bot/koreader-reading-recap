param([string]$Device)
$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction Stop).Source
if ($Device) {
    $devices = @($Device)
} else {
    $devices = @(Get-Volume | Where-Object DriveLetter | ForEach-Object {
        $readerRoot = "$($_.DriveLetter):\"
        if (Test-Path -LiteralPath (Join-Path $readerRoot 'koreader\plugins\readingrecap.koplugin\main.lua')) {
            $readerRoot
        }
    })
}
if (-not $devices.Count) { Write-Host 'No connected KOReader with Reading Recap found.'; exit 0 }
$failed = $false
foreach ($reader in $devices) {
    if (-not (Test-Path -LiteralPath (Join-Path $reader 'koreader\settings'))) {
        throw "Not a mounted KOReader directory: $reader"
    }
    & $python -I (Join-Path $PSScriptRoot 'recap_sync.py') --device $reader
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}
if ($failed) { exit 1 }
