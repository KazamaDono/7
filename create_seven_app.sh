#!/bin/bash

# ============================================================================
# SEVEN AI ASSISTANT - APPLICATION PACKAGER
# ============================================================================
# This script creates two clickable applications:
#   1. Seven Installer.app - One-time setup
#   2. Seven.app - The actual assistant
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                    SEVEN AI - APPLICATION PACKAGER                             ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# CREATE INSTALLER APP
# ============================================================================
echo -e "${YELLOW}Creating Seven Installer.app...${NC}"

mkdir -p "Seven Installer.app/Contents/MacOS"
mkdir -p "Seven Installer.app/Contents/Resources"

# Create the launcher script for installer
cat > "Seven Installer.app/Contents/MacOS/Seven Installer" << 'EOF'
#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Open terminal and run installation
osascript -e "tell application \"Terminal\" to do script \"cd '$APP_DIR' && ./install_seven.sh && echo '' && echo 'Installation complete! You can now close this window and use Seven.app' && read -p 'Press Enter to close...'\""

# Wait a moment and bring terminal to front
sleep 1
osascript -e 'tell application "Terminal" to activate'
EOF

chmod +x "Seven Installer.app/Contents/MacOS/Seven Installer"

# Create Info.plist for installer
cat > "Seven Installer.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Seven Installer</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.seven.installer</string>
    <key>CFBundleName</key>
    <string>Seven Installer</string>
    <key>CFBundleDisplayName</key>
    <string>Seven Installer</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.10</string>
</dict>
</plist>
EOF

echo -e "${GREEN}✓ Seven Installer.app created${NC}"

# ============================================================================
# CREATE MAIN SEVEN APP
# ============================================================================
echo -e "${YELLOW}Creating Seven.app...${NC}"

mkdir -p "Seven.app/Contents/MacOS"
mkdir -p "Seven.app/Contents/Resources"

# Create the launcher script for Seven
cat > "Seven.app/Contents/MacOS/Seven" << 'EOF'
#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$APP_DIR"

# Check if installation has been completed
if [ ! -d "voice_env" ]; then
    osascript -e 'display dialog "Seven is not installed yet!\n\nPlease run Seven Installer.app first." buttons {"OK"} default button "OK" with icon caution'
    exit 1
fi

# Check if ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    # Start ollama in background
    ollama serve > /dev/null 2>&1 &
fi

# Set audio environment
export PULSE_SERVER=127.0.0.1

# Activate virtual environment and run Seven
source "$APP_DIR/voice_env/bin/activate"

# Open terminal for Seven
osascript -e "tell application \"Terminal\" to do script \"cd '$APP_DIR' && source voice_env/bin/activate && export PULSE_SERVER=127.0.0.1 && python3 main.py\""

# Wait a moment and bring terminal to front
sleep 1
osascript -e 'tell application "Terminal" to activate'
EOF

chmod +x "Seven.app/Contents/MacOS/Seven"

# Create Info.plist for Seven
cat > "Seven.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Seven</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.seven.assistant</string>
    <key>CFBundleName</key>
    <string>Seven</string>
    <key>CFBundleDisplayName</key>
    <string>Seven AI Assistant</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.10</string>
</dict>
</plist>
EOF

echo -e "${GREEN}✓ Seven.app created${NC}"

# ============================================================================
# CREATE ICONS (Simple generated icons)
# ============================================================================
echo -e "${YELLOW}Creating app icons...${NC}"

# Create a simple icon using Python if available
if command -v python3 &> /dev/null; then
    python3 << 'PYEOF'
from PIL import Image, ImageDraw
import os

def create_icon(name, color1, color2, size=512):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw gradient circles
    center = size // 2
    for i in range(size // 2, 0, -1):
        ratio = i / (size // 2)
        r = int(color1[0] * ratio + color2[0] * (1 - ratio))
        g = int(color1[1] * ratio + color2[1] * (1 - ratio))
        b = int(color1[2] * ratio + color2[2] * (1 - ratio))
        alpha = int(255 * ratio)
        draw.ellipse([center - i, center - i, center + i, center + i], 
                     fill=(r, g, b, alpha))
    
    # Draw "S" in center
    draw.text((center - 80, center - 100), "S", fill=(255, 255, 255, 255))
    
    return img

# Create installer icon (amber/orange)
installer_icon = create_icon("installer", (255, 200, 0), (255, 100, 0))
installer_icon.save("Seven Installer.app/Contents/Resources/AppIcon.icns")

# Create Seven icon (cyan/blue)
seven_icon = create_icon("seven", (0, 255, 255), (100, 0, 255))
seven_icon.save("Seven.app/Contents/Resources/AppIcon.icns")

print("Icons created")
PYEOF
    echo -e "${GREEN}✓ Icons created${NC}"
else
    echo -e "${YELLOW}⚠ Python3 not found - skipping icon creation${NC}"
fi

# ============================================================================
# CREATE DESKTOP ENTRIES (Linux)
# ============================================================================
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${YELLOW}Creating desktop entries...${NC}"
    
    # Installer desktop entry
    cat > "$HOME/.local/share/applications/seven-installer.desktop" << EOF
[Desktop Entry]
Name=Seven Installer
Comment=Install Seven AI Assistant
Exec=$SCRIPT_DIR/Seven Installer.app/Contents/MacOS/Seven Installer
Icon=$SCRIPT_DIR/Seven Installer.app/Contents/Resources/AppIcon.icns
Terminal=false
Type=Application
Categories=Utility;
EOF
    
    # Seven desktop entry
    cat > "$HOME/.local/share/applications/seven.desktop" << EOF
[Desktop Entry]
Name=Seven
Comment=Seven AI Assistant
Exec=$SCRIPT_DIR/Seven.app/Contents/MacOS/Seven
Icon=$SCRIPT_DIR/Seven.app/Contents/Resources/AppIcon.icns
Terminal=false
Type=Application
Categories=Office;Utility;
EOF
    
    echo -e "${GREEN}✓ Desktop entries created${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}                         APPS CREATED SUCCESSFULLY!                              ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${MAGENTA}1.${NC} Double-click ${YELLOW}Seven Installer.app${NC} to set up Seven (one-time only)"
echo -e "  ${MAGENTA}2.${NC} Double-click ${YELLOW}Seven.app${NC} to run Seven anytime after installation"
echo ""
echo -e "${CYAN}You can move these apps anywhere (Desktop, Applications folder, etc.)${NC}"
echo ""