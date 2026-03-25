#Requires -Version 5.1
# KERT Windows Setup Installer (English)

$Host.UI.RawUI.WindowTitle = "KERT Setup Installer"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ============================================================
# Utility functions
# ============================================================

function Write-Header {
    param([string]$Title)
    Clear-Host
    Write-Host ""
    Write-Host "-----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "-----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host ""
}

function Ask-Continue {
    Write-Host ""
    do {
        $choice = (Read-Host "Proceed to the next step? (Y=Continue / N=Abort)").Trim().ToUpper()
    } while ($choice -ne 'Y' -and $choice -ne 'N')
    if ($choice -eq 'N') {
        Show-Abort
        exit 1
    }
}

function Show-Abort {
    Clear-Host
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host "   Setup aborted" -ForegroundColor Yellow
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Setup has been aborted."
    Write-Host "Any steps already completed remain effective."
    Write-Host "Run this script again to resume from where you left off."
    Write-Host "(Completed steps will be skipped automatically.)"
    Write-Host ""
    Read-Host "Press Enter to exit"
}

function Add-ToUserPath {
    param([string]$NewPath)
    if ($env:PATH -notlike "*$NewPath*") {
        $env:PATH = "$NewPath;$env:PATH"
    }
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$NewPath*") {
        try {
            [Environment]::SetEnvironmentVariable("PATH", "$NewPath;$userPath", "User")
            Write-Host "[Done] Permanently added to PATH: $NewPath"
        } catch {
            Write-Host "[Warning] Could not save PATH permanently. Please add manually:" -ForegroundColor Yellow
            Write-Host "          Folder: $NewPath"
        }
    }
}

# ============================================================
# Welcome screen
# ============================================================
Clear-Host
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "   KERT Setup Installer (English)" -ForegroundColor Green
Write-Host "   This script sets up the KERT runtime environment step by step." -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "[Installation Steps]"
Write-Host ""
Write-Host "  Step 1  Install Python 3.12"
Write-Host "  Step 2  Install Miniforge (conda)"
Write-Host "  Step 3  Verify conda PATH"
Write-Host "  Step 4  Install Montreal Forced Aligner (MFA)"
Write-Host "  Step 5  Install FFmpeg"
Write-Host "  Step 6  Install textgrid / saxonche"
Write-Host "  Step 7  Download English MFA models"
Write-Host ""
Write-Host "You will be asked to continue or abort after each step."
Write-Host "Press N at any time to abort."
Write-Host ""
Read-Host "Press Enter to start the installation"

# ============================================================
# Step 1: Python 3.12
# ============================================================
Write-Header "Step 1 / 7  :  Install Python 3.12"

$pyOk = $false
try {
    $pyVer = & py -3.12 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python 3.12 is already installed. Skipping."
        Write-Host $pyVer
        $pyOk = $true
    }
} catch {}

if (-not $pyOk) {
    Write-Host "Python 3.12 not found. Downloading and installing..."
    Write-Host ""
    $pyInstaller = "$env:TEMP\python-3.12.10-amd64.exe"

    Write-Host "Downloading..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' `
            -OutFile $pyInstaller -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[Error] Failed to download the Python installer." -ForegroundColor Red
        Write-Host "Please download manually:"
        Write-Host "  https://www.python.org/downloads/release/python-31210/"
        Write-Host "  File: python-3.12.10-amd64.exe"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $pyInstaller)) {
        Write-Host "Download complete. Starting installation (please wait)..."
        $result = Start-Process -FilePath $pyInstaller `
            -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "[Error] Python installation failed (exit code: $($result.ExitCode))." -ForegroundColor Red
            Write-Host "Please install manually:"
            Write-Host "  https://www.python.org/downloads/release/python-31210/"
            Write-Host ""
        } else {
            $pyPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
            $pyScripts = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
            $env:PATH = "$pyPath;$pyScripts;$env:PATH"
            Write-Host ""
            Write-Host "[Done] Python 3.12 installation complete."
            try { & py -3.12 --version 2>&1 | Write-Host } catch {}
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Step 2: Miniforge
# ============================================================
Write-Header "Step 2 / 7  :  Install Miniforge (conda)"

$condaCmd = Get-Command conda -ErrorAction SilentlyContinue

if ($null -ne $condaCmd) {
    Write-Host "[OK] conda is already available. Skipping."
    & conda --version
} elseif (Test-Path "$env:USERPROFILE\miniforge3\Scripts\conda.exe") {
    Write-Host "[OK] Miniforge is already installed. Updating PATH."
    $env:PATH = "$env:USERPROFILE\miniforge3\Scripts;$env:USERPROFILE\miniforge3\condabin;$env:PATH"
    Write-Host "PATH updated for this session."
} else {
    Write-Host "Miniforge not found. Downloading and installing..."
    Write-Host ""
    $mfInstaller = "$env:TEMP\Miniforge3-Windows-x86_64.exe"

    Write-Host "Downloading..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe' `
            -OutFile $mfInstaller -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[Error] Failed to download Miniforge." -ForegroundColor Red
        Write-Host "Please download manually:"
        Write-Host "  https://github.com/conda-forge/miniforge/releases/latest"
        Write-Host "  File: Miniforge3-Windows-x86_64.exe"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $mfInstaller)) {
        Write-Host "Download complete. Starting installation (please wait)..."
        $result = Start-Process -FilePath $mfInstaller `
            -ArgumentList "/S /D=$env:USERPROFILE\miniforge3" -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "[Error] Miniforge installation failed (exit code: $($result.ExitCode))." -ForegroundColor Red
            Write-Host "Please install manually:"
            Write-Host "  https://github.com/conda-forge/miniforge/releases/latest"
            Write-Host ""
        } else {
            Write-Host "[Done] Miniforge installation complete."
            $env:PATH = "$env:USERPROFILE\miniforge3\Scripts;$env:USERPROFILE\miniforge3\condabin;$env:PATH"
            Write-Host "PATH updated for this session."
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Step 3: conda PATH
# ============================================================
Write-Header "Step 3 / 7  :  Verify conda PATH"

if ($null -ne (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] conda is registered in PATH."
    & conda --version
} else {
    Write-Host "conda not found in PATH. Searching for conda folder..."
    Write-Host ""

    $condaFound = $null
    $condaScripts = $null

    if (Test-Path "$env:USERPROFILE\miniforge3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\miniforge3"
        $condaScripts = "$env:USERPROFILE\miniforge3\Scripts"
        Write-Host "Found: $env:USERPROFILE\miniforge3"
    } elseif (Test-Path "$env:USERPROFILE\miniconda3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\miniconda3"
        $condaScripts = "$env:USERPROFILE\miniconda3\Scripts"
        Write-Host "Found: $env:USERPROFILE\miniconda3"
    } elseif (Test-Path "$env:USERPROFILE\Anaconda3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\Anaconda3"
        $condaScripts = "$env:USERPROFILE\Anaconda3\Scripts"
        Write-Host "Found: $env:USERPROFILE\Anaconda3"
    }

    if ($null -ne $condaFound) {
        Add-ToUserPath $condaScripts
        $env:PATH = "$condaScripts;$condaFound\condabin;$env:PATH"
        Write-Host "PATH updated for this session."
    } else {
        Write-Host "[Warning] conda executable not found." -ForegroundColor Yellow
        Write-Host "Please go back to Step 2 and install Miniforge."
        Write-Host ""
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Step 4: Montreal Forced Aligner (MFA)
# ============================================================
Write-Header "Step 4 / 7  :  Install Montreal Forced Aligner"

Write-Host "Checking conda environment (mfa)..."
Write-Host ""

& conda run -n mfa echo check 2>&1 | Out-Null
$mfaEnvExists = ($LASTEXITCODE -eq 0)

if ($mfaEnvExists) {
    Write-Host "conda environment ""mfa"" exists. Checking for MFA..."
    & conda run -n mfa mfa version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] MFA is already installed. Skipping."
        & conda run -n mfa mfa version
    } else {
        Write-Host "MFA not found. Installing into mfa environment..."
        & conda install -n mfa -c conda-forge montreal-forced-aligner -y
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "[Error] MFA installation failed." -ForegroundColor Red
            Write-Host "Please verify that conda is installed and you have an internet connection."
            Write-Host ""
        } else {
            Write-Host ""
            Write-Host "[Done] Montreal Forced Aligner installation complete."
        }
    }
} else {
    Write-Host "conda environment ""mfa"" does not exist. Creating and installing..."
    Write-Host "(This may take several minutes.)"
    & conda create -n mfa -c conda-forge montreal-forced-aligner -y
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[Error] MFA installation failed." -ForegroundColor Red
        Write-Host "Please verify that conda is installed and you have an internet connection."
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[Done] Montreal Forced Aligner installation complete."
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Step 5: FFmpeg
# ============================================================
Write-Header "Step 5 / 7  :  Install FFmpeg"

if ($null -ne (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] FFmpeg is already registered in PATH. Skipping."
    & ffmpeg -version 2>&1 | Select-String -Pattern "ffmpeg version" | ForEach-Object { Write-Host $_ }
} elseif (Test-Path "$env:USERPROFILE\ffmpeg\bin\ffmpeg.exe") {
    Write-Host "[OK] FFmpeg is already installed. Updating PATH."
    Add-ToUserPath "$env:USERPROFILE\ffmpeg\bin"
} else {
    Write-Host "FFmpeg not found. Downloading and installing..."
    Write-Host ""
    $ffZip = "$env:TEMP\ffmpeg-latest.zip"
    $ffWork = "$env:TEMP\ffmpeg_work"

    Write-Host "Downloading (this may take a few minutes)..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' `
            -OutFile $ffZip -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[Error] Failed to download FFmpeg." -ForegroundColor Red
        Write-Host "Please download manually:"
        Write-Host "  https://ffmpeg.org/download.html"
        Write-Host "  or https://github.com/BtbN/FFmpeg-Builds/releases"
        Write-Host "  Place ffmpeg.exe in a folder and add it to PATH."
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $ffZip)) {
        Write-Host "Download complete. Extracting..."
        if (Test-Path $ffWork) { Remove-Item $ffWork -Recurse -Force }
        New-Item -ItemType Directory -Path $ffWork | Out-Null

        $expandOk = $true
        try {
            Expand-Archive -LiteralPath $ffZip -DestinationPath $ffWork -Force -ErrorAction Stop
        } catch {
            $expandOk = $false
            Write-Host ""
            Write-Host "[Error] Failed to extract ZIP." -ForegroundColor Red
            Write-Host "Please install manually: https://ffmpeg.org/download.html"
            Write-Host ""
        }

        if ($expandOk) {
            $ffExtracted = Get-ChildItem -Path $ffWork -Directory | Select-Object -First 1
            if ($null -eq $ffExtracted) {
                Write-Host ""
                Write-Host "[Error] Extracted folder not found." -ForegroundColor Red
                Write-Host "Please install manually: https://ffmpeg.org/download.html"
                Write-Host ""
            } else {
                Write-Host "Copying files..."
                $destBin = "$env:USERPROFILE\ffmpeg\bin"
                New-Item -ItemType Directory -Path $destBin -Force | Out-Null
                Copy-Item "$($ffExtracted.FullName)\bin\*" $destBin -Force
                Add-ToUserPath $destBin
                Write-Host ""
                Write-Host "[Done] FFmpeg installation complete."
                & ffmpeg -version 2>&1 | Select-String -Pattern "ffmpeg version" | ForEach-Object { Write-Host $_ }
            }
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Step 6: textgrid / saxonche
# ============================================================
Write-Header "Step 6 / 7  :  Install textgrid / saxonche"

$pyExe = $null
if ($null -ne (Get-Command python -ErrorAction SilentlyContinue)) {
    $testOut = & python --version 2>&1
    if ($testOut -match "Python \d") { $pyExe = "python" }
}
if ($null -eq $pyExe -and $null -ne (Get-Command py -ErrorAction SilentlyContinue)) {
    $testOut = & py -3 --version 2>&1
    if ($testOut -match "Python \d") { $pyExe = "py -3" }
}
if ($null -eq $pyExe) {
    Write-Host "[Error] Python not found. Please check Step 1." -ForegroundColor Red
    Write-Host ""
} else {
    Write-Host "Python in use: $pyExe ($( & $pyExe.Split()[0] $pyExe.Split()[1..99] --version 2>&1 ))"
    Write-Host ""

    $pyArgs = $pyExe.Split()

    Write-Host "[1/2] Installing textgrid..."
    & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "textgrid"))
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[Done] textgrid installation complete."
    } else {
        Write-Host "[Error] textgrid installation failed." -ForegroundColor Red
    }

    Write-Host ""

    Write-Host "[2/2] Installing saxonche..."
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "ARM64") {
        Write-Host ""
        Write-Host "[Warning] ARM64 Windows detected." -ForegroundColor Yellow
        Write-Host "saxonche is not available for ARM64 Windows on PyPI."
        Write-Host ""
        Write-Host "[Workaround] If you need XML input support:"
        Write-Host "  1. Download the x64 Python installer from:"
        Write-Host "     https://www.python.org/downloads/release/python-31210/"
        Write-Host "     File: python-3.12.10-amd64.exe"
        Write-Host "  2. After installation, run:"
        Write-Host "     py -3.12-64 -m pip install saxonche"
        Write-Host ""
        Write-Host "saxonche is not required for CommonMark (.md) input."
    } else {
        & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "saxonche"))
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[Done] saxonche installation complete."
        } else {
            Write-Host "[Error] saxonche installation failed." -ForegroundColor Red
            Write-Host "Please check your internet connection and Python version (3.8 or later required)."
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Step 7: English MFA models
# ============================================================
Write-Header "Step 7 / 7  :  Download English MFA Models"

Write-Host "Downloading English MFA models (dictionary and acoustic)."
Write-Host "(Files are large — this may take several minutes.)"
Write-Host ""

Write-Host "[1/2] Downloading English dictionary model..."
& conda run -n mfa mfa model download dictionary english_us_arpa
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Error] Failed to download English dictionary model (exit code: $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Please check your internet connection and MFA environment."
} else {
    Write-Host "[Done] English dictionary model downloaded."
}

Write-Host ""
Write-Host "[2/2] Downloading English acoustic model..."
& conda run -n mfa mfa model download acoustic english_us_arpa
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Error] Failed to download English acoustic model (exit code: $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Please check your internet connection and MFA environment."
} else {
    Write-Host "[Done] English acoustic model downloaded."
}

Write-Host ""
Ask-Continue

# ============================================================
# Completion screen
# ============================================================
Clear-Host
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "   Setup complete!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "All installation steps have been completed."
Write-Host ""
Write-Host "[Next steps]"
Write-Host "  1. Navigate to the KERT folder"
Write-Host "  2. Run: python main.py"
Write-Host ""
Write-Host "For more information, see README.md."
Write-Host ""
Read-Host "Press Enter to exit"
