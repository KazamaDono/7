@echo off
echo ============================================================
echo                    BUILDING SEVEN.EXE
echo ============================================================
echo.

:: Check if icon exists
if not exist "seven_icon.ico" (
    echo [!] seven_icon.ico not found!
    echo [*] Place your .ico file in this folder as 'seven_icon.ico'
    pause
    exit /b
)

:: Install PyInstaller if needed
echo [*] Installing PyInstaller...
pip install pyinstaller

echo.
echo [*] Building Seven.exe...
pyinstaller --name="Seven" ^
    --onefile ^
    --windowed ^
    --icon="seven_icon.ico" ^
    --add-data="bs.gif;." ^
    --add-data="ws.gif;." ^
    --add-data="seven_plugins.py;." ^
    --add-data="seven_network_security.py;." ^
    --add-data="seven_orb.py;." ^
    --hidden-import=speech_recognition ^
    --hidden-import=pyaudio ^
    --hidden-import=pygame ^
    --hidden-import=PIL ^
    --hidden-import=edge_tts ^
    --hidden-import=langchain_ollama ^
    --collect-all=speech_recognition ^
    main.py

echo.
echo ============================================================
echo                      BUILD COMPLETE!
echo ============================================================
echo.
echo Your executable: dist\Seven.exe
echo.
echo Double-click Seven.exe to run!
echo ============================================================
pause