# Windows setup helper for Free Claude Code
# Usage: Run from PowerShell as administrator or with appropriate permissions:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1

Set-StrictMode -Version Latest

function Ensure-UV {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "uv not found. Installing uv via official installer..."
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    } else {
        Write-Host "uv already installed."
    }
    try {
        uv self update
    } catch {
        Write-Warning "Failed to run 'uv self update' (uv may not be on PATH yet)."
    }
}

function Ensure-Python-3_14 {
    Write-Host "Ensuring Python 3.14 is available via uv..."
    try {
        $list = uv python list 2>$null
        if ($list -and $list -match "3.14") {
            Write-Host "Python 3.14 already available in uv."
        } else {
            Write-Host "Installing Python 3.14 (uv python install 3.14)..."
            uv python install 3.14
        }
    } catch {
        Write-Warning "Could not query uv python list; attempting to install Python 3.14 anyway."
        uv python install 3.14
    }
}

function Install-Project {
    Write-Host "Installing Free Claude Code via uv tool (this installs the CLI entrypoints)..."
    uv tool install --force git+https://github.com/Alishahryar1/free-claude-code.git
    Write-Host "Installation finished. To start the server, run: fcc-server"
}

# Main
Ensure-UV
Ensure-Python-3_14
Install-Project
Write-Host "Done. If anything failed, check the output above and re-run the script with elevated permissions."