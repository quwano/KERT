#!/bin/bash
cd "$(dirname "$0")"

# Try Python from PATH (end users: python3.12 installed by KERT installer)
for PY in python3.12 python3.13 python3; do
    if command -v "$PY" &>/dev/null && "$PY" -c "import tkinterdnd2" 2>/dev/null; then
        exec "$PY" kert_gui.py
    fi
done

# Try direct conda env Python paths (development environments)
for CONDA_ROOT in \
    "$HOME/opt/miniconda3" \
    "$HOME/miniconda3" \
    "/opt/homebrew/Caskroom/miniconda/base" \
    "/opt/miniconda3" \
    "/usr/local/miniconda3" \
    "$HOME/anaconda3" \
    "/opt/anaconda3"
do
    PY="$CONDA_ROOT/envs/DaisyTrial_conda/bin/python"
    if [ -x "$PY" ] && "$PY" -c "import tkinterdnd2" 2>/dev/null; then
        exec "$PY" kert_gui.py
    fi
done

echo "Error: Could not find Python with KERT packages installed."
echo "Please run the KERT installer first."
read -rp "Press Enter to close..."
