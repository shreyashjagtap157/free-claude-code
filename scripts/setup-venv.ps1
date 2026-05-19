# Windows PowerShell helper: create venv + install project (pip)
# Usage: Run from PowerShell: .\scripts\setup-venv.ps1

param(
    [string]$PythonExe = "python"
)

Set-StrictMode -Version Latest

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    Write-Error "Python executable '$PythonExe' not found. Install Python 3.14 and re-run, or pass path via -PythonExe."
    exit 1
}

# Check Python version
$verCheck = & $PythonExe -c "import sys; print(sys.version_info >= (3,14))"
if ($verCheck -ne 'True') {
    Write-Warning "Detected Python version is older than 3.14. Proceeding may fail. Install Python 3.14 or use the 'uv' flow."
    $ans = Read-Host "Continue anyway? (y/N)"
    if ($ans -ne 'y') { exit 1 }
}

$venvPath = ".venv"
Write-Host "Creating virtual environment at $venvPath..."
& $PythonExe -m venv $venvPath

$pythonInVenv = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $pythonInVenv)) {
    Write-Error "Failed to create venv or locate python at $pythonInVenv"
    exit 1
}

Write-Host "Upgrading pip and installing project dependencies..."
& $pythonInVenv -m pip install --upgrade pip
& $pythonInVenv -m pip install .

Write-Host "Installation complete."
Write-Host "To install development tools (formatter, type checker, tests), run:" 
Write-Host "  .\$venvPath\Scripts\python.exe -m pip install pytest pytest-asyncio pytest-cov ty ruff pytest-xdist"
Write-Host "Activate the venv with: .\$venvPath\Scripts\Activate.ps1"
Write-Host "Then run: fcc-server"
