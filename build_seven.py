import os
import subprocess
import sys
from pathlib import Path

def build_seven():
    print("=" * 60)
    print("Building Seven AI Assistant with Custom Icon")
    print("=" * 60)
    
    # Check for icon file
    icon_file = "seven_icon.ico"
    if not os.path.exists(icon_file):
        print(f"\nWARNING: {icon_file} not found!")
        print("Building without custom icon...")
        icon_option = []
    else:
        print(f"\n✓ Found icon: {icon_file}")
        icon_option = [f"--icon={icon_file}"]
    
    # Check for required files
    required = ["main.py", "seven_plugins.py", "seven_orb.py", "seven_network_security.py"]
    missing = [f for f in required if not os.path.exists(f)]
    
    if missing:
        print(f"\nERROR: Missing files: {', '.join(missing)}")
        return False
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name=Seven",
        "--windowed",  # No console window
        "--clean",     # Clean temporary files
        "--noconfirm", # Overwrite output without asking
        *icon_option,
        "--hidden-import=pygame",
        "--hidden-import=speech_recognition",
        "--hidden-import=edge_tts",
        "--hidden-import=langchain_ollama",
        "--hidden-import=PIL",
        "--hidden-import=psutil",
        "--hidden-import=requests",
        "--hidden-import=schedule",
        "--hidden-import=pyaudio",
        "--collect-all=langchain_ollama",
        "main.py"
    ]
    
    print("\nBuilding... (this may take 3-5 minutes)")
    print("Command:", " ".join(cmd[:10]) + "...\n")
    
    # Run PyInstaller
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("✓ BUILD SUCCESSFUL!")
        print("=" * 60)
        
        exe_path = Path("dist/Seven.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\nExecutable created: {exe_path.absolute()}")
            print(f"Size: {size_mb:.1f} MB")
            
            # Create info file
            with open("dist/README.txt", "w") as f:
                f.write("""Seven AI Assistant - Standalone Executable
============================================

REQUIRED FILES (place in same folder as Seven.exe):
- bs.gif (idle animation)
- ws.gif (speaking animation)

REQUIRED SOFTWARE:
- Ollama (https://ollama.ai)
- Run: ollama pull qwen3:1.7b

RUNNING:
- Double-click Seven.exe
- Grant microphone access
- Say "Seven" followed by your command

First run may take 30-60 seconds to initialize.
""")
            
            print("\n✓ Created README.txt in dist folder")
            
            # Create launcher batch file
            with open("dist/Launch_Seven.bat", "w") as f:
                f.write("""@echo off
title Seven AI Assistant
echo Starting Seven AI Assistant...
echo.
Seven.exe
pause
""")
            
            print("✓ Created Launch_Seven.bat")
            
            print("\n" + "=" * 60)
            print("NEXT STEPS:")
            print("=" * 60)
            print("1. Copy these files to your Desktop:")
            print("   - dist/Seven.exe")
            print("   - bs.gif")
            print("   - ws.gif")
            print("2. Double-click Seven.exe to run!")
            print("=" * 60)
            
            return True
    else:
        print("\n" + "=" * 60)
        print("✗ BUILD FAILED!")
        print("=" * 60)
        print("\nTry building without --windowed first to see errors:")
        print("python -m PyInstaller --onefile --name=Seven main.py")
        return False

if __name__ == "__main__":
    build_seven()