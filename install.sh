#!/usr/bin/env bash
#
# Seven AI Assistant - portable installer
# ---------------------------------------
# Sets Seven up from scratch on a fresh Linux machine (native, NOT WSL):
#   * Python virtual environment + dependencies
#   * Ollama + the local language model
#   * (optional) the hand-gesture / hologram module on its own Python 3.11 venv
#
# Safe to re-run: every step checks whether it is already done.
#
set -u

# ---- pretty output --------------------------------------------------------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
say()  { echo -e "${CYAN}==>${NC} $*"; }
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
err()  { echo -e "${RED}  ✗${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${SEVEN_MODEL:-qwen3:1.7b}"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              SEVEN AI ASSISTANT - INSTALLER              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ---- 0. sanity: this is native Linux, not WSL -----------------------------
if grep -qi microsoft /proc/version 2>/dev/null; then
    warn "You appear to be running under WSL. Seven is built for native Linux."
    warn "Audio/mic/camera may need extra WSL bridging that this installer does not do."
fi

# ---- 1. Python ------------------------------------------------------------
say "Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
    err "python3 not found. Install it first:  sudo apt install python3 python3-venv python3-dev"
    exit 1
fi
PYVER="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
ok "python3 $PYVER found"

# ---- 2. System build deps (best-effort, needs sudo) -----------------------
say "Checking system audio/build packages..."
NEED_PKGS=()
command -v gcc >/dev/null 2>&1 || NEED_PKGS+=("build-essential")
dpkg -s portaudio19-dev >/dev/null 2>&1 || NEED_PKGS+=("portaudio19-dev")
dpkg -s python3-dev >/dev/null 2>&1 || NEED_PKGS+=("python3-dev")
dpkg -s python3-venv >/dev/null 2>&1 || NEED_PKGS+=("python3-venv")
if [ "${#NEED_PKGS[@]}" -gt 0 ]; then
    if command -v apt >/dev/null 2>&1; then
        warn "Installing: ${NEED_PKGS[*]} (needs sudo)"
        sudo apt update && sudo apt install -y "${NEED_PKGS[@]}" || warn "apt install failed; continuing"
    else
        warn "Please install these yourself: ${NEED_PKGS[*]}"
    fi
else
    ok "audio/build packages present"
fi

# ---- 3. Virtual environment + Python deps ---------------------------------
say "Setting up the Python virtual environment (voice_env)..."
if [ ! -d voice_env ]; then
    python3 -m venv voice_env || { err "Could not create venv"; exit 1; }
    ok "created voice_env"
else
    ok "voice_env already exists"
fi
# shellcheck disable=SC1091
source voice_env/bin/activate
python -m pip install --upgrade pip >/dev/null 2>&1
say "Installing Python dependencies (this can take a few minutes)..."
if pip install -r requirements.txt; then
    ok "dependencies installed"
else
    err "pip install failed. See the output above."
    exit 1
fi
# psutil powers the agent's system tools; ensure it is present.
python -c "import psutil" 2>/dev/null || pip install psutil >/dev/null 2>&1
ok "system-inspection support (psutil) ready"

# ---- 4. Ollama + language model -------------------------------------------
say "Checking Ollama (local LLM runtime)..."
if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama is not installed."
    read -r -p "  Install Ollama now via the official script? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        curl -fsSL https://ollama.com/install.sh | sh || warn "Ollama install failed; install it manually from https://ollama.com"
    else
        warn "Skipping. Install Ollama yourself from https://ollama.com before running Seven."
    fi
fi
if command -v ollama >/dev/null 2>&1; then
    ok "Ollama present"
    # Make sure the server is up so we can pull.
    if ! pgrep -x ollama >/dev/null 2>&1; then
        say "Starting Ollama service..."
        (ollama serve >/dev/null 2>&1 &) ; sleep 3
    fi
    if ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
        ok "model $MODEL already pulled"
    else
        say "Pulling model $MODEL (~1-2 GB)..."
        ollama pull "$MODEL" && ok "model ready" || warn "Could not pull $MODEL; pull it manually: ollama pull $MODEL"
    fi
fi

# ---- 5. Optional: hologram / hand-gesture module --------------------------
if [ -d hologram ] && [ -f hologram/hologram_viewer.py ]; then
    echo
    read -r -p "Set up the hand-gesture / hologram module too? (needs a separate Python 3.11) [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        say "Setting up the hologram environment..."
        if [ ! -d .uv-bootstrap ]; then
            python3 -m venv .uv-bootstrap && .uv-bootstrap/bin/pip install -q uv
        fi
        UV=".uv-bootstrap/bin/uv"
        if [ -x "$UV" ]; then
            "$UV" python install 3.11
            "$UV" venv hologram/.venv --python 3.11
            "$UV" pip install --python hologram/.venv/bin/python3 -r hologram/requirements.txt \
                && ok "hologram module ready (say 'Seven, open the hologram')" \
                || warn "hologram deps failed; the voice assistant still works without it"
        else
            warn "Could not bootstrap uv; skipping hologram setup"
        fi
    fi
fi

# ---- 6. Audio note --------------------------------------------------------
echo
say "Audio: Seven uses your system default microphone (PulseAudio/PipeWire)."
say "Pick your mic in your desktop Sound settings, or with:  pactl set-default-source <name>"
warn "Do NOT set PULSE_SERVER=127.0.0.1 on native Linux - that is a WSL-only hack and breaks audio."

# ---- done -----------------------------------------------------------------
echo
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation complete.                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo
echo "Start Seven with:"
echo -e "    ${CYAN}bash run_seven.sh${NC}"
echo
echo "Then say 'Seven' followed by a request, e.g.:"
echo "    \"Seven, what's eating my memory?\""
echo "    \"Seven, run a security audit.\""
echo "    \"Seven, decode this JWT ...\""
echo "    \"Seven, open a terminal with htop and tell me the top processes.\""
echo
echo "Full command guide:  COMMANDS.md    (say 'type' to switch to keyboard input)"
echo
echo "Tip: for more reliable answers on a machine with 16GB+ RAM, use a bigger model:"
echo -e "    ${CYAN}export SEVEN_MODEL=qwen3:4b${NC}   (then re-run this installer to pull it)"
