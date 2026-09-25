[CmdletBinding()]
param(
    [string]$Entrada = "data/mensagem_zap.txt",
    [string]$Saida = "output/docx",
    [string]$Modelo = "qwen3:8b",
    [switch]$SemIA,
    [switch]$Sobrescrever
)

$ErrorActionPreference = "Stop"
$raizWindows = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($raizWindows -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "O projeto precisa estar em uma unidade local do Windows."
}
$raizWsl = "/mnt/{0}/{1}" -f $Matches[1].ToLowerInvariant(), $Matches[2].Replace('\', '/')

foreach ($path in @($Entrada, $Saida)) {
    if ([System.IO.Path]::IsPathRooted($path) -or $path.StartsWith('/')) {
        throw "Entrada e Saida devem ser caminhos relativos a pasta do projeto."
    }
}

$comando = @(
    "-d", "Ubuntu", "--", "env", "PYTHONPATH=$raizWsl/src",
    "$raizWsl/.venv/bin/python", "-m", "stageflow.cli",
    "--input", "$raizWsl/$($Entrada.Replace('\', '/'))",
    "--output", "$raizWsl/$($Saida.Replace('\', '/'))",
    "--model", $Modelo
)
if ($SemIA) { $comando += "--sem-ia" }
if ($Sobrescrever) { $comando += "--overwrite" }

& wsl.exe @comando
exit $LASTEXITCODE
