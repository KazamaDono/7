# launch_seven_fixed.ps1 - Fixed WSL path handling
param(
    [string]$WSLDistro = "Ubuntu"  # Change to your WSL distro name (run 'wsl -l' to see)
)

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Launching Seven AI Assistant" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Get the directory where this script is located (Windows path)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Windows path: $ScriptDir" -ForegroundColor Gray

# Convert Windows path to WSL path
# C:\Users\User\Downloads\seven -> /mnt/c/Users/User/Downloads/seven
$WSLPath = $ScriptDir -replace '\\', '/' -replace '^([A-Za-z]):', '/mnt/$1' -replace ' ', '\\ '
$WSLPath = $WSLPath.ToLower() -replace '/mnt/c/', '/mnt/c/'  # Keep case sensitivity
Write-Host "WSL path: $WSLPath" -ForegroundColor Gray

# Check if WSL is available
$wslCheck = wsl --status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: WSL is not installed or not running!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if the directory exists in WSL
$dirCheck = wsl bash -c "test -d '$WSLPath' && echo 'exists'"
if ($dirCheck -ne "exists") {
    Write-Host "ERROR: Directory not found in WSL: $WSLPath" -ForegroundColor Red
    Write-Host "`nPlease make sure you're running this script from the correct folder!" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if venv exists
$venvCheck = wsl bash -c "test -d '$WSLPath/voice_env' && echo 'exists'"
if ($venvCheck -ne "exists") {
    Write-Host "`nVirtual environment not found at: $WSLPath/voice_env" -ForegroundColor Yellow
    Write-Host "Creating virtual environment..." -ForegroundColor Green
    
    # Create venv
    Write-Host "Running: python -m venv voice_env" -ForegroundColor Gray
    wsl bash -c "cd '$WSLPath' && python3 -m venv voice_env"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment!" -ForegroundColor Red
        Write-Host "Make sure Python3 is installed in WSL." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    # Install requirements if requirements.txt exists
    $requirementsCheck = wsl bash -c "test -f '$WSLPath/requirements.txt' && echo 'exists'"
    if ($requirementsCheck -eq "exists") {
        Write-Host "Installing requirements..." -ForegroundColor Green
        wsl bash -c "cd '$WSLPath' && source voice_env/bin/activate && pip install -r requirements.txt"
    } else {
        Write-Host "No requirements.txt found. Installing core packages..." -ForegroundColor Yellow
        wsl bash -c "cd '$WSLPath' && source voice_env/bin/activate && pip install pygame SpeechRecognition edge-tts langchain-ollama pillow psutil requests python-dotenv schedule pyaudio"
    }
    
    Write-Host "Virtual environment setup complete!" -ForegroundColor Green
}

# Check if main.py exists
$mainCheck = wsl bash -c "test -f '$WSLPath/main.py' && echo 'exists'"
if ($mainCheck -ne "exists") {
    Write-Host "ERROR: main.py not found in: $WSLPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "`nStarting Seven AI Assistant..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Launch Seven
$wslCommand = "cd '$WSLPath' && source voice_env/bin/activate && python main.py"
wsl -d $WSLDistro -- bash -c "$wslCommand"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Seven has exited." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Read-Host "Press Enter to exit"