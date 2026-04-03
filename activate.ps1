$ErrorActionPreference = "Stop"
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$VenvDir = Join-Path $ScriptDir ".venv"
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$ScriptsDir = Join-Path $VenvDir "Scripts"

if (Test-Path $ActivateScript) {
    Write-Host "[OK] Activating .venv..." -ForegroundColor Green
    . $ActivateScript
    return
}

if (Test-Path $PythonExe) {
    $env:VIRTUAL_ENV = $VenvDir
    if (-not (($env:PATH -split ';') -contains $ScriptsDir)) {
        $env:PATH = "$ScriptsDir;$env:PATH"
    }
    if (-not (Test-Path function:global:__llm_sdk_old_prompt)) {
        $function:global:__llm_sdk_old_prompt = $function:prompt
    }
    function global:prompt {
        $basePrompt = if ($function:global:__llm_sdk_old_prompt) {
            & $function:global:__llm_sdk_old_prompt
        } else {
            "PS $((Get-Location).Path)> "
        }
        if ($basePrompt -like "(.venv)*") {
            $basePrompt
        } else {
            "(.venv) $basePrompt"
        }
    }
    Write-Host "[OK] Activating .venv (fallback mode)..." -ForegroundColor Green
    return
}

Write-Host "[Error] .venv not found at: $VenvDir" -ForegroundColor Red
