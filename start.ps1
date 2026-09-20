param([switch]$Reload)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $serverArguments = @('run', 'uvicorn', 'src.app.api:app', '--host', '127.0.0.1', '--port', '8000')
    if ($Reload) { $serverArguments += '--reload' }
    & uv @serverArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Server startup failed. Check the message above. Port 8000 may already be occupied.'
    }
} finally {
    Pop-Location
}
