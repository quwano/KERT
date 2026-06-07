#!/bin/bash
cd "$(dirname "$0")"
if command -v python3.12 &>/dev/null; then
    python3.12 main.py
else
    python3 main.py
fi
