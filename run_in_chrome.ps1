$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$site = Join-Path $projectRoot ".web-site"

if (-not (Test-Path -LiteralPath (Join-Path $site "index.html"))) {
    throw "Browser game files not found: $site"
}

$serverArgs = @("-m", "http.server", "8000", "--bind", "127.0.0.1", "--directory", $site)
if (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
    $pythonPrefix = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = (Get-Command py).Source
    $pythonPrefix = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = (Get-Command python).Source
    $pythonPrefix = @()
} else {
    throw "Python 3 is required to serve the browser game. Install Python or create .venv."
}

Write-Host "Monster Rampage is hosted at http://localhost:8000"
Write-Host "Open that address in Chrome. Keep this window open while playing; press Ctrl+C to stop."
& $python @pythonPrefix @serverArgs
