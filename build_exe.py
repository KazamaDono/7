"""
Build script to create Windows executable for Seven AI Assistant
Run: python build_exe.py
"""

import os
import sys
import shutil
from pathlib import Path

def clean_build_dirs():
    """Clean up previous build directories"""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Removing {dir_name}...")
            shutil.rmtree(dir_name)
    
    # Remove spec file if exists
    spec_file = "seven.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

def build_executable():
    """Build the executable using PyInstaller"""
    
    print("=" * 60)
    print("Building Seven AI Assistant Executable")
    print("=" * 60)
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("\nPyInstaller not found. Installing...")
        os.system(f"{sys.executable} -m pip install pyinstaller")
    
    # Ensure we're in the correct directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Clean previous builds
    clean_build_dirs()
    
    # Check for required files
    required_files = [
        "main.py",
        "seven_plugins.py",
        "seven_orb.py",
        "seven_network_security.py",
        "launcher.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"\nERROR: Missing required files: {', '.join(missing_files)}")
        print("\nMake sure all files are in the current directory.")
        return False
    
    # Check for GIF files (optional but recommended)
    gif_files = ["bs.gif", "ws.gif"]
    missing_gifs = []
    for gif in gif_files:
        if not os.path.exists(gif):
            missing_gifs.append(gif)
    
    if missing_gifs:
        print(f"\nWARNING: Missing GIF files: {', '.join(missing_gifs)}")
        print("The orb visualizer may not work properly without these files.\n")
    
    # Build PyInstaller command
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Seven",
        "--onefile",
        "--windowed",  # Don't show console window
        "--icon=NONE",  # You can add an icon file path here
        "--add-data=bs.gif;." if os.path.exists("bs.gif") else "",
        "--add-data=ws.gif;." if os.path.exists("ws.gif") else "",
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
        "launcher.py"
    ]
    
    # Filter out empty strings
    pyinstaller_cmd = [cmd for cmd in pyinstaller_cmd if cmd]
    
    print("\nBuilding executable...")
    print("This may take a few minutes...\n")
    
    # Run PyInstaller
    import subprocess
    result = subprocess.run(pyinstaller_cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print("=" * 60)
        print(f"\nExecutable created at: {script_dir}/dist/Seven.exe")
        print("\nYou can now:")
        print("  1. Copy Seven.exe to your Desktop")
        print("  2. Double-click to run Seven AI Assistant")
        print("\nNOTE: First run may take a moment to initialize.")
        
        # Create a shortcut launcher script
        create_launcher_script(script_dir)
        
        return True
    else:
        print("\n" + "=" * 60)
        print("BUILD FAILED!")
        print("=" * 60)
        print("\nPlease check the error messages above.")
        return False

def create_launcher_script(script_dir):
    """Create a simple batch file to launch the executable"""
    batch_content = f"""@echo off
title Seven AI Assistant
echo Starting Seven AI Assistant...
echo.
cd /d "{script_dir}\\dist"
Seven.exe
pause
"""
    
    batch_path = script_dir / "Launch_Seven.bat"
    with open(batch_path, 'w') as f:
        f.write(batch_content)
    
    print(f"\nAlso created launcher: {batch_path}")

def create_setup_instructions():
    """Create setup instructions file"""
    instructions = """Seven AI Assistant - Setup Instructions
============================================

REQUIREMENTS BEFORE RUNNING:
---------------------------
1. Install Ollama from: https://ollama.ai
2. Pull the Qwen model: ollama pull qwen3:1.7b
3. Ensure you have working microphone

RUNNING THE EXECUTABLE:
-----------------------
1. Double-click Seven.exe
2. If Windows SmartScreen appears, click "More info" then "Run anyway"
3. Grant microphone access when prompted
4. Wait for initialization (may take 30 seconds)

TROUBLESHOOTING:
----------------
If Seven.exe doesn't work:

Option 1: Run from Command Prompt
  1. Open Command Prompt
  2. Navigate to dist folder: cd path\\to\\dist
  3. Run: Seven.exe
  4. Check error messages

Option 2: Install Python and run directly
  1. Install Python 3.10+
  2. Run: pip install -r requirements.txt
  3. Run: python main.py

REQUIRED FILES:
---------------
Make sure these files are in the same folder as Seven.exe:
- bs.gif (idle animation)
- ws.gif (speaking animation)

MICROPHONE SETUP:
----------------
1. Right-click speaker icon in taskbar
2. Select "Sound settings"
3. Go to "Input" section
4. Ensure correct microphone is selected
5. Test microphone levels

COMMANDS:
---------
- Say "Seven" followed by your command
- "Seven open notepad"
- "Seven what time is it"
- "Seven search for [file name] files"
- "Seven take a screenshot"
- "Seven set timer for 5 minutes"
- "Seven scan network for hosts"

SUPPORT:
--------
For issues, ensure:
1. Ollama is running (ollama serve)
2. Model is downloaded (ollama list)
3. Microphone is working
4. Internet connection for voice recognition
"""
    
    instructions_path = script_dir / "dist" / "README.txt"
    with open(instructions_path, 'w') as f:
        f.write(instructions)
    
    print(f"Created README.txt in dist folder")

if __name__ == "__main__":
    success = build_executable()
    if success:
        create_setup_instructions()
        print("\n" + "=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print("1. Navigate to the 'dist' folder")
        print("2. Copy 'Seven.exe' to your Desktop")
        print("3. Make sure 'bs.gif' and 'ws.gif' are in the same folder")
        print("4. Double-click Seven.exe to run!")
        print("\nEnjoy using Seven AI Assistant!")
        input("\nPress Enter to exit...")
    else:
        input("\nPress Enter to exit...")