"""
Seven WSL Launcher - Launches Seven from Windows using WSL venv
This can be converted to EXE with PyInstaller easily!
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # Configuration
    WSL_DISTRO = "Ubuntu"  # Change to your WSL distro
    PROJECT_DIR = Path(__file__).parent.absolute()
    WSL_PATH = str(PROJECT_DIR).replace('\\', '/')
    
    print("=" * 60)
    print("Seven AI Assistant - WSL Launcher")
    print("=" * 60)
    print(f"Project path: {PROJECT_DIR}")
    print(f"WSL path: {WSL_PATH}")
    print(f"WSL Distro: {WSL_DISTRO}")
    print("=" * 60)
    
    # Check if WSL is available
    try:
        subprocess.run(["wsl", "--status"], capture_output=True, check=True)
    except:
        print("\nERROR: WSL is not installed or not running!")
        print("Please install WSL first: https://aka.ms/wslinstall")
        input("\nPress Enter to exit...")
        return
    
    # Check if venv exists
    result = subprocess.run(
        ["wsl", "bash", "-c", f"test -d '{WSL_PATH}/voice_env' && echo 'exists'"],
        capture_output=True, text=True
    )
    
    if "exists" not in result.stdout:
        print(f"\nERROR: Virtual environment not found at: {WSL_PATH}/voice_env")
        print("\nPlease run these commands in WSL:")
        print(f"  cd {WSL_PATH}")
        print("  python -m venv voice_env")
        print("  source voice_env/bin/activate")
        print("  pip install -r requirements.txt")
        input("\nPress Enter to exit...")
        return
    
    print("\nStarting Seven in WSL...")
    print("(This window will close when Seven exits)\n")
    
    # Launch Seven in WSL
    wsl_command = f"cd '{WSL_PATH}' && source voice_env/bin/activate && python main.py"
    
    try:
        subprocess.run(
            ["wsl", "-d", WSL_DISTRO, "bash", "-c", wsl_command],
            check=True
        )
    except KeyboardInterrupt:
        print("\n\nSeven stopped by user.")
    except Exception as e:
        print(f"\nERROR: {e}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()