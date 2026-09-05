@echo off
setlocal enabledelayedexpansion

echo ================================================================================
echo                     SEVEN AI - WINDOWS APPLICATION PACKAGER
echo ================================================================================
echo.

:: Create Seven Installer folder
echo Creating Seven Installer...
mkdir "Seven Installer" 2>nul

:: Create installer batch file
(
echo @echo off
echo echo ================================================================================
echo echo                         SEVEN AI - INSTALLER
echo echo ================================================================================
echo echo.
echo echo This will install Seven AI Assistant on your system.
echo echo The installation may take several minutes.
echo echo.
echo pause
echo.
echo :: Run WSL commands
echo wsl bash -c "cd $(wsl wslpath -a '%CD%') && chmod +x install_seven.sh && ./install_seven.sh"
echo.
echo echo.
echo echo ================================================================================
echo echo                         INSTALLATION COMPLETE!
echo echo ================================================================================
echo echo.
echo echo You can now close this window and use Seven.lnk to start the assistant.
echo pause
) > "Seven Installer\Install Seven.bat"

:: Create shortcut for installer
powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%CD%\Seven Installer.lnk'); $SC.TargetPath = '%CD%\Seven Installer\Install Seven.bat'; $SC.WorkingDirectory = '%CD%\Seven Installer'; $SC.Save()"

echo ✓ Seven Installer created
echo.

:: Create Seven folder
echo Creating Seven...
mkdir "Seven" 2>nul

:: Create Seven batch file
(
echo @echo off
echo.
echo :: Check if installed
echo if not exist "..\voice_env" (
echo     powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Seven is not installed yet! Please run Seven Installer first.', 'Seven AI', 'OK', 'Warning')"
echo     exit /b 1
echo )
echo.
echo :: Set environment
echo set PULSE_SERVER=127.0.0.1
echo.
echo :: Start Ollama if not running
echo tasklist /fi "ImageName eq ollama.exe" ^| find /i "ollama.exe" ^>nul
echo if errorlevel 1 (
echo     start /B ollama serve
echo     timeout /t 3 /nobreak ^>nul
echo )
echo.
echo :: Activate and run
echo cd ..
echo call voice_env\Scripts\activate.bat
echo python main.py
echo.
echo :: Keep window open if error
echo if errorlevel 1 pause
) > "Seven\Seven.bat"

:: Create shortcut for Seven
powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%CD%\Seven.lnk'); $SC.TargetPath = '%CD%\Seven\Seven.bat'; $SC.WorkingDirectory = '%CD%\Seven'; $SC.IconLocation = '%SystemRoot%\System32\imageres.dll,65'; $SC.Save()"

echo ✓ Seven created
echo.

echo ================================================================================
echo                              APPS CREATED SUCCESSFULLY!
echo ================================================================================
echo.
echo   1. Double-click "Seven Installer.lnk" to set up Seven (one-time only)
echo   2. Double-click "Seven.lnk" to run Seven anytime after installation
echo.
echo You can move these shortcuts anywhere (Desktop, Start Menu, etc.)
echo ================================================================================
pause