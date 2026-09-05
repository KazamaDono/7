"""
seven_plugins.py - Extensible plugins for Seven AI Assistant
Enhanced with file search, app launcher, and advanced file operations
"""

import os
import time
import threading
import subprocess
import platform
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
import json
import glob
from seven_network_security import SecurityPlugin



# For scheduling (lightweight, no GUI)
import schedule

# ----------------------------------------------------------------------
# Lazy loaders for optional features
# ----------------------------------------------------------------------
def _get_pyautogui():
    """Lazy import pyautogui only when needed"""
    try:
        import pyautogui
        return pyautogui
    except ImportError:
        raise ImportError("pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        raise ImportError(f"pyautogui unavailable: {e}")

def _get_cv2():
    """Lazy import cv2 only when needed"""
    try:
        import cv2
        return cv2
    except ImportError:
        raise ImportError("opencv-python not installed. Run: pip install opencv-python")

def _get_numpy():
    """Lazy import numpy only when needed"""
    try:
        import numpy as np
        return np
    except ImportError:
        raise ImportError("numpy not installed. Run: pip install numpy")

# ----------------------------------------------------------------------
# Application Manager - Fixed with direct VPN command
# ----------------------------------------------------------------------
class AppManager:
    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        
        # Full paths for apps
        self.app_paths = {
            "proton vpn": [
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Proton\Proton VPN.lnk",
                r"C:\Program Files\Proton Technologies\Proton VPN\ProtonVPN.exe",
            ],
            "vpn": [
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Proton\Proton VPN.lnk",
                r"C:\Program Files\Proton Technologies\Proton VPN\ProtonVPN.exe",
            ],
            "vscode": [
                r"C:\Users\User\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
            "code": [
                r"C:\Users\User\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
            "ollama": [
                r"C:\Users\User\AppData\Local\Programs\Ollama\ollama.exe",
                r"C:\Program Files\Ollama\ollama.exe",
            ],
            "telegram": [
                r"C:\Users\User\AppData\Roaming\Telegram Desktop\Telegram.exe",
                r"C:\Program Files\Telegram Desktop\Telegram.exe",
            ],
            "discord": [
                r"C:\Users\User\AppData\Local\Discord\app-1.0.9166\Discord.exe",
                r"C:\Program Files\Discord\Discord.exe",
            ],
            "notion": [
                r"C:\Users\User\AppData\Local\Programs\Notion\Notion.exe",
                r"C:\Program Files\Notion\Notion.exe",
            ],
            "greenshot": [
                r"C:\Program Files\Greenshot\Greenshot.exe",
                r"C:\Program Files (x86)\Greenshot\Greenshot.exe",
            ],
            "spotify": [
                r"C:\Users\User\AppData\Roaming\Spotify\Spotify.exe",
                r"C:\Program Files\Spotify\Spotify.exe",
            ],
            "clock": [
                r"shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            "ms-clock:",  # Windows protocol URI
            ],
            "alarms": [
                r"shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            "ms-clock:",
            ],
            "timer": [
            r"shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            "ms-clock:",
            ],
            "windows clock": [
                r"shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            "ms-clock:",
            ],
            "clock timer": [
                "ms-clock:timer",
                "shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            ],
            "clock alarms": [
                "ms-clock:alarms",
                "shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            ],
            "clock stopwatch": [
                "ms-clock:stopwatch",
                "shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
            ],
        }
        
        # System apps that work with simple commands
        self.system_apps = {
            "powershell": "powershell.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "file explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "control panel": "control.exe",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
        }
    
    def launch_app(self, app_name: str) -> Dict[str, any]:
        """Launch an application by name"""
        app_key = app_name.lower().strip()
        
        print(f"[DEBUG] Looking for app: '{app_key}'")
        
        # Special case for VPN - use the exact working command
        if app_key == "vpn" or "vpn" in app_key:
            print(f"[DEBUG] VPN detected, using direct PowerShell command")
            return self._launch_vpn()
        
        if app_key in ["clock", "alarms", "timer", "stopwatch", "windows clock"]:
            print(f"[DEBUG] Windows Clock detected")
            return self._launch_clock()       
        # Special case for Windows Clock with specific tabs
        if app_key in ["clock timer", "timer tab", "clock timer tab"]:
            return self._launch_clock("timer")
        if app_key in ["clock alarms", "alarms tab"]:
            return self._launch_clock("alarms")
        if app_key in ["clock stopwatch", "stopwatch tab"]:
            return self._launch_clock("stopwatch") 

        # Check for partial matches in app_paths
        for key, paths in self.app_paths.items():
            if app_key in key or key in app_key:
                print(f"[DEBUG] Matched app_paths key: '{key}'")
                for path in paths:
                    # For .lnk files, try directly without existence check
                    if path.endswith('.lnk'):
                        print(f"[DEBUG] Using .lnk file: {path}")
                        return self._launch_with_powershell(path)
                    elif Path(path).exists():
                        print(f"[DEBUG] Found existing path: {path}")
                        return self._launch_with_powershell(path)
        
        # Check system apps
        for key, cmd in self.system_apps.items():
            if app_key in key or key in app_key:
                print(f"[DEBUG] Matched system_apps key: '{key}' -> {cmd}")
                return self._launch_command(cmd)
        
        return {"success": False, "error": f"Could not find {app_name}"}
    
    def _launch_vpn(self) -> Dict[str, any]:
        """Special method to launch VPN using the exact working command"""
        try:
            # Use the exact command that works from your test
            cmd = ['powershell.exe', '-Command', "Start-Process 'C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Proton\\Proton VPN.lnk'"]
            
            subprocess.Popen(cmd, shell=False)
            
            return {"success": True, "message": "Launched Proton VPN"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _launch_with_powershell(self, path: str) -> Dict[str, any]:
        """Launch using PowerShell Start-Process"""
        try:
            cmd = ['powershell.exe', '-Command', f"Start-Process '{path}'"]
            
            subprocess.Popen(cmd, shell=False)
            
            clean_name = Path(path).stem.replace('.lnk', '').replace('.exe', '')
            return {"success": True, "message": f"Launched {clean_name}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _launch_command(self, command: str) -> Dict[str, any]:
        """Launch a system command"""
        try:
            subprocess.Popen([command], shell=False)
            return {"success": True, "message": f"Launched {command.replace('.exe', '')}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def open_file_explorer(self, path: str = None) -> Dict[str, any]:
        """Open file explorer at specified path"""
        try:
            if path is None:
                path = str(Path.home())
            
            if path.startswith('/mnt/c/'):
                path = path.replace('/mnt/c/', 'C:\\').replace('/', '\\')
            
            subprocess.Popen(['explorer.exe', path])
            return {"success": True, "message": f"Opened explorer at {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def open_with_default_app(self, filepath: str) -> Dict[str, any]:
        """Open a file with its default application"""
        try:
            full_path = Path(filepath).expanduser().resolve()
            if not full_path.exists():
                return {"success": False, "error": f"File not found: {filepath}"}
            
            windows_path = str(full_path)
            if windows_path.startswith('/mnt/c/'):
                windows_path = windows_path.replace('/mnt/c/', 'C:\\').replace('/', '\\')
            
            return self._launch_with_powershell(windows_path)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _launch_clock(self, tab: str = None) -> Dict[str, any]:
        """Launch Windows Clock app with optional tab (alarms, timer, stopwatch)"""
        try:
            if tab:
                # Open specific tab
                subprocess.Popen(['cmd', '/c', f'start ms-clock:{tab}'], shell=False)
                return {"success": True, "message": f"Launched Windows Clock - {tab} tab"}
            else:
                # Use shell:AppsFolder (most reliable for Windows Store apps)
                cmd = ['explorer.exe', 'shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App']
                subprocess.Popen(cmd, shell=False)
                return {"success": True, "message": "Launched Windows Clock"}
        except Exception as e:
            # Fallback to URI protocol
            try:
                subprocess.Popen(['cmd', '/c', 'start ms-clock:'], shell=False)
                return {"success": True, "message": "Launched Windows Clock"}
            except:
                return {"success": False, "error": f"Could not launch Clock: {str(e)}"}
            
            
    def set_windows_timer(self, minutes: int, seconds: int = 0) -> Dict[str, any]:
        """Set a timer in the Windows Clock app"""
        try:
            total_seconds = (minutes * 60) + seconds
            
            # Method 1: Use ms-clock: URI with timer parameter (if supported)
            # This opens the timer tab directly
            subprocess.Popen(['cmd', '/c', 'start ms-clock:timer'], shell=False)
            time.sleep(0.5)  # Wait for app to open
            
            # Method 2: Use PowerShell to automate the timer setting
            # This simulates keyboard input to set the timer
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            Start-Sleep -Milliseconds 500
            [System.Windows.Forms.SendKeys]::SendWait("^t")
            Start-Sleep -Milliseconds 300
            [System.Windows.Forms.SendKeys]::SendWait("{{TAB}}")
            Start-Sleep -Milliseconds 100
            
            # Set hours
            $hours = [Math]::Floor({minutes} / 60)
            $remainingMinutes = {minutes} % 60
            
            if ($hours -gt 0) {{
                for ($i = 0; $i -lt $hours; $i++) {{
                    [System.Windows.Forms.SendKeys]::SendWait("{{UP}}")
                    Start-Sleep -Milliseconds 50
                }}
                [System.Windows.Forms.SendKeys]::SendWait("{{TAB}}")
                Start-Sleep -Milliseconds 100
            }}
            
            # Set minutes
            if ($remainingMinutes -gt 0) {{
                for ($i = 0; $i -lt $remainingMinutes; $i++) {{
                    [System.Windows.Forms.SendKeys]::SendWait("{{UP}}")
                    Start-Sleep -Milliseconds 50
                }}
                [System.Windows.Forms.SendKeys]::SendWait("{{TAB}}")
                Start-Sleep -Milliseconds 100
            }}
            
            # Set seconds
            if ({seconds} -gt 0) {{
                for ($i = 0; $i -lt {seconds}; $i++) {{
                    [System.Windows.Forms.SendKeys]::SendWait("{{UP}}")
                    Start-Sleep -Milliseconds 50
                }}
            }}
            
            # Start the timer
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
            '''
            
            # Run the automation in background
            threading.Thread(target=lambda: subprocess.run(
                ['powershell.exe', '-Command', ps_script], 
                capture_output=True, 
                timeout=10
            ), daemon=True).start()
            
            return {"success": True, "message": f"Opening Windows Clock and setting timer for {minutes} minutes and {seconds} seconds"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def open_timer_tab(self) -> Dict[str, any]:
        """Open the Clock app directly to the Timer tab"""
        try:
            subprocess.Popen(['cmd', '/c', 'start ms-clock:timer'], shell=False)
            return {"success": True, "message": "Opened Windows Clock Timer tab"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ----------------------------------------------------------------------
# File Search Manager - Advanced file searching capabilities
# ----------------------------------------------------------------------
class FileSearchManager:
    def __init__(self):
        self.search_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            Path.home() / "Pictures",
            Path.home() / "Videos",
            Path.home() / "Music",
        ]
    
    def search_files(self, query: str, search_root: str = None) -> List[Path]:
        """Search for files matching query"""
        found_files = []
        query_lower = query.lower()
        
        if search_root:
            roots = [Path(search_root)]
        else:
            roots = self.search_dirs
        
        for root in roots:
            if not root.exists():
                continue
            
            try:
                for filepath in root.rglob('*'):
                    if not filepath.is_file():
                        continue
                    
                    if query_lower in filepath.name.lower():
                        found_files.append(filepath)
                        
                    if len(found_files) >= 100:
                        break
            except (PermissionError, OSError):
                continue
            
            if len(found_files) >= 100:
                break
        
        return found_files
    
    def search_by_extension(self, extension: str, search_root: str = None) -> List[Path]:
        """Search for files with specific extension"""
        found_files = []
        
        if not extension.startswith('.'):
            extension = '.' + extension
        
        if search_root:
            roots = [Path(search_root)]
        else:
            roots = self.search_dirs
        
        for root in roots:
            if not root.exists():
                continue
            
            try:
                for filepath in root.rglob(f'*{extension}'):
                    if filepath.is_file():
                        found_files.append(filepath)
                        
                    if len(found_files) >= 100:
                        break
            except (PermissionError, OSError):
                continue
            
            if len(found_files) >= 100:
                break
        
        return found_files
    
    def search_recent_files(self, days: int = 7) -> List[Path]:
        """Search for recently modified files"""
        recent_files = []
        cutoff_time = datetime.now() - timedelta(days=days)
        
        for root in self.search_dirs:
            if not root.exists():
                continue
            
            try:
                for filepath in root.rglob('*'):
                    if not filepath.is_file():
                        continue
                    
                    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                    if mtime > cutoff_time:
                        recent_files.append((mtime, filepath))
            except (PermissionError, OSError):
                continue
        
        recent_files.sort(reverse=True)
        return [fp for _, fp in recent_files[:50]]
    
    def export_search_results(self, files: List[Path], output_file: str = None) -> Dict[str, any]:
        """Export search results to a file"""
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"search_results_{timestamp}.txt"
            
            output_path = Path(output_file)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Search Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, filepath in enumerate(files, 1):
                    f.write(f"{i}. {filepath}\n")
                    try:
                        size = filepath.stat().st_size
                        f.write(f"   Size: {size:,} bytes\n")
                        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                        f.write(f"   Modified: {mtime}\n\n")
                    except:
                        f.write("\n")
            
            # Open the file in notepad
            subprocess.Popen(['notepad.exe', str(output_path)])
            
            return {
                "success": True,
                "path": str(output_path),
                "count": len(files),
                "message": f"Found {len(files)} files. Results exported to {output_file}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# ----------------------------------------------------------------------
# Screenshot Manager (Using Greenshot on Windows)
# ----------------------------------------------------------------------
class ScreenshotManager:
    def __init__(self, save_dir: str = "screenshots"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        
        self.greenshot_paths = [
            "/mnt/c/Program Files/Greenshot/Greenshot.exe",
            "/mnt/c/Program Files (x86)/Greenshot/Greenshot.exe",
        ]
        
        self.greenshot_cmd = self._find_greenshot()
        
        if self.greenshot_cmd:
            print(f"[✓] Greenshot found at: {self.greenshot_cmd}")
        else:
            print("[!] Greenshot not found. Using PowerShell fallback.")
    
    def _find_greenshot(self) -> Optional[str]:
        for path in self.greenshot_paths:
            if Path(path).exists():
                return path
        return None
    
    def take_screenshot(self, filename: Optional[str] = None) -> Dict[str, any]:
        if self.greenshot_cmd:
            result = self._greenshot_screenshot(filename)
            if result["success"]:
                return result
        
        return self._powershell_screenshot(filename)
    
    def _greenshot_screenshot(self, filename: Optional[str] = None) -> Dict[str, any]:
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            filepath = self.save_dir / filename
            abs_path = str(filepath.absolute())
            
            if abs_path.startswith('/mnt/c/'):
                windows_path = abs_path.replace('/mnt/c/', 'C:\\').replace('/', '\\')
            else:
                windows_path = abs_path.replace('/', '\\')
            
            cmd = [
                self.greenshot_cmd,
                "/capture=fullscreen",
                f"/saveas={windows_path}",
                "/exit"
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if filepath.exists() and filepath.stat().st_size > 0:
                return {
                    "success": True,
                    "path": str(filepath),
                    "message": f"Screenshot saved: {filename}"
                }
            else:
                return {
                    "success": True,
                    "message": "Greenshot opened. Use it to capture and save your screenshot."
                }
        except Exception as e:
            return {"success": False, "error": f"Greenshot error: {str(e)}"}
    
    def _powershell_screenshot(self, filename: Optional[str] = None) -> Dict[str, any]:
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            filepath = self.save_dir / filename
            abs_path = str(filepath.absolute())
            
            if abs_path.startswith('/mnt/c/'):
                windows_path = abs_path.replace('/mnt/c/', 'C:\\').replace('/', '\\')
            else:
                windows_path = abs_path
            
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            $screen = [System.Windows.Forms.SystemInformation]::VirtualScreen
            $bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($screen.X, $screen.Y, 0, 0, $screen.Size)
            $bitmap.Save("{windows_path}")
            $graphics.Dispose()
            $bitmap.Dispose()
            '''
            
            subprocess.run(['powershell.exe', '-Command', ps_script], timeout=10)
            
            if filepath.exists() and filepath.stat().st_size > 0:
                return {
                    "success": True,
                    "path": str(filepath),
                    "message": f"Screenshot saved: {filename}"
                }
            else:
                return {"success": False, "error": "PowerShell screenshot failed"}
        except Exception as e:
            return {"success": False, "error": f"PowerShell error: {str(e)}"}

# ----------------------------------------------------------------------
# Screen Recorder
# ----------------------------------------------------------------------
class ScreenRecorder:
    def __init__(self, save_dir: str = "recordings"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.recording = False
        self.recording_thread = None
        self.output_file = None
    
    def start_recording(self, filename: Optional[str] = None) -> Dict[str, any]:
        if self.recording:
            return {"success": False, "error": "Already recording"}
        
        try:
            pyautogui = _get_pyautogui()
            cv2 = _get_cv2()
            np = _get_numpy()
        except ImportError as e:
            return {"success": False, "error": str(e)}
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.avi"
        
        self.output_file = self.save_dir / filename
        self.recording = True
        
        self.recording_thread = threading.Thread(
            target=self._record_loop,
            args=(pyautogui, cv2, np),
            daemon=True
        )
        self.recording_thread.start()
        
        return {"success": True, "message": f"Recording started. Will save to {self.output_file}"}
    
    def _record_loop(self, pyautogui, cv2, np):
        screen_size = pyautogui.size()
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(str(self.output_file), fourcc, 20.0, (screen_size.width, screen_size.height))
        
        while self.recording:
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)
            time.sleep(0.05)
        
        out.release()
    
    def stop_recording(self) -> Dict[str, any]:
        if not self.recording:
            return {"success": False, "error": "Not recording"}
        
        self.recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=5)
        
        return {
            "success": True,
            "path": str(self.output_file),
            "message": f"Recording saved: {self.output_file}"
        }

# ----------------------------------------------------------------------
# Scheduler & Alarms - Enhanced with multiple alarm types
# ----------------------------------------------------------------------
class Scheduler:
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self.jobs = []
        self.running = True
        self.alarms = {}  # Store active alarms
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
    
    def _run_scheduler(self):
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def set_alarm(self, time_str: str, message: str) -> Dict[str, any]:
        """
        Set a one-time alarm at specific time.
        Formats: "3:30 PM", "15:30", "7:00 AM"
        """
        try:
            # Parse time
            time_str = time_str.strip()
            if 'am' in time_str.lower() or 'pm' in time_str.lower():
                alarm_time = datetime.strptime(time_str, "%I:%M %p")
            else:
                # Try 24-hour format
                if ':' in time_str:
                    alarm_time = datetime.strptime(time_str, "%H:%M")
                else:
                    # Assume it's just hour
                    alarm_time = datetime.strptime(time_str, "%H")
            
            now = datetime.now()
            alarm_datetime = now.replace(
                hour=alarm_time.hour, 
                minute=alarm_time.minute, 
                second=0
            )
            
            # If time already passed today, set for tomorrow
            if alarm_datetime <= now:
                alarm_datetime += timedelta(days=1)
            
            delay_seconds = (alarm_datetime - now).total_seconds()
            
            # Create job
            job_id = f"alarm_{int(time.time())}"
            job = schedule.every(delay_seconds).seconds.do(
                self._trigger_alarm, message, job_id
            )
            
            self.alarms[job_id] = {
                'type': 'alarm',
                'time': alarm_datetime,
                'message': message,
                'job': job
            }
            self.jobs.append(job)
            
            return {
                "success": True,
                "message": f"Alarm set for {alarm_datetime.strftime('%I:%M %p')}: '{message}'"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def set_timer(self, minutes: int, message: str = None) -> Dict[str, any]:
        """Set a timer for X minutes"""
        try:
            if minutes <= 0:
                return {"success": False, "error": "Time must be positive"}
            
            if message is None:
                message = f"Timer for {minutes} minute(s) has finished"
            
            delay_seconds = minutes * 60
            job_id = f"timer_{int(time.time())}"
            
            job = schedule.every(delay_seconds).seconds.do(
                self._trigger_alarm, message, job_id
            )
            
            self.alarms[job_id] = {
                'type': 'timer',
                'duration': minutes,
                'message': message,
                'job': job,
                'end_time': datetime.now() + timedelta(minutes=minutes)
            }
            self.jobs.append(job)
            
            return {
                "success": True,
                "message": f"Timer set for {minutes} minute(s). I'll remind you when it's done."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def set_seconds_timer(self, seconds: int, message: str = None) -> Dict[str, any]:
        """Set a timer for X seconds (for short intervals)"""
        try:
            if seconds <= 0:
                return {"success": False, "error": "Time must be positive"}
            
            if message is None:
                message = f"Timer for {seconds} second(s) has finished"
            
            delay_seconds = seconds
            job_id = f"second_timer_{int(time.time())}"
            
            job = schedule.every(delay_seconds).seconds.do(
                self._trigger_alarm, message, job_id
            )
            
            self.alarms[job_id] = {
                'type': 'second_timer',
                'duration': seconds,
                'message': message,
                'job': job,
                'end_time': datetime.now() + timedelta(seconds=seconds)
            }
            self.jobs.append(job)
            
            return {
                "success": True,
                "message": f"Timer set for {seconds} second(s)."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def set_recurring_alarm(self, time_str: str, message: str, days: List[int] = None) -> Dict[str, any]:
        """
        Set a recurring alarm (daily or specific days)
        days: List of days (0=Monday, 6=Sunday)
        """
        try:
            # Parse time
            if 'am' in time_str.lower() or 'pm' in time_str.lower():
                alarm_time = datetime.strptime(time_str, "%I:%M %p")
            else:
                alarm_time = datetime.strptime(time_str, "%H:%M")
            
            job_id = f"recurring_{int(time.time())}"
            
            if days is None:
                # Daily alarm
                job = schedule.every().day.at(time_str).do(
                    self._trigger_alarm, f"Daily reminder: {message}", job_id
                )
                schedule_text = f"daily at {time_str}"
            else:
                # Specific days
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                selected_days = [day_names[d] for d in days if 0 <= d <= 6]
                
                # Build schedule
                job = None
                for day in days:
                    if day == 0:
                        job = schedule.every().monday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                    elif day == 1:
                        job = schedule.every().tuesday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                    elif day == 2:
                        job = schedule.every().wednesday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                    elif day == 3:
                        job = schedule.every().thursday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                    elif day == 4:
                        job = schedule.every().friday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                    elif day == 5:
                        job = schedule.every().saturday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                    elif day == 6:
                        job = schedule.every().sunday.at(time_str).do(
                            self._trigger_alarm, f"Reminder: {message}", job_id
                        )
                
                schedule_text = f"on {', '.join(selected_days)} at {time_str}"
            
            if job:
                self.alarms[job_id] = {
                    'type': 'recurring',
                    'time': time_str,
                    'message': message,
                    'job': job
                }
                self.jobs.append(job)
                
                return {
                    "success": True,
                    "message": f"Recurring alarm set {schedule_text}: '{message}'"
                }
            
            return {"success": False, "error": "Could not set recurring alarm"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _trigger_alarm(self, message, job_id):
        """Trigger an alarm"""
        self.callback(f"⏰ {message}")
        
        # Remove one-time jobs
        if job_id in self.alarms:
            if self.alarms[job_id]['type'] in ['alarm', 'timer', 'second_timer']:
                # Remove one-time alarm
                for job in self.jobs:
                    if job == self.alarms[job_id]['job']:
                        schedule.cancel_job(job)
                        self.jobs.remove(job)
                        break
                del self.alarms[job_id]
        
        return schedule.CancelJob
    
    def list_alarms(self) -> List[Dict]:
        """Return list of pending alarms"""
        alarms_list = []
        for job_id, alarm in self.alarms.items():
            if alarm['type'] == 'timer':
                remaining = (alarm['end_time'] - datetime.now()).total_seconds()
                alarms_list.append({
                    'id': job_id,
                    'type': alarm['type'],
                    'message': alarm['message'],
                    'remaining_minutes': int(remaining / 60),
                    'remaining_seconds': int(remaining)
                })
            elif alarm['type'] == 'second_timer':
                remaining = (alarm['end_time'] - datetime.now()).total_seconds()
                alarms_list.append({
                    'id': job_id,
                    'type': alarm['type'],
                    'message': alarm['message'],
                    'remaining_seconds': int(remaining)
                })
            elif alarm['type'] == 'alarm':
                alarms_list.append({
                    'id': job_id,
                    'type': alarm['type'],
                    'message': alarm['message'],
                    'time': alarm['time'].strftime('%I:%M %p')
                })
            elif alarm['type'] == 'recurring':
                alarms_list.append({
                    'id': job_id,
                    'type': alarm['type'],
                    'message': alarm['message'],
                    'time': alarm['time']
                })
        return alarms_list
    
    def cancel_alarm(self, alarm_id: str = None) -> Dict[str, any]:
        """Cancel a specific alarm or all alarms"""
        try:
            if alarm_id is None:
                # Cancel all alarms
                count = len(self.alarms)
                for job in self.jobs:
                    schedule.cancel_job(job)
                self.jobs.clear()
                self.alarms.clear()
                return {"success": True, "message": f"Cancelled {count} alarms"}
            
            # Cancel specific alarm
            if alarm_id in self.alarms:
                schedule.cancel_job(self.alarms[alarm_id]['job'])
                self.jobs.remove(self.alarms[alarm_id]['job'])
                del self.alarms[alarm_id]
                return {"success": True, "message": "Alarm cancelled"}
            
            return {"success": False, "error": "Alarm not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def snooze_alarm(self, minutes: int = 5) -> Dict[str, any]:
        """Snooze the last triggered alarm"""
        # This would need to track last alarm, simplified version
        return {"success": True, "message": f"Snoozed for {minutes} minutes"}
    
    def shutdown(self):
        self.running = False

# ----------------------------------------------------------------------
# Program Executor
# ----------------------------------------------------------------------
class ProgramExecutor:
    def __init__(self):
        self.system = platform.system()
    
    def launch_program(self, path: str, args: str = "") -> Dict[str, any]:
        try:
            full_path = Path(path).expanduser().resolve()
            if not full_path.exists():
                return {"success": False, "error": f"File not found: {path}"}
            
            if self.system == "Windows":
                if full_path.suffix.lower() in ['.exe', '.bat', '.cmd']:
                    subprocess.Popen([str(full_path)] + (args.split() if args else []), shell=False)
                else:
                    os.startfile(str(full_path))
            else:
                if full_path.suffix.lower() in ['.sh', ''] and os.access(full_path, os.X_OK):
                    subprocess.Popen([str(full_path)] + (args.split() if args else []))
                else:
                    subprocess.Popen(["xdg-open", str(full_path)])
            
            return {"success": True, "message": f"Launched: {full_path.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ----------------------------------------------------------------------
# Hologram / 3D gesture-controlled viewer (webcam + MediaPipe)
# ----------------------------------------------------------------------
class HologramPlugin:
    """Launches the OpenCV/MediaPipe hand-gesture 3D holographic viewer."""

    def __init__(self):
        self.module_dir = Path(__file__).parent / "hologram"
        self.script = self.module_dir / "hologram_viewer.py"
        # Legacy mediapipe.solutions.hands has no compiled build for Seven's
        # Python 3.14 venv, so this module runs on its own Python 3.11 venv.
        self.python = self.module_dir / ".venv" / "bin" / "python3"
        self.process: Optional[subprocess.Popen] = None

    def launch(self) -> Dict[str, any]:
        if self.process and self.process.poll() is None:
            return {"success": True, "message": "The hologram interface is already open, sir."}

        if not self.script.exists():
            return {"success": False, "message": "Hologram module not found."}

        if not self.python.exists():
            return {"success": False, "message": "Hologram environment not set up yet."}

        try:
            self.process = subprocess.Popen(
                [str(self.python), str(self.script)],
                cwd=str(self.module_dir),
            )
            return {
                "success": True,
                "message": "Opening the holographic interface now, sir. Press Q in that window to close it.",
            }
        except Exception as e:
            return {"success": False, "message": f"Could not open the hologram interface: {e}"}

# ----------------------------------------------------------------------
# Plugin Manager - Enhanced with all new capabilities
# ----------------------------------------------------------------------
class PluginManager:
    """Central registry for all extra commands."""

    def __init__(self, seven_core):
        self.seven = seven_core
        self.screenshot_mgr = ScreenshotManager()
        self.recorder = ScreenRecorder()
        self.scheduler = Scheduler(self.seven.speak)
        self.program_exec = ProgramExecutor()
        self.app_manager = AppManager()
        self.file_search = FileSearchManager()
        self.security = SecurityPlugin(seven_core)
        self.hologram = HologramPlugin()

    def process_command(self, command: str) -> Tuple[bool, str]:
        """Check if command matches any plugin and execute."""
        cmd_lower = command.lower().strip()
        print(f"[DEBUG] PluginManager processing: '{command[:50]}'")

        # --- Hologram / 3D gesture viewer ---
        if re.search(r'\b(hologram|holographic|gesture\s+(mode|control|interface)|3d\s+(interface|viewer|mode))\b', cmd_lower):
            result = self.hologram.launch()
            return True, result["message"]

        # --- Launch Applications ---
        # Defer "open a terminal" and terminal/TUI monitoring tools to the smart
        # agent (it has an open_terminal tool that works on this Linux desktop).
        defer_to_agent = re.search(
            r'\b(terminal|console|shell|htop|btop|nvtop|glances|top|nvidia-smi|watch|tail|journalctl)\b',
            cmd_lower,
        )
        app_match = re.search(r'(?:open|launch|start)\s+(.+?)$', command, re.IGNORECASE)
        if app_match and not defer_to_agent:
            app_name = app_match.group(1).strip()
            print(f"[DEBUG] Attempting to launch: '{app_name}'")
            result = self.app_manager.launch_app(app_name)
            if result["success"]:
                return True, result["message"]
            else:
                return True, f"Could not launch {app_name}: {result.get('error', 'App not found')}"
        
        # --- Open File Explorer ---
        if re.search(r'open\s+file\s+explorer', cmd_lower):
            path_match = re.search(r'(?:at|in)\s+(.+?)$', command, re.IGNORECASE)
            path = path_match.group(1) if path_match else None
            result = self.app_manager.open_file_explorer(path)
            return True, result["message"]
        
        # --- Open file with default app ---
        if re.search(r'open\s+file\s+', cmd_lower):
            file_match = re.search(r'open\s+file\s+(.+?)$', command, re.IGNORECASE)
            if file_match:
                filepath = file_match.group(1).strip()
                result = self.app_manager.open_with_default_app(filepath)
                return True, result["message"]
        
        # --- File Search by name ---
        if re.search(r'search\s+for\s+.*\s+files', cmd_lower):
            query_match = re.search(r'search\s+for\s+(.+?)\s+files', cmd_lower)
            if query_match:
                query = query_match.group(1).strip()
                self.seven.speak(f"Searching for files containing '{query}'. This may take a moment, sir.")
                
                files = self.file_search.search_files(query)
                
                if files:
                    result = self.file_search.export_search_results(files)
                    return True, result["message"]
                else:
                    return True, f"No files found containing '{query}'"
        
        # --- File Search by extension ---
        if re.search(r'search\s+for\s+.*\s+files\s+with\s+extension', cmd_lower):
            ext_match = re.search(r'extension\s+(\w+)', cmd_lower)
            if ext_match:
                extension = ext_match.group(1)
                self.seven.speak(f"Searching for {extension} files, sir.")
                
                files = self.file_search.search_by_extension(extension)
                
                if files:
                    result = self.file_search.export_search_results(files)
                    return True, result["message"]
                else:
                    return True, f"No {extension} files found"
        
        # --- Recent files search ---
        if re.search(r'recent\s+files', cmd_lower):
            days_match = re.search(r'last\s+(\d+)\s+days', cmd_lower)
            days = int(days_match.group(1)) if days_match else 7
            
            self.seven.speak(f"Searching for files modified in the last {days} days, sir.")
            files = self.file_search.search_recent_files(days)
            
            if files:
                result = self.file_search.export_search_results(files)
                return True, result["message"]
            else:
                return True, f"No recent files found in the last {days} days"
        
        # --- Screenshot ---
        if re.search(r'(?:take|make|capture).*screenshot', cmd_lower):
            filename = None
            fn_match = re.search(r'as\s+(\S+\.png)', cmd_lower)
            if fn_match:
                filename = fn_match.group(1)
            result = self.screenshot_mgr.take_screenshot(filename)
            if result["success"]:
                if "path" in result:
                    return True, f"Screenshot saved: {result['path']}"
                else:
                    return True, result["message"]
            else:
                return True, f"Failed to take screenshot: {result.get('error', 'Unknown error')}"
        
        # --- Screen Recording ---
        if re.search(r'start\s+recording', cmd_lower):
            fn_match = re.search(r'as\s+(\S+\.avi)', cmd_lower)
            filename = fn_match.group(1) if fn_match else None
            result = self.recorder.start_recording(filename)
            return True, result["message"]
        
        if re.search(r'stop\s+recording', cmd_lower):
            result = self.recorder.stop_recording()
            return True, result["message"]
        
        
        
        
        # --- Alarms & Timers ---        
        
        
        
        
        if re.search(r'(?:list|show).*alarms?', cmd_lower):
            alarms = self.scheduler.list_alarms()
            if alarms:
                alarm_list = []
                for a in alarms:
                    if a['type'] == 'timer':
                        alarm_list.append(f"  - Timer: {a['message']} ({a['remaining_minutes']} min left)")
                    elif a['type'] == 'second_timer':
                        alarm_list.append(f"  - Timer: {a['message']} ({a['remaining_seconds']} seconds left)")
                    elif a['type'] == 'alarm':
                        alarm_list.append(f"  - Alarm: {a['message']} at {a['time']}")
                    elif a['type'] == 'recurring':
                        alarm_list.append(f"  - Recurring: {a['message']} at {a['time']}")
                
                return True, f"Active alarms:\n" + "\n".join(alarm_list)
            return True, "No active alarms, sir."
        
        # Check if there are any alarms
        if re.search(r'(?:are there|any).*alarms?', cmd_lower):
            alarms = self.scheduler.list_alarms()
            if alarms:
                return True, f"Yes, sir. You have {len(alarms)} active alarms."
            return True, "No active alarms at the moment, sir."
        
        # Cancel all alarms
        if re.search(r'cancel\s+all\s+alarms?', cmd_lower):
            result = self.scheduler.cancel_alarm()
            return True, result["message"]
        
        # Cancel specific alarm (by message)
        cancel_match = re.search(r'cancel\s+alarm\s+(?:called\s+)?["\']?(.+?)["\']?', cmd_lower)
        if cancel_match:
            alarm_identifier = cancel_match.group(1)
            for alarm_id, alarm in self.scheduler.alarms.items():
                if alarm_identifier.lower() in alarm['message'].lower():
                    result = self.scheduler.cancel_alarm(alarm_id)
                    return True, result["message"]
            return True, f"No alarm found matching '{alarm_identifier}', sir."
        
        # Set alarm at specific time
        alarm_match = re.search(r'(?:set|create).*alarm\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', cmd_lower)
        if alarm_match:
            time_str = alarm_match.group(1)
            msg_match = re.search(r'(?:for|to|with message|called)\s+(.+?)$', command, re.IGNORECASE)
            message = msg_match.group(1) if msg_match else "Alarm!"
            result = self.scheduler.set_alarm(time_str, message)
            return True, result["message"]
        
        # Set timer for X minutes
        timer_match = re.search(r'(?:set|start).*timer\s+for\s+(\d+)\s*(?:minute|min|m)', cmd_lower)
        if timer_match:
            minutes = int(timer_match.group(1))
            msg_match = re.search(r'(?:for|to|with message|called)\s+(.+?)$', command, re.IGNORECASE)
            message = msg_match.group(1) if msg_match else None
            result = self.scheduler.set_timer(minutes, message)
            return True, result["message"]
        
        # Set timer for X seconds
        seconds_match = re.search(r'(?:set|start).*timer\s+for\s+(\d+)\s*seconds?', cmd_lower)
        if seconds_match:
            seconds = int(seconds_match.group(1))
            msg_match = re.search(r'(?:for|to|with message|called)\s+(.+?)$', command, re.IGNORECASE)
            message = msg_match.group(1) if msg_match else None
            result = self.scheduler.set_seconds_timer(seconds, message)
            return True, result["message"]
        
        # Set recurring alarm
        recurring_match = re.search(r'(?:set|create).*recurring\s+alarm\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', cmd_lower)
        if recurring_match:
            time_str = recurring_match.group(1)
            msg_match = re.search(r'(?:for|to|with message|called)\s+(.+?)$', command, re.IGNORECASE)
            message = msg_match.group(1) if msg_match else "Recurring reminder!"
            result = self.scheduler.set_recurring_alarm(time_str, message)
            return True, result["message"]
        
        # --- Execute program by path ---
        # Only fire for an ACTUAL path/binary (contains a path separator or a file
        # extension). Natural phrases like "run a security audit" or "run
        # diagnostics" must fall through to the skills/agent, not be treated as a
        # program to launch (which also used to KeyError on a missing 'message').
        prog_match = re.search(r'(?:execute|launch|run)\s+(.+?)(?:\s+with\s+args\s+(.+))?$', command, re.IGNORECASE)
        if prog_match:
            path = prog_match.group(1).strip()
            looks_like_path = bool(re.search(r'[/~]', path) or re.search(r'\.\w{1,4}$', path))
            if looks_like_path:
                args = prog_match.group(2).strip() if prog_match.group(2) else ""
                result = self.program_exec.launch_program(path, args)
                return True, result.get("message") or result.get("error") or f"Attempted to launch {path}."
            # else: not a path -> let a better handler take it
        
        # Check security commands
        handled, response = self.security.process_command(command)
        if handled:
            return True, response
        
        
            # --- Windows Clock Timer Control ---
        
        # Set timer using Windows Clock app
        if re.search(r'(?:set|start).*timer\s+on\s+clock', cmd_lower) or \
           re.search(r'(?:set|start).*windows\s+timer', cmd_lower) or \
           (re.search(r'set\s+timer', cmd_lower) and re.search(r'clock', cmd_lower)):
            
            # Parse minutes
            minutes_match = re.search(r'(\d+)\s*(?:minute|min|m)', cmd_lower)
            minutes = int(minutes_match.group(1)) if minutes_match else 0
            
            # Parse seconds
            seconds_match = re.search(r'(\d+)\s*(?:second|sec|s)', cmd_lower)
            seconds = int(seconds_match.group(1)) if seconds_match else 0
            
            if minutes == 0 and seconds == 0:
                return True, "Please specify a time, sir. For example: set a 5 minute timer on clock"
            
            result = self.app_manager.set_windows_timer(minutes, seconds)
            return True, result["message"]
        
        # Just open the timer tab without setting a timer
        if re.search(r'open\s+timer\s+tab', cmd_lower) or \
           re.search(r'open\s+clock\s+timer', cmd_lower):
            result = self.app_manager.open_timer_tab()
            return True, result["message"]
    

        return False, ""