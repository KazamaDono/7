"""
main.py - JARVIS Professional AI Assistant
Always listening with smooth voice response and conversation memory
"""

import os
import sys
import logging
import time
import asyncio
import edge_tts
import pygame
import tempfile
import re
import subprocess
import platform
import webbrowser
import json
import shutil
import threading
import signal
import socket
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import deque
from dotenv import load_dotenv
import speech_recognition as sr
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

# Optional imports with fallbacks
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    trigger_word: str = "jarvis"
    silence_timeout: float = 1.2
    command_timeout: int = 30
    max_file_read_size: int = 50000
    log_level: int = logging.WARNING
    
    # Voice settings - Professional British male voice (JARVIS style)
    voice: str = "en-GB-RyanNeural"
    voice_rate: str = "-4%"
    voice_volume: str = "+0%"
    
    # Paths
    log_file: str = "jarvis.log"
    memory_dir: str = "jarvis_memory"

# ============================================================================
# CONVERSATION MEMORY
# ============================================================================

class ConversationMemory:
    """Stores and retrieves conversation history for personalization"""
    
    def __init__(self, memory_dir: str = "jarvis_memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(exist_ok=True)
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_file = self.memory_dir / f"conversation_{self.current_session_id}.json"
        self.long_term_memory_file = self.memory_dir / "long_term_memory.json"
        self._init_memory_files()
        
    def _init_memory_files(self):
        """Initialize memory files if they don't exist"""
        if not self.long_term_memory_file.exists():
            with open(self.long_term_memory_file, 'w') as f:
                json.dump({"conversations": [], "user_preferences": {}, "topics": {}}, f, indent=2)
        
        if not self.conversation_file.exists():
            with open(self.conversation_file, 'w') as f:
                json.dump({"session_id": self.current_session_id, "conversations": []}, f, indent=2)
    
    def save_conversation(self, user_input: str, jarvis_response: str, context: str = None):
        """Save a conversation exchange"""
        try:
            # Load current session
            with open(self.conversation_file, 'r') as f:
                session_data = json.load(f)
            
            # Add new exchange
            exchange = {
                "timestamp": datetime.now().isoformat(),
                "user": user_input,
                "jarvis": jarvis_response,
                "context": context
            }
            session_data["conversations"].append(exchange)
            
            # Save back
            with open(self.conversation_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            # Also save to long-term memory periodically
            if len(session_data["conversations"]) % 5 == 0:
                self._update_long_term_memory(user_input, jarvis_response)
                
        except Exception as e:
            print(f"Error saving conversation: {e}")
    
    def _update_long_term_memory(self, user_input: str, jarvis_response: str):
        """Update long-term memory with key information"""
        try:
            with open(self.long_term_memory_file, 'r') as f:
                memory = json.load(f)
            
            # Extract potential preferences or important info
            important_patterns = [
                (r'(?:my name is|call me|i am)\s+(\w+)', 'name'),
                (r'i like\s+(.+)', 'preference'),
                (r'i prefer\s+(.+)', 'preference'),
                (r'remember that\s+(.+)', 'fact'),
            ]
            
            for pattern, info_type in important_patterns:
                match = re.search(pattern, user_input.lower())
                if match:
                    if info_type == 'name':
                        memory["user_preferences"]["name"] = match.group(1)
                    elif info_type == 'preference':
                        if "preferences" not in memory:
                            memory["preferences"] = []
                        memory["preferences"].append(match.group(1))
                    elif info_type == 'fact':
                        if "facts" not in memory:
                            memory["facts"] = []
                        memory["facts"].append(match.group(1))
            
            # Store conversation summary
            memory["conversations"].append({
                "timestamp": datetime.now().isoformat(),
                "user_summary": user_input[:100],
                "response_summary": jarvis_response[:100]
            })
            
            # Keep only last 100 conversations in long-term memory
            if len(memory["conversations"]) > 100:
                memory["conversations"] = memory["conversations"][-100:]
            
            with open(self.long_term_memory_file, 'w') as f:
                json.dump(memory, f, indent=2)
                
        except Exception as e:
            print(f"Error updating long-term memory: {e}")
    
    def get_recent_context(self, n: int = 5) -> str:
        """Get recent conversation context"""
        try:
            with open(self.conversation_file, 'r') as f:
                session_data = json.load(f)
            
            recent = session_data["conversations"][-n:]
            context = []
            for conv in recent:
                context.append(f"User: {conv['user']}")
                context.append(f"JARVIS: {conv['jarvis']}")
            
            return "\n".join(context)
        except:
            return ""
    
    def get_user_preferences(self) -> Dict:
        """Get stored user preferences"""
        try:
            with open(self.long_term_memory_file, 'r') as f:
                memory = json.load(f)
            return memory.get("user_preferences", {})
        except:
            return {}
    
    def get_previous_topics(self) -> List[str]:
        """Get previously discussed topics"""
        try:
            with open(self.long_term_memory_file, 'r') as f:
                memory = json.load(f)
            topics = []
            for conv in memory.get("conversations", [])[-20:]:
                topics.append(conv.get("user_summary", ""))
            return topics
        except:
            return []

# ============================================================================
# COMMAND EXECUTOR
# ============================================================================

class CommandExecutor:
    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        
    def execute(self, command: str) -> Dict[str, Any]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def open_app(self, app_name: str) -> Dict[str, Any]:
        app_paths = {
            "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
            "cmd": "cmd.exe", "powershell": "powershell.exe", "explorer": "explorer.exe",
            "chrome": "start chrome", "firefox": "start firefox", "edge": "start msedge",
            "vscode": "code", "spotify": "spotify",
        }
        
        app_key = app_name.lower().strip()
        for key, path in app_paths.items():
            if key in app_key or app_key in key:
                try:
                    subprocess.Popen(path, shell=True)
                    return {"success": True, "output": f"Launched {app_name}"}
                except:
                    pass
        
        try:
            subprocess.Popen(app_name, shell=True)
            return {"success": True, "output": f"Launched {app_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def web_search(self, query: str) -> Dict[str, Any]:
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            return {"success": True, "output": f"Searching for: {query}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_time(self) -> str:
        now = datetime.now()
        return now.strftime("%I:%M %p")
    
    def get_date(self) -> str:
        now = datetime.now()
        return now.strftime("%A, %B %d, %Y")
    
    def get_system_info(self) -> Dict[str, Any]:
        return {
            "os": self.system,
            "hostname": platform.node(),
            "working_dir": os.getcwd(),
            "python_version": platform.python_version()
        }
    
    def list_files(self, path: str = ".") -> Dict[str, Any]:
        try:
            if not os.path.exists(path):
                return {"success": False, "error": f"Path not found: {path}"}
            
            items = os.listdir(path)
            files = [f for f in items if os.path.isfile(os.path.join(path, f))]
            dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
            
            output = f"Directory: {os.path.abspath(path)}\n"
            output += f"Found {len(dirs)} folders and {len(files)} files.\n"
            if dirs:
                output += f"Folders: {', '.join(dirs[:15])}\n"
            if files:
                output += f"Files: {', '.join(files[:15])}"
                if len(files) > 15:
                    output += f" ... and {len(files) - 15} more"
            
            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, filepath: str) -> Dict[str, Any]:
        try:
            if not os.path.exists(filepath):
                return {"success": False, "error": f"File not found: {filepath}"}
            
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            if len(content) > 500:
                content = content[:500] + "\n... (truncated)"
            
            return {"success": True, "output": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_folder(self, path: str) -> Dict[str, Any]:
        try:
            os.makedirs(path, exist_ok=True)
            return {"success": True, "output": f"Created directory: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_public_ip(self) -> Dict[str, Any]:
        if HAS_REQUESTS:
            try:
                response = requests.get('https://api.ipify.org', timeout=10)
                return {"success": True, "ip": response.text}
            except:
                pass
        
        result = self.execute("curl -s ifconfig.me")
        if result["success"] and result["output"]:
            return {"success": True, "ip": result["output"].strip()}
        
        return {"success": False, "error": "Could not get public IP"}
    
    def ping_host(self, host: str) -> Dict[str, Any]:
        if self.is_windows:
            result = self.execute(f"ping {host} -n 4")
        else:
            result = self.execute(f"ping {host} -c 4")
        return result
    
    def get_cpu_usage(self) -> float:
        if HAS_PSUTIL:
            return psutil.cpu_percent(interval=0.5)
        return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            return {"total_gb": mem.total // (1024**3), "percent": mem.percent}
        return {"total_gb": 0, "percent": 0}
    
    def get_disk_usage(self, path: str = "/") -> Dict[str, Any]:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": usage.total // (1024**3),
            "used_gb": usage.used // (1024**3),
            "free_gb": usage.free // (1024**3),
            "percent": (usage.used / usage.total) * 100
        }
    
    def calculate(self, expression: str) -> Dict[str, Any]:
        allowed_chars = set("0123456789+-*/().% ")
        if not all(c in allowed_chars for c in expression):
            return {"success": False, "error": "Invalid characters"}
        
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def write_file_with_content(self, filename: str, content: str) -> Dict[str, Any]:
        """Write content to a file and optionally open it"""
        try:
            # Ensure directory exists
            filepath = Path(filename)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Open the file in notepad (Windows) or default editor
            if self.is_windows:
                subprocess.Popen(["notepad.exe", str(filepath)])
            else:
                subprocess.Popen(["xdg-open", str(filepath)])
            
            return {"success": True, "output": f"Created and opened {filename}", "path": str(filepath)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def append_to_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Append content to an existing file"""
        try:
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"\n{content}")
            return {"success": True, "output": f"Appended to {filename}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
    
    def write_to_notepad(self, filename: str, content: str) -> Dict[str, Any]:
        """Write content to a file and open it in the default editor"""
        try:
            # Ensure directory exists
            filepath = Path(filename)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Open the file with appropriate editor based on platform
            if self.is_windows:
                subprocess.Popen(["notepad.exe", str(filepath)])
            else:
                # For WSL/Linux - try various editors
                editors = ['code', 'gedit', 'nano', 'vim', 'vi']
                editor_opened = False
                
                for editor in editors:
                    if shutil.which(editor):
                        # Open in background
                        subprocess.Popen([editor, str(filepath)])
                        editor_opened = True
                        break
                
                if not editor_opened:
                    # Fallback: just print the path
                    print(f"\nFile created at: {filepath}")
                    print(f"Content:\n{content}")
            
            return {"success": True, "output": f"Created and opened {filename} with your content", "path": str(filepath), "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_to_notepad(self, filename: str, content: str) -> Dict[str, Any]:
        """Append content to an existing file"""
        try:
            filepath = Path(filename)
            
            if not filepath.exists():
                return self.write_to_notepad(filename, content)
            
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n{content}")
            
            # For WSL, just show the appended content
            print(f"\nAppended to {filename}: {content[:100]}")
            
            return {"success": True, "output": f"Appended to {filename}", "path": str(filepath)}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================================================
# COMMAND PARSER
# ============================================================================

class CommandParser:
    def __init__(self, executor: CommandExecutor, memory: ConversationMemory = None):
        self.executor = executor
        self.memory = memory
        
    def parse_and_execute(self, command: str) -> Tuple[bool, str]:
        cmd_lower = command.lower().strip()
        
        # Write/Create file with content
        if re.search(r'(?:create|write|make).*(?:file|document|note|notepad)', cmd_lower):
            # Extract filename
            filename_match = re.search(r'(?:file|document|note|notepad)\s+(\S+\.\w+)', cmd_lower)
            if not filename_match:
                filename_match = re.search(r'(\S+\.\w+)', cmd_lower)
    
            if filename_match:
                filename = filename_match.group(1)
                # Ensure .txt extension if none provided
                if '.' not in filename:
                    filename += '.txt'
        
                # Extract content - look for content after various indicators
                content_patterns = [
                    r'(?:following|inside it|this|content|text)[;:]?\s*(.+?)(?:\s*$)',
                    r'(?:with|containing)\s+["\']?(.+?)["\']?(?:\s*$)',
                    r'(?:write|put)\s+["\']?(.+?)["\']?\s+into',
                ]
        
                content = None
                for pattern in content_patterns:
                    content_match = re.search(pattern, command, re.IGNORECASE | re.DOTALL)
                    if content_match:
                        content = content_match.group(1).strip()
                        break
        
                # Also handle content after "says:" or "says"
                if not content:
                    says_match = re.search(r'says?\s+["\']?(.+?)["\']?(?:\s*$)', command, re.IGNORECASE)
                    if says_match:
                        content = says_match.group(1).strip()
        
                if content:
                    # Clean up content - remove quotes and format nicely
                    content = content.strip('"\'')
                    # Replace literal \n with actual newlines
                    content = content.replace('\\n', '\n')
            
                    result = self.executor.write_to_notepad(filename, content)
                    if result["success"]:
                        return True, f"Created {filename} with your content and opened it in notepad, sir.\n\nContent written:\n{content[:200]}{'...' if len(content) > 200 else ''}"
                    return True, f"Could not create the file, sir. {result.get('error', '')}"
                else:
                    # If no specific content, just open empty notepad
                    result = self.executor.write_to_notepad(filename, "")
                    if result["success"]:
                        return True, f"Created empty file {filename} and opened it in notepad, sir."
                    return True, f"Could not create the file, sir."

        # Append to file (Enhanced for notepad)
        if re.search(r'(?:append|add to).*(?:file|document|notepad)', cmd_lower):
            filename_match = re.search(r'(?:file|document|notepad)\s+(\S+\.\w+)', cmd_lower)
            if filename_match:
                filename = filename_match.group(1)
                if '.' not in filename:
                    filename += '.txt'
        
                content_match = re.search(r'(?:with|content)[;:]?\s*(.+?)(?:\s*$)', command, re.IGNORECASE)
                if content_match:
                    content = content_match.group(1).strip()
                    content = content.strip('"\'')
                    content = content.replace('\\n', '\n')
            
                    result = self.executor.append_to_notepad(filename, content)
                    if result["success"]:
                        return True, f"Appended to {filename} and updated notepad, sir.\n\nAdded:\n{content[:200]}{'...' if len(content) > 200 else ''}"
                    return True, f"Could not append to file, sir."
        
        # Conversation memory recall
        if self.memory and re.search(r'(?:do you remember|recall|what did we talk about|previous conversation)', cmd_lower):
            context = self.memory.get_recent_context(5)
            if context:
                return True, f"Based on our conversation history, here is what we discussed recently:\n{context}"
            return True, "I don't recall any recent conversations, sir. This is our first exchange."
        
        # User preference recall
        if self.memory and re.search(r'(?:what do you know about me|my preferences|what have i told you|remember me)', cmd_lower):
            prefs = self.memory.get_user_preferences()
            if prefs:
                pref_text = "\n".join([f"  - {k}: {v}" for k, v in prefs.items()])
                return True, f"Based on our conversations, I know the following about you, sir:\n{pref_text}"
            return True, "I haven't learned much about you yet, sir. As we talk more, I will remember your preferences."
        
        # Time and Date commands
        if re.search(r'(?:what.*time|current time|time now)', cmd_lower):
            return True, f"The current time is {self.executor.get_time()}."
        
        if re.search(r'(?:what.*date|today.*date|current date)', cmd_lower):
            return True, f"Today is {self.executor.get_date()}."
        
        # System commands
        if re.search(r'(?:system info|computer info|about)', cmd_lower):
            info = self.executor.get_system_info()
            return True, f"System: {info['os']}. Hostname: {info['hostname']}. Working directory: {info['working_dir']}."
        
        if HAS_PSUTIL and re.search(r'(?:cpu usage|processor usage)', cmd_lower):
            cpu = self.executor.get_cpu_usage()
            return True, f"CPU usage is {cpu} percent."
        
        if HAS_PSUTIL and re.search(r'(?:memory|ram).*(?:usage|status)', cmd_lower):
            mem = self.executor.get_memory_usage()
            return True, f"Memory usage is {mem['percent']} percent. Total {mem['total_gb']} gigabytes."
        
        if re.search(r'(?:disk|drive).*(?:usage|space)', cmd_lower):
            disk = self.executor.get_disk_usage()
            return True, f"Disk usage is {disk['percent']:.1f} percent. Free space: {disk['free_gb']} gigabytes."
        
        # Application commands
        if re.search(r'(?:open|launch|start)\s+(.+)', cmd_lower):
            match = re.search(r'(?:open|launch|start)\s+(.+)', cmd_lower)
            app_name = match.group(1)
            result = self.executor.open_app(app_name)
            if result["success"]:
                return True, f"Launching {app_name}."
            return True, f"Could not launch {app_name}."
        
        # Web search
        if re.search(r'(?:search|google)\s+(?:for\s+)?(.+)$', cmd_lower):
            match = re.search(r'(?:search|google)\s+(?:for\s+)?(.+)$', cmd_lower)
            query = match.group(1)
            result = self.executor.web_search(query)
            if result["success"]:
                return True, f"Searching for {query}."
            return True, "Search failed."
        
        # File operations
        if re.search(r'(?:list|show).*(?:files|contents|directory)', cmd_lower):
            path_match = re.search(r'(?:in|from|of)\s+(\S+)', cmd_lower)
            path = path_match.group(1) if path_match else "."
            
            if path == "desktop":
                path = os.path.join(os.path.expanduser("~"), "Desktop")
            elif path == "documents":
                path = os.path.join(os.path.expanduser("~"), "Documents")
            elif path == "downloads":
                path = os.path.join(os.path.expanduser("~"), "Downloads")
            
            result = self.executor.list_files(path)
            if result["success"]:
                return True, result["output"]
            return True, f"Could not list directory."
        
        if re.search(r'(?:read|show).*file\s+(.+)', cmd_lower):
            match = re.search(r'(?:read|show).*file\s+(.+)', cmd_lower)
            filepath = match.group(1)
            result = self.executor.read_file(filepath)
            if result["success"]:
                return True, f"File contents:\n{result['output']}"
            return True, f"Could not read file."
        
        if re.search(r'(?:create|make).*(?:folder|directory)', cmd_lower):
            match = re.search(r'(?:folder|directory)\s+(?:called\s+)?(\w+)', cmd_lower)
            if match:
                folder_name = match.group(1)
                result = self.executor.create_folder(folder_name)
                if result["success"]:
                    return True, f"Created folder {folder_name}."
            return True, "Could not create folder."
        
        # Network commands
        if re.search(r'(?:public\s+)?ip(?:\s+address)?', cmd_lower):
            result = self.executor.get_public_ip()
            if result["success"]:
                return True, f"Your public IP address is {result['ip']}."
            return True, "Could not determine public IP."
        
        if re.search(r'ping\s+(\S+)', cmd_lower):
            match = re.search(r'ping\s+(\S+)', cmd_lower)
            target = match.group(1)
            result = self.executor.ping_host(target)
            if result["success"]:
                return True, f"Ping results for {target}:\n{result['output'][:300]}"
            return True, f"Could not ping {target}."
        
        # Calculations
        if re.search(r'(?:calculate|what is|compute)\s+(.+)', cmd_lower):
            match = re.search(r'(?:calculate|what is|compute)\s+(.+)', cmd_lower)
            expression = match.group(1)
            result = self.executor.calculate(expression)
            if result["success"]:
                return True, f"{expression} equals {result['result']}."
            return True, f"Could not calculate."
        
        return False, ""

# ============================================================================
# JARVIS CORE
# ============================================================================

class JarvisCore:
    def __init__(self):
        self.config = Config()
        self.memory = ConversationMemory(self.config.memory_dir)
        self.executor = CommandExecutor()
        self.parser = CommandParser(self.executor, self.memory)
        self.running = True
        self.conversation_active = False
        self.visualizer = None  # Visualizer reference
        self.is_listening = False  # Track listening state
        self.is_speaking = False  # Track speaking state
        
        # Setup logging
        logging.basicConfig(level=self.config.log_level)
        self.logger = logging.getLogger("JARVIS")
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = self.config.silence_timeout
        
        # Initialize microphone
        self.microphone = None
        self._init_microphone()
        
        # Initialize TTS
        pygame.mixer.init()
        
    def _init_microphone(self):
        try:
            self.microphone = sr.Microphone()
            print("Microphone initialized successfully.")
        except Exception as e:
            print(f"Microphone initialization failed: {e}")
            print("Voice input will be disabled.")
            self.microphone = None
    
    def set_visualizer(self, visualizer):
        """Set the visualizer instance for UI updates"""
        self.visualizer = visualizer
    
    def update_visualizer_state(self, state):
        """Update visualizer state if available"""
        if self.visualizer:
            self.visualizer.set_state(state)
            # Force UI update
            self.visualizer.root.update_idletasks()
    
    def show_visualizer_notification(self, message, duration=2):
        """Show notification in visualizer"""
        if self.visualizer:
            self.visualizer.show_notification(message, duration)
    
    def speak(self, text: str):
        """Speak with visual feedback"""
        try:
            # Update visualizer state
            self.is_speaking = True
            self.update_visualizer_state('speaking')
            self.show_visualizer_notification(f"JARVIS: {text[:100]}...", 3)
            
            # Speak the text
            asyncio.run(self._speak_async(text))
            
            # Clear speaking state
            self.is_speaking = False
            self.update_visualizer_state('idle')
            
        except Exception as e:
            print(f"JARVIS: {text}")
            self.is_speaking = False
            self.update_visualizer_state('idle')
            
    async def _speak_async(self, text: str):
        """Speak with pitch-shifted deep voice"""
        tmp_path = None
        shifted_path = None
        try:
            # Generate normal speech
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                tmp_path = tmp.name
        
            communicate = edge_tts.Communicate(
                text, voice=self.config.voice,
                rate=self.config.voice_rate, volume=self.config.voice_volume
            )
            await communicate.save(tmp_path)
        
            # Apply pitch shifting for deeper voice
            shifted_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
        
            # Use ffmpeg to lower pitch (install if needed: sudo apt install ffmpeg)
            # '-filter:a "asetrate=44100*0.85,aresample=44100"' lowers pitch by 15%
            #subprocess.run([
            #    'ffmpeg', '-i', tmp_path, 
            #    '-filter:a', 'rubberband=pitch=0.75',
            #    '-y', shifted_path
            #], capture_output=True, check=False)
        
            # Play the shifted audio
            pygame.mixer.music.load(shifted_path)
            pygame.mixer.music.play()
        
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)
        
            pygame.mixer.music.unload()
        
        except Exception as e:
            print(f"TTS error: {e}")
            # Fallback to normal TTS
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)
            pygame.mixer.music.unload()
    
        finally:
            # Cleanup
            for path in [tmp_path, shifted_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    def listen_continuously(self):
        """Listen continuously and respond when user speaks"""
        print("\n" + "="*60)
        print("JARVIS - Professional AI Assistant")
        print("="*60)
        print("I am always listening. Just speak naturally.")
        print("Say 'Jarvis' followed by your command, or just start talking.")
        print("Commands: 'exit', 'quit', or 'shutdown' to terminate")
        print("="*60 + "\n")
        
        self.speak("JARVIS online. I am listening.")
        
        if not self.microphone:
            print("Microphone not available. Entering text command mode.\n")
            self._text_mode()
            return
        
        # Calibrate microphone
        with self.microphone as source:
            print("Calibrating microphone...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
            print("Ready. I am always listening.\n")
        
        while self.running:
            try:
                with self.microphone as source:
                    # Update listening state
                    self.is_listening = True
                    self.update_visualizer_state('listening')
                    
                    # Always listening - blocks until speech is detected
                    print("Listening...", end="\r", flush=True)
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=10)
                    
                    # Process the speech
                    print("\nProcessing...", end=" ", flush=True)
                    
                    # Update visualizer to processing state
                    self.is_listening = False
                    self.update_visualizer_state('processing')
                    self.show_visualizer_notification("Processing your request...", 1)
                    
                    text = self.recognizer.recognize_google(audio)
                    print(f"\nUser: {text}")
                    
                    # Show user input in visualizer
                    self.show_visualizer_notification(f"You: {text[:100]}...", 2)
                    
                    # Check for exit
                    if any(word in text.lower() for word in ["exit", "quit", "shutdown", "power down"]):
                        self.speak("Shutting down.")
                        self.running = False
                        break
                    
                    # Check for wake word or direct command
                    if self.config.trigger_word in text.lower():
                        # Remove wake word from command
                        command = text.lower().replace(self.config.trigger_word, "").strip()
                        if command:
                            response = self._process_command(command)
                        else:
                            self.speak("Yes sir?")
                            # Wait for follow-up command
                            try:
                                self.update_visualizer_state('listening')
                                follow_audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                                follow_text = self.recognizer.recognize_google(follow_audio)
                                print(f"User: {follow_text}")
                                response = self._process_command(follow_text)
                                print(f"JARVIS: {response}")
                                self.speak(response)
                            except:
                                pass
                            continue
                    else:
                        # Direct command without wake word
                        response = self._process_command(text)
                    
                    print(f"JARVIS: {response}")
                    self.speak(response)
                    
                    # Reset to idle state
                    self.update_visualizer_state('idle')
                    
            except sr.UnknownValueError:
                # Could not understand - just continue listening silently
                self.is_listening = False
                self.update_visualizer_state('idle')
                continue
            except sr.RequestError as e:
                print(f"\nRecognition service error: {e}")
                self.is_listening = False
                self.update_visualizer_state('idle')
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
                self.is_listening = False
                self.update_visualizer_state('idle')
                time.sleep(0.5)
    
    def _process_command(self, command: str) -> str:
        """Process command and return response"""
        # Update visualizer
        self.update_visualizer_state('processing')
        
        # Try to execute a command
        executed, response = self.parser.parse_and_execute(command)
        
        if executed:
            # Save to memory
            self.memory.save_conversation(command, response, "command_execution")
            return response
        
        # Use LLM for conversation with context
        response = self._llm_conversation_with_context(command)
        
        # Save to memory
        self.memory.save_conversation(command, response, "llm_conversation")
        return response
    
    def _llm_conversation_with_context(self, command: str) -> str:
        """Use LLM with conversation context for natural dialogue"""
        try:
            # Get recent context
            recent_context = self.memory.get_recent_context(3)
            user_prefs = self.memory.get_user_preferences()
            
            system_prompt = """You are JARVIS, Tony Stark's AI assistant. You are efficient, precise, and professional.

Characteristics:
- Speak clearly and concisely
- Use proper grammar and complete sentences
- Be helpful but not verbose
- Address the user as "sir"
- Maintain a calm, authoritative tone
- Be direct and informative
- Reference previous conversations naturally when relevant

Respond naturally while maintaining professional demeanor."""

            # Add context if available
            if recent_context:
                system_prompt += f"\n\nRecent conversation context:\n{recent_context}"
            
            if user_prefs:
                system_prompt += f"\n\nKnown user information:\n{json.dumps(user_prefs, indent=2)}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", command)
            ])
            
            llm = ChatOllama(model="qwen3:1.7b", reasoning=False)
            chain = prompt | llm
            response = chain.invoke({"input": command})
            
            return response.content
            
        except Exception as e:
            return "I am having difficulty processing that request, sir."
    
    def _text_mode(self):
        """Fallback text input mode when microphone is unavailable"""
        print("Entering text command mode. Type your commands below.\n")
        while self.running:
            try:
                command = input("> ")
                if command.lower() in ["exit", "quit", "shutdown"]:
                    break
                
                response = self._process_command(command)
                print(f"JARVIS: {response}\n")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

def main():
    jarvis = JarvisCore()
    jarvis.listen_continuously()

if __name__ == "__main__":
    main()