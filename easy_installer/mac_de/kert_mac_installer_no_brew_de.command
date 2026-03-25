#!/bin/bash
# KERT macOS Setup-Installationsprogramm (Deutsch, ohne Homebrew)
# Unterstuetzt: macOS 11 oder neuer (Apple Silicon / Intel)

# ============================================================
# Farbdefinitionen
# ============================================================
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ARCH=$(uname -m)   # arm64 oder x86_64
CONDA_DIR="$HOME/miniforge3"
CONDA_BIN="$CONDA_DIR/bin/conda"

# ============================================================
# Hilfsfunktionen
# ============================================================

write_header() {
    clear
    echo ""
    echo -e "${CYAN}-----------------------------------------------------------${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}-----------------------------------------------------------${NC}"
    echo ""
}

ask_continue() {
    echo ""
    local _ac_choice
    while true; do
        read -rp "Zum naechsten Schritt fortfahren? (Y=Weiter / N=Abbrechen): " _ac_choice
        _ac_choice=$(echo "$_ac_choice" | tr '[:lower:]' '[:upper:]')
        [[ "$_ac_choice" == "Y" || "$_ac_choice" == "N" ]] && break
    done
    if [[ "$_ac_choice" == "N" ]]; then
        show_abort
        exit 1
    fi
}

show_abort() {
    clear
    echo ""
    echo -e "${YELLOW}===========================================================${NC}"
    echo -e "${YELLOW}   Setup wurde abgebrochen${NC}"
    echo -e "${YELLOW}===========================================================${NC}"
    echo ""
    echo "Das Setup wurde abgebrochen."
    echo "Bereits abgeschlossene Schritte bleiben wirksam."
    echo "Starten Sie dieses Skript erneut, um fortzufahren."
    echo "(Abgeschlossene Schritte werden automatisch uebersprungen.)"
    echo ""
    read -rp "Druecken Sie Enter zum Beenden"
}

add_to_path_persistent() {
    local new_path="$1"
    local shell_profile
    if [[ "$SHELL" == *"zsh"* ]]; then
        shell_profile="$HOME/.zshrc"
    else
        shell_profile="$HOME/.bash_profile"
    fi

    if ! grep -qF "$new_path" "$shell_profile" 2>/dev/null; then
        echo "" >> "$shell_profile"
        echo "export PATH=\"$new_path:\$PATH\"" >> "$shell_profile"
        echo "[Fertig] Dauerhaft zum PATH hinzugefuegt: $new_path"
        echo "         Profildatei: $shell_profile"
    else
        echo "[OK] Bereits im PATH registriert: $new_path"
    fi

    export PATH="$new_path:$PATH"
}

resolve_conda() {
    if command -v conda &>/dev/null; then
        command -v conda
    elif [ -f "$CONDA_BIN" ]; then
        echo "$CONDA_BIN"
    else
        echo ""
    fi
}

# ============================================================
# Willkommensbildschirm
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   KERT Setup-Installationsprogramm (Deutsch / ohne Homebrew)${NC}"
echo -e "${GREEN}   Dieses Skript richtet die KERT-Laufzeitumgebung ein.${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "[Installationsschritte]"
echo ""
echo "  Schritt 1  Python 3.12 installieren"
echo "  Schritt 2  Miniforge (conda) installieren"
echo "  Schritt 3  conda-PATH pruefen"
echo "  Schritt 4  Montreal Forced Aligner (MFA) installieren"
echo "  Schritt 5  FFmpeg installieren"
echo "  Schritt 6  textgrid / saxonche installieren"
echo "  Schritt 7  Deutsche MFA-Modelle herunterladen"
echo ""
echo "Nach jedem Schritt werden Sie gefragt, ob Sie fortfahren moechten."
echo "Druecken Sie N, um jederzeit abzubrechen."
echo ""
echo "Umgebung: $(uname -s) $(uname -r) (${ARCH})"
echo ""
read -rp "Druecken Sie Enter, um die Installation zu starten"

# ============================================================
# Schritt 1: Python 3.12
# ============================================================
write_header "Schritt 1 / 7  :  Python 3.12 installieren"

if python3.12 --version &>/dev/null; then
    echo "[OK] Python 3.12 ist bereits installiert. Wird uebersprungen."
    python3.12 --version
else
    echo "Python 3.12 nicht gefunden. Wird heruntergeladen und installiert..."
    echo ""
    echo "Hinweis: Waehrend der Installation wird Ihr Systempasswort benoetigt."
    echo ""

    PY_PKG="/tmp/python-3.12.10-macos11.pkg"
    PY_URL="https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg"

    echo "Wird heruntergeladen..."
    if curl -L --progress-bar -o "$PY_PKG" "$PY_URL"; then
        echo "Download abgeschlossen. Installation wird gestartet..."
        echo "(Ihr Systempasswort wird abgefragt.)"
        echo ""
        if sudo installer -pkg "$PY_PKG" -target /; then
            echo ""
            echo "[Fertig] Python 3.12 wurde erfolgreich installiert."
            PY312_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin"
            add_to_path_persistent "$PY312_BIN"
            python3.12 --version 2>/dev/null || true
        else
            echo ""
            echo -e "${RED}[Fehler] Python-Installation fehlgeschlagen.${NC}"
            echo "Bitte manuell installieren:"
            echo "  https://www.python.org/downloads/release/python-31210/"
            echo "  Datei: python-3.12.10-macos11.pkg"
            echo ""
        fi
    else
        echo ""
        echo -e "${RED}[Fehler] Download des Python-Installationsprogramms fehlgeschlagen.${NC}"
        echo "Bitte manuell herunterladen:"
        echo "  https://www.python.org/downloads/release/python-31210/"
        echo "  Datei: python-3.12.10-macos11.pkg"
        echo ""
    fi
fi

ask_continue

# ============================================================
# Schritt 2: Miniforge (conda)
# ============================================================
write_header "Schritt 2 / 7  :  Miniforge (conda) installieren"

if command -v conda &>/dev/null; then
    echo "[OK] conda ist bereits verfuegbar. Wird uebersprungen."
    conda --version
elif [ -f "$CONDA_BIN" ]; then
    echo "[OK] Miniforge ist bereits installiert. PATH wird aktualisiert."
    export PATH="$CONDA_DIR/bin:$PATH"
    echo "PATH fuer diese Sitzung aktualisiert."
else
    echo "Miniforge nicht gefunden. Wird heruntergeladen und installiert..."
    echo ""

    if [ "$ARCH" = "arm64" ]; then
        MF_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
        MF_FILE="/tmp/Miniforge3-MacOSX-arm64.sh"
    else
        MF_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh"
        MF_FILE="/tmp/Miniforge3-MacOSX-x86_64.sh"
    fi

    echo "Architektur: ${ARCH}"
    echo "Wird heruntergeladen..."

    if curl -L --progress-bar -o "$MF_FILE" "$MF_URL"; then
        chmod +x "$MF_FILE"
        echo "Download abgeschlossen. Installation wird gestartet..."
        echo "(Installationsziel: $CONDA_DIR)"
        echo ""
        if bash "$MF_FILE" -b -p "$CONDA_DIR"; then
            echo ""
            echo "[Fertig] Miniforge wurde erfolgreich installiert."
            export PATH="$CONDA_DIR/bin:$PATH"
            echo "PATH fuer diese Sitzung aktualisiert."
        else
            echo ""
            echo -e "${RED}[Fehler] Miniforge-Installation fehlgeschlagen.${NC}"
            echo "Bitte manuell installieren:"
            echo "  https://github.com/conda-forge/miniforge/releases/latest"
            echo ""
        fi
    else
        echo ""
        echo -e "${RED}[Fehler] Download von Miniforge fehlgeschlagen.${NC}"
        echo "Bitte manuell herunterladen:"
        echo "  https://github.com/conda-forge/miniforge/releases/latest"
        echo ""
    fi
fi

ask_continue

# ============================================================
# Schritt 3: conda-PATH pruefen
# ============================================================
write_header "Schritt 3 / 7  :  conda-PATH pruefen"

CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda ist verfuegbar."
    "$CONDA_CMD" --version

    if ! grep -qF "$CONDA_DIR/bin" "${HOME}/.zshrc" 2>/dev/null && \
       ! grep -qF "$CONDA_DIR/bin" "${HOME}/.bash_profile" 2>/dev/null; then
        add_to_path_persistent "$CONDA_DIR/bin"
    else
        echo "[OK] PATH-Registrierung ist bereits abgeschlossen."
    fi
else
    echo "conda nicht im PATH. Suche nach installiertem conda..."
    echo ""
    FOUND_CONDA=""
    for candidate in \
        "$HOME/miniforge3/bin/conda" \
        "$HOME/miniconda3/bin/conda" \
        "$HOME/anaconda3/bin/conda"; do
        if [ -f "$candidate" ]; then
            FOUND_CONDA="$candidate"
            FOUND_DIR=$(dirname "$candidate")
            echo "Gefunden: $candidate"
            break
        fi
    done

    if [ -n "$FOUND_CONDA" ]; then
        CONDA_BIN="$FOUND_CONDA"
        CONDA_DIR=$(dirname "$FOUND_DIR")
        add_to_path_persistent "$FOUND_DIR"
        "$CONDA_BIN" --version
    else
        echo -e "${YELLOW}[Warnung] conda-Ausfuehrungsdatei nicht gefunden.${NC}"
        echo "Bitte zu Schritt 2 zurueckkehren und Miniforge installieren."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Schritt 4: Montreal Forced Aligner (MFA)
# ============================================================
write_header "Schritt 4 / 7  :  Montreal Forced Aligner installieren"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Fehler] conda nicht gefunden. Bitte Schritte 2 und 3 pruefen.${NC}"
else
    echo "conda-Umgebung (mfa) wird geprueft..."
    echo ""

    if "$CONDA_CMD" run -n mfa echo check &>/dev/null 2>&1; then
        if "$CONDA_CMD" run -n mfa mfa version &>/dev/null 2>&1; then
            echo "[OK] MFA ist bereits installiert. Wird uebersprungen."
            "$CONDA_CMD" run -n mfa mfa version
        else
            echo "MFA nicht gefunden. Installation in mfa-Umgebung..."
            if "$CONDA_CMD" install -n mfa -c conda-forge montreal-forced-aligner -y; then
                echo ""
                echo "[Fertig] Montreal Forced Aligner wurde erfolgreich installiert."
            else
                echo ""
                echo -e "${RED}[Fehler] MFA-Installation fehlgeschlagen.${NC}"
                echo "Bitte pruefen Sie, ob conda korrekt installiert ist und eine Internetverbindung besteht."
                echo ""
            fi
        fi
    else
        echo "conda-Umgebung \"mfa\" nicht vorhanden. Wird neu erstellt und installiert..."
        echo "(Dieser Vorgang kann mehrere Minuten dauern.)"
        if "$CONDA_CMD" create -n mfa -c conda-forge montreal-forced-aligner -y; then
            echo ""
            echo "[Fertig] Montreal Forced Aligner wurde erfolgreich installiert."
        else
            echo ""
            echo -e "${RED}[Fehler] MFA-Installation fehlgeschlagen.${NC}"
            echo "Bitte pruefen Sie, ob conda korrekt installiert ist und eine Internetverbindung besteht."
            echo ""
        fi
    fi
fi

ask_continue

# ============================================================
# Schritt 5: FFmpeg
# ============================================================
write_header "Schritt 5 / 7  :  FFmpeg installieren"

if command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg ist bereits im PATH registriert. Wird uebersprungen."
    ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1
elif [ -f "$CONDA_DIR/bin/ffmpeg" ]; then
    echo "[OK] FFmpeg ist bereits installiert (conda). PATH wird geprueft."
    add_to_path_persistent "$CONDA_DIR/bin"
else
    CONDA_CMD=$(resolve_conda)
    if [ -z "$CONDA_CMD" ]; then
        echo -e "${RED}[Fehler] conda nicht gefunden. Bitte FFmpeg manuell installieren.${NC}"
        echo "  https://evermeet.cx/ffmpeg/"
        echo "  Die heruntergeladene ffmpeg-Datei nach /usr/local/bin/ kopieren."
    else
        echo "FFmpeg nicht gefunden. Installation ueber conda-forge..."
        echo "(Dieser Vorgang kann mehrere Minuten dauern.)"
        echo ""
        if "$CONDA_CMD" install -c conda-forge ffmpeg -y; then
            echo ""
            echo "[Fertig] FFmpeg wurde erfolgreich installiert."
            add_to_path_persistent "$CONDA_DIR/bin"
            ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1 || true
        else
            echo ""
            echo -e "${RED}[Fehler] FFmpeg-Installation fehlgeschlagen.${NC}"
            echo "Bitte manuell installieren:"
            echo "  https://evermeet.cx/ffmpeg/"
            echo "  Die heruntergeladene ffmpeg-Datei nach /usr/local/bin/ kopieren."
            echo ""
        fi
    fi
fi

ask_continue

# ============================================================
# Schritt 6: textgrid / saxonche
# ============================================================
write_header "Schritt 6 / 7  :  textgrid / saxonche installieren"

PY_CMD=""
if python3.12 --version &>/dev/null; then
    PY_CMD="python3.12"
elif python3 --version &>/dev/null; then
    PY_CMD="python3"
fi

if [ -z "$PY_CMD" ]; then
    echo -e "${RED}[Fehler] Python nicht gefunden. Bitte Schritt 1 pruefen.${NC}"
    echo ""
else
    echo "Verwendetes Python: $PY_CMD ($($PY_CMD --version))"
    echo ""

    echo "[1/2] textgrid wird installiert..."
    if $PY_CMD -m pip install textgrid; then
        echo "[Fertig] textgrid wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] textgrid-Installation fehlgeschlagen.${NC}"
    fi

    echo ""

    echo "[2/2] saxonche wird installiert..."
    if $PY_CMD -m pip install saxonche; then
        echo "[Fertig] saxonche wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] saxonche-Installation fehlgeschlagen.${NC}"
        echo "Bitte Internetverbindung und Python-Version pruefen."
    fi
fi

ask_continue

# ============================================================
# Schritt 7: Deutsche MFA-Modelle
# ============================================================
write_header "Schritt 7 / 7  :  Deutsche MFA-Modelle herunterladen"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Fehler] conda nicht gefunden. Bitte Schritte 2 und 3 pruefen.${NC}"
else
    echo "Deutsche MFA-Modelle (Woerterbuch und akustisches Modell) werden heruntergeladen."
    echo "(Die Dateien sind gross - dieser Vorgang kann mehrere Minuten dauern.)"
    echo ""

    echo "[1/2] Deutsches Woerterbuchmodell wird heruntergeladen..."
    if "$CONDA_CMD" run -n mfa mfa model download dictionary german_mfa; then
        echo "[Fertig] Deutsches Woerterbuchmodell heruntergeladen."
    else
        echo -e "${RED}[Fehler] Download des deutschen Woerterbuchmodells fehlgeschlagen.${NC}"
        echo "Bitte Internetverbindung und MFA-Umgebung pruefen."
    fi

    echo ""

    echo "[2/2] Deutsches akustisches Modell wird heruntergeladen..."
    if "$CONDA_CMD" run -n mfa mfa model download acoustic german_mfa; then
        echo "[Fertig] Deutsches akustisches Modell heruntergeladen."
    else
        echo -e "${RED}[Fehler] Download des deutschen akustischen Modells fehlgeschlagen.${NC}"
        echo "Bitte Internetverbindung und MFA-Umgebung pruefen."
    fi
fi

ask_continue

# ============================================================
# Abschlussbildschirm
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   Setup abgeschlossen!${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "Alle Installationsschritte wurden abgeschlossen."
echo ""
echo "[Naechste Schritte]"
echo "  1. Terminal neu starten (damit PATH-Aenderungen wirksam werden)"
echo "  2. Zum KERT-Ordner navigieren"
echo "  3. Ausfuehren: python3.12 main.py"
echo ""
echo "Weitere Informationen finden Sie in README.md."
echo ""
read -rp "Druecken Sie Enter zum Beenden"
