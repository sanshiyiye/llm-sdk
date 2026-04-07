$ErrorActionPreference = "Stop"
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$VenvDir = Join-Path $ScriptDir ".venv"
$ScriptsDir = Join-Path $VenvDir "Scripts"
$ScriptsPythonExe = Join-Path $ScriptsDir "python.exe"
$RootPythonExe = Join-Path $VenvDir "python.exe"
$MinimumVersion = [Version]"3.11.0"

function Normalize-PathValue {
    param(
        [string]$PathValue
    )

    if (-not $PathValue) {
        return ""
    }

    return $PathValue.Trim().TrimEnd('\').ToLowerInvariant()
}

function Get-VenvPythonPath {
    foreach ($candidate in @($ScriptsPythonExe, $RootPythonExe)) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-VenvPathEntries {
    $entries = @()
    if (Test-Path $ScriptsDir) {
        $entries += $ScriptsDir
    }
    if (Test-Path $VenvDir) {
        $entries += $VenvDir
    }
    return ($entries | Select-Object -Unique)
}

function Reset-VenvState {
    $pathEntries = @()
    if ($env:PATH) {
        $pathEntries = $env:PATH -split ';'
    }

    $normalizedVenvEntries = Get-VenvPathEntries | ForEach-Object { Normalize-PathValue -PathValue $_ }
    $env:PATH = (($pathEntries | Where-Object {
        $normalizedEntry = Normalize-PathValue -PathValue $_
        $_ -and ($normalizedVenvEntries -notcontains $normalizedEntry)
    }) -join ';')

    if ($env:VIRTUAL_ENV -eq $VenvDir) {
        Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
    }

    if ((Test-Path function:global:__llm_sdk_old_prompt) -and (Test-Path function:global:prompt)) {
        $function:global:prompt = $function:global:__llm_sdk_old_prompt
    }
}

function Get-PythonVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath
    )

    if (-not (Test-Path $PythonPath)) {
        return $null
    }

    try {
        $rawVersion = & $PythonPath -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
        if (-not $rawVersion) {
            return $null
        }
        return [Version]$rawVersion.Trim()
    } catch {
        return $null
    }
}

function Get-CompatiblePython {
    $candidates = @()

    if ($env:LLM_SDK_PYTHON) {
        $candidates += $env:LLM_SDK_PYTHON
    }

    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
    if ($localAppData) {
        $candidates += @(
            (Join-Path $localAppData "Programs\Python\Python313\python.exe"),
            (Join-Path $localAppData "Programs\Python\Python312\python.exe"),
            (Join-Path $localAppData "Programs\Python\Python311\python.exe")
        )
    }

    $candidates += @(
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )

    foreach ($commandName in @("python3.13", "python3.12", "python3.11", "python")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            $candidates += $command.Source
        }
    }

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        $resolvedPath = $candidate
        if (-not (Test-Path $resolvedPath)) {
            continue
        }

        $version = Get-PythonVersion -PythonPath $resolvedPath
        if ($version -and $version -ge $MinimumVersion) {
            return @{
                Path = $resolvedPath
                Version = $version
            }
        }
    }

    return $null
}

function Ensure-Venv {
    $venvPythonPath = Get-VenvPythonPath
    $venvVersion = if ($venvPythonPath) { Get-PythonVersion -PythonPath $venvPythonPath } else { $null }
    if ($venvVersion -and $venvVersion -ge $MinimumVersion) {
        return $true
    }

    if ($venvVersion) {
        Write-Host "[Warn] Existing .venv uses Python $venvVersion, but Python $MinimumVersion or newer is required." -ForegroundColor Yellow
    } else {
        Write-Host "[Info] .venv not found or is incomplete. A compatible virtual environment will be created." -ForegroundColor Yellow
    }

    $compatiblePython = Get-CompatiblePython
    if (Test-Path $VenvDir) {
        Reset-VenvState
        Remove-Item $VenvDir -Recurse -Force
    }

    if ($compatiblePython) {
        Write-Host "[OK] Creating .venv with Python $($compatiblePython.Version)..." -ForegroundColor Green
        & $compatiblePython.Path -m venv $VenvDir
        return [bool](Get-VenvPythonPath)
    }

    $condaCommand = Get-Command conda -ErrorAction SilentlyContinue
    if ($condaCommand) {
        Write-Host "[OK] Creating .venv with Conda Python 3.11..." -ForegroundColor Green
        & $condaCommand.Source create -p $VenvDir python=3.11 -y
        return [bool](Get-VenvPythonPath)
    }

    Reset-VenvState
    Write-Host "[Error] Python 3.11+ was not found. Install Python 3.11+ or set LLM_SDK_PYTHON to a compatible interpreter path." -ForegroundColor Red
    return $false
}

function Activate-Venv {
    $venvPythonPath = Get-VenvPythonPath
    if (-not $venvPythonPath) {
        Write-Host "[Error] No Python executable was found inside .venv." -ForegroundColor Red
        return
    }

    $env:VIRTUAL_ENV = $VenvDir

    $pathEntries = @()
    if ($env:PATH) {
        $pathEntries = $env:PATH -split ';'
    }

    $venvPathEntries = Get-VenvPathEntries
    $normalizedVenvEntries = $venvPathEntries | ForEach-Object { Normalize-PathValue -PathValue $_ }
    $remainingEntries = $pathEntries | Where-Object {
        $normalizedEntry = Normalize-PathValue -PathValue $_
        $_ -and ($normalizedVenvEntries -notcontains $normalizedEntry)
    }
    $env:PATH = (($venvPathEntries + $remainingEntries) | Select-Object -Unique) -join ';'

    if (-not (Test-Path function:global:__llm_sdk_old_prompt) -and (Test-Path function:prompt)) {
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

    $activeVersion = Get-PythonVersion -PythonPath $venvPythonPath
    Write-Host "[OK] Activated .venv with Python $activeVersion" -ForegroundColor Green
}

if (-not (Ensure-Venv)) {
    return
}

Activate-Venv
