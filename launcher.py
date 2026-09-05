"""
Seven AI Assistant Launcher
Entry point for the standalone executable
"""

import sys
import os
import subprocess
import platform
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []
    
    try:
        import pygame
    except ImportError:
        missing.append("pygame")
    
    try:
        import speech_recognition
    except ImportError:
        missing.append("speech_recognition")
    
    try:
        import edge_tts
    except ImportError:
        missing.append("edge-tts")
    
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        missing.append("langchain-ollama")
    
    try:
        import PIL
    except ImportError:
        missing.append("pillow")
    
    return missing

def install_dependencies():
    """Install missing dependencies"""
    print("Installing missing dependencies...")
    packages = [
        "pygame",
        "SpeechRecognition",
        "edge-tts",
        "langchain-ollama",
        "pillow",
        "pyaudio",
        "psutil",
        "requests",
        "python-dotenv",
        "schedule"
    ]
    
    for package in packages:
        print(f"Installing {package}...")
        subprocess.run([sys.executable, "-m", "pip", "install", package], 
                      capture_output=True)

def main():
    """Main entry point"""
    print("=" * 60)
    print("SEVEN - AI Assistant")
    print("=" * 60)
    
    # Check for dependencies
    missing = check_dependencies()
    if missing:
        print(f"\nMissing dependencies: {', '.join(missing)}")
        response = input("\nInstall missing dependencies? (y/n): ")
        if response.lower() == 'y':
            install_dependencies()
            print("\nDependencies installed. Please restart Seven.")
            input("\nPress Enter to exit...")
            return
        else:
            print("\nCannot continue without dependencies.")
            input("\nPress Enter to exit...")
            return
    
    # Import and run Seven
    try:
        from main import SevenCore, main as seven_main
        
        # Check if orb GIFs exist
        gif_dir = Path(__file__).parent
        idle_gif = gif_dir / "bs.gif"
        active_gif = gif_dir / "ws.gif"
        
        if not idle_gif.exists():
            print("\n[WARNING] bs.gif not found. Orb visualizer may not work properly.")
        if not active_gif.exists():
            print("[WARNING] ws.gif not found. Orb visualizer may not work properly.")
        
        print("\nStarting Seven...\n")
        
        # Run the main function
        seven_main()
        
    except ImportError as e:
        print(f"\nError importing Seven modules: {e}")
        print("\nMake sure all files are in the same directory:")
        print("  - main.py")
        print("  - seven_plugins.py")
        print("  - seven_orb.py")
        print("  - seven_network_security.py")
        print("  - bs.gif")
        print("  - ws.gif")
        input("\nPress Enter to exit...")
        
    except Exception as e:
        print(f"\nError running Seven: {e}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()