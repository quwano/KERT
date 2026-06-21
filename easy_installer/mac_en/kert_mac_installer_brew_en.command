#!/bin/bash
# KERT macOS Setup Installer (English, with Homebrew)
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

resolve_conda_bin_dir() {
    local conda_cmd
    conda_cmd=$(resolve_conda)
    if [ -n "$conda_cmd" ]; then
        dirname "$conda_cmd"
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
echo -e "${GREEN}   KERT Setup Installer (English / with Homebrew)${NC}"
echo -e "${GREEN}   This script sets up the KERT runtime environment step by step.${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "[Installation Steps]"
echo ""
echo "  Step 1   Verify Homebrew installation"
echo "  Step 2   Install Python 3.12"
echo "  Step 3   Install Miniforge (conda)"
echo "  Step 4   Verify conda PATH"
echo "  Step 5   Install Montreal Forced Aligner (MFA)"
echo "  Step 6   Install FFmpeg"
echo "  Step 7   Install textgrid / saxonche"
echo "  Step 8   Download English MFA models"
echo ""
echo "You will be asked to continue or abort after each step."
echo "Press N at any time to abort."
echo ""
echo "Environment: $(uname -s) $(uname -r) (${ARCH})"
echo ""
read -rp "Press Enter to start the installation"

# ============================================================
# Step 1: Homebrew
# ============================================================
write_header "Step 1 / 8  :  Verify Homebrew installation"

BREW_CMD=$(resolve_brew)

if [ -n "$BREW_CMD" ]; then
    echo "[OK] Homebrew is already installed. Skipping."
    "$BREW_CMD" --version
else
    echo "Homebrew not found. Running the official installer."
    echo ""
    echo "Note: Your system password will be required."
    echo "      Xcode Command Line Tools will also be installed if needed (first time only)."
    echo ""

    if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
        echo ""
        echo "[Done] Homebrew installation complete."

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
        echo -e "${RED}[Error] Homebrew installation failed.${NC}"
        echo "Please install manually:"
        echo "  https://brew.sh/"
        echo ""
    fi

    echo "[3/3] Installing pdfplumber Pillow..."
    if $PY_CMD -m pip install --break-system-packages pdfplumber Pillow; then
        echo "[Done] pdfplumber Pillow installation complete."
    else
        echo -e "${RED}[Error] pdfplumber Pillow installation failed.${NC}"
    fi
fi

ask_continue

# ============================================================
# Step 2: Python 3.12
# ============================================================
write_header "Step 2 / 8  :  Install Python 3.12"

BREW_CMD=$(resolve_brew)

if python3.12 --version &>/dev/null; then
    echo "[OK] Python 3.12 is already installed. Skipping."
    python3.12 --version
elif [ -z "$BREW_CMD" ]; then
    echo -e "${RED}[Error] Homebrew not found. Please check Step 1.${NC}"
else
    echo "Python 3.12 not found. Installing via Homebrew..."
    echo ""
    if "$BREW_CMD" install python@3.12; then
        echo ""
        echo "[Done] Python 3.12 installation complete."
        BREW_PREFIX=$("$BREW_CMD" --prefix)
        add_to_path_persistent "$BREW_PREFIX/bin"
        python3.12 --version 2>/dev/null || true
    else
        echo ""
        echo -e "${RED}[Error] Python 3.12 installation failed.${NC}"
        echo "Please verify that Homebrew is correctly installed."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Step 3: Miniforge (conda)
# ============================================================
write_header "Step 3 / 8  :  Install Miniforge (conda)"

BREW_CMD=$(resolve_brew)
CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda is already available. Skipping."
    "$CONDA_CMD" --version
elif [ -z "$BREW_CMD" ]; then
    echo -e "${RED}[Error] Homebrew not found. Please check Step 1.${NC}"
else
    echo "Miniforge not found. Installing via Homebrew..."
    echo "(This may take several minutes.)"
    echo ""
    if "$BREW_CMD" install --cask miniforge; then
        echo ""
        echo "[Done] Miniforge installation complete."
        BREW_PREFIX=$("$BREW_CMD" --prefix)
        CASK_CONDA_BIN="$BREW_PREFIX/Caskroom/miniforge/base/bin"
        if [ -d "$CASK_CONDA_BIN" ]; then
            export PATH="$CASK_CONDA_BIN:$PATH"
            echo "PATH updated for this session."
        fi
        CONDA_CMD=$(resolve_conda)
        if [ -n "$CONDA_CMD" ]; then
            "$CONDA_CMD" --version
        fi
    else
        echo ""
        echo -e "${RED}[Error] Miniforge installation failed.${NC}"
        echo "Please verify that Homebrew is correctly installed."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Step 4: conda PATH
# ============================================================
write_header "Step 4 / 8  :  Verify conda PATH"

CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda is available."
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
        echo "[OK] Shell profile or conda init already configured."
    fi
else
    echo -e "${YELLOW}[Warning] conda not found.${NC}"
    echo "Please go back to Step 3 and install Miniforge."
    echo ""
fi

ask_continue

# ============================================================
# Step 5: Montreal Forced Aligner (MFA)
# ============================================================
write_header "Step 5 / 8  :  Install Montreal Forced Aligner"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Error] conda not found. Please check Steps 3 and 4.${NC}"
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
# Step 6: FFmpeg
# ============================================================
write_header "Step 6 / 8  :  Install FFmpeg"

BREW_CMD=$(resolve_brew)

if command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg is already registered in PATH. Skipping."
    ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1
elif [ -z "$BREW_CMD" ]; then
    echo -e "${RED}[Error] Homebrew not found. Please check Step 1.${NC}"
else
    echo "FFmpeg not found. Installing via Homebrew..."
    echo ""
    if "$BREW_CMD" install ffmpeg; then
        echo ""
        echo "[Done] FFmpeg installation complete."
        ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1 || true
    else
        echo ""
        echo -e "${RED}[Error] FFmpeg installation failed.${NC}"
        echo "Please verify that Homebrew is correctly installed."
        echo ""
    fi
fi

ask_continue

# ============================================================
# Step 7: textgrid / saxonche
# ============================================================
write_header "Step 7 / 8  :  Install textgrid / saxonche"

PY_CMD=""
if python3.12 --version &>/dev/null; then
    PY_CMD="python3.12"
elif python3 --version &>/dev/null; then
    PY_CMD="python3"
fi

if [ -z "$PY_CMD" ]; then
    echo -e "${RED}[Error] Python not found. Please check Step 2.${NC}"
    echo ""
else
    echo "Python in use: $PY_CMD ($($PY_CMD --version))"
    echo ""

    echo "[1/3] Installing textgrid..."
    if $PY_CMD -m pip install --break-system-packages textgrid; then
        echo "[Done] textgrid installation complete."
    else
        echo -e "${RED}[Error] textgrid installation failed.${NC}"
    fi

    echo ""

    echo "[2/3] Installing saxonche..."
    if [ "$ARCH" = "arm64" ]; then
        echo ""
        echo -e "${YELLOW}[Warning] Apple Silicon (ARM64) Mac detected.${NC}"
        echo "saxonche is not available for ARM64 macOS on PyPI and cannot be"
        echo "installed automatically."
        echo ""
        echo "saxonche is not required if you only use CommonMark (.md) input."
    elif $PY_CMD -m pip install --break-system-packages saxonche; then
        echo "[Done] saxonche installation complete."
    else
        echo -e "${RED}[Error] saxonche installation failed.${NC}"
        echo "Please check your internet connection and Python version."
    fi

    echo ""

    echo "[3/3] Installing tkinterdnd2..."
    if $PY_CMD -m pip install --break-system-packages "tkinterdnd2>=0.4.2,<0.5.0"; then
        echo "[Done] tkinterdnd2 installation complete."
    else
        echo -e "${RED}[Error] tkinterdnd2 installation failed.${NC}"
    fi
fi

ask_continue

# ============================================================
# Step 8: English MFA models
# ============================================================
write_header "Step 8 / 8  :  Download English MFA Models"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[Error] conda not found. Please check Steps 3 and 4.${NC}"
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

# Set execute permission on start_kert.command
KERT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$KERT_DIR/start_kert.command" ]; then
    chmod +x "$KERT_DIR/start_kert.command"
fi

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
echo "  2. Double-click start_kert.command in the KERT folder to launch"
echo ""
echo "For more information, see README.md."
echo ""
read -rp "Press Enter to exit"
