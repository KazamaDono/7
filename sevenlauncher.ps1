# SevenLauncher.ps1 - Complete launcher with error handling
Add-Type -AssemblyName System.Windows.Forms

# Configuration
$WSLDistro = "Ubuntu"  # Change to your WSL distribution
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WSLPath = $ScriptDir -replace '\\', '/'

# Function to show message box
function Show-Message {
    param($Title, $Message, $Type = "Info")
    [System.Windows.Forms.MessageBox]::Show($Message, $Title, [System.Windows.Forms.MessageBoxButtons]::OK, $Type)
}

# Check if WSL is available
$wslCheck = wsl --status 2>$null
if ($LASTEXITCODE -ne 0) {
    Show-Message -Title "Seven Error" -Message "WSL is not installed or not running. Please install WSL first." -Type "Error"
    exit 1
}

# Check if venv exists in WSL
$venvCheck = wsl bash -c "test -d '$WSLPath/voice_env' && echo 'exists'"
if ($venvCheck -ne "exists") {
    Show-Message -Title "Seven Error" -Message "Virtual environment not found at: $WSLPath/voice_env`n`nPlease run: cd $WSLPath && python -m venv voice_env && source voice_env/bin/activate && pip install -r requirements.txt" -Type "Error"
    exit 1
}

# Check if main.py exists
if (-not (Test-Path "$ScriptDir\main.py")) {
    Show-Message -Title "Seven Error" -Message "main.py not found in: $ScriptDir" -Type "Error"
    exit 1
}

# Hide console window
$windowStyle = if ($args[0] -eq '-hidden') { "Hidden" } else { "Normal" }

# Launch Seven
try {
    $wslCommand = "cd '$WSLPath' && source voice_env/bin/activate && python main.py"
    
    if ($windowStyle -eq "Hidden") {
        # Run hidden
        Start-Process -FilePath "wsl.exe" -ArgumentList "-d $WSLDistro -- bash -c `"$wslCommand`"" -WindowStyle Hidden
    } else {
        # Run with console
        wsl -d $WSLDistro -- bash -c "$wslCommand"
    }
}
catch {
    Show-Message -Title "Seven Error" -Message "Failed to launch Seven: $_" -Type "Error"
    exit 1
}