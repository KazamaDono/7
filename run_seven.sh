#!/bin/bash

# Seven AI Assistant Launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                         SEVEN AI ASSISTANT LAUNCHER                           ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo -e "${YELLOW}Starting Ollama service...${NC}"
    ollama serve > /dev/null 2>&1 &
    sleep 3
    echo -e "${GREEN}✓ Ollama started${NC}"
else
    echo -e "${GREEN}✓ Ollama already running${NC}"
fi

# WSL needed a TCP bridge to reach Windows' audio server; native Linux
# already has a local PulseAudio/Pipewire socket, so only set this under WSL.
# On native Linux a stale PULSE_SERVER=127.0.0.1 (from WSL install guides) makes
# every audio call fail with "Connection refused", so clear it.
if grep -qi microsoft /proc/version 2>/dev/null; then
    export PULSE_SERVER=127.0.0.1
elif [ -n "$PULSE_SERVER" ]; then
    echo -e "${YELLOW}Ignoring stale PULSE_SERVER=$PULSE_SERVER (not WSL)${NC}"
    unset PULSE_SERVER
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source voice_env/bin/activate

# Check if orb exists
if [ -f "seven_orb.py" ] && [ -f "ws.gif" ] && [ -f "bs.gif" ]; then
    echo -e "${GREEN}✓ Orb visualizer available${NC}"
fi

echo ""
echo -e "${CYAN}Launching Seven AI Assistant...${NC}"
echo -e "${YELLOW}Say 'Seven' to activate, 'stop' to interrupt speech, 'exit' to quit${NC}"
echo ""

# Run Seven
python3 main.py

# Cleanup on exit
echo ""
echo -e "${CYAN}Seven has shut down. Goodbye.${NC}"
