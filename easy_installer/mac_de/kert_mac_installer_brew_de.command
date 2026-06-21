#!/bin/bash
# KERT macOS Setup-Installationsprogramm (Deutsch, mit Homebrew)
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

resolve_brew() {
    if command -v brew &>/dev/null; then
        command -v brew
    elif [ -f "/opt/homebrew/bin/brew" ]; then
        echo "/opt/homebrew/bin/brew"
    elif [ -f "/usr/local/bin/brew" ]; then
        echo "/usr/local/bin/brew"
    else
        echo ""
    fi
}

resolve_conda() {
    if command -v conda &>/dev/null; then
        command -v conda
        return
    fi

    local brew_cmd
    brew_cmd=$(resolve_brew)
    if [ -n "$brew_cmd" ]; then
        local brew_prefix
        brew_prefix=$("$brew_cmd" --prefix 2>/dev/null)
        local cask_conda="$brew_prefix/Caskroom/miniforge/base/bin/conda"
        if [ -f "$cask_conda" ]; then
            echo "$cask_conda"
            return
        fi
    fi

    for candidate in \
        "$HOME/miniforge3/bin/conda" \
        "$HOME/miniconda3/bin/conda" \
        "$HOME/anaconda3/bin/conda"; do
        if [ -f "$candidate" ]; then
            echo "$candidate"
            return
        fi
    done

    echo ""
}

# ============================================================
# Willkommensbildschirm
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   KERT Setup-Installationsprogramm (Deutsch / mit Homebrew)${NC}"
echo -e "${GREEN}   Dieses Skript richtet die KERT-Laufzeitumgebung ein.${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "[Installationsschritte]"
echo ""
echo "  Schritt 1  Homebrew pruefen und installieren"
echo "  Schritt 2  Python 3.12 installieren"
echo "  Schritt 3  Miniforge (conda) installieren"
echo "  Schritt 4  conda-PATH pruefen"
echo "  Schritt 5  Montreal Forced Aligner (MFA) installieren"
echo "  Schritt 6  FFmpeg installieren"
echo "  Schritt 7  textgrid / saxonche installieren"
echo "  Schritt 8  Deutsche MFA-Modelle herunterladen"
echo ""
echo "Nach jedem Schritt werden Sie gefragt, ob Sie fortfahren moechten."
echo "Druecken Sie N, um jederzeit abzubrechen."
echo ""
echo "Umgebung: $(uname -s) $(uname -r) (${ARCH})"
echo ""
read -rp "Druecken Sie Enter, um die Installation zu starten"

# ============================================================
# Schritt 1: Homebrew
# ============================================================
write_header "Schritt 1 / 8  :  Homebrew pruefen und installieren"

BREW_CMD=$(resolve_brew)

if [ -n "$BREW_CMD" ]; then
    echo "[OK] Homebrew ist bereits installiert. Wird uebersprungen."
    "$BREW_CMD" --version
else
    echo "Homebrew nicht gefunden. Offizieller Installer wird ausgefuehrt."
    echo ""
    echo "Hinweis: Ihr Systempasswort wird benoetigt."
    echo "         Xcode Command Line Tools werden ggf. automatisch installiert."
    echo ""

    if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
        echo ""
        echo "[Fertig] Homebrew wurde erfolgreich installiert."

        if [ "$ARCH" = "arm64" ] && [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            add_to_path_persistent "/opt/homebrew/bin"
        fi

        BREW_CMD=$(resolve_brew)
        if [ -n "$BREW_CMD" ]; then
            "$BREW_CMD" --version
        fi
    else
        echo ""
        echo -e "${RED}[Fehler] Homebrew-Installation fehlgeschlagen.${NC}"
        echo "Bitte manuell installieren:"
        echo "  https://brew.sh/"
        echo ""
    fi

    echo "[3/3] pdfplumber Pillow wird installiert..."
    if $PY_CMD -m pip install --break-system-packages pdfplumber Pillow; then
        echo "[Fertig] pdfplumber Pillow wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] pdfplumber Pillow-Installation fehlgeschlagen.${NC}"
    fi
fi

ask_continue

# ============================================================
# Schritt 2: Python 3.12
# ============================================================
write_header "Schritt 2 / 8  :  Python 3.12 installieren"

BREW_CMD=$(resolve_brew)

if python3.12 --version &>/dev/null; then
    echo "[OK] Python 3.12 ist bereits installiert. Wird uebersprungen."
    python3.12 --version
elif [ -z "$BREW_CMD" ]; then
    echo -e "${RED}[Fehler] Homebrew nicht gefunden. Bitte Schritt 1 pruefen.${NC}"
else
    echo "Python 3.12 nicht gefunden. Installation ueber Homebrew..."
    echo ""
    if "$BREW_CMD" install python@3.12; then
        echo ""
        echo "[Fertig] Python 3.12 wurde erfolgreich installiert."
        BREW_PREFIX=$("$BREW_CMD" --prefix)
        add_to_path_persistent "$BREW_PREFIX/bin"
        python3.12 --version 2>/dev/null || true
    else
        echo ""
        echo -e "${RED}[Fehler] Python 3.12-Installation fehlgeschlagen.${NC}"
        echo "Bitte pruefen Sie, ob Homebrew korrekt installiert ist."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Schritt 3: Miniforge (conda)
# ============================================================
write_header "Schritt 3 / 8  :  Miniforge (conda) installieren"

BREW_CMD=$(resolve_brew)
CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda ist bereits verfuegbar. Wird uebersprungen."
    "$CONDA_CMD" --version
elif [ -z "$BREW_CMD" ]; then
    echo -e "${RED}[Fehler] Homebrew nicht gefunden. Bitte Schritt 1 pruefen.${NC}"
else
    echo "Miniforge nicht gefunden. Installation ueber Homebrew..."
    echo "(Dieser Vorgang kann mehrere Minuten dauern.)"
    echo ""
    if "$BREW_CMD" install --cask miniforge; then
        echo ""
        echo "[Fertig] Miniforge wurde erfolgreich installiert."
        BREW_PREFIX=$("$BREW_CMD" --prefix)
        CASK_CONDA_BIN="$BREW_PREFIX/Caskroom/miniforge/base/bin"
        if [ -d "$CASK_CONDA_BIN" ]; then
            export PATH="$CASK_CONDA_BIN:$PATH"
            echo "PATH fuer diese Sitzung aktualisiert."
        fi
        CONDA_CMD=$(resolve_conda)
        if [ -n "$CONDA_CMD" ]; then
            "$CONDA_CMD" --version
        fi
    else
        echo ""
        echo -e "${RED}[Fehler] Miniforge-Installation fehlgeschlagen.${NC}"
        echo "Bitte pruefen Sie, ob Homebrew korrekt installiert ist."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Schritt 4: conda-PATH pruefen
# ============================================================
write_header "Schritt 4 / 8  :  conda-PATH pruefen"

CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda ist verfuegbar."
    "$CONDA_CMD" --version

    CONDA_BIN_DIR=$(dirname "$CONDA_CMD")
    shell_profile=""
    if [[ "$SHELL" == *"zsh"* ]]; then
        shell_profile="$HOME/.zshrc"
    else
        shell_profile="$HOME/.bash_profile"
    fi

    if ! grep -qF "$CONDA_BIN_DIR" "$shell_profile" 2>/dev/null && \
       ! grep -q "conda initialize" "$shell_profile" 2>/dev/null; then
        add_to_path_persistent "$CONDA_BIN_DIR"
    else
        echo "[OK] Shellprofil oder conda-Initialisierung ist bereits konfiguriert."
    fi
else
    echo -e "${YELLOW}[Warnung] conda nicht gefunden.${NC}"
    echo "Bitte zu Schritt 3 zurueckkehren und Miniforge installieren."
    echo ""
fi

ask_continue

# ============================================================
# Schritt 5: Montreal Forced Aligner (MFA)
# ============================================================
write_header "Schritt 5 / 8  :  Montreal Forced Aligner installieren"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Fehler] conda nicht gefunden. Bitte Schritte 3 und 4 pruefen.${NC}"
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
# Schritt 6: FFmpeg
# ============================================================
write_header "Schritt 6 / 8  :  FFmpeg installieren"

BREW_CMD=$(resolve_brew)

if command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg ist bereits im PATH registriert. Wird uebersprungen."
    ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1
elif [ -z "$BREW_CMD" ]; then
    echo -e "${RED}[Fehler] Homebrew nicht gefunden. Bitte Schritt 1 pruefen.${NC}"
else
    echo "FFmpeg nicht gefunden. Installation ueber Homebrew..."
    echo ""
    if "$BREW_CMD" install ffmpeg; then
        echo ""
        echo "[Fertig] FFmpeg wurde erfolgreich installiert."
        ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1 || true
    else
        echo ""
        echo -e "${RED}[Fehler] FFmpeg-Installation fehlgeschlagen.${NC}"
        echo "Bitte pruefen Sie, ob Homebrew korrekt installiert ist."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Schritt 7: textgrid / saxonche
# ============================================================
write_header "Schritt 7 / 8  :  textgrid / saxonche installieren"

PY_CMD=""
if python3.12 --version &>/dev/null; then
    PY_CMD="python3.12"
elif python3 --version &>/dev/null; then
    PY_CMD="python3"
fi

BREW_CMD=$(resolve_brew)

if [ -z "$PY_CMD" ]; then
    echo -e "${RED}[Fehler] Python nicht gefunden. Bitte Schritt 2 pruefen.${NC}"
    echo ""
else
    echo "Verwendetes Python: $PY_CMD ($($PY_CMD --version))"
    echo ""

    echo "[1/4] python-tk (Tkinter) wird installiert..."
    if [ -z "$BREW_CMD" ]; then
        echo -e "${RED}[Fehler] Homebrew nicht gefunden. Bitte Schritt 1 pruefen.${NC}"
    elif "$BREW_CMD" install python-tk@3.12; then
        echo "[Fertig] python-tk wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] python-tk-Installation fehlgeschlagen.${NC}"
        echo "Dies kann verhindern, dass die GUI (tkinterdnd2) startet."
    fi

    echo ""

    echo "[2/4] textgrid wird installiert..."
    if $PY_CMD -m pip install --break-system-packages textgrid; then
        echo "[Fertig] textgrid wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] textgrid-Installation fehlgeschlagen.${NC}"
    fi

    echo ""

    echo "[3/4] saxonche wird installiert..."
    if [ "$ARCH" = "arm64" ]; then
        echo ""
        echo -e "${YELLOW}[Warnung] Apple Silicon (ARM64) Mac erkannt.${NC}"
        echo "saxonche ist fuer ARM64 macOS auf PyPI nicht verfuegbar und kann"
        echo "nicht automatisch installiert werden."
        echo ""
        echo "saxonche wird nicht benoetigt, wenn nur CommonMark (.md)-Eingabe verwendet wird."
    elif $PY_CMD -m pip install --break-system-packages saxonche; then
        echo "[Fertig] saxonche wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] saxonche-Installation fehlgeschlagen.${NC}"
        echo "Bitte Internetverbindung und Python-Version pruefen."
    fi

    echo ""

    echo "[4/4] tkinterdnd2 wird installiert..."
    if $PY_CMD -m pip install --break-system-packages "tkinterdnd2>=0.4.2,<0.5.0"; then
        echo "[Fertig] tkinterdnd2 wurde erfolgreich installiert."
    else
        echo -e "${RED}[Fehler] tkinterdnd2-Installation fehlgeschlagen.${NC}"
    fi
fi

ask_continue

# ============================================================
# Schritt 8: Deutsche MFA-Modelle
# ============================================================
write_header "Schritt 8 / 8  :  Deutsche MFA-Modelle herunterladen"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Fehler] conda nicht gefunden. Bitte Schritte 3 und 4 pruefen.${NC}"
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

# Ausfuehrungsrecht fuer start_kert.command setzen
KERT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$KERT_DIR/start_kert.command" ]; then
    chmod +x "$KERT_DIR/start_kert.command"
fi

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
echo "  2. start_kert.command im KERT-Ordner doppelklicken, um zu starten"
echo ""
echo "Weitere Informationen finden Sie in README.md."
echo ""
read -rp "Druecken Sie Enter zum Beenden"
