#!/usr/bin/env bash
# setup_venv.sh - recreate the project virtual environment on a new machine.
#
# Creates `main/.venv` (Python 3.13) and installs the pinned dependencies
# from requirements.txt. Uses `uv` when available (fast), falls back to
# `python3 -m venv` + `pip`.
#
# Usage:
#   ./setup_venv.sh            # create/refresh .venv and install deps
#   ./setup_venv.sh --force    # delete an existing .venv first, then recreate
#
# After running, start Jupyter with:
#   .venv/bin/jupyter notebook main.ipynb
# (or open main.ipynb in VS Code and select the .venv kernel).

set -euo pipefail

cd "$(dirname "$0")"   # main/

PYTHON_VERSION="3.13"
VENV_DIR=".venv"
REQ_FILE="requirements.txt"

FORCE=0
if [[ "${1:-}" == "--force" ]]; then
    FORCE=1
fi

if [[ -d "$VENV_DIR" ]]; then
    if [[ "$FORCE" == "1" ]]; then
        echo "setup: removing existing $VENV_DIR (--force)"
        rm -rf "$VENV_DIR"
    else
        echo "setup: $VENV_DIR already exists (use --force to recreate)"
        echo "setup: installing/updating dependencies into it..."
    fi
fi

# --- Create the venv if needed -------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    if command -v uv >/dev/null 2>&1; then
        echo "setup: creating venv with uv (Python $PYTHON_VERSION)"
        uv venv --python "$PYTHON_VERSION" "$VENV_DIR"
    else
        echo "setup: uv not found, using python3 -m venv"
        if ! command -v python3 >/dev/null 2>&1; then
            echo "error: neither uv nor python3 is available" >&2
            exit 1
        fi
        python3 -m venv "$VENV_DIR"
    fi
fi

# --- Install dependencies -------------------------------------------------
if command -v uv >/dev/null 2>&1; then
    echo "setup: installing dependencies with uv"
    uv pip install --python "$VENV_DIR/bin/python" -r "$REQ_FILE"
else
    echo "setup: installing dependencies with pip"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
fi

echo
echo "setup: done."
echo "setup: start Jupyter with:  $VENV_DIR/bin/jupyter notebook main.ipynb"
