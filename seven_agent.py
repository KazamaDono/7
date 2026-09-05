"""
seven_agent.py - Agentic brain for Seven.

Gives Seven real capability: the local LLM (qwen3 via Ollama) is bound to a set
of concrete system tools and runs a tool-calling loop, so a spoken request like
"what's eating my memory?" becomes: model -> top_processes() -> reads real psutil
data -> natural-language answer. This is the difference between Seven parroting
regex matches and Seven actually doing things and reporting back.
"""

import os
import re
import json
import shutil
import platform
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

try:
    from seven_skills import ResearchSkills
    HAS_SKILLS = True
except Exception:
    HAS_SKILLS = False


# ----------------------------------------------------------------------
# Concrete system capabilities the agent can invoke
# ----------------------------------------------------------------------
class SystemTools:
    """Real system actions. Each public method returns a short human-readable
    string -- that string is fed straight back to the LLM as the tool result and
    is also suitable for Seven to speak."""

    def __init__(self, executor=None):
        # Reuse CommandExecutor when available so run_command shares its blocklist.
        self.executor = executor
        self.system = platform.system()
        self._command_cache = None  # cached list of executables on PATH

    # -- discover every runnable command on PATH (for fuzzy "did you mean") --
    def _all_system_commands(self) -> List[str]:
        if self._command_cache is not None:
            return self._command_cache
        cmds = set()
        for d in os.environ.get("PATH", "").split(os.pathsep):
            try:
                for entry in os.scandir(d):
                    if entry.is_file() and os.access(entry.path, os.X_OK):
                        cmds.add(entry.name)
            except (FileNotFoundError, NotADirectoryError, PermissionError):
                pass
        self._command_cache = sorted(cmds)
        return self._command_cache

    def suggest_commands(self, term: str, count: int = 6) -> str:
        """Search the system for installed commands whose names resemble `term`.
        Used when a requested command isn't recognised, to offer alternatives."""
        import difflib
        term = (term or "").strip().split()[0] if term else ""
        if not term:
            return "No command name to search for."
        allcmds = self._all_system_commands()
        # Close fuzzy matches, plus substring matches (catches 'monitor' -> 'htop'? no,
        # but 'disk' -> 'disktype' etc.), deduped, preserving relevance order.
        close = difflib.get_close_matches(term, allcmds, n=count, cutoff=0.6)
        substr = [c for c in allcmds if term.lower() in c.lower() and c not in close]
        hits = (close + substr)[:count]
        if not hits:
            return f"No installed commands resemble '{term}'."
        return f"Installed commands similar to '{term}': {', '.join(hits)}"

    # -- resource inspection (the flagship "what's eating my memory" feature) --
    def top_processes(self, sort_by: str = "memory", count: int = 5) -> str:
        if not HAS_PSUTIL:
            return "psutil is not available, so I cannot inspect processes."

        count = max(1, min(int(count or 5), 15))
        sort_by = (sort_by or "memory").lower()

        procs = []
        # Prime cpu_percent so the second read returns real per-process values.
        for p in psutil.process_iter(["pid", "name"]):
            try:
                p.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        import time
        time.sleep(0.4)

        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mem_mb = p.info["memory_info"].rss / (1024 ** 2) if p.info["memory_info"] else 0
                cpu = p.cpu_percent(None)
                procs.append((p.info["name"] or "?", p.info["pid"], mem_mb, cpu))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if sort_by == "cpu":
            procs.sort(key=lambda x: x[3], reverse=True)
            top = procs[:count]
            lines = [f"{name} (pid {pid}): {cpu:.0f}% CPU, {mem:.0f} MB"
                     for name, pid, mem, cpu in top]
            return "Top processes by CPU:\n" + "\n".join(lines)
        else:
            procs.sort(key=lambda x: x[2], reverse=True)
            top = procs[:count]
            lines = [f"{name} (pid {pid}): {mem:.0f} MB, {cpu:.0f}% CPU"
                     for name, pid, mem, cpu in top]
            return "Top processes by memory:\n" + "\n".join(lines)

    def system_status(self) -> str:
        parts = []
        if HAS_PSUTIL:
            cpu = psutil.cpu_percent(interval=0.4)
            mem = psutil.virtual_memory()
            parts.append(f"CPU at {cpu:.0f}%")
            parts.append(f"memory {mem.percent:.0f}% used "
                         f"({mem.used / 1024**3:.1f} of {mem.total / 1024**3:.1f} GB)")
            try:
                boot = datetime.fromtimestamp(psutil.boot_time())
                up = datetime.now() - boot
                hrs = int(up.total_seconds() // 3600)
                parts.append(f"up for {hrs} hours")
            except Exception:
                pass
        try:
            du = shutil.disk_usage("/")
            parts.append(f"disk {du.used / 1024**3:.0f} of {du.total / 1024**3:.0f} GB used")
        except Exception:
            pass
        return "System status: " + ", ".join(parts) + "." if parts else "No system metrics available."

    # -- COMPOUND SKILLS: multi-source gather + correlate, all in code so the
    #    result is guaranteed regardless of how small the language model is. --

    def check_process(self, name: str, show: bool = True) -> str:
        """The 'is X running?' skill. Deterministically: find every matching
        process, correlate count + total memory + CPU, and (if running and show)
        open htop focused on exactly those PIDs so the user can watch them live.
        Returns a single spoken-ready sentence."""
        if not HAS_PSUTIL:
            return "psutil is not available, sir."
        term = (name or "").lower().strip()
        if not term:
            return "Which program should I check, sir?"

        # Prime CPU counters for a real per-process reading.
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                if term in (p.info["name"] or "").lower():
                    p.cpu_percent(None)
                    procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if not procs:
            return f"No, {name} is not currently running, sir."

        import time
        time.sleep(0.3)
        pids, total_mem, total_cpu = [], 0.0, 0.0
        for p in procs:
            try:
                mi = p.memory_info()
                total_mem += mi.rss / (1024 ** 2)
                total_cpu += p.cpu_percent(None)
                pids.append(p.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        n = len(pids)
        proc_word = "process" if n == 1 else f"{n} processes"
        watched = ""
        if show and pids:
            # Open htop focused on just these PIDs (htop -p pid1,pid2,...).
            pid_arg = ",".join(str(x) for x in pids[:40])
            opened = self.open_terminal(f"htop -p {pid_arg}")
            if opened.startswith("Opened"):
                watched = " I've opened htop focused on it so you can watch."

        if total_mem >= 1024:
            mem_str = f"{total_mem / 1024:.1f} GB"
        else:
            mem_str = f"{total_mem:.0f} MB"
        cpu_str = f", {total_cpu:.0f}% CPU" if total_cpu >= 1 else ""
        return (f"Yes, {name} is running as {proc_word}, using {mem_str}{cpu_str} in total, sir."
                + watched)

    def resource_advice(self) -> str:
        """Correlate memory pressure, swap, and the biggest consumer into a single
        efficiency recommendation -- 'what should I close to speed things up'."""
        if not HAS_PSUTIL:
            return "psutil is not available, sir."
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Aggregate memory per program name (chrome spawns many processes).
        by_name: Dict[str, float] = {}
        for p in psutil.process_iter(["name", "memory_info"]):
            try:
                mb = p.info["memory_info"].rss / (1024 ** 2) if p.info["memory_info"] else 0
                by_name[p.info["name"] or "?"] = by_name.get(p.info["name"] or "?", 0) + mb
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        ranked = sorted(by_name.items(), key=lambda kv: kv[1], reverse=True)[:3]

        verdict = []
        if mem.percent >= 90:
            verdict.append(f"Memory is critically high at {mem.percent:.0f}%")
        elif mem.percent >= 75:
            verdict.append(f"Memory is getting tight at {mem.percent:.0f}%")
        else:
            verdict.append(f"Memory is healthy at {mem.percent:.0f}% used")
        if swap.total and swap.percent >= 40:
            verdict.append(f"and the system is swapping ({swap.percent:.0f}% of swap used), which slows things down")

        if ranked:
            top_name, top_mb = ranked[0]
            top_str = f"{top_mb/1024:.1f} GB" if top_mb >= 1024 else f"{top_mb:.0f} MB"
            advice = f" Your biggest consumer is {top_name} at {top_str}"
            if len(ranked) > 1:
                advice += f", then {ranked[1][0]}"
            advice += ". Closing it would free the most memory."
        else:
            advice = ""
        return ". ".join(verdict) + "." + advice + " Sir."

    def find_process(self, name: str) -> str:
        if not HAS_PSUTIL:
            return "psutil is not available."
        name = (name or "").lower().strip()
        if not name:
            return "No process name given."
        matches = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                pname = (p.info["name"] or "").lower()
                if name in pname:
                    mem_mb = p.info["memory_info"].rss / (1024 ** 2) if p.info["memory_info"] else 0
                    matches.append(f"{p.info['name']} (pid {p.info['pid']}): {mem_mb:.0f} MB")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if not matches:
            return f"No running process matching '{name}'."
        return f"Found {len(matches)} process(es) matching '{name}':\n" + "\n".join(matches[:10])

    # -- general execution --
    def run_command(self, command: str) -> str:
        command = (command or "").strip()
        if not command:
            return "No command given."

        if self.executor is not None:
            result = self.executor.execute(command)
            if result.get("success"):
                out = (result.get("output") or "").strip()
                return f"Command succeeded. Output:\n{out[:1500]}" if out else "Command succeeded (no output)."
            err = result.get("error", "unknown error")
            return self._augment_command_error(command, err)
        # Fallback if no executor was wired in
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                out = (r.stdout or "").strip()
                return f"Output:\n{out[:1500]}" if out else "Command finished with no output."
            return self._augment_command_error(command, (r.stderr or "").strip() or "non-zero exit")
        except Exception as e:
            return f"Command failed: {e}"

    def _augment_command_error(self, command: str, err: str) -> str:
        """On 'command not found', attach fuzzy suggestions so the model can ask
        the user 'did you mean X?' instead of just giving up."""
        first = command.split()[0] if command.split() else command
        if "not found" in err.lower() or "no such file" in err.lower():
            allcmds = self._all_system_commands()
            if first not in allcmds:
                sugg = self.suggest_commands(first)
                return f"Command '{first}' is not installed or not found. {sugg}"
        return f"Command failed: {err[:500]}"

    # -- diagnostics: open a terminal and run a quick/full health check --
    def run_diagnostics(self, level: str = "quick") -> str:
        level = (level or "quick").lower()
        full = level in ("full", "deep", "complete", "thorough")

        quick_cmds = [
            "echo '===== SEVEN DIAGNOSTICS ($LEVEL) ====='",
            "echo; echo '--- Uptime / Load ---'; uptime",
            "echo; echo '--- Memory ---'; free -h",
            "echo; echo '--- Disk ---'; df -h -x tmpfs -x devtmpfs",
            "echo; echo '--- Top 8 by memory ---'; ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -9",
            "echo; echo '--- Top 8 by CPU ---'; ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -9",
            "echo; echo '--- Network interfaces ---'; ip -br addr 2>/dev/null || ifconfig",
        ]
        full_extra = [
            "echo; echo '--- Connectivity ---'; ping -c 2 8.8.8.8",
            "echo; echo '--- Listening ports ---'; (ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null) | head -20",
            "echo; echo '--- Failed services ---'; systemctl --failed --no-pager 2>/dev/null | head -20",
            "echo; echo '--- Recent errors (journal) ---'; journalctl -p err -n 15 --no-pager 2>/dev/null",
            "echo; echo '--- Sensors ---'; sensors 2>/dev/null || echo '(lm-sensors not installed)'",
            "echo; echo '--- Kernel/OS ---'; uname -a; echo; (lsb_release -d 2>/dev/null || cat /etc/os-release | head -1)",
        ]
        cmds = quick_cmds + (full_extra if full else [])
        script = ("LEVEL='%s'; " % ("full" if full else "quick")) + " ; ".join(cmds) + \
                 " ; echo ; echo '===== diagnostics complete ====='"
        result = self.open_terminal(script)
        label = "full" if full else "quick"
        if result.startswith("Opened"):
            return f"Running a {label} diagnostics report in a new terminal window, sir."
        return f"Could not open a diagnostics terminal: {result}"

    # -- open a real terminal window, optionally running a command --
    def open_terminal(self, command: str = "") -> str:
        command = (command or "").strip()

        # Each entry: (binary, arg-builder that returns the full argv given an
        # inner shell command, or None to just open a shell).
        def keep_open(inner: str) -> str:
            # Run the command then drop to an interactive shell so the window
            # doesn't vanish when the command exits.
            return f"{inner}; exec bash" if inner else "exec bash"

        candidates = [
            ("ptyxis", lambda c: ["ptyxis", "--", "bash", "-c", keep_open(c)]),
            ("gnome-terminal", lambda c: ["gnome-terminal", "--", "bash", "-c", keep_open(c)]),
            ("konsole", lambda c: ["konsole", "-e", "bash", "-c", keep_open(c)]),
            ("xfce4-terminal", lambda c: ["xfce4-terminal", "-e", f"bash -c '{keep_open(c)}'"]),
            ("xterm", lambda c: ["xterm", "-e", "bash", "-c", keep_open(c)]),
            ("x-terminal-emulator", lambda c: ["x-terminal-emulator", "-e", "bash", "-c", keep_open(c)]),
        ]

        for binary, build in candidates:
            if shutil.which(binary):
                try:
                    subprocess.Popen(build(command))
                    if command:
                        return f"Opened a terminal running: {command}"
                    return "Opened a new terminal."
                except Exception as e:
                    return f"Failed to open terminal ({binary}): {e}"
        return "No terminal emulator found on this system."


# ----------------------------------------------------------------------
# Tool schemas advertised to the model (OpenAI function-calling format)
# ----------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "top_processes",
            "description": ("List the processes currently using the most memory or CPU. "
                            "Use this whenever asked what is consuming, eating, or hogging "
                            "memory, CPU, RAM, or system resources."),
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {"type": "string", "enum": ["memory", "cpu"],
                                "description": "Whether to rank by 'memory' or 'cpu'."},
                    "count": {"type": "integer", "description": "How many to list (default 5)."},
                },
                "required": ["sort_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": ("Get an overall snapshot of the machine: CPU load, memory usage, "
                            "uptime, and disk usage. Use for 'how is my system', 'system status', "
                            "'how much memory is free'."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_process",
            "description": ("Answer 'is X running?' and correlate it: reports whether the program is "
                            "running, how many processes, and total memory/CPU, and opens htop focused "
                            "on it so the user can watch. Use for 'is claude running', 'is chrome open', "
                            "'check if X is running'."),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Program/process name, e.g. 'claude', 'firefox'."}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resource_advice",
            "description": ("Correlate memory pressure, swap, and the biggest consumers into one "
                            "recommendation. Use for 'what should I close', 'why is my system slow', "
                            "'how do I free up memory', 'what's slowing me down'."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_process",
            "description": "List running processes whose name matches a term (raw list, no correlation).",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Process name to search for, e.g. 'chrome'."}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": ("Run a shell command on this Linux machine and return its output. "
                            "Use for concrete actions not covered by other tools. Do NOT use for "
                            "privileged (sudo) actions."),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "The shell command to run."}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_terminal",
            "description": ("Open a real terminal window for the user, optionally running a live "
                            "program in it such as htop, top, or a log tail. Use when the user wants "
                            "to watch something live or wants a terminal opened."),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string",
                                           "description": "Command to run in the terminal, e.g. 'htop'. Empty for a plain shell."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_diagnostics",
            "description": ("Open a new terminal window and run a system health/diagnostics report. "
                            "Use when the user asks to 'run diagnostics', a 'quick check', or a "
                            "'full check' of the machine."),
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "string", "enum": ["quick", "full"],
                                         "description": "'quick' for a fast snapshot, 'full' for a thorough report."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_commands",
            "description": ("Search the system for installed commands whose names resemble a word. "
                            "Use when the user's requested command is unknown or misheard, to offer "
                            "'did you mean' alternatives before asking them."),
            "parameters": {
                "type": "object",
                "properties": {"term": {"type": "string", "description": "The command name to find alternatives for."}},
                "required": ["term"],
            },
        },
    },
]

# Security-research / engineering skills (from seven_skills.ResearchSkills).
RESEARCH_TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "decode_data",
        "description": "Auto-detect and decode a string: JWT, base64, hex, URL-encoding, or ROT13. Use for 'decode this', JWTs, or encoded blobs.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "The encoded string."}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "identify_hash",
        "description": "Identify what kind of hash a value is (MD5, SHA-1/256/512, bcrypt, NTLM, etc.).",
        "parameters": {"type": "object", "properties": {"value": {"type": "string", "description": "The hash string."}}, "required": ["value"]}}},
    {"type": "function", "function": {
        "name": "hash_text",
        "description": "Compute a hash of some text (md5, sha1, sha256, sha512).",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "algo": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "analyze_file",
        "description": "Triage a file: type, size, SHA-256, entropy (is it packed/encrypted?), and printable strings. Use for 'analyze', 'what is this file', malware triage.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "find_secrets",
        "description": "Scan a directory for hardcoded secrets: API keys, tokens, private keys, passwords.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "listening_ports",
        "description": "List what is listening on THIS host, the owning process, and whether each is exposed to the network or localhost-only.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "active_connections",
        "description": "Show who this machine is talking to right now: established external connections with the owning process and remote host. Use for 'what am I connected to', spotting exfiltration.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "scan_ports",
        "description": "TCP connect-scan common ports on a host you are authorised to test.",
        "parameters": {"type": "object", "properties": {"host": {"type": "string"}}, "required": ["host"]}}},
    {"type": "function", "function": {
        "name": "http_recon",
        "description": "Fetch a URL and report status, server, detected tech, and security-header posture (CSP, HSTS, etc.).",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "security_audit",
        "description": "Correlated host-hardening report: exposed listeners, SUID binaries, world-writable files, firewall state, failed logins. Use for 'security audit', 'am I secure', 'harden my box'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "suspicious_processes",
        "description": "Blue-team hunt of the process table for signs of compromise: processes from temp dirs, deleted binaries still running, or name masquerading.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "suspicious_files",
        "description": "Hunt the filesystem for compromise tells: SUID in odd places, executables in temp, recently-modified system binaries, world-writable /etc files.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "check_persistence",
        "description": "Review persistence footholds: cron, systemd units, shell rc files, SSH authorized_keys, rc.local.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "threat_hunt",
        "description": "Full defensive sweep correlating processes, files, network, and persistence into one blue-team report, opened in a terminal. Use for 'threat hunt', 'am I compromised', 'check for malware', 'is anything suspicious'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "system_sweep",
        "description": "Run a FULL system sweep: inventory processes, listeners, connections, persistence, SUID, accounts, SSH/firewall posture. Returns flagged findings for you to assess. Use for 'scan my whole PC', 'is my system vulnerable', 'full security sweep'. After it returns, assess the findings: overall risk and why.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content (code, config, a script, notes) to a file, creating folders as needed. Use when asked to create/save/write a file or some code. Generate the full content yourself and pass it.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Destination path, e.g. ~/scripts/hello.py"},
            "content": {"type": "string", "description": "The full file content."}},
            "required": ["path", "content"]}}},
]


# ----------------------------------------------------------------------
# Agentic loop
# ----------------------------------------------------------------------
def strip_think(text: str) -> str:
    """Remove qwen3 reasoning traces so Seven never speaks its chain-of-thought.
    Handles complete <think>...</think> blocks and a stray leading block that
    only has the closing tag."""
    if not text:
        return text
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Some responses emit reasoning then a lone </think> with no opening tag.
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


class AgentBrain:
    """Wraps ChatOllama with tools bound and runs the call/execute/summarise loop."""

    MAX_ITERS = 6  # room for multi-step requests (e.g. open htop AND report memory)

    def __init__(self, executor=None, model: str = "qwen3:4b", persona: str = "",
                 speak_callback=None):
        self.tools = SystemTools(executor=executor)
        self.persona = persona
        self.model = model
        # Optional callback so Seven can speak progress in real time while it works.
        self.speak_callback = speak_callback
        all_schemas = list(TOOL_SCHEMAS)
        # Latency tuning: keep_alive keeps the model resident in RAM between turns
        # (no cold reload -> much snappier back-and-forth); num_predict caps runaway
        # generation so replies come back fast for natural conversation.
        self.llm = ChatOllama(model=model, reasoning=False, keep_alive="30m", num_predict=400)
        self._dispatch = {
            "top_processes": self.tools.top_processes,
            "system_status": self.tools.system_status,
            "check_process": self.tools.check_process,
            "resource_advice": self.tools.resource_advice,
            "find_process": self.tools.find_process,
            "run_command": self.tools.run_command,
            "open_terminal": self.tools.open_terminal,
            "run_diagnostics": self.tools.run_diagnostics,
            "suggest_commands": self.tools.suggest_commands,
        }
        # Merge the security-research / engineering toolkit if available.
        if HAS_SKILLS:
            self.research = ResearchSkills(executor=executor)
            all_schemas += RESEARCH_TOOL_SCHEMAS
            self._dispatch.update({
                "decode_data": self.research.decode_data,
                "identify_hash": self.research.identify_hash,
                "hash_text": self.research.hash_text,
                "analyze_file": self.research.analyze_file,
                "find_secrets": self.research.find_secrets,
                "listening_ports": self.research.listening_ports,
                "active_connections": self.research.active_connections,
                "scan_ports": self.research.scan_ports,
                "http_recon": self.research.http_recon,
                "security_audit": self.research.security_audit,
                "suspicious_processes": self.research.suspicious_processes,
                "suspicious_files": self.research.suspicious_files,
                "check_persistence": self.research.check_persistence,
                "threat_hunt": self.research.threat_hunt,
                "system_sweep": self.research.system_sweep,
                "write_file": self.research.write_file,
            })
        self.llm = self.llm.bind_tools(all_schemas)

    # Short spoken acknowledgement per tool, so the user hears what Seven is doing
    # as it happens instead of waiting in silence.
    _TOOL_NARRATION = {
        "top_processes": "Checking what's using the most resources.",
        "system_status": "Checking your system status.",
        "check_process": "Let me check that for you.",
        "resource_advice": "Analyzing what's slowing you down.",
        "find_process": "Looking for that process.",
        "run_command": "Running that now.",
        "open_terminal": "Opening a terminal.",
        "run_diagnostics": "Starting the diagnostics.",
        "suggest_commands": "Searching for similar commands.",
        "decode_data": "Decoding that.",
        "identify_hash": "Identifying the hash.",
        "hash_text": "Hashing that.",
        "analyze_file": "Analyzing the file.",
        "find_secrets": "Scanning for secrets.",
        "listening_ports": "Checking what's listening.",
        "active_connections": "Checking who you're connected to.",
        "scan_ports": "Scanning the target.",
        "http_recon": "Reconning that URL.",
        "security_audit": "Running a security audit.",
        "suspicious_processes": "Hunting through your processes.",
        "suspicious_files": "Sweeping the filesystem.",
        "check_persistence": "Checking persistence footholds.",
        "threat_hunt": "Starting a full threat hunt.",
        "system_sweep": "Running a full system sweep.",
        "write_file": "Writing that out for you.",
    }

    # Tool-usage guidance appended to the persona so the small model reliably
    # reaches for tools AND completes every part of a multi-step request.
    _TOOL_GUIDE = (
        "\n\nYOU CAN RUN ANY SHELL COMMAND on this Linux machine with the run_command tool "
        "(kernel version -> `uname -r`, users -> `who`, network -> `ip a`, packages, git, etc). "
        "Never say you cannot check something about the system -- if there is no dedicated tool "
        "for it, call run_command with the right shell command. Never print a tool call as text; "
        "actually call the tool.\n"
        "IMPORTANT: a request may contain SEVERAL actions (for example 'open htop AND tell me the "
        "top memory processes'). Do EVERY part: call one tool, then when it returns call the next "
        "tool, and only give your final spoken answer once all parts are done.\n"
        "If a command is not found, call suggest_commands to find close alternatives, then ask the "
        "user which they meant rather than guessing.\n"
        "If the user asks a GENERAL KNOWLEDGE, explanation, definition, how-to, or coding question "
        "(for example 'explain what XSS is') that does NOT need live data from THIS machine, just "
        "answer it directly and helpfully from your own knowledge -- do NOT call any tool. Never "
        "say you cannot answer a general question.\n"
        "After the tools are done, reply in one or two short, warm, natural spoken sentences."
    )

    def _narrate(self, name: str):
        if self.speak_callback:
            line = self._TOOL_NARRATION.get(name)
            if line:
                try:
                    self.speak_callback(line)
                except Exception:
                    pass

    def _run_leaked_call(self, content: str) -> Optional[str]:
        """Small models sometimes emit a tool call as plain text instead of a real
        function call. Detect `{"name": ..., "arguments": {...}}` and execute it."""
        if not content:
            return None
        m = re.search(r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}', content, re.DOTALL)
        if not m:
            return None
        name = m.group(1)
        fn = self._dispatch.get(name)
        if not fn:
            return None
        try:
            args = json.loads(m.group(2))
            # Drop args the tool doesn't accept (models invent extras like disk_usage=true).
            import inspect
            valid = set(inspect.signature(fn).parameters)
            args = {k: v for k, v in args.items() if k in valid}
            return str(fn(**args))
        except Exception:
            try:
                return str(fn())
            except Exception:
                return None

    def run(self, user_message: str, context: str = "") -> str:
        system_text = (self.persona or (
            "You are Seven, a capable AI assistant with real control over this Linux machine. "
            "Address the user as 'sir'."
        )) + self._TOOL_GUIDE
        if context:
            system_text += f"\n\nRecent conversation:\n{context}"
        # qwen3 is a reasoning model; /no_think disables its <think> trace, which
        # is faster and stops Seven from speaking its chain-of-thought aloud.
        system_text += "\n\n/no_think"

        messages: List[Any] = [SystemMessage(content=system_text), HumanMessage(content=user_message)]

        for _ in range(self.MAX_ITERS):
            ai = self.llm.invoke(messages)
            messages.append(ai)

            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                content = strip_think(ai.content or "")
                # Recover a tool call the model leaked into the text, if any.
                leaked = self._run_leaked_call(content)
                if leaked is not None:
                    messages.append(HumanMessage(
                        content=f"Tool result:\n{leaked}\n\nNow answer me in one or two short sentences, sir."))
                    continue
                return content or "Done, sir."

            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {}) or {}
                fn = self._dispatch.get(name)
                self._narrate(name)  # speak what we're about to do, in real time
                try:
                    result = fn(**args) if fn else f"Unknown tool: {name}"
                except Exception as e:
                    result = f"Tool {name} failed: {e}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tc.get("id", name)))

        # Hit the iteration cap -- ask for a final answer from whatever tools returned.
        messages.append(HumanMessage(content="Summarise what you found in one or two sentences, sir."))
        try:
            final = self.llm.invoke(messages)
            return strip_think(final.content or "") or "I gathered the information but could not summarise it, sir."
        except Exception:
            return "I gathered the information but had trouble summarising it, sir."
