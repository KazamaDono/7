#!/bin/bash
echo "Fixing WSL Audio for Seven..."

# Install PulseAudio
sudo apt update
sudo apt install -y pulseaudio

# Configure PulseAudio for Windows interop
cat << EOF | sudo tee -a /etc/pulse/default.pa
load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1
load-module module-esound-protocol-tcp auth-ip-acl=127.0.0.1
EOF

# Create PulseAudio config
mkdir -p ~/.config/pulse
cat << EOF > ~/.config/pulse/client.conf
default-server = tcp:127.0.0.1
autospawn = no
EOF

# Start PulseAudio
pulseaudio --kill 2>/dev/null
pulseaudio --start

# Install audio test tools
sudo apt install -y alsa-utils pulseaudio-utils

# Test audio
echo "Testing audio..."
paplay --server=tcp:127.0.0.1 /usr/share/sounds/gnome/default/alerts/drip.ogg 2>/dev/null || echo "Audio test failed - make sure Windows PulseAudio client is running"

echo "Fix complete! Restart your WSL terminal."