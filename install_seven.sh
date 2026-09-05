#!/bin/bash

# ============================================================================
# SEVEN AI ASSISTANT - COMPLETE INSTALLATION SCRIPT
# ============================================================================
# This script installs everything needed to run Seven:
# - System dependencies (WSL/Linux)
# - Ollama with qwen3:1.7b model
# - Python virtual environment
# - All Python packages
# - Audio configuration (PulseAudio)
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║                    ░▒▓███████▓▒░ ░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                   ░▒▓█▓▒░        ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                   ░▒▓███████▓▒░  ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                          ░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                   ░▒▓███████▓▒░  ░▒▓████████▓▒░▒▓████████▓▒░                  ║"
echo "║                                                                              ║"
echo "║                         INORGANIC INTELLIGENT AGENT                           ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                         INSTALLATION SCRIPT                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# STEP 1: System Update
# ============================================================================
echo -e "${BLUE}[STEP 1/8]${NC} ${YELLOW}Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y
echo -e "${GREEN}✓ System updated${NC}"
echo ""

# ============================================================================
# STEP 2: Install System Dependencies
# ============================================================================
echo -e "${BLUE}[STEP 2/8]${NC} ${YELLOW}Installing system dependencies...${NC}"

# Build tools and Python
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    curl \
    wget \
    git \
    portaudio19-dev \
    pulseaudio \
    pulseaudio-utils \
    alsa-utils \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    espeak \
    flac \
    tshark \
    nano

echo -e "${GREEN}✓ System dependencies installed${NC}"
echo ""

# ============================================================================
# STEP 3: Install Ollama
# ============================================================================
echo -e "${BLUE}[STEP 3/8]${NC} ${YELLOW}Installing Ollama...${NC}"

if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama already installed${NC}"
else
    curl -fsSL https://ollama.com/install.sh | sh
    echo -e "${GREEN}✓ Ollama installed${NC}"
fi
echo ""

# ============================================================================
# STEP 4: Start Ollama and Pull Model
# ============================================================================
echo -e "${BLUE}[STEP 4/8]${NC} ${YELLOW}Starting Ollama service...${NC}"

# Check if ollama is already running
if pgrep -x "ollama" > /dev/null; then
    echo -e "${GREEN}✓ Ollama service already running${NC}"
else
    # Start ollama in background
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    echo -e "${GREEN}✓ Ollama service started (PID: $OLLAMA_PID)${NC}"
    sleep 3  # Wait for service to initialize
fi

echo ""
echo -e "${BLUE}[STEP 5/8]${NC} ${YELLOW}Pulling qwen3:1.7b model...${NC}"
echo -e "${CYAN}This may take a few minutes depending on your internet speed...${NC}"

ollama pull qwen3:1.7b

echo -e "${GREEN}✓ Model qwen3:1.7b pulled successfully${NC}"
echo ""

# ============================================================================
# STEP 5: Create Python Virtual Environment
# ============================================================================
echo -e "${BLUE}[STEP 6/8]${NC} ${YELLOW}Creating Python virtual environment...${NC}"

if [ -d "voice_env" ]; then
    echo -e "${YELLOW}Virtual environment already exists. Recreating...${NC}"
    rm -rf voice_env
fi

python3 -m venv voice_env
echo -e "${GREEN}✓ Virtual environment created${NC}"
echo ""

# ============================================================================
# STEP 6: Create requirements.txt
# ============================================================================
echo -e "${BLUE}[STEP 7/8]${NC} ${YELLOW}Creating requirements.txt...${NC}"

cat > requirements.txt << 'EOF'
# Core dependencies
edge-tts==6.1.9
pygame==2.6.1
SpeechRecognition==3.10.4
pyaudio==0.2.14

# LLM and AI
langchain==0.3.13
langchain-ollama==0.2.2
langchain-core==0.3.28

# System and utilities
psutil==5.9.8
requests==2.32.3
python-dotenv==1.0.1
schedule==1.2.2
keyboard==0.13.5

# Image processing (for orb)
Pillow==10.4.0

# Optional but recommended
colorama==0.4.6
rich==13.9.4
EOF

echo -e "${GREEN}✓ requirements.txt created${NC}"
echo ""

# ============================================================================
# STEP 7: Install Python Packages
# ============================================================================
echo -e "${BLUE}[STEP 8/8]${NC} ${YELLOW}Installing Python packages...${NC}"
echo -e "${CYAN}This may take a few minutes...${NC}"

source voice_env/bin/activate
pip install --upgrade pip
pip install wheel
pip install -r requirements.txt

echo -e "${GREEN}✓ Python packages installed${NC}"
echo ""

# ============================================================================
# STEP 8: Configure PulseAudio
# ============================================================================
echo -e "${BLUE}[AUDIO CONFIG]${NC} ${YELLOW}Configuring PulseAudio...${NC}"

# Check if running in WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${CYAN}WSL detected - applying special audio configuration...${NC}"
    IS_WSL=true
else
    IS_WSL=false
fi

# Backup original config if exists
if [ -f /etc/pulse/default.pa ]; then
    sudo cp /etc/pulse/default.pa /etc/pulse/default.pa.backup
    echo -e "${GREEN}✓ Backed up original PulseAudio config${NC}"
fi

# Add TCP module if not present
if ! grep -q "module-native-protocol-tcp" /etc/pulse/default.pa 2>/dev/null; then
    echo -e "${YELLOW}Adding TCP module to PulseAudio config...${NC}"
    echo "" | sudo tee -a /etc/pulse/default.pa
    echo "# Seven AI Assistant - Network audio support" | sudo tee -a /etc/pulse/default.pa
    echo "load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1" | sudo tee -a /etc/pulse/default.pa
    echo "load-module module-esound-protocol-tcp auth-ip-acl=127.0.0.1" | sudo tee -a /etc/pulse/default.pa
    echo -e "${GREEN}✓ TCP modules added${NC}"
else
    echo -e "${GREEN}✓ TCP modules already configured${NC}"
fi

# Kill existing pulseaudio and restart
pulseaudio --kill 2>/dev/null || true
sleep 2
pulseaudio --start
echo -e "${GREEN}✓ PulseAudio restarted${NC}"

# Set PULSE_SERVER environment variable
export PULSE_SERVER=127.0.0.1

# Add to bashrc if not present
if ! grep -q "PULSE_SERVER=127.0.0.1" ~/.bashrc 2>/dev/null; then
    echo "" >> ~/.bashrc
    echo "# Seven AI Assistant - PulseAudio configuration" >> ~/.bashrc
    echo "export PULSE_SERVER=127.0.0.1" >> ~/.bashrc
    echo -e "${GREEN}✓ Added PULSE_SERVER to ~/.bashrc${NC}"
fi

echo ""

# ============================================================================
# Create launcher script
# ============================================================================
echo -e "${BLUE}[LAUNCHER]${NC} ${YELLOW}Creating launcher script...${NC}"

cat > run_seven.sh << 'EOF'
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

# Set audio environment
export PULSE_SERVER=127.0.0.1

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
EOF

chmod +x run_seven.sh
echo -e "${GREEN}✓ Launcher script created: ./run_seven.sh${NC}"
echo ""

# ============================================================================
# INSTALLATION COMPLETE
# ============================================================================
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║                    ░▒▓███████▓▒░ ░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                   ░▒▓█▓▒░        ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                   ░▒▓███████▓▒░  ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                          ░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░                  ║"
echo "║                   ░▒▓███████▓▒░  ░▒▓████████▓▒░▒▓████████▓▒░                  ║"
echo "║                                                                              ║"
echo "║                         INSTALLATION COMPLETE!                                ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                              QUICK START GUIDE                                 ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}1.${NC} Run Seven:           ${YELLOW}./run_seven.sh${NC}"
echo -e "  ${GREEN}2.${NC} Or manually:"
echo -e "                         ${YELLOW}source voice_env/bin/activate${NC}"
echo -e "                         ${YELLOW}python3 main.py${NC}"
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                 COMMANDS                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${MAGENTA}Voice Commands:${NC}"
echo -e "    • 'Seven'              - Wake word"
echo -e "    • 'stop'               - Interrupt speech"
echo -e "    • 'exit'               - Shutdown Seven"
echo ""
echo -e "  ${MAGENTA}Keyboard:${NC}"
echo -e "    • Ctrl+\\               - Stop speech"
echo -e "    • Ctrl+C               - Exit program"
echo ""
echo -e "  ${MAGENTA}Orb Controls:${NC}"
echo -e "    • F                    - Toggle fullscreen"
echo -e "    • ESC                  - Close orb"
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                             TROUBLESHOOTING                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}Audio not working?${NC}"
echo -e "    pulseaudio --kill && pulseaudio --start"
echo -e "    export PULSE_SERVER=127.0.0.1"
echo ""
echo -e "  ${YELLOW}Ollama not running?${NC}"
echo -e "    ollama serve"
echo ""
echo -e "  ${YELLOW}Reinstall everything?${NC}"
echo -e "    rm -rf voice_env && ./install_seven.sh"
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}                    Seven is ready. Wake her up.${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"