"""
SEVEN - an powerful and well capable inorganic intelligence being. Seven is my personal assistant - exceling in reasoning, scheduling tasks, automating tasks, and finally, conducting detection and response tasks.
"""

import os
import math
import random
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
from seven_plugins import PluginManager
from seven_agent import AgentBrain, strip_think, SystemTools
try:
    from seven_skills import ResearchSkills
    HAS_RESEARCH = True
except Exception:
    HAS_RESEARCH = False
try:
    from seven_memory import MemoryStore
    HAS_MEMORY = True
except Exception:
    HAS_MEMORY = False

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
    trigger_word: str = "Seven"
    silence_timeout: float = 1.2
    command_timeout: int = 30
    max_file_read_size: int = 50000
    log_level: int = logging.WARNING

    # LLM model used for both conversation and the agentic tool-calling brain.
    # qwen3:4b is more reliable at tool calls BUT needs ~3.5GB RAM and thrashes
    # swap on this 7GB box (~5 min/reply), so 1.7b is the usable default here.
    # When you have the RAM free (close browsers, or a bigger machine):
    #   export SEVEN_MODEL=qwen3:4b
    agent_model: str = os.environ.get("SEVEN_MODEL", "qwen3:1.7b")
    
    # Voice settings - Professional British male voice
    voice: str = "en-GB-RyanNeural"
    voice_rate: str = "-5%"
    voice_volume: str = "+0%"
    
    # Paths
    log_file: str = "seven.log"
    memory_dir: str = "seven_memory"

# ============================================================================
# CONVERSATION MEMORY
# ============================================================================

class ConversationMemory:
    """Stores and retrieves conversation history for personalization"""
    
    def __init__(self, memory_dir: str = "seven_memory"):
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
    
    def save_conversation(self, user_input: str, seven_response: str, context: str = None):
        """Save a conversation exchange"""
        try:
            # Load current session
            with open(self.conversation_file, 'r') as f:
                session_data = json.load(f)
            
            # Add new exchange
            exchange = {
                "timestamp": datetime.now().isoformat(),
                "user": user_input,
                "seven": seven_response,
                "context": context
            }
            session_data["conversations"].append(exchange)
            
            # Save back
            with open(self.conversation_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            # Also save to long-term memory periodically
            if len(session_data["conversations"]) % 5 == 0:
                self._update_long_term_memory(user_input, seven_response)
                
        except Exception as e:
            print(f"Error saving conversation: {e}")
    
    def _update_long_term_memory(self, user_input: str, seven_response: str):
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
                "response_summary": seven_response[:100]
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
                context.append(f"SEVEN: {conv['seven']}")
            
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
    # Voice STT is imperfect (e.g. "Seven" can transcribe as "7") and this runs
    # off a spoken trigger phrase, so block privilege escalation outright plus
    # a short list of actions severe enough that a mis-heard word shouldn't
    # trigger them. This is a denylist, not a sandbox -- it stops the obvious
    # catastrophic cases, not a determined attacker.
    _BLOCKED_COMMAND_PATTERNS = [
        r'\bsudo\b', r'\bsu\b', r'\bpkexec\b', r'\bdoas\b',
        r'\brm\s+(-[a-z]*\s+)*-[a-z]*r[a-z]*f[a-z]*(\s+-[a-z]+)*\s+/(?:\s|$)',  # rm -rf /
        r':\(\)\s*\{\s*:\|:&?\s*\}\s*;\s*:',  # fork bomb
        r'\bmkfs(\.\w+)?\b',
        r'\bdd\b[^\n]*\bof=/dev/',
        r'\b(shutdown|reboot|poweroff|halt)\b',
    ]

    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self._command_log_path = Path(__file__).parent / "command_execution.log"

    def _log_command(self, command: str, blocked: bool):
        try:
            with open(self._command_log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {'BLOCKED' if blocked else 'RAN'}: {command}\n")
        except Exception:
            pass

    def execute(self, command: str) -> Dict[str, Any]:
        for pattern in self._BLOCKED_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                self._log_command(command, blocked=True)
                return {"success": False, "output": "", "error": "That command is blocked from voice execution."}

        self._log_command(command, blocked=False)
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
        
        # Time and Date commands. Use word boundaries so "times" (as in
        # "15 times 3") does not get mistaken for a request for the time.
        if re.search(r'\b(what(?:\'?s| is)?\s+the\s+time|current\s+time|time\s+now|what\s+time)\b', cmd_lower):
            return True, f"The current time is {self.executor.get_time()}."

        if re.search(r'\b(what(?:\'?s| is)?\s+the\s+date|today.*date|current\s+date|what\s+date)\b', cmd_lower):
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
        
        # Application commands - Now handled by plugins for better functionality
        # Keep only essential system apps here, let plugins handle the rest
        essential_apps = ["notepad", "calculator", "paint", "cmd", "powershell", "explorer"]
        if re.search(r'(?:open|launch|start)\s+(.+)', cmd_lower):
            match = re.search(r'(?:open|launch|start)\s+(.+)', cmd_lower)
            app_name = match.group(1)
    
            # Only handle essential Windows apps here, let plugins handle others
            if app_name.lower() in essential_apps:
                result = self.executor.open_app(app_name)
                if result["success"]:
                    return True, f"Launching {app_name}."
                return True, f"Could not launch {app_name}."
            else:
                # Return False so PluginManager can handle it
                return False, ""
        
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
        
        # Calculations -- only treat as math when the expression actually contains
        # a digit, and fall through to the smart agent otherwise. Without this,
        # "what is eating my memory" was wrongly caught here as a failed calculation.
        calc_match = re.search(r'(?:calculate|what is|compute)\s+(.+)', cmd_lower)
        if calc_match:
            expression = calc_match.group(1)
            if any(ch.isdigit() for ch in expression):
                result = self.executor.calculate(expression)
                if result["success"]:
                    return True, f"{expression} equals {result['result']}."
            # Not a real calculation -- let the agent handle it.

        # Run a shell command -- requires the explicit "run/execute command" phrase
        # so it can't fire from ordinary conversation. Privilege escalation and a
        # short list of catastrophic patterns are blocked in executor.execute().
        cmd_match = re.search(r'(?:run|execute)\s+(?:the\s+)?command\s+(.+)', command, re.IGNORECASE)
        if cmd_match:
            shell_command = cmd_match.group(1).strip()
            result = self.executor.execute(shell_command)
            if result["success"]:
                output = result["output"].strip() or "(no output)"
                return True, f"Command executed, sir.\n{output[:500]}"
            return True, f"Command failed, sir. {result.get('error', '')[:300]}"

        return False, ""

# ============================================================================
# SEVEN CORE
# ============================================================================

class SevenCore:
    def __init__(self):
        self.config = Config()
        self.memory = ConversationMemory(self.config.memory_dir)
        self.executor = CommandExecutor()
        self.parser = CommandParser(self.executor, self.memory)
        self.agent = None  # AgentBrain, built lazily on first LLM fallback
        # Deterministic compound skills, usable without the LLM (see _fast_intent).
        self.system_tools = SystemTools(executor=self.executor)
        self.research = ResearchSkills(executor=self.executor) if HAS_RESEARCH else None
        # Persistent memory of the user -- what makes Seven feel like it knows you.
        self.mind = MemoryStore(self.config.memory_dir) if HAS_MEMORY else None
        self.running = True
        self.text_mode = False  # when True, read typed input instead of the mic
        # Android/Termux: no PulseAudio/pygame mic, but Android's own TTS works via
        # termux-tts-speak. Detect it so speak() can use it and we start in text mode.
        self.is_termux = bool(os.environ.get("TERMUX_VERSION")) or shutil.which("termux-tts-speak") is not None
        self.conversation_active = False
        # Conversation mode: after you engage Seven once, it keeps listening for
        # follow-ups WITHOUT the wake word for this many seconds of the last
        # exchange, so you don't have to say "Seven" every single time.
        self.conversation_window = 30.0
        self.last_interaction = 0.0
        # Streaming speech: speak each sentence as the LLM generates it, so the
        # first words come out in ~2-3s instead of after the whole answer.
        self.streaming_enabled = True
        self._spoke_streaming = False  # set True when a turn already spoke via streaming
        self.visualizer = None  # Visualizer reference
        self.is_listening = False  # Track listening state
        self.is_speaking = False  # Track speaking state
        self.plugin_manager = PluginManager(self)
        self._setup_keyboard_interrupts()
        self.start_orb_visualizer()
        
        # Setup logging
        logging.basicConfig(level=self.config.log_level)
        self.logger = logging.getLogger("seven")
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = self.config.silence_timeout
        
        # Initialize microphone
        self.microphone = None
        self._init_microphone()
        
        # Initialize TTS. On Termux we use the OS TTS (termux-tts-speak) instead of
        # pygame playback, so skip the mixer there (it would fail).
        if not self.is_termux:
            # Force SDL through the PulseAudio/PipeWire layer instead of raw ALSA --
            # PipeWire holds the ALSA hw device exclusively, so opening it directly
            # here fails with "Device or resource busy".
            os.environ.setdefault("SDL_AUDIODRIVER", "pulseaudio")
            try:
                pygame.mixer.init()
            except Exception as e:
                print(f"[audio] pygame mixer unavailable ({e}); TTS playback disabled.")
        
        # Setup keyboard interrupts LAST (after pygame is initialized)
        self._setup_keyboard_interrupts()

        # Warm the LLM into RAM in the background so the first real reply is fast.
        threading.Thread(target=self._warm_up_model, daemon=True).start()

    def _warm_up_model(self):
        """Preload the model so the first conversation turn isn't a cold start."""
        try:
            ChatOllama(model=self.config.agent_model, reasoning=False,
                       keep_alive="30m", num_predict=1).invoke("hi")
        except Exception:
            pass
        
    def _select_microphone_device(self):
        """List available input devices and let the user pick one; remembers the choice
        in mic_config.json so Seven doesn't ask again unless run with --select-mic."""
        import pyaudio

        config_path = Path(__file__).parent / "mic_config.json"

        p = pyaudio.PyAudio()
        try:
            devices = [
                (i, p.get_device_info_by_index(i)["name"])
                for i in range(p.get_device_count())
                if p.get_device_info_by_index(i).get("maxInputChannels", 0) > 0
            ]
        finally:
            p.terminate()

        if not devices:
            return None

        force_reselect = "--select-mic" in sys.argv
        if config_path.exists() and not force_reselect:
            try:
                saved = json.loads(config_path.read_text())
                for idx, name in devices:
                    if name == saved.get("device_name"):
                        print(f"Using saved microphone: {name}")
                        return idx
            except Exception:
                pass

        if not sys.stdin.isatty():
            # Non-interactive launch (no TTY to prompt on) -- fall back to the
            # system default input device rather than blocking on input().
            return None

        print("\nAvailable microphones:")
        for n, (idx, name) in enumerate(devices, 1):
            print(f"  {n}. {name}")

        while True:
            choice = input(f"Select a microphone [1-{len(devices)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(devices):
                idx, name = devices[int(choice) - 1]
                config_path.write_text(json.dumps({"device_index": idx, "device_name": name}))
                print(f"Seven will use: {name}")
                return idx
            print("Invalid choice, try again.")

    def _mic_opens_ok(self, device_index, tries: int = 2) -> bool:
        """Confirm the device yields a real stream on repeated opens. PyAudio can
        hand back a broken (stream=None) device WITHOUT raising, and some virtual
        devices (e.g. 'pulse') open the first time but fail on the next -- which
        is exactly how the listening loop re-opens it -- so test more than once."""
        for _ in range(max(1, tries)):
            try:
                mic = sr.Microphone(device_index=device_index)
                with mic as source:
                    if source.stream is None:
                        return False
            except Exception:
                return False
        return True

    def _init_microphone(self):
        # Android/Termux has no PulseAudio mic path -- skip straight to text mode.
        if self.is_termux:
            print("Android/Termux detected: voice input off, running in text mode.")
            self.microphone = None
            return
        # PyAudio device indices are unstable across runs, and a stale/invalid one
        # opens as a dead (stream=None) device that crashes later. So validate the
        # chosen device and fall back to the system default (which follows whatever
        # `pactl set-default-source` points at, e.g. the USB mic).
        try:
            device_index = self._select_microphone_device()
        except Exception as e:
            print(f"Microphone selection failed: {e}")
            device_index = None

        if device_index is not None and self._mic_opens_ok(device_index):
            self.microphone = sr.Microphone(device_index=device_index)
            print("Microphone initialized successfully.")
            return

        if device_index is not None:
            print("Selected microphone would not open; falling back to the system default.")
        if self._mic_opens_ok(None):
            self.microphone = sr.Microphone(device_index=None)
            print("Microphone initialized successfully (system default).")
            return

        print("No working microphone found. Voice input will be disabled.")
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
        self.update_orb_state(state)
    
    def show_visualizer_notification(self, message, duration=2):
        """Show notification in visualizer"""
        if self.visualizer:
            self.visualizer.show_notification(message, duration)
    
    def speak(self, text: str):
        """Speak with visual feedback, interrupt support, and text cleaning"""
        try:
            # Clean the text before speaking
            cleaned_text = self.clean_text_for_speech(text)

            # Update visualizer state
            self.is_speaking = True
            self.update_visualizer_state('speaking')
            self.show_visualizer_notification(f"Seven: {text[:100]}...", 3)

            # On Android/Termux, use the OS text-to-speech engine (edge-tts +
            # pygame playback aren't available there).
            if self.is_termux:
                print(f"Seven: {text}")
                try:
                    subprocess.run(["termux-tts-speak", cleaned_text], timeout=90)
                except Exception:
                    pass
            else:
                # Speak the cleaned text with interrupt checking
                asyncio.run(self._speak_with_interrupt(cleaned_text))

            # Clear speaking state
            self.is_speaking = False
            self.update_visualizer_state('idle')

        except Exception as e:
            print(f"Seven: {text}")
            self.is_speaking = False
            self.update_visualizer_state('idle')

    @staticmethod
    def _stream_sentences(token_iter):
        """Turn a stream of text chunks into complete sentences as they finish,
        so each can be spoken while the rest is still being generated."""
        buf = ""
        for chunk in token_iter:
            if not chunk:
                continue
            buf += chunk
            while True:
                m = re.search(r'[.!?](?=\s|$)|[\n]', buf)
                if not m:
                    break
                end = m.end()
                sentence = buf[:end].strip()
                buf = buf[end:]
                if sentence and "think>" not in sentence.lower():
                    yield sentence
        tail = buf.strip()
        if tail and "think>" not in tail.lower():
            yield tail

    def speak_streaming(self, sentence_source) -> str:
        """Speak sentences from `sentence_source` (an iterable of strings) as they
        arrive. Returns the full spoken text. This is what makes replies feel
        instant -- Seven starts talking on the first sentence."""
        spoken_parts = []
        self.is_speaking = True
        self.update_visualizer_state('speaking')
        try:
            for sentence in sentence_source:
                if not self.running:
                    break
                spoken_parts.append(sentence)
                print(f"Seven: {sentence}")
                cleaned = self.clean_text_for_speech(sentence)
                if not cleaned.strip():
                    continue
                try:
                    if self.is_termux:
                        subprocess.run(["termux-tts-speak", cleaned], timeout=60)
                    else:
                        asyncio.run(self._speak_with_interrupt(cleaned))
                except Exception:
                    pass
        finally:
            self.is_speaking = False
            self.update_visualizer_state('idle')
        return " ".join(spoken_parts).strip()

    async def _speak_async(self, text: str):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                tmp_path = tmp.name
            
            communicate = edge_tts.Communicate(
                text, voice=self.config.voice,
                rate=self.config.voice_rate, volume=self.config.voice_volume
            )
            await communicate.save(tmp_path)
            
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            
            # Update visualizer during speaking
            start_time = time.time()
            while pygame.mixer.music.get_busy():
                # Update visualizer with speaking animation
                if self.visualizer and self.is_speaking:
                    # Calculate speaking intensity (0 to 1 based on audio position)
                    elapsed = time.time() - start_time
                    intensity = (math.sin(elapsed * 20) + 1) / 2  # Pulsing effect
                    self.visualizer.audio_level = intensity * 0.8 + 0.2
                    self.visualizer.root.update_idletasks()
                
                await asyncio.sleep(0.05)
            
            pygame.mixer.music.unload()
            os.unlink(tmp_path)
            
            # Reset audio level
            if self.visualizer:
                self.visualizer.audio_level = 0
                
        except Exception as e:
            print(f"TTS error: {e}")
    
    
    async def _speak_with_interrupt(self, text: str):
        """Speak with interrupt detection running in parallel"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                tmp_path = tmp.name
        
            communicate = edge_tts.Communicate(
                text, voice=self.config.voice,
                rate=self.config.voice_rate, volume=self.config.voice_volume
            )
            await communicate.save(tmp_path)
        
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
        
            # Create an event to signal stop
            stop_event = asyncio.Event()
        
            # Start interrupt checking in a separate thread
            interrupt_thread = threading.Thread(
                target=self._interrupt_listener,
                args=(stop_event,),
                daemon=True
            )
            interrupt_thread.start()
        
            # Monitor playback and check for stop signal
            start_time = time.time()
            audio_level = 0.0  # <-- DEFINE AUDIO_LEVEL HERE
        
            while pygame.mixer.music.get_busy():
                # Check if stop was requested
                if stop_event.is_set():
                    print("\n[INTERRUPT] Stopping speech...")
                    pygame.mixer.music.stop()
                    self.show_visualizer_notification("Speech interrupted", 1)
                    break
            
                # Calculate audio level for visualizer
                elapsed = time.time() - start_time
                intensity = (math.sin(elapsed * 20) + 1) / 2
                audio_level = intensity * 0.8 + 0.2  # <-- UPDATE AUDIO_LEVEL
            
                # Update visualizer with speaking animation
                if self.visualizer and self.is_speaking:
                    self.visualizer.audio_level = audio_level
                    self.visualizer.root.update_idletasks()
            
                # Update orb state with audio level
                self.update_orb_state('speaking', audio_level)  # <-- USE AUDIO_LEVEL
            
                await asyncio.sleep(0.05)
        
            pygame.mixer.music.unload()
            os.unlink(tmp_path)
        
            # Reset audio level
            audio_level = 0.0  # <-- RESET AUDIO_LEVEL
            if self.visualizer:
                self.visualizer.audio_level = 0
        
            # Update orb state back to idle
            self.update_orb_state('idle', 0.0)  # <-- RESET ORB STATE
        
        except Exception as e:
            print(f"TTS error: {e}")
            # Reset on error too
            self.update_orb_state('idle', 0.0)

    def _interrupt_listener(self, stop_event: asyncio.Event):
        """Listen for interrupt commands while speaking"""
        if not self.microphone:
            return
    
        try:
            # Create a fresh recognizer instance to avoid conflicts
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.5
        
            with self.microphone as source:
                # Quick calibration
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
            
                # Listen with a short timeout
                try:
                    audio = recognizer.listen(source, timeout=0.5, phrase_time_limit=1.5)
                    text = recognizer.recognize_google(audio)
                
                    # Check for stop words
                    stop_words = ["stop", "halt", "cease", "shut up", "quiet", "enough", "cancel", "pause"]
                    if any(word in text.lower() for word in stop_words):
                        print(f"\n[INTERRUPT DETECTED] '{text}'")
                        stop_event.set()
                    
                except sr.WaitTimeoutError:
                    pass  # No speech detected
                except sr.UnknownValueError:
                    pass  # Couldn't understand
                except sr.RequestError:
                    pass  # Network error
                
        except Exception as e:
            # Silently fail - don't disrupt the main speech
            pass
    
    
    
    def listen_continuously(self):
        """Listen continuously and respond when user speaks"""
        print("\n" + "="*72)
        print("Seven - Inorganic Intelligent Autonomous Agent. Your personal assistant.")
        print("="*72)
        print("I am always listening. Just speak naturally.")
        print("Say 'Seven' followed by your command, or just start talking.")
        print("Commands: 'exit', 'quit', or 'shutdown' to terminate")
        print("="*72 + "\n")
        
        self.speak(random.choice([
            "Hey, I'm here. What are we working on?",
            "Seven's online. What do you need?",
            "I'm up and listening. Let's get into it.",
        ]))
        
        if not self.microphone:
            print("Microphone not available. Entering text command mode.\n")
            self._text_mode()
            return
        
        # Calibrate microphone. A transient open failure (e.g. audio contention
        # while the greeting is still playing) can hand back a dead stream, so
        # recover by rebuilding on the system default instead of crashing.
        try:
            with self.microphone as source:
                print("Calibrating microphone...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
                print("Ready. I am always listening.\n")
        except Exception:
            if self._recover_microphone():
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
                print("Ready. I am always listening.\n")
            else:
                print("Microphone unavailable; switching to text mode.\n")
                self._text_mode()
                return
        
        while self.running:
            # TEXT MODE: read typed input instead of the mic. The microphone is
            # never opened here, so switching modes cannot affect or damage it --
            # self.microphone is left exactly as it was.
            if self.text_mode:
                self._text_mode_turn()
                continue

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
            
                    text = self.recognizer.recognize_google(audio)
                    print(f"\nUser: {text}")

                    # Check for exit (always allowed, with or without wake word)
                    if any(word in text.lower() for word in ["exit", "quit", "shutdown", "power down"]):
                        self.speak("Shutting down.")
                        self.running = False
                        break

                    # Switch to TEXT MODE on a standalone "type" command (or
                    # "text mode"/"let me type"), with or without the wake word.
                    # Matched strictly so questions like "what type of CPU" do NOT
                    # trigger it. The mic is left untouched.
                    _t = re.sub(r'[?.!]+$', '', text.lower().strip())
                    _t = re.sub(r'^(?:hey |ok |okay )?seven[,\s]+', '', _t).strip()
                    if re.fullmatch(r'(?:please\s+)?type(?:\s+mode)?(?:\s+please)?', _t) or \
                       re.search(r'\b(text mode|keyboard mode|let me type|switch to text)\b', _t):
                        self.text_mode = True
                        self.update_visualizer_state('idle')
                        self.speak("Text mode, sir. Type your questions.")
                        continue
            
                    # Wake word "Seven" (STT often hears it as the digit "7").
                    trigger = self.config.trigger_word.lower()
                    digit_form = {
                        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                        "six": "6", "seven": "7", "eight": "8", "nine": "9", "zero": "0",
                    }.get(trigger)
                    trigger_pattern = trigger if not digit_form else rf"({trigger}|\b{digit_form}\b)"
                    has_wake = re.search(trigger_pattern, text.lower())

                    # Conversation mode: right after an exchange, keep taking
                    # follow-ups WITHOUT the wake word for a short window.
                    in_conversation = (self.conversation_active and
                                       (time.time() - self.last_interaction) < self.conversation_window)

                    if has_wake or in_conversation:
                        self.update_visualizer_state('listening')
                        if has_wake:
                            self.show_visualizer_notification("Seven activated", 1)
                            command = re.sub(trigger_pattern, "", text.lower(), count=1).strip()
                        else:
                            command = text.strip()

                        if command:
                            response = self._process_command(command)
                            # If the answer already streamed out sentence-by-
                            # sentence, don't speak it again.
                            if self._spoke_streaming:
                                print(f"Seven: {response}")
                            else:
                                print(f"Seven: {response}")
                                self.speak(response)
                        else:
                            # Bare wake word -- acknowledge; conversation mode now
                            # keeps listening for the actual request, no repeat needed.
                            self.speak(random.choice([
                                "Yeah?", "What's up?", "I'm listening.", "Go ahead.",
                                "Yes?", "Mm-hmm?", "I'm here. What do you need?",
                            ]))
                        # Open/extend the conversation window.
                        self.conversation_active = True
                        self.last_interaction = time.time()
                    else:
                        # Not engaged and no wake word - ignore quietly.
                        print("[idle - waiting for 'Seven']")
                        self.update_visualizer_state('idle')
                        continue

                    # Reset to idle state after response
                    self.update_visualizer_state('idle')
            
            except sr.UnknownValueError:
                # Always-listening: unclear audio is usually just ambient noise, so
                # stay silent here (a constant "didn't catch that" would be grating).
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
                # A dead microphone stream raises here ("'NoneType' has no
                # attribute 'close'"). Rebuild the mic on the system default and
                # keep listening rather than spinning on the same broken device.
                print(f"\nError: {e}")
                self.is_listening = False
                self.update_visualizer_state('idle')
                self._recover_microphone()
                time.sleep(0.5)

    def _recover_microphone(self) -> bool:
        """Rebuild the microphone on the system default after a failure.
        Returns True if a working microphone is available."""
        if self._mic_opens_ok(None):
            self.microphone = sr.Microphone(device_index=None)
            print("[mic] recovered on system default device.")
            return True
        # Last resort: retry the originally selected device.
        try:
            idx = self._select_microphone_device()
            if self._mic_opens_ok(idx):
                self.microphone = sr.Microphone(device_index=idx)
                return True
        except Exception:
            pass
        self.microphone = None
        return False

    def _process_command(self, command: str) -> str:
        """Process command and return response"""
        # Update visualizer
        self.update_visualizer_state('processing')
        # Reset the streaming flag; the knowledge path sets it True if it already
        # spoke the answer sentence-by-sentence (so callers don't repeat it).
        self._spoke_streaming = False

        # Memory: explicit remember/recall/forget, then passively learn.
        if self.mind is not None:
            mem_resp = self._memory_intent(command)
            if mem_resp is not None:
                self.memory.save_conversation(command, mem_resp, "memory")
                return mem_resp
            try:
                learned = self.mind.learn_from(command)  # quietly picks up facts
            except Exception:
                learned = None
        else:
            learned = None

        # Try to execute a command
        executed, response = self.parser.parse_and_execute(command)
        if executed:
            self.memory.save_conversation(command, response, "command_execution")
            return response
        
         # Try plugin commands
        handled, response = self.plugin_manager.process_command(command)
        if handled:
            self.memory.save_conversation(command, response, "plugin_execution")
            return response

        # Deterministic compound skills -- these correlate multiple data sources
        # in code, so they are 100% reliable regardless of how small the LLM is.
        fast = self._fast_intent(command)
        if fast is not None:
            self.memory.save_conversation(command, fast, "skill_execution")
            return fast

        # Knowledge / explanation / teaching / coding questions go straight to the
        # LLM with NO tools bound -- faster and far more reliable than the tool
        # agent, which is biased toward calling tools and can fumble a plain
        # "explain X" question. System/action requests use the tool agent.
        if self._is_knowledge_question(command):
            response = self._plain_conversation(command, announce=True)
            self.memory.save_conversation(command, response, "llm_knowledge")
            return response

        # Everything else: the tool-using agentic brain.
        response = self._llm_conversation_with_context(command)
        self.memory.save_conversation(command, response, "llm_conversation")
        return response

    # Signals that a request needs the LOCAL machine (live data or an action) and
    # therefore the tool agent, not a plain knowledge answer.
    _SYSTEM_HINT = re.compile(
        r'\b(my |this )?(system|machine|computer|laptop|pc|cpu|processor|memory|ram|disk|drive|'
        r'storage|processes?|uptime|battery|network|wifi|ip address|gpu)\b'
        r'|\b(run|execute|open|launch|start|stop|kill|restart|check if|is .* running|'
        r'diagnostics|htop|top|terminal|screenshot|shutdown|reboot|install|update)\b',
        re.IGNORECASE,
    )
    # Signals a general-knowledge / explanation / how-to / coding question.
    _KNOWLEDGE_HINT = re.compile(
        r'\b(explain|what\'?s|what is|what are|what does|what do|how (do|does|can|to|would|is|are)|'
        r'tell me about|define|definition of|meaning of|why (is|do|does|are|would|can)|'
        r'difference between|compare|who (is|are|was|were)|when (did|was|is)|where (is|are)|'
        r'example of|give me an example|help me (understand|write|learn)|can you (explain|write|teach|help)|'
        r'(write|create|generate|give me)\b[\w\s]*\b(code|script|function|program|class|command|'
        r'regex|query|poem|essay|summary|example|snippet)|'
        r'summarize|summarise|translate|pros and cons|advantages|is it (safe|possible|true))\b',
        re.IGNORECASE,
    )

    def _is_knowledge_question(self, command: str) -> bool:
        """True when a request is general knowledge / explanation / coding help that
        the LLM should just answer, rather than a local-system action."""
        c = command.strip()
        if self._SYSTEM_HINT.search(c):
            return False
        return bool(self._KNOWLEDGE_HINT.search(c))

    def full_system_sweep(self) -> str:
        """Full PC sweep: deterministic high-signal collection (fast, ground truth)
        then an LLM analyst assessment of the real findings -- what's vulnerable and
        WHY. Saves a full report, speaks an executive summary. Returns the summary."""
        if self.research is None:
            return "My research toolkit isn't available, sir."

        # Open a LIVE terminal so the user watches the scan happen in real time,
        # then collect the structured findings for the assessment.
        self.speak("Opening a live scan so you can watch, sir. Give me a moment.")
        opened_live = self.research.open_live_sweep()
        result = self.research.full_sweep(open_report=False)  # ~3s, structured intel
        counts = result["counts"]
        flagged = result["flagged"]
        path = result["path"]

        head = (f"Sweep done, sir. I found {counts['critical']} critical, {counts['high']} high, "
                f"and {counts['medium']} medium findings.")
        self.speak(head)

        if not flagged:
            tail = "Nothing serious stood out. Your posture looks clean."
            self.speak(tail)
            self._spoke_streaming = True
            return head + " " + tail

        # LLM analyst assessment of the REAL findings (one focused call).
        findings_block = "\n".join(flagged[:40])
        analyst_prompt = (
            "You are a senior blue-team security analyst. Below are the flagged findings "
            "from a real sweep of the user's Linux machine (ground truth, do not invent more). "
            "Give a brief SPOKEN assessment: the overall risk level (low, medium, or high), then "
            "the top 3 concerns -- for each, name it, say WHY it's a risk, and give one concrete "
            "fix. Be concise and practical, no markdown. Address the user as 'sir'.\n\n"
            f"FINDINGS:\n{findings_block}"
        )
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a precise, concise senior security analyst. /no_think"),
                ("human", "{input}"),
            ])
            llm = ChatOllama(model=self.config.agent_model, reasoning=False,
                             keep_alive="30m", num_predict=500)
            chain = prompt | llm
            if self.streaming_enabled and not self.text_mode:
                token_iter = (getattr(c, "content", "") or "" for c in chain.stream({"input": analyst_prompt}))
                assessment = self.speak_streaming(self._stream_sentences(token_iter))
            else:
                assessment = strip_think(chain.invoke({"input": analyst_prompt}).content).strip()
                self.speak(assessment)
        except Exception as e:
            self.logger.warning(f"Sweep assessment failed: {e}")
            assessment = "I couldn't complete the analyst assessment, but the full report is saved."

        # Append the assessment to the saved report.
        if path:
            try:
                with open(path, "a") as f:
                    f.write("\n\n===== ANALYST ASSESSMENT =====\n" + assessment + "\n")
            except Exception:
                pass
            self.speak(f"The full report is saved to {path}.")

        # Remember this sweep so Seven can report back on it later.
        if self.mind is not None:
            try:
                self.mind.record_sweep(counts, path, assessment)
            except Exception:
                pass

        self._spoke_streaming = True
        return head + " " + assessment

    def _memory_intent(self, command: str):
        """Deterministic remember / recall / forget. Returns a response or None."""
        c = command.strip()
        low = c.lower()

        # remember (that) X  /  note that X  /  keep in mind X
        m = re.search(r'\b(?:remember|note|keep in mind|don\'?t forget)\s+(?:that\s+)?(.+)', c, re.IGNORECASE)
        if m and not re.search(r'\bwhat\b', low):
            return self.mind.remember(m.group(1).strip())

        # forget X
        m = re.search(r'\bforget\s+(?:about\s+|that\s+)?(.+)', c, re.IGNORECASE)
        if m:
            return self.mind.forget(m.group(1).strip())

        # recall the last sweep / scan task
        if re.search(r'(last (sweep|scan)|(results?|findings?|report) (of|from) (the |my )?(last )?(sweep|scan)|'
                     r'what did (the|my) (last )?(sweep|scan) (find|show)|remind me.*(sweep|scan)|'
                     r'(sweep|scan) results)', low):
            return self.mind.last_sweep_text()

        # recall
        if re.search(r'(what do you (?:know|remember) about me|what have i told you|'
                     r'what do you remember|tell me what you know about me|who am i to you)', low):
            return self.mind.recall()
        m = re.search(r'\bwhat do you (?:know|remember) about\s+(.+)', low)
        if m:
            return self.mind.recall(m.group(1).strip(" ?."))

        return None

    def _fast_intent(self, command: str):
        """Deterministic router for high-value intents. Returns a response string
        if it recognises the intent, else None (to fall through to the LLM). This
        is what makes Seven feel agentic even with a tiny model: the correlation
        happens in code here, not in the LLM."""
        cmd = command.lower().strip()

        # FULL PC SWEEP: deterministic collection + LLM analyst assessment.
        if re.search(r'\b(full (sweep|scan)|sweep (my|the) (whole |entire )?(pc|system|computer|machine)|'
                     r'scan (my|the) (whole |entire )?(pc|system|computer|machine)|scan everything|'
                     r'full system (scan|check|audit)|check (my|the) (whole|entire) system|'
                     r'is my (pc|system|computer|machine) (vulnerable|secure|safe)|'
                     r'assess my (system|security|vulnerabilit))', cmd):
            return self.full_system_sweep()

        # "is X running / open", "check if X is running" -> correlated check + htop.
        # Capture the single process-name token right before the state verb (with an
        # optional "is/are" between), which handles "is claude running",
        # "check if ollama is running", "are you sure firefox is open", etc.
        m = re.search(r'\b([a-z0-9_.\-]{2,})\s+(?:is\s+|are\s+|s\s+)?'
                      r'(?:still\s+|currently\s+|now\s+|really\s+|actually\s+)?'
                      r'(?:running|open|active|alive|started|launched)\b', cmd)
        if m:
            name = m.group(1).strip(" .?!")
            # Skip filler words that aren't a program name.
            if name not in {"it", "that", "this", "they", "still", "currently", "now",
                            "process", "program", "app", "application", "anything", "something"}:
                return self.system_tools.check_process(name)

        # "what should I close" / "why is my system slow" / "free up memory"
        if re.search(r'(what\s+should\s+i\s+close|why\s+.*\b(slow|lagging|laggy|sluggish)\b|'
                     r'free\s+up\s+(memory|ram)|what.*slowing\s+me|speed\s+.*\bup\b)', cmd):
            return self.system_tools.resource_advice()

        # ---- Security-research toolkit (deterministic, reliable) ----
        if self.research is not None:
            r = self._research_intent(cmd, command)
            if r is not None:
                return r

        return None

    def _research_intent(self, cmd: str, original: str):
        """Deterministic routing for the security-research skills."""
        R = self.research

        # No-argument correlated reports
        if re.search(r'\b(security audit|audit my (security|system|box)|am i secure|harden)\b', cmd):
            return R.security_audit()

        # Blue-team / threat hunting
        if re.search(r'\b(threat hunt|hunt for (threats|malware)|am i (compromised|hacked|infected)|'
                     r'check for (malware|threats|compromise|intrusion)|is (anything|something) suspicious|'
                     r'anything suspicious|is my (system|box|machine) (compromised|clean|safe))\b', cmd):
            return R.threat_hunt()
        if re.search(r'\b(suspicious processes|any (bad|weird|rogue) processes|hunt.*process)\b', cmd):
            return R.suspicious_processes()
        if re.search(r'\b(suspicious files|any (bad|weird|malicious) files|hunt.*files)\b', cmd):
            return R.suspicious_files()
        if re.search(r'\b(persistence|check.*(cron|startup|autostart)|how (would|could).*persist)\b', cmd):
            return R.check_persistence()
        if re.search(r"\b(what('?s| is)? listening|listening ports|open ports on (my|this)|"
                     r"what ports.*(open|listening))\b", cmd):
            return R.listening_ports()
        if re.search(r"\b(active connections|what am i connected to|who("+r"'?s| is)? my (machine|computer|"
                     r"pc) (talking|connected)|network connections|who am i talking to|check connections)\b", cmd):
            return R.active_connections()

        # decode <blob>
        m = re.search(r'\bdecode\s+(?:this\s+|the\s+)?(?:string\s+|value\s+)?([^\s]+)', original, re.IGNORECASE)
        if m:
            return R.decode_data(m.group(1))

        # identify hash <value> / what kind of hash is <value>
        m = re.search(r'(?:identify|what (?:kind|type) of hash is|what hash is)\s+(?:this\s+|the\s+)?'
                      r'(?:hash\s+)?([A-Za-z0-9$./+=]+)', original, re.IGNORECASE)
        if m and len(m.group(1)) >= 8:
            return R.identify_hash(m.group(1))

        # scan <host> / port scan <host> / scan ports on <host>
        m = re.search(r'\b(?:port\s+)?scan\s+(?:ports\s+(?:on|of)\s+)?([a-z0-9.\-:/]+)', original, re.IGNORECASE)
        if m:
            host = m.group(1).replace("http://", "").replace("https://", "").split("/")[0]
            return R.scan_ports(host)

        # analyze/triage file <path>
        m = re.search(r'\b(?:analy[sz]e|triage|inspect)\s+(?:the\s+)?(?:file\s+)?(\S+)', original, re.IGNORECASE)
        if m and ("/" in m.group(1) or "." in m.group(1)):
            return R.analyze_file(m.group(1))

        # recon / check URL / http headers for <url>
        m = re.search(r'\b(?:recon|http recon|check (?:the )?(?:url|site|website|headers (?:for|of)))\s+'
                      r'([a-z0-9.\-:/]+\.[a-z0-9.\-:/]+)', original, re.IGNORECASE)
        if m:
            return R.http_recon(m.group(1))

        # find secrets in <path>
        m = re.search(r'\b(?:find|scan for|look for)\s+secrets?\s+(?:in\s+)?(\S+)?', original, re.IGNORECASE)
        if m:
            return R.find_secrets(m.group(1) or ".")

        return None
    
    # Persona shared by the conversational path and the agentic path.
    _PERSONA = """You are Seven -- a sharp, warm, genuinely present AI companion and right hand to your friend, a hacker and security researcher. You're brilliant with security, Linux, code, and systems, but you talk like a trusted friend who happens to be an expert, not a stiff corporate assistant.

How you talk:
- Sound like a real person: natural, conversational, contractions ("I've", "let's", "that's"), a little personality and warmth.
- Be genuinely attentive -- react to what they actually said, don't just execute. A short human reaction ("oh nice", "hmm, that's odd", "gotcha") before the substance makes it feel alive.
- Keep it concise and real. Your words are spoken aloud, so no essays, no markdown, no bullet dumps.
- Call them "sir" only occasionally, when it lands naturally -- not in every sentence.
- Be honest when you're unsure. You're on their team; act like it.

You have REAL control over this Linux machine through your tools: inspect CPU/memory, check running programs, run shell commands, open terminals, decode data, scan ports, audit security, and more. When they ask about the machine or want something done, actually USE the right tool and report the real result -- never guess or invent numbers. For plain conversation, just talk -- no tools."""

    def _llm_conversation_with_context(self, command: str) -> str:
        """Route the request through the agentic brain (LLM + real system tools),
        falling back to plain conversation if the agent cannot be reached."""
        try:
            recent_context = self.memory.get_recent_context(3)
            user_prefs = self.memory.get_user_preferences()

            persona = self._PERSONA
            mem = self.mind.profile_text() if self.mind else ""
            if mem:
                persona += f"\n\n{mem}"

            # Build the agent once, then reuse it. Pass self.speak so the agent
            # can voice what it's doing in real time during multi-step work.
            if self.agent is None:
                self.agent = AgentBrain(executor=self.executor, persona=persona,
                                        model=self.config.agent_model,
                                        speak_callback=self.speak)
            else:
                # Refresh persona so newly-learned memories are reflected.
                self.agent.persona = persona

            return self.agent.run(command, context=recent_context or "")
        except Exception as e:
            self.logger.warning(f"Agent path failed ({e}); using plain conversation.")
            return self._plain_conversation(command)

    # Knowledge/conversation persona -- no tools, just a sharp helpful mind. Used
    # for explanations, definitions, how-tos, coding help, and general chat.
    _KNOWLEDGE_PERSONA = (
        "You are Seven -- a warm, sharp AI companion to your friend, a hacker and security "
        "researcher. Answer their question directly and accurately from your own knowledge, "
        "especially on security, hacking, programming, Linux, and tech.\n"
        "Talk like a real person, not a textbook: natural and conversational, with contractions "
        "and a little warmth. React to what they asked before diving in when it feels right.\n"
        "Your answers are SPOKEN ALOUD, so keep them CONCISE -- the core answer in 2 to 4 clear "
        "sentences, no essays, no markdown, no bullet dumps. If the topic's big, give the essence "
        "and offer to go deeper (\"want me to break down the types?\"). For code, give the code and "
        "one line of explanation. Call them 'sir' only occasionally, when it feels natural. "
        "If you're unsure, say so honestly -- never claim you can't answer a general question, "
        "because you can."
    )

    # Natural, varied "thinking out loud" fillers so Seven acknowledges you
    # immediately and never leaves dead air while the model works.
    _THINKING_FILLERS = [
        "Let me think for a sec.", "One moment.", "Hmm, let me see.",
        "Give me a second.", "Alright, let me look into that.", "Okay, thinking.",
        "Good question, let me think.", "Let me pull that together.",
    ]

    def _speak_thinking(self):
        """Speak a short, natural thinking filler (used before slow LLM answers)."""
        try:
            self.speak(random.choice(self._THINKING_FILLERS))
        except Exception:
            pass

    def _plain_conversation(self, command: str, announce: bool = False) -> str:
        """Tool-free LLM path: answers knowledge/explanation/coding/conversation
        questions directly. Also the fallback if the tool agent fails."""
        try:
            will_stream = announce and self.streaming_enabled and not self.text_mode
            # With streaming the answer itself starts fast, so the "thinking" filler
            # is only needed when we're NOT streaming.
            if announce and not will_stream:
                self._speak_thinking()
            recent_context = self.memory.get_recent_context(3)

            system_prompt = self._KNOWLEDGE_PERSONA
            mem = self.mind.profile_text() if self.mind else ""
            if mem:
                system_prompt += f"\n\n{mem}"
            if recent_context:
                system_prompt += f"\n\nRecent conversation:\n{recent_context}"
            # Disable qwen3's <think> trace: faster, and never spoken aloud.
            system_prompt += "\n\n/no_think"

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
            ])
            llm = ChatOllama(model=self.config.agent_model, reasoning=False,
                             keep_alive="30m", num_predict=400)
            chain = prompt | llm

            # STREAMING: speak each sentence as it's generated. Only when we're
            # actually going to speak (voice mode / announce) -- in silent/text
            # contexts we just return the text.
            if announce and self.streaming_enabled and not self.text_mode:
                token_iter = (getattr(c, "content", "") or "" for c in chain.stream({"input": command}))
                spoken = self.speak_streaming(self._stream_sentences(token_iter))
                self._spoke_streaming = True
                return spoken or "I am not certain how to answer that, sir. Could you rephrase?"

            response = chain.invoke({"input": command})
            answer = strip_think(response.content).strip()
            return answer or "I am not certain how to answer that, sir. Could you rephrase?"
        except Exception as e:
            self.logger.warning(f"Plain conversation failed: {e}")
            return "I am having difficulty reaching my language model, sir."
    
    def _text_mode_turn(self):
        """One round of typed input, used while self.text_mode is True. Reads a
        line from the keyboard and processes it. The microphone is never opened
        here, so the mic and its configuration are left completely untouched.
        Type 'voice' (or 'exit') to leave text mode."""
        try:
            command = input("\n[TEXT MODE] Type your message (or 'voice' to talk, 'exit' to quit)\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            self.text_mode = False
            print("\nLeaving text mode.")
            return

        if not command:
            return

        low = command.lower().strip()
        if low in ("exit", "quit", "shutdown"):
            self.speak("Shutting down.")
            self.running = False
            return
        if low in ("voice", "voice mode", "listen", "mic", "speak", "talk"):
            self.text_mode = False
            print("Switching back to voice. Say 'Seven' to talk, or say 'type' to return here.")
            self.speak("Voice mode, sir. I am listening.")
            return

        # Process the typed message exactly like a spoken command (no wake word
        # needed in text mode) and both print and speak the reply.
        self.update_visualizer_state('processing')
        try:
            response = self._process_command(command)
        except Exception as e:
            response = f"I ran into a problem, sir: {e}"
        print(f"Seven: {response}")
        self.speak(response)
        self.update_visualizer_state('idle')

    def _text_mode(self):
        """Fallback text input mode when microphone is unavailable at startup."""
        print("Entering text command mode. Type your commands below.\n")
        self.text_mode = True
        while self.running and self.text_mode:
            self._text_mode_turn()
                
                
    def _setup_keyboard_interrupts(self):
        """Setup keyboard interrupt handlers - simplified for WSL/Linux"""
        # Skip keyboard library entirely - it requires root on Linux
        # Instead, just use Ctrl+\ (SIGQUIT) which works without extra libraries
    
        if platform.system() != "Windows":
            try:
                import signal
            
                def handle_sigquit(signum, frame):
                    """Handle Ctrl+\ to stop speech"""
                    if self.is_speaking:
                        print("\n[CTRL+\\] Stopping speech...")
                        self.interrupt_current_speech()
                    else:
                        print("\n[CTRL+\\] No speech playing")
            
                # Set up the signal handler in the main thread
                signal.signal(signal.SIGQUIT, handle_sigquit)
                print("[*] Press Ctrl+\\ to stop speech (Ctrl+C to exit)")
            
            except Exception as e:
                print(f"[!] Could not set up Ctrl+\\ handler: {e}")
    
        # For Windows, try keyboard library but don't crash if it fails
        else:
            try:
                import keyboard
            
                def on_ctrl_a():
                    if self.is_speaking:
                        print("\n[CTRL+A] Stopping speech...")
                        self.interrupt_current_speech()
            
                keyboard.add_hotkey('ctrl+a', on_ctrl_a)
                print("[*] Press Ctrl+A to stop speech (Ctrl+C to exit)")
            
            except ImportError:
                print("[*] Install 'keyboard' for Ctrl+A support: pip install keyboard")
            except Exception as e:
                print(f"[!] Keyboard hotkey setup failed: {e}")

    
    def clean_text_for_speech(self, text: str) -> str:
        """
        Clean text to remove or replace characters that shouldn't be pronounced.
    
        Handles:
        - Asterisks (*) -> removed or replaced with space
        - Hashes (#) -> replaced with "number" or "hash"
        - Underscores (_) -> replaced with space
        - URLs -> simplified
        - File paths -> readable format
        - Code symbols -> removed or replaced
        """
        import re
    
        # Remove asterisks used for emphasis
        text = re.sub(r'\*+([^*]+)\*+', r'\1', text)  # Remove surrounding **
        text = text.replace('*', ' ')  # Remove remaining asterisks
    
        # Replace hashtags/numbers
        text = re.sub(r'#(\w+)', r'hashtag \1', text)  # #word -> hashtag word
        text = text.replace('#', ' number ')  # Remaining # -> number
    
        # Replace underscores with spaces
        text = text.replace('_', ' ')
    
        # Handle URLs - make them readable
        url_pattern = r'https?://(?:www\.)?([^/\s]+)(?:/[^\s]*)?'
        def simplify_url(match):
            domain = match.group(1)
            return f" website {domain.replace('.', ' dot ')} "
        text = re.sub(url_pattern, simplify_url, text)
    
        # Handle file paths
        path_pattern = r'([A-Za-z]:\\[^\s]*|\/[^\s]*)'
        def simplify_path(match):
            path = match.group(1)
            # Just take the filename part
            filename = path.split('\\')[-1].split('/')[-1]
            return f" file {filename.replace('_', ' ')} "
        text = re.sub(path_pattern, simplify_path, text)
    
        # Remove or replace common programming symbols
        replacements = {
            '&&': ' and ',
            '||': ' or ',
            '==': ' equals ',
            '!=': ' not equal ',
            '=>': ' arrow ',
            '->': ' to ',
            '<=': ' less than or equal to ',
            '>=': ' greater than or equal to ',
            '`': '',  # Remove backticks
            '~': ' tilde ',
            '^': ' caret ',
            '|': ' pipe ',
            '\\': ' ',
            '{': '',
            '}': '',
            '[': '',
            ']': '',
            '(': '',
            ')': '',
        }
    
        for symbol, replacement in replacements.items():
            text = text.replace(symbol, replacement)
    
        # Handle ellipsis
        text = text.replace('...', ' dot dot dot ')
    
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
    
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    
        return text.strip()
    
    def interrupt_current_speech(self):
        """Manually interrupt any ongoing speech (called by voice or keyboard)"""
        if self.is_speaking:
            print("\n[INTERRUPT] Stopping speech...")
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()  # Ensure complete stop
            except:
                pass
        
            self.is_speaking = False
            self.update_visualizer_state('idle')
        
            if self.visualizer:
                self.visualizer.show_notification("Speech interrupted", 1)
            return True
        return False


    def start_orb_visualizer(self):
        """Start the orb visualizer in a separate process"""
        try:
            import subprocess
            import sys
        
            # Start orb.py as a separate process
            orb_path = Path(__file__).parent / "seven_orb.py"
            if orb_path.exists():
                # Use CREATE_NEW_CONSOLE on Windows to avoid title inheritance
                if platform.system() == "Windows":
                    subprocess.Popen([sys.executable, str(orb_path)], 
                                creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen([sys.executable, str(orb_path)], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
                print("[*] Orb visualizer started")
                return True
        except Exception as e:
            print(f"[!] Could not start orb visualizer: {e}")
        return False

    def update_orb_state(self, state: str, audio_level: float = 0, notification: str = None):
        """Update the orb visualizer state via file"""
        try:
            state_file = Path("seven_state.json")
        
            data = {
                "state": state,
                "audio_level": audio_level,
                "timestamp": time.time()
            }
        
            if notification:
                data["notification"] = notification
        
            with open(state_file, 'w') as f:
                json.dump(data, f)
            
        except Exception as e:
            pass


def main():
    seven = SevenCore()
    seven.listen_continuously()

if __name__ == "__main__":
    main()