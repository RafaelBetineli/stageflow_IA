[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Porta = 8501,
    [switch]$NaoAbrirNavegador
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL nao encontrado. Instale ou habilite o WSL antes de executar o projeto."
}

$raizWindows = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($raizWindows -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "O projeto precisa estar em uma unidade local do Windows para ser aberto pelo WSL."
}
$raizWsl = "/mnt/{0}/{1}" -f $Matches[1].ToLowerInvariant(), $Matches[2].Replace('\', '/')

$comando = @(
    "-d"
    "Ubuntu"
    "--"
    "env"
    "PYTHONPATH=$raizWsl/src"
    "$raizWsl/.venv/bin/python"
    "-m"
    "streamlit"
    "run"
    "$raizWsl/src/stageflow/ui.py"
    "--server.address=127.0.0.1"
    "--server.port=$Porta"
    "--server.headless=true"
    "--browser.gatherUsageStats=false"
)

$url = "http://localhost:$Porta"
Write-Host "StageFlow sera aberto em $url"
Write-Host "Mantenha esta janela aberta. Use Ctrl+C para encerrar."

if (-not $NaoAbrirNavegador) {
    Start-Job -ScriptBlock {
        Start-Sleep -Seconds 2
        Start-Process $using:url
    } | Out-Null
}

& wsl.exe @comando
exit $LASTEXITCODE
