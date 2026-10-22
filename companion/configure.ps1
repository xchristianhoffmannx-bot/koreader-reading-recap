$ErrorActionPreference = 'Stop'
Write-Host 'Choose a provider: codex, openai, anthropic, gemini'
$provider = (Read-Host 'Provider').Trim().ToLowerInvariant()
if ($provider -notin @('codex', 'openai', 'anthropic', 'gemini')) { throw 'Unsupported provider' }
$config = @{ provider = $provider }
if ($provider -ne 'codex') {
    $model = (Read-Host 'Exact model ID from your provider account').Trim()
    if (-not $model -or $model.Length -gt 150 -or $model -match '\s') { throw 'Invalid model ID' }
    Write-Host "Read book text will be sent to $provider. API usage can incur charges on your account."
    $secret = Read-Host 'Your API key (hidden input; Enter cancels)' -AsSecureString
    try {
        if ($secret.Length -eq 0) { throw 'No key entered; configuration unchanged' }
        $config.model = $model
        $config.encrypted_key = ConvertFrom-SecureString -SecureString $secret
    } finally { $secret.Dispose() }
}
$dir = Join-Path $env:LOCALAPPDATA 'KOReaderReadingRecap'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$path = Join-Path $dir 'provider.json'
$config | ConvertTo-Json | Set-Content -LiteralPath ($path + '.tmp') -Encoding UTF8
Move-Item -LiteralPath ($path + '.tmp') -Destination $path -Force
Write-Host 'Saved. The key is protected for your Windows user on this computer. Run sync.ps1 to use it.'
