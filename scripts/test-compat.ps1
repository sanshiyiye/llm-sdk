$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
python "$PSScriptRoot\test_compat.py"
exit $LASTEXITCODE
