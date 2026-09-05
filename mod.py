"""
mod.py - Bridge Module for System Operations
"""

import os
import subprocess
import platform
import webbrowser
import shutil
from pathlib import Path
from typing import Dict, Any

class SystemBridge:
    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        
    def execute(self, command: str) -> Dict[str, Any]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def open_app(self, app_name: str) -> Dict[str, Any]:
        try:
            if self.is_windows:
                app_map = {
                    "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
                    "cmd": "cmd.exe", "powershell": "powershell.exe", "explorer": "explorer.exe",
                    "chrome": "start chrome", "firefox": "start firefox", "edge": "start msedge",
                }
                app_key = app_name.lower()
                for key, cmd in app_map.items():
                    if key in app_key or app_key in key:
                        subprocess.Popen(cmd, shell=True)
                        return {"success": True, "output": f"Opened {app_name}"}
                subprocess.Popen(app_name, shell=True)
                return {"success": True, "output": f"Opened {app_name}"}
            else:
                subprocess.Popen([app_name])
                return {"success": True, "output": f"Opened {app_name}"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def run_powershell(self, script: str) -> Dict[str, Any]:
        if not self.is_windows:
            return {"success": False, "output": "", "error": "PowerShell only on Windows"}
        try:
            result = subprocess.run(["powershell.exe", "-Command", script], capture_output=True, text=True, timeout=30)
            return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def web_search(self, query: str) -> Dict[str, Any]:
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            return {"success": True, "output": f"Searching for: {query}"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def get_system_info(self) -> Dict[str, Any]:
        return {"system": self.system, "is_windows": self.is_windows, "hostname": platform.node(), 
                "working_dir": os.getcwd(), "python_version": platform.python_version()}
    
    def list_files(self, path: str = ".") -> Dict[str, Any]:
        try:
            if not os.path.exists(path):
                return {"success": False, "output": "", "error": f"Path not found: {path}"}
            items = os.listdir(path)
            files = [f for f in items if os.path.isfile(os.path.join(path, f))]
            dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
            output = f"📁 {path}\n"
            if dirs: output += f"Folders ({len(dirs)}): {', '.join(dirs[:10])}\n"
            if files: output += f"Files ({len(files)}): {', '.join(files[:10])}\n"
            if len(files) > 10: output += f"... and {len(files) - 10} more"
            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def read_file(self, filepath: str) -> Dict[str, Any]:
        try:
            if not os.path.exists(filepath):
                return {"success": False, "output": "", "error": f"File not found: {filepath}"}
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if len(content) > 1000:
                content = content[:1000] + "\n... (truncated)"
            return {"success": True, "output": content}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def create_folder(self, path: str) -> Dict[str, Any]:
        try:
            os.makedirs(path, exist_ok=True)
            return {"success": True, "output": f"Created folder: {path}"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def delete_file(self, filepath: str) -> Dict[str, Any]:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return {"success": True, "output": f"Deleted: {filepath}"}
            return {"success": False, "output": "", "error": "File not found"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

_bridge = None
def get_bridge():
    global _bridge
    if _bridge is None: _bridge = SystemBridge()
    return _bridge

def execute_command(command): return get_bridge().execute(command)
def open_app(app_name): return get_bridge().open_app(app_name)
def run_powershell(script): return get_bridge().run_powershell(script)
def web_search(query): return get_bridge().web_search(query)
def get_system_info(): return get_bridge().get_system_info()
def list_files(path="."): return get_bridge().list_files(path)
def read_file(filepath): return get_bridge().read_file(filepath)
def create_folder(path): return get_bridge().create_folder(path)
def delete_file(filepath): return get_bridge().delete_file(filepath)