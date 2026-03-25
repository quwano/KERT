#!/bin/bash
# KERT macOS Setup Installer (English, no Homebrew)
# Supported: macOS 11 or later (Apple Silicon / Intel)

# ============================================================
# Color definitions
# ============================================================
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ARCH=$(uname -m)   # arm64 or x86_64
CONDA_DIR="$HOME/miniforge3"
CONDA_BIN="$CONDA_DIR/bin/conda"

# ============================================================
# Utility functions
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
        read -rp "Proceed to the next step? (Y=Continue / N=Abort): " _ac_choice
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
    echo -e "${YELLOW}   Setup aborted${NC}"
    echo -e "${YELLOW}===========================================================${NC}"
    echo ""
    echo "Setup has been aborted."
    echo "Any steps already completed remain effective."
    echo "Run this script again to resume from where you left off."
    echo "(Completed steps will be skipped automatically.)"
    echo ""
    read -rp "Press Enter to exit"
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
        echo "[Done] Permanently added to PATH: $new_path"
        echo "       Profile: $shell_profile"
    else
        echo "[OK] Already registered in PATH: $new_path"
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
# Welcome screen
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   KERT Setup Installer (English / no Homebrew)${NC}"
echo -e "${GREEN}   This script sets up the KERT runtime environment step by step.${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "[Installation Steps]"
echo ""
echo "  Step 1  Install Python 3.12"
echo "  Step 2  Install Miniforge (conda)"
echo "  Step 3  Verify conda PATH"
echo "  Step 4  Install Montreal Forced Aligner (MFA)"
echo "  Step 5  Install FFmpeg"
echo "  Step 6  Install textgrid / saxonche"
echo "  Step 7  Download English MFA models"
echo ""
echo "You will be asked to continue or abort after each step."
echo "Press N at any time to abort."
echo ""
echo "Environment: $(uname -s) $(uname -r) (${ARCH})"
echo ""
read -rp "Press Enter to start the installation"

# ============================================================
# Step 1: Python 3.12
# ============================================================
write_header "Step 1 / 7  :  Install Python 3.12"

if python3.12 --version &>/dev/null; then
    echo "[OK] Python 3.12 is already installed. Skipping."
    python3.12 --version
else
    echo "Python 3.12 not found. Downloading and installing..."
    echo ""
    echo "Note: Your system password will be required during installation."
    echo ""

    PY_PKG="/tmp/python-3.12.10-macos11.pkg"
    PY_URL="https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg"

    echo "Downloading..."
    if curl -L --progress-bar -o "$PY_PKG" "$PY_URL"; then
        echo "Download complete. Starting installation..."
        echo "(Your system password will be prompted.)"
        echo ""
        if sudo installer -pkg "$PY_PKG" -target /; then
            echo ""
            echo "[Done] Python 3.12 installation complete."
            PY312_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin"
            add_to_path_persistent "$PY312_BIN"
            python3.12 --version 2>/dev/null || true
        else
            echo ""
            echo -e "${RED}[Error] Python installation failed.${NC}"
            echo "Please install manually:"
            echo "  https://www.python.org/downloads/release/python-31210/"
            echo "  File: python-3.12.10-macos11.pkg"
            echo ""
        fi
    else
        echo ""
        echo -e "${RED}[Error] Failed to download the Python installer.${NC}"
        echo "Please download manually:"
        echo "  https://www.python.org/downloads/release/python-31210/"
        echo "  File: python-3.12.10-macos11.pkg"
        echo ""
    fi
fi

ask_continue

# ============================================================
# Step 2: Miniforge (conda)
# ============================================================
write_header "Step 2 / 7  :  Install Miniforge (conda)"

if command -v conda &>/dev/null; then
    echo "[OK] conda is already available. Skipping."
    conda --version
elif [ -f "$CONDA_BIN" ]; then
    echo "[OK] Miniforge is already installed. Updating PATH."
    export PATH="$CONDA_DIR/bin:$PATH"
    echo "PATH updated for this session."
else
    echo "Miniforge not found. Downloading and installing..."
    echo ""

    if [ "$ARCH" = "arm64" ]; then
        MF_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
        MF_FILE="/tmp/Miniforge3-MacOSX-arm64.sh"
    else
        MF_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh"
        MF_FILE="/tmp/Miniforge3-MacOSX-x86_64.sh"
    fi

    echo "Architecture: ${ARCH}"
    echo "Downloading..."

    if curl -L --progress-bar -o "$MF_FILE" "$MF_URL"; then
        chmod +x "$MF_FILE"
        echo "Download complete. Starting installation..."
        echo "(Install location: $CONDA_DIR)"
        echo ""
        if bash "$MF_FILE" -b -p "$CONDA_DIR"; then
            echo ""
            echo "[Done] Miniforge installation complete."
            export PATH="$CONDA_DIR/bin:$PATH"
            echo "PATH updated for this session."
        else
            echo ""
            echo -e "${RED}[Error] Miniforge installation failed.${NC}"
            echo "Please install manually:"
            echo "  https://github.com/conda-forge/miniforge/releases/latest"
            echo ""
        fi
    else
        echo ""
        echo -e "${RED}[Error] Failed to download Miniforge.${NC}"
        echo "Please download manually:"
        echo "  https://github.com/conda-forge/miniforge/releases/latest"
        echo ""
    fi
fi

ask_continue

# ============================================================
# Step 3: conda PATH
# ============================================================
write_header "Step 3 / 7  :  Verify conda PATH"

CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda is available."
    "$CONDA_CMD" --version

    if ! grep -qF "$CONDA_DIR/bin" "${HOME}/.zshrc" 2>/dev/null && \
       ! grep -qF "$CONDA_DIR/bin" "${HOME}/.bash_profile" 2>/dev/null; then
        add_to_path_persistent "$CONDA_DIR/bin"
    else
        echo "[OK] PATH registration is already complete."
    fi
else
    echo "conda not found in PATH. Searching for installed conda..."
    echo ""
    FOUND_CONDA=""
    for candidate in \
        "$HOME/miniforge3/bin/conda" \
        "$HOME/miniconda3/bin/conda" \
        "$HOME/anaconda3/bin/conda"; do
        if [ -f "$candidate" ]; then
            FOUND_CONDA="$candidate"
            FOUND_DIR=$(dirname "$candidate")
            echo "Found: $candidate"
            break
        fi
    done

    if [ -n "$FOUND_CONDA" ]; then
        CONDA_BIN="$FOUND_CONDA"
        CONDA_DIR=$(dirname "$FOUND_DIR")
        add_to_path_persistent "$FOUND_DIR"
        "$CONDA_BIN" --version
    else
        echo -e "${YELLOW}[Warning] conda executable not found.${NC}"
        echo "Please go back to Step 2 and install Miniforge."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Step 4: Montreal Forced Aligner (MFA)
# ============================================================
write_header "Step 4 / 7  :  Install Montreal Forced Aligner"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Error] conda not found. Please check Steps 2 and 3.${NC}"
else
    echo "Checking conda environment (mfa)..."
    echo ""

    if "$CONDA_CMD" run -n mfa echo check &>/dev/null 2>&1; then
        if "$CONDA_CMD" run -n mfa mfa version &>/dev/null 2>&1; then
            echo "[OK] MFA is already installed. Skipping."
            "$CONDA_CMD" run -n mfa mfa version
        else
            echo "MFA not found. Installing into mfa environment..."
            if "$CONDA_CMD" install -n mfa -c conda-forge montreal-forced-aligner -y; then
                echo ""
                echo "[Done] Montreal Forced Aligner installation complete."
            else
                echo ""
                echo -e "${RED}[Error] MFA installation failed.${NC}"
                echo "Please verify that conda is installed and you have an internet connection."
                echo ""
            fi
        fi
    else
        echo "conda environment \"mfa\" does not exist. Creating and installing..."
        echo "(This may take several minutes.)"
        if "$CONDA_CMD" create -n mfa -c conda-forge montreal-forced-aligner -y; then
            echo ""
            echo "[Done] Montreal Forced Aligner installation complete."
        else
            echo ""
            echo -e "${RED}[Error] MFA installation failed.${NC}"
            echo "Please verify that conda is installed and you have an internet connection."
            echo ""
        fi
    fi
fi

ask_continue

# ============================================================
# Step 5: FFmpeg
# ============================================================
write_header "Step 5 / 7  :  Install FFmpeg"

if command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg is already registered in PATH. Skipping."
    ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1
elif [ -f "$CONDA_DIR/bin/ffmpeg" ]; then
    echo "[OK] FFmpeg is already installed (conda). Checking PATH."
    add_to_path_persistent "$CONDA_DIR/bin"
else
    CONDA_CMD=$(resolve_conda)
    if [ -z "$CONDA_CMD" ]; then
        echo -e "${RED}[Error] conda not found. Please install FFmpeg manually.${NC}"
        echo "  https://evermeet.cx/ffmpeg/"
        echo "  Copy the downloaded ffmpeg binary to /usr/local/bin/."
    else
        echo "FFmpeg not found. Installing via conda-forge..."
        echo "(This may take several minutes.)"
        echo ""
        if "$CONDA_CMD" install -c conda-forge ffmpeg -y; then
            echo ""
            echo "[Done] FFmpeg installation complete."
            add_to_path_persistent "$CONDA_DIR/bin"
            ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1 || true
        else
            echo ""
            echo -e "${RED}[Error] FFmpeg installation failed.${NC}"
            echo "Please install manually:"
            echo "  https://evermeet.cx/ffmpeg/"
            echo "  Copy the downloaded ffmpeg binary to /usr/local/bin/."
            echo ""
        fi
    fi
fi

ask_continue

# ============================================================
# Step 6: textgrid / saxonche
# ============================================================
write_header "Step 6 / 7  :  Install textgrid / saxonche"

PY_CMD=""
if python3.12 --version &>/dev/null; then
    PY_CMD="python3.12"
elif python3 --version &>/dev/null; then
    PY_CMD="python3"
fi

if [ -z "$PY_CMD" ]; then
    echo -e "${RED}[Error] Python not found. Please check Step 1.${NC}"
    echo ""
else
    echo "Python in use: $PY_CMD ($($PY_CMD --version))"
    echo ""

    echo "[1/2] Installing textgrid..."
    if $PY_CMD -m pip install textgrid; then
        echo "[Done] textgrid installation complete."
    else
        echo -e "${RED}[Error] textgrid installation failed.${NC}"
    fi

    echo ""

    echo "[2/2] Installing saxonche..."
    if $PY_CMD -m pip install saxonche; then
        echo "[Done] saxonche installation complete."
    else
        echo -e "${RED}[Error] saxonche installation failed.${NC}"
        echo "Please check your internet connection and Python version."
    fi
fi

ask_continue

# ============================================================
# Step 7: English MFA models
# ============================================================
write_header "Step 7 / 7  :  Download English MFA Models"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Error] conda not found. Please check Steps 2 and 3.${NC}"
else
    echo "Downloading English MFA models (dictionary and acoustic)."
    echo "(Files are large — this may take several minutes.)"
    echo ""

    echo "[1/2] Downloading English dictionary model..."
    if "$CONDA_CMD" run -n mfa mfa model download dictionary english_us_arpa; then
        echo "[Done] English dictionary model downloaded."
    else
        echo -e "${RED}[Error] Failed to download English dictionary model.${NC}"
        echo "Please check your internet connection and MFA environment."
    fi

    echo ""

    echo "[2/2] Downloading English acoustic model..."
    if "$CONDA_CMD" run -n mfa mfa model download acoustic english_us_arpa; then
        echo "[Done] English acoustic model downloaded."
    else
        echo -e "${RED}[Error] Failed to download English acoustic model.${NC}"
        echo "Please check your internet connection and MFA environment."
    fi
fi

ask_continue

# ============================================================
# Completion screen
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   Setup complete!${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "All installation steps have been completed."
echo ""
echo "[Next steps]"
echo "  1. Restart Terminal (to apply PATH changes)"
echo "  2. Navigate to the KERT folder"
echo "  3. Run: python3.12 main.py"
echo ""
echo "For more information, see README.md."
echo ""
read -rp "Press Enter to exit"
