#Requires -Version 5.1
# KERT Windows Setup-Installationsprogramm (Deutsch)

$Host.UI.RawUI.WindowTitle = "KERT Setup-Installationsprogramm"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ============================================================
# Hilfsfunktionen
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
        $choice = (Read-Host "Zum naechsten Schritt fortfahren? (Y=Weiter / N=Abbrechen)").Trim().ToUpper()
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
    Write-Host "   Setup wurde abgebrochen" -ForegroundColor Yellow
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Das Setup wurde abgebrochen."
    Write-Host "Bereits abgeschlossene Schritte bleiben wirksam."
    Write-Host "Starten Sie dieses Skript erneut, um fortzufahren."
    Write-Host "(Abgeschlossene Schritte werden automatisch uebersprungen.)"
    Write-Host ""
    Read-Host "Druecken Sie Enter zum Beenden"
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
            Write-Host "[Fertig] Dauerhaft zum PATH hinzugefuegt: $NewPath"
        } catch {
            Write-Host "[Warnung] PATH konnte nicht dauerhaft gespeichert werden. Bitte manuell hinzufuegen:" -ForegroundColor Yellow
            Write-Host "          Ordner: $NewPath"
        }
    }
}

# ============================================================
# Willkommensbildschirm
# ============================================================
Clear-Host
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "   KERT Setup-Installationsprogramm (Deutsch)" -ForegroundColor Green
Write-Host "   Dieses Skript richtet die KERT-Laufzeitumgebung ein." -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "[Installationsschritte]"
Write-Host ""
Write-Host "  Schritt 1  Python 3.12 installieren"
Write-Host "  Schritt 2  Miniforge (conda) installieren"
Write-Host "  Schritt 3  conda-PATH pruefen"
Write-Host "  Schritt 4  Montreal Forced Aligner (MFA) installieren"
Write-Host "  Schritt 5  FFmpeg installieren"
Write-Host "  Schritt 6  textgrid / saxonche installieren"
Write-Host "  Schritt 7  Deutsche MFA-Modelle herunterladen"
Write-Host ""
Write-Host "Nach jedem Schritt werden Sie gefragt, ob Sie fortfahren moechten."
Write-Host "Druecken Sie N, um jederzeit abzubrechen."
Write-Host ""
Read-Host "Druecken Sie Enter, um die Installation zu starten"

# ============================================================
# Schritt 1: Python 3.12
# ============================================================
Write-Header "Schritt 1 / 7  :  Python 3.12 installieren"

$pyOk = $false
try {
    $pyVer = & py -3.12 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python 3.12 ist bereits installiert. Wird uebersprungen."
        Write-Host $pyVer
        $pyOk = $true
    }
} catch {}

if (-not $pyOk) {
    Write-Host "Python 3.12 nicht gefunden. Wird heruntergeladen und installiert..."
    Write-Host ""
    $pyInstaller = "$env:TEMP\python-3.12.10-amd64.exe"

    Write-Host "Wird heruntergeladen..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' `
            -OutFile $pyInstaller -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[Fehler] Download des Python-Installationsprogramms fehlgeschlagen." -ForegroundColor Red
        Write-Host "Bitte manuell herunterladen:"
        Write-Host "  https://www.python.org/downloads/release/python-31210/"
        Write-Host "  Datei: python-3.12.10-amd64.exe"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $pyInstaller)) {
        Write-Host "Download abgeschlossen. Installation wird gestartet (bitte warten)..."
        $result = Start-Process -FilePath $pyInstaller `
            -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "[Fehler] Python-Installation fehlgeschlagen (Exit-Code: $($result.ExitCode))." -ForegroundColor Red
            Write-Host "Bitte manuell installieren:"
            Write-Host "  https://www.python.org/downloads/release/python-31210/"
            Write-Host ""
        } else {
            $pyPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
            $pyScripts = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
            $env:PATH = "$pyPath;$pyScripts;$env:PATH"
            Write-Host ""
            Write-Host "[Fertig] Python 3.12 wurde erfolgreich installiert."
            try { & py -3.12 --version 2>&1 | Write-Host } catch {}
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Schritt 2: Miniforge
# ============================================================
Write-Header "Schritt 2 / 7  :  Miniforge (conda) installieren"

$condaCmd = Get-Command conda -ErrorAction SilentlyContinue

if ($null -ne $condaCmd) {
    Write-Host "[OK] conda ist bereits verfuegbar. Wird uebersprungen."
    & conda --version
} elseif (Test-Path "$env:USERPROFILE\miniforge3\Scripts\conda.exe") {
    Write-Host "[OK] Miniforge ist bereits installiert. PATH wird aktualisiert."
    $env:PATH = "$env:USERPROFILE\miniforge3\Scripts;$env:USERPROFILE\miniforge3\condabin;$env:PATH"
    Write-Host "PATH fuer diese Sitzung aktualisiert."
} else {
    Write-Host "Miniforge nicht gefunden. Wird heruntergeladen und installiert..."
    Write-Host ""
    $mfInstaller = "$env:TEMP\Miniforge3-Windows-x86_64.exe"

    Write-Host "Wird heruntergeladen..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe' `
            -OutFile $mfInstaller -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[Fehler] Download von Miniforge fehlgeschlagen." -ForegroundColor Red
        Write-Host "Bitte manuell herunterladen:"
        Write-Host "  https://github.com/conda-forge/miniforge/releases/latest"
        Write-Host "  Datei: Miniforge3-Windows-x86_64.exe"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $mfInstaller)) {
        Write-Host "Download abgeschlossen. Installation wird gestartet (bitte warten)..."
        $result = Start-Process -FilePath $mfInstaller `
            -ArgumentList "/S /D=$env:USERPROFILE\miniforge3" -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "[Fehler] Miniforge-Installation fehlgeschlagen (Exit-Code: $($result.ExitCode))." -ForegroundColor Red
            Write-Host "Bitte manuell installieren:"
            Write-Host "  https://github.com/conda-forge/miniforge/releases/latest"
            Write-Host ""
        } else {
            Write-Host "[Fertig] Miniforge wurde erfolgreich installiert."
            $env:PATH = "$env:USERPROFILE\miniforge3\Scripts;$env:USERPROFILE\miniforge3\condabin;$env:PATH"
            Write-Host "PATH fuer diese Sitzung aktualisiert."
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Schritt 3: conda PATH
# ============================================================
Write-Header "Schritt 3 / 7  :  conda-PATH pruefen"

if ($null -ne (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] conda ist im PATH registriert."
    & conda --version
} else {
    Write-Host "conda nicht im PATH. Suche nach conda-Ordner..."
    Write-Host ""

    $condaFound = $null
    $condaScripts = $null

    if (Test-Path "$env:USERPROFILE\miniforge3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\miniforge3"
        $condaScripts = "$env:USERPROFILE\miniforge3\Scripts"
        Write-Host "Gefunden: $env:USERPROFILE\miniforge3"
    } elseif (Test-Path "$env:USERPROFILE\miniconda3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\miniconda3"
        $condaScripts = "$env:USERPROFILE\miniconda3\Scripts"
        Write-Host "Gefunden: $env:USERPROFILE\miniconda3"
    } elseif (Test-Path "$env:USERPROFILE\Anaconda3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\Anaconda3"
        $condaScripts = "$env:USERPROFILE\Anaconda3\Scripts"
        Write-Host "Gefunden: $env:USERPROFILE\Anaconda3"
    }

    if ($null -ne $condaFound) {
        Add-ToUserPath $condaScripts
        $env:PATH = "$condaScripts;$condaFound\condabin;$env:PATH"
        Write-Host "PATH fuer diese Sitzung aktualisiert."
    } else {
        Write-Host "[Warnung] conda-Ausfuehrungsdatei nicht gefunden." -ForegroundColor Yellow
        Write-Host "Bitte zu Schritt 2 zurueckkehren und Miniforge installieren."
        Write-Host ""
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Schritt 4: Montreal Forced Aligner (MFA)
# ============================================================
Write-Header "Schritt 4 / 7  :  Montreal Forced Aligner installieren"

Write-Host "conda-Umgebung (mfa) wird geprueft..."
Write-Host ""

& conda run -n mfa echo check 2>&1 | Out-Null
$mfaEnvExists = ($LASTEXITCODE -eq 0)

if ($mfaEnvExists) {
    Write-Host "conda-Umgebung ""mfa"" vorhanden. MFA wird geprueft..."
    & conda run -n mfa mfa version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] MFA ist bereits installiert. Wird uebersprungen."
        & conda run -n mfa mfa version
    } else {
        Write-Host "MFA nicht gefunden. Installation in mfa-Umgebung..."
        & conda install -n mfa -c conda-forge montreal-forced-aligner -y
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "[Fehler] MFA-Installation fehlgeschlagen." -ForegroundColor Red
            Write-Host "Bitte pruefen Sie, ob conda korrekt installiert ist und eine Internetverbindung besteht."
            Write-Host ""
        } else {
            Write-Host ""
            Write-Host "[Fertig] Montreal Forced Aligner wurde erfolgreich installiert."
        }
    }
} else {
    Write-Host "conda-Umgebung ""mfa"" nicht vorhanden. Wird neu erstellt und installiert..."
    Write-Host "(Dieser Vorgang kann mehrere Minuten dauern.)"
    & conda create -n mfa -c conda-forge montreal-forced-aligner -y
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[Fehler] MFA-Installation fehlgeschlagen." -ForegroundColor Red
        Write-Host "Bitte pruefen Sie, ob conda korrekt installiert ist und eine Internetverbindung besteht."
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[Fertig] Montreal Forced Aligner wurde erfolgreich installiert."
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Schritt 5: FFmpeg
# ============================================================
Write-Header "Schritt 5 / 7  :  FFmpeg installieren"

if ($null -ne (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] FFmpeg ist bereits im PATH registriert. Wird uebersprungen."
    & ffmpeg -version 2>&1 | Select-String -Pattern "ffmpeg version" | ForEach-Object { Write-Host $_ }
} elseif (Test-Path "$env:USERPROFILE\ffmpeg\bin\ffmpeg.exe") {
    Write-Host "[OK] FFmpeg ist bereits installiert. PATH wird aktualisiert."
    Add-ToUserPath "$env:USERPROFILE\ffmpeg\bin"
} else {
    Write-Host "FFmpeg nicht gefunden. Wird heruntergeladen und installiert..."
    Write-Host ""
    $ffZip = "$env:TEMP\ffmpeg-latest.zip"
    $ffWork = "$env:TEMP\ffmpeg_work"

    Write-Host "Wird heruntergeladen (kann einige Minuten dauern)..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' `
            -OutFile $ffZip -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[Fehler] Download von FFmpeg fehlgeschlagen." -ForegroundColor Red
        Write-Host "Bitte manuell herunterladen:"
        Write-Host "  https://ffmpeg.org/download.html"
        Write-Host "  oder https://github.com/BtbN/FFmpeg-Builds/releases"
        Write-Host "  ffmpeg.exe in einen Ordner legen und zum PATH hinzufuegen."
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $ffZip)) {
        Write-Host "Download abgeschlossen. Wird entpackt..."
        if (Test-Path $ffWork) { Remove-Item $ffWork -Recurse -Force }
        New-Item -ItemType Directory -Path $ffWork | Out-Null

        $expandOk = $true
        try {
            Expand-Archive -LiteralPath $ffZip -DestinationPath $ffWork -Force -ErrorAction Stop
        } catch {
            $expandOk = $false
            Write-Host ""
            Write-Host "[Fehler] ZIP-Extraktion fehlgeschlagen." -ForegroundColor Red
            Write-Host "Bitte manuell installieren: https://ffmpeg.org/download.html"
            Write-Host ""
        }

        if ($expandOk) {
            $ffExtracted = Get-ChildItem -Path $ffWork -Directory | Select-Object -First 1
            if ($null -eq $ffExtracted) {
                Write-Host ""
                Write-Host "[Fehler] Entpackter Ordner nicht gefunden." -ForegroundColor Red
                Write-Host "Bitte manuell installieren: https://ffmpeg.org/download.html"
                Write-Host ""
            } else {
                Write-Host "Wird kopiert..."
                $destBin = "$env:USERPROFILE\ffmpeg\bin"
                New-Item -ItemType Directory -Path $destBin -Force | Out-Null
                Copy-Item "$($ffExtracted.FullName)\bin\*" $destBin -Force
                Add-ToUserPath $destBin
                Write-Host ""
                Write-Host "[Fertig] FFmpeg wurde erfolgreich installiert."
                & ffmpeg -version 2>&1 | Select-String -Pattern "ffmpeg version" | ForEach-Object { Write-Host $_ }
            }
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Schritt 6: textgrid / saxonche
# ============================================================
Write-Header "Schritt 6 / 7  :  textgrid / saxonche installieren"

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
    Write-Host "[Fehler] Python nicht gefunden. Bitte Schritt 1 pruefen." -ForegroundColor Red
    Write-Host ""
} else {
    Write-Host "Verwendetes Python: $pyExe ($( & $pyExe.Split()[0] $pyExe.Split()[1..99] --version 2>&1 ))"
    Write-Host ""

    $pyArgs = $pyExe.Split()

    Write-Host "[1/2] textgrid wird installiert..."
    & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "textgrid"))
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[Fertig] textgrid wurde erfolgreich installiert."
    } else {
        Write-Host "[Fehler] textgrid-Installation fehlgeschlagen." -ForegroundColor Red
    }

    Write-Host ""

    Write-Host "[2/2] saxonche wird installiert..."
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "ARM64") {
        Write-Host ""
        Write-Host "[Warnung] ARM64-Windows erkannt." -ForegroundColor Yellow
        Write-Host "saxonche ist fuer ARM64 Windows auf PyPI nicht verfuegbar."
        Write-Host ""
        Write-Host "[Workaround] Falls XML-Eingabe benoetigt wird:"
        Write-Host "  1. x64-Python von der Python-Website herunterladen:"
        Write-Host "     https://www.python.org/downloads/release/python-31210/"
        Write-Host "     Datei: python-3.12.10-amd64.exe"
        Write-Host "  2. Nach der Installation ausfuehren:"
        Write-Host "     py -3.12-64 -m pip install saxonche"
        Write-Host ""
        Write-Host "saxonche ist fuer CommonMark (.md)-Eingabe nicht erforderlich."
    } else {
        & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "saxonche"))
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[Fertig] saxonche wurde erfolgreich installiert."
        } else {
            Write-Host "[Fehler] saxonche-Installation fehlgeschlagen." -ForegroundColor Red
            Write-Host "Bitte Internetverbindung und Python-Version (3.8 oder hoeher) pruefen."
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# Schritt 7: Deutsche MFA-Modelle
# ============================================================
Write-Header "Schritt 7 / 7  :  Deutsche MFA-Modelle herunterladen"

Write-Host "Deutsche MFA-Modelle (Woerterbuch und akustisches Modell) werden heruntergeladen."
Write-Host "(Die Dateien sind gross - dieser Vorgang kann mehrere Minuten dauern.)"
Write-Host ""

Write-Host "[1/2] Deutsches Woerterbuchmodell wird heruntergeladen..."
& conda run -n mfa mfa model download dictionary german_mfa
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Fehler] Download des deutschen Woerterbuchmodells fehlgeschlagen (Exit-Code: $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Bitte Internetverbindung und MFA-Umgebung pruefen."
} else {
    Write-Host "[Fertig] Deutsches Woerterbuchmodell heruntergeladen."
}

Write-Host ""
Write-Host "[2/2] Deutsches akustisches Modell wird heruntergeladen..."
& conda run -n mfa mfa model download acoustic german_mfa
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Fehler] Download des deutschen akustischen Modells fehlgeschlagen (Exit-Code: $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Bitte Internetverbindung und MFA-Umgebung pruefen."
} else {
    Write-Host "[Fertig] Deutsches akustisches Modell heruntergeladen."
}

Write-Host ""
Ask-Continue

# ============================================================
# Abschlussbildschirm
# ============================================================
Clear-Host
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "   Setup abgeschlossen!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Alle Installationsschritte wurden abgeschlossen."
Write-Host ""
Write-Host "[Naechste Schritte]"
Write-Host "  1. Zum KERT-Ordner navigieren"
Write-Host "  2. Ausfuehren: python main.py"
Write-Host ""
Write-Host "Weitere Informationen finden Sie in README.md."
Write-Host ""
Read-Host "Druecken Sie Enter zum Beenden"
