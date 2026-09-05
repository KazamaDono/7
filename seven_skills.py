"""
seven_skills.py - Seven's security-research & engineering toolkit.

A suite of DETERMINISTIC compound skills for a hacker / researcher / engineer.
Every skill gathers and correlates real data in code and returns a spoken-ready
string, so results are reliable no matter how small the language model is. Pure
Python where possible (stdlib + psutil), with graceful degradation when an
optional CLI tool is absent.

These are standard defensive/research tools. Network-reaching skills
(scan_ports, http_recon) are for systems you are AUTHORISED to test.
"""

import os
import re
import ssl
import json
import math
import socket
import base64
import codecs
import hashlib
import binascii
import ipaddress
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# Common port -> service, for quick labelling without a scan tool.
_COMMON_PORTS = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios", 143: "imap",
    443: "https", 445: "smb", 993: "imaps", 995: "pop3s", 1433: "mssql",
    1521: "oracle", 2049: "nfs", 3000: "dev-http", 3306: "mysql", 3389: "rdp",
    4444: "metasploit", 5432: "postgres", 5900: "vnc", 5985: "winrm",
    6379: "redis", 8000: "http-alt", 8080: "http-proxy", 8443: "https-alt",
    9200: "elasticsearch", 11211: "memcached", 27017: "mongodb",
}
_DEFAULT_SCAN_PORTS = sorted(_COMMON_PORTS.keys())


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return printable / len(data)


class ResearchSkills:
    """The researcher/engineer toolkit."""

    def __init__(self, executor=None):
        self.executor = executor

    def open_terminal(self, command: str = "") -> str:
        """Open a real terminal window, optionally running a command live. Tries
        common emulators and keeps the window open after the command finishes."""
        command = (command or "").strip()

        def keep_open(inner: str) -> str:
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
                    return f"Opened a terminal running: {command}" if command else "Opened a new terminal."
                except Exception as e:
                    return f"Failed to open terminal ({binary}): {e}"
        return "No terminal emulator found on this system."

    # ==================================================================
    # CRYPTO / ENCODING
    # ==================================================================
    def decode_data(self, text: str) -> str:
        """Auto-detect and decode: JWT, base64, hex, URL-encoding, ROT13.
        The Swiss-army decoder a hacker reaches for a dozen times a day."""
        s = (text or "").strip()
        if not s:
            return "Give me the string to decode, sir."
        results = []

        # JWT: three base64url segments separated by dots.
        if s.count(".") == 2 and re.fullmatch(r"[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*", s):
            try:
                h, p, _ = s.split(".")
                def b64url(x):
                    return base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
                header = json.loads(b64url(h))
                payload = json.loads(b64url(p))
                note = ""
                if header.get("alg") == "none":
                    note = "  [!] alg is 'none' -- signature not verified, a classic JWT bypass."
                return (f"That's a JWT.\nHeader: {json.dumps(header)}\n"
                        f"Payload: {json.dumps(payload)}{note}")
            except Exception:
                pass

        # base64
        try:
            if re.fullmatch(r"[A-Za-z0-9+/=\s]+", s) and len(s.strip()) % 4 == 0:
                raw = base64.b64decode(s, validate=True)
                if _printable_ratio(raw) > 0.85:
                    results.append(f"base64 -> {raw.decode('utf-8', 'replace')}")
        except Exception:
            pass

        # hex
        try:
            hs = re.sub(r"[\s:]", "", s)
            if re.fullmatch(r"(?:[0-9a-fA-F]{2})+", hs):
                raw = bytes.fromhex(hs)
                if _printable_ratio(raw) > 0.85:
                    results.append(f"hex -> {raw.decode('utf-8', 'replace')}")
        except Exception:
            pass

        # URL-encoding
        if "%" in s:
            try:
                from urllib.parse import unquote
                dec = unquote(s)
                if dec != s:
                    results.append(f"url -> {dec}")
            except Exception:
                pass

        # ROT13
        try:
            rot = codecs.decode(s, "rot_13")
            if rot != s and re.search(r"[A-Za-z]", s):
                results.append(f"rot13 -> {rot}")
        except Exception:
            pass

        if not results:
            return f"I couldn't decode that as JWT, base64, hex, URL, or ROT13, sir."
        return "Decoded:\n" + "\n".join(results)

    def identify_hash(self, value: str) -> str:
        """Identify a hash by length and character set."""
        h = (value or "").strip()
        if not h:
            return "Give me the hash to identify, sir."
        if h.startswith("$2a$") or h.startswith("$2b$") or h.startswith("$2y$"):
            return "That looks like a bcrypt hash, sir."
        if h.startswith("$6$"):
            return "That's a SHA-512 crypt hash (Linux /etc/shadow), sir."
        if h.startswith("$5$"):
            return "That's a SHA-256 crypt hash (Linux /etc/shadow), sir."
        if h.startswith("$1$"):
            return "That's an MD5 crypt hash, sir."
        if h.startswith("$argon2"):
            return "That's an Argon2 hash, sir."
        is_hex = bool(re.fullmatch(r"[0-9a-fA-F]+", h))
        by_len = {
            32: "MD5 or NTLM", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256",
            96: "SHA-384", 128: "SHA-512",
        }
        if is_hex and len(h) in by_len:
            return f"That's most likely {by_len[len(h)]} ({len(h)} hex chars), sir."
        if is_hex:
            return f"A hex string of {len(h)} chars -- not a standard hash length, sir."
        return "That doesn't match a hash format I recognise, sir."

    def hash_text(self, text: str, algo: str = "sha256") -> str:
        """Hash a string with the given algorithm."""
        algo = (algo or "sha256").lower().replace("-", "")
        if algo not in hashlib.algorithms_available:
            return f"I don't know the {algo} algorithm, sir."
        digest = hashlib.new(algo, (text or "").encode()).hexdigest()
        return f"{algo} of that text is {digest}, sir."

    # ==================================================================
    # FILE TRIAGE / REVERSE-ENGINEERING
    # ==================================================================
    _MAGIC = [
        (b"\x7fELF", "ELF executable/library (Linux)"),
        (b"MZ", "PE executable (Windows)"),
        (b"\x89PNG", "PNG image"),
        (b"\xff\xd8\xff", "JPEG image"),
        (b"GIF8", "GIF image"),
        (b"%PDF", "PDF document"),
        (b"PK\x03\x04", "ZIP archive (or docx/jar/apk)"),
        (b"\x1f\x8b", "gzip archive"),
        (b"ustar", "tar archive"),
        (b"\xca\xfe\xba\xbe", "Java class / Mach-O fat binary"),
        (b"#!", "script with shebang"),
        (b"\x53\x51\x4c\x69\x74\x65", "SQLite database"),
    ]

    def analyze_file(self, path: str) -> str:
        """Triage a file like a malware analyst: type, size, SHA-256, entropy
        (packed/encrypted?), and a peek at printable strings."""
        p = Path(os.path.expanduser(path or "")).resolve()
        if not p.exists():
            return f"No file at {path}, sir."
        if not p.is_file():
            return f"{path} is not a regular file, sir."
        try:
            data = p.read_bytes()
        except Exception as e:
            return f"Couldn't read {path}: {e}, sir."

        size = len(data)
        sha256 = hashlib.sha256(data).hexdigest()
        head = data[:4096]
        ftype = "unknown / raw data"
        for sig, label in self._MAGIC:
            if data[:len(sig)] == sig or (sig == b"ustar" and data[257:262] == b"ustar"):
                ftype = label
                break
        entropy = _shannon_entropy(data[:65536])
        packed = " -- high entropy, likely packed/encrypted/compressed" if entropy > 7.2 else ""

        # printable strings (min length 4)
        strings = re.findall(rb"[\x20-\x7e]{4,}", head)
        preview = ", ".join(s.decode("ascii", "replace") for s in strings[:6])[:200]

        size_str = f"{size} bytes" if size < 1024 else f"{size/1024:.1f} KB" if size < 1024**2 else f"{size/1024**2:.1f} MB"
        return (f"File: {p.name}\nType: {ftype}\nSize: {size_str}\n"
                f"SHA-256: {sha256}\nEntropy: {entropy:.2f}/8.0{packed}\n"
                f"Strings: {preview or '(none printable)'}")

    def find_secrets(self, path: str, max_files: int = 400) -> str:
        """Scan a directory tree for hardcoded secrets -- keys, tokens, passwords.
        Invaluable before pushing code or when auditing a target's source."""
        root = Path(os.path.expanduser(path or ".")).resolve()
        if not root.exists():
            return f"No such path: {path}, sir."

        patterns = {
            "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "AWS secret": re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}"),
            "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
            "Generic API key": re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
            "Password assignment": re.compile(r"(?i)password\s*[=:]\s*['\"][^'\"]{4,}['\"]"),
            "Slack token": re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
            "Google API key": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
            "JWT": re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"),
            "Private IP + creds URL": re.compile(r"[a-z]+://[^:@\s]+:[^@\s]+@"),
        }
        skip_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", "voice_env", "dist", "build"}
        text_ext = {".py", ".js", ".ts", ".env", ".json", ".yml", ".yaml", ".txt", ".sh",
                    ".conf", ".cfg", ".ini", ".xml", ".php", ".rb", ".go", ".java", ".c", ".cpp", ".md", ""}

        hits, scanned = [], 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fn in filenames:
                if scanned >= max_files:
                    break
                fp = Path(dirpath) / fn
                if fp.suffix.lower() not in text_ext:
                    continue
                try:
                    if fp.stat().st_size > 2_000_000:
                        continue
                    content = fp.read_text(errors="ignore")
                except Exception:
                    continue
                scanned += 1
                for label, pat in patterns.items():
                    for m in pat.finditer(content):
                        line = content[:m.start()].count("\n") + 1
                        rel = fp.relative_to(root)
                        hits.append(f"{label} in {rel}:{line}")
        if not hits:
            return f"Scanned {scanned} files under {root.name} -- no obvious secrets, sir."
        shown = "\n".join(f"  [!] {h}" for h in hits[:15])
        more = f"\n  ...and {len(hits)-15} more" if len(hits) > 15 else ""
        return f"Found {len(hits)} potential secret(s) in {scanned} files, sir:\n{shown}{more}"

    # ==================================================================
    # LIVE NETWORK FORENSICS
    # ==================================================================
    def listening_ports(self) -> str:
        """What is listening on this host, which process owns it, and whether it
        is exposed to the network (0.0.0.0/::) or bound to localhost only."""
        if not HAS_PSUTIL:
            return "psutil is not available, sir."
        rows, exposed = [], 0
        try:
            conns = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            return "I need elevated permissions to read all sockets, sir."
        for c in conns:
            if c.status != psutil.CONN_LISTEN or not c.laddr:
                continue
            ip, port = c.laddr.ip, c.laddr.port
            pname = ""
            if c.pid:
                try:
                    pname = psutil.Process(c.pid).name()
                except Exception:
                    pass
            is_exposed = ip in ("0.0.0.0", "::", "*")
            if is_exposed:
                exposed += 1
            tag = "EXPOSED" if is_exposed else "local"
            svc = _COMMON_PORTS.get(port, "")
            rows.append((port, f"  {ip}:{port} [{tag}] {pname} {('('+svc+')') if svc else ''}".rstrip()))
        if not rows:
            return "Nothing is listening on this host, sir."
        rows.sort()
        body = "\n".join(r[1] for r in rows[:25])
        head = f"{len(rows)} listening port(s), {exposed} exposed to the network, sir:\n"
        return head + body

    def active_connections(self) -> str:
        """Who is this machine talking to right now -- established outbound/inbound
        connections correlated with the owning process and remote host. Great for
        spotting exfiltration or unexpected callbacks."""
        if not HAS_PSUTIL:
            return "psutil is not available, sir."
        try:
            conns = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            return "I need elevated permissions to read all sockets, sir."
        by_remote = {}
        for c in conns:
            if c.status != psutil.CONN_ESTABLISHED or not c.raddr:
                continue
            try:
                ip = c.raddr.ip
                if ipaddress.ip_address(ip).is_loopback:
                    continue
            except Exception:
                continue
            pname = ""
            if c.pid:
                try:
                    pname = psutil.Process(c.pid).name()
                except Exception:
                    pass
            key = (pname or "?", ip, c.raddr.port)
            by_remote[key] = by_remote.get(key, 0) + 1
        if not by_remote:
            return "No active external connections right now, sir."
        rows = sorted(by_remote.items(), key=lambda kv: kv[0][0])
        body = "\n".join(f"  {pname} -> {ip}:{port}" + (f" x{n}" if n > 1 else "")
                         for (pname, ip, port), n in rows[:20])
        return f"{len(rows)} external connection(s) right now, sir:\n{body}"

    # ==================================================================
    # RECON (authorised targets only)
    # ==================================================================
    def scan_ports(self, host: str, ports: Optional[List[int]] = None) -> str:
        """Fast pure-Python TCP connect scan of common ports on a host you are
        authorised to test. No external tools required."""
        host = (host or "").strip()
        if not host:
            return "Which host should I scan, sir?"
        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            return f"I couldn't resolve {host}, sir."
        targets = ports or _DEFAULT_SCAN_PORTS

        def probe(port):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.7)
            try:
                if s.connect_ex((ip, port)) == 0:
                    return port
            except Exception:
                return None
            finally:
                s.close()
            return None

        open_ports = []
        with ThreadPoolExecutor(max_workers=64) as ex:
            for fut in as_completed([ex.submit(probe, p) for p in targets]):
                r = fut.result()
                if r:
                    open_ports.append(r)
        if not open_ports:
            return f"{host} ({ip}): no common ports open, sir."
        open_ports.sort()
        listing = ", ".join(f"{p} ({_COMMON_PORTS.get(p,'?')})" for p in open_ports)
        return f"{host} ({ip}) has {len(open_ports)} open port(s), sir: {listing}"

    def http_recon(self, url: str) -> str:
        """Fetch a URL and report status, server, detected tech, and the state of
        the important security headers -- fast web recon."""
        import urllib.request
        url = (url or "").strip()
        if not url:
            return "Which URL should I check, sir?"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "Seven-Recon/1.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=8, context=ctx)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            status = resp.status
            body = resp.read(4096).decode("utf-8", "replace")
        except Exception as e:
            return f"Couldn't reach {url}: {e}, sir."

        server = headers.get("server", "unknown")
        powered = headers.get("x-powered-by", "")
        sec = {
            "Content-Security-Policy": "content-security-policy" in headers,
            "Strict-Transport-Security": "strict-transport-security" in headers,
            "X-Frame-Options": "x-frame-options" in headers,
            "X-Content-Type-Options": "x-content-type-options" in headers,
        }
        missing = [name for name, present in sec.items() if not present]
        tech = []
        if "wordpress" in body.lower() or "wp-content" in body.lower():
            tech.append("WordPress")
        if powered:
            tech.append(powered)
        if "cf-ray" in headers:
            tech.append("Cloudflare")
        tech_str = f" Tech: {', '.join(tech)}." if tech else ""
        miss_str = (" Missing security headers: " + ", ".join(missing) + ".") if missing else \
                   " All key security headers present."
        return (f"{url} -> HTTP {status}, server: {server}.{tech_str}{miss_str}")

    # ==================================================================
    # HOST SECURITY POSTURE (correlated)
    # ==================================================================
    def security_audit(self) -> str:
        """Correlate several signals into one host-hardening report: exposed
        listeners, SUID binaries, world-writable sensitive files, failed logins,
        and firewall state."""
        findings = []

        # Exposed listeners
        exposed = 0
        if HAS_PSUTIL:
            try:
                for c in psutil.net_connections(kind="inet"):
                    if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.ip in ("0.0.0.0", "::"):
                        exposed += 1
            except Exception:
                pass
        findings.append(f"{exposed} network-exposed listening port(s)")

        # SUID binaries (limited scan)
        suid = self._count_cmd(r"find /usr/bin /usr/sbin /bin -perm -4000 -type f 2>/dev/null")
        if suid is not None:
            findings.append(f"{suid} SUID binaries in standard bin dirs")

        # World-writable files in sensitive dirs
        ww = self._count_cmd(r"find /etc -perm -0002 -type f 2>/dev/null")
        if ww is not None and ww > 0:
            findings.append(f"[!] {ww} world-writable file(s) under /etc")

        # Firewall
        fw = "unknown"
        try:
            r = subprocess.run("command -v ufw >/dev/null && ufw status 2>/dev/null | head -1",
                               shell=True, capture_output=True, text=True, timeout=5)
            if "active" in r.stdout.lower():
                fw = "ufw active"
            elif "inactive" in r.stdout.lower():
                fw = "[!] ufw inactive"
            else:
                r2 = subprocess.run("command -v nft >/dev/null && nft list ruleset 2>/dev/null | head -1",
                                    shell=True, capture_output=True, text=True, timeout=5)
                fw = "nftables rules present" if r2.stdout.strip() else "no obvious firewall"
        except Exception:
            pass
        findings.append(f"firewall: {fw}")

        # Recent failed logins
        try:
            r = subprocess.run("(lastb 2>/dev/null || journalctl -q _COMM=sshd 2>/dev/null | grep -i 'failed') | wc -l",
                               shell=True, capture_output=True, text=True, timeout=5)
            n = int((r.stdout or "0").strip() or 0)
            if n:
                findings.append(f"{n} recent failed login attempt(s)")
        except Exception:
            pass

        return "Security audit, sir:\n" + "\n".join(f"  - {f}" for f in findings)

    def _count_cmd(self, cmd: str) -> Optional[int]:
        try:
            r = subprocess.run(cmd + " | wc -l", shell=True, capture_output=True, text=True, timeout=10)
            return int((r.stdout or "0").strip() or 0)
        except Exception:
            return None

    # ==================================================================
    # BLUE TEAM / THREAT HUNTING  (seasoned defender skills)
    # ==================================================================
    _SUSPECT_DIRS = ("/tmp/", "/dev/shm/", "/var/tmp/", "/run/user/", "/home/")

    def suspicious_processes(self) -> str:
        """Hunt for processes that a defender would flag: running from world-
        writable/temp dirs, executing a deleted binary, masquerading under a
        fake name, or an interpreter with a network connection."""
        if not HAS_PSUTIL:
            return "psutil is not available, sir."
        flags = []
        # PIDs that own an established/listening socket (for correlation).
        net_pids = set()
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid and c.status in (psutil.CONN_ESTABLISHED, psutil.CONN_LISTEN):
                    net_pids.add(c.pid)
        except Exception:
            pass

        for p in psutil.process_iter(["pid", "name", "username"]):
            try:
                exe = ""
                try:
                    exe = p.exe()
                except (psutil.AccessDenied, psutil.ZombieProcess, FileNotFoundError):
                    exe = ""
                name = p.info["name"] or "?"

                # Deleted-on-disk binary still running -- classic malware sign.
                if exe.endswith(" (deleted)"):
                    flags.append(f"[!] {name} (pid {p.info['pid']}) runs a DELETED binary: {exe}")
                    continue
                if exe:
                    # Executing from a temp / world-writable location.
                    if exe.startswith(("/tmp/", "/dev/shm/", "/var/tmp/", "/run/")):
                        net = " + network" if p.info["pid"] in net_pids else ""
                        flags.append(f"[!] {name} (pid {p.info['pid']}) runs from a temp dir: {exe}{net}")
                        continue
                    # Name masquerading (process name != binary basename).
                    base = os.path.basename(exe)
                    if base and name and base != name and name not in base and base not in name \
                       and not name.startswith("(") and len(name) > 2:
                        flags.append(f"[?] {name} (pid {p.info['pid']}) may be masquerading (binary is {base})")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if not flags:
            return "I hunted the process table and nothing jumped out as suspicious, sir."
        shown = "\n".join(flags[:15])
        more = f"\n  ...and {len(flags)-15} more" if len(flags) > 15 else ""
        return f"Process hunt, sir -- {len(flags)} thing(s) worth a look:\n{shown}{more}"

    def suspicious_files(self) -> str:
        """Look for the file-system tells of compromise: SUID binaries in odd
        places, executables in temp dirs, recently-modified system binaries, and
        world-writable files under /etc."""
        checks = [
            ("SUID binaries outside standard dirs",
             r"find / -perm -4000 -type f 2>/dev/null | grep -vE '^/(usr/)?(bin|sbin|lib|libexec)/' | head -20"),
            ("Executables in temp dirs",
             r"find /tmp /dev/shm /var/tmp -type f -executable 2>/dev/null | head -20"),
            ("System binaries modified in last 2 days",
             r"find /usr/bin /usr/sbin /bin /sbin -type f -mtime -2 2>/dev/null | head -20"),
            ("World-writable files under /etc",
             r"find /etc -perm -0002 -type f 2>/dev/null | head -20"),
            ("Hidden files in temp dirs",
             r"find /tmp /dev/shm -name '.*' -type f 2>/dev/null | head -20"),
        ]
        blocks = []
        for label, cmd in checks:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
                out = (r.stdout or "").strip()
            except Exception:
                out = ""
            if out:
                lines = out.splitlines()
                tag = "[!]" if label != "System binaries modified in last 2 days" else "[?]"
                blocks.append(f"{tag} {label} ({len(lines)}):\n" +
                              "\n".join("    " + l for l in lines[:8]))
        if not blocks:
            return "File-system hunt came back clean, sir -- nothing obviously out of place."
        return "File hunt, sir:\n" + "\n".join(blocks)

    def check_persistence(self) -> str:
        """Check the usual persistence footholds a defender reviews: cron, systemd,
        shell rc files, SSH authorized_keys, and rc.local."""
        report = []
        cmds = [
            ("User cron jobs", "crontab -l 2>/dev/null | grep -vE '^\\s*#' | head -10"),
            ("System cron.d / cron dirs", "ls -1 /etc/cron.d /etc/cron.hourly /etc/cron.daily 2>/dev/null | head -20"),
            ("Recently changed systemd units", "find /etc/systemd/system ~/.config/systemd -name '*.service' -mtime -14 2>/dev/null | head -10"),
            ("SSH authorized_keys", "for f in ~/.ssh/authorized_keys /root/.ssh/authorized_keys; do [ -f \"$f\" ] && echo \"$f: $(wc -l < \"$f\") key(s)\"; done 2>/dev/null"),
            ("rc.local", "[ -s /etc/rc.local ] && echo 'present and non-empty' || echo 'none'"),
            ("Shell rc tails (.bashrc/.profile)", "tail -n 3 ~/.bashrc 2>/dev/null"),
        ]
        for label, cmd in cmds:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                out = (r.stdout or "").strip()
            except Exception:
                out = ""
            if out:
                report.append(f"- {label}:\n" + "\n".join("    " + l for l in out.splitlines()[:6]))
        if not report:
            return "No obvious persistence entries found, sir."
        return "Persistence review, sir:\n" + "\n".join(report)

    def threat_hunt(self) -> str:
        """Full defensive sweep: correlate process, file, network, and persistence
        signals into one seasoned blue-team report, and open it in a terminal so
        you can read the detail."""
        sections = [
            "===== SEVEN THREAT HUNT =====",
            "date; echo",
            "echo '--- Suspicious processes (temp dirs / deleted binaries) ---'",
            "ps -eo pid,user,comm,args | grep -iE '/tmp/|/dev/shm/|/var/tmp/' | grep -v grep | head",
            "echo; echo '--- Deleted-binary processes ---'",
            "ls -l /proc/*/exe 2>/dev/null | grep -i deleted | head",
            "echo; echo '--- Listening services ---'",
            "(ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null) | head -25",
            "echo; echo '--- Established external connections ---'",
            "(ss -tunp state established 2>/dev/null || netstat -tunp 2>/dev/null | grep ESTAB) | head -25",
            "echo; echo '--- SUID outside standard dirs ---'",
            "find / -perm -4000 -type f 2>/dev/null | grep -vE '^/(usr/)?(bin|sbin|lib|libexec)/' | head",
            "echo; echo '--- Executables in temp ---'",
            "find /tmp /dev/shm /var/tmp -type f -executable 2>/dev/null | head",
            "echo; echo '--- Recent auth failures ---'",
            "(journalctl -q _COMM=sshd 2>/dev/null | grep -i 'failed' | tail -10) || (grep -i 'failed password' /var/log/auth.log 2>/dev/null | tail -10)",
            "echo; echo '--- User cron ---'",
            "crontab -l 2>/dev/null | grep -vE '^\\s*#'",
            "echo; echo '===== hunt complete ====='",
        ]
        script = " ; ".join(sections)
        opened = self.open_terminal(script)

        # Also return a spoken summary from the pure-python hunts.
        quick = []
        sp = self.suspicious_processes()
        if "nothing jumped out" not in sp:
            quick.append(sp.splitlines()[0])
        if opened.startswith("Opened"):
            head = "I'm running a full threat hunt in a new terminal, sir."
        else:
            head = "I ran a threat hunt, sir."
        return head + ((" " + " ".join(quick)) if quick else " Nothing screamed compromise on the quick pass.")

    # ==================================================================
    # ENGINEERING: create files / write code
    # ==================================================================
    def write_file(self, path: str, content: str) -> str:
        """Write content (code, config, notes) to a file, creating directories as
        needed. Refuses to clobber sensitive system files."""
        if not path:
            return "Where should I write it, sir?"
        target = Path(os.path.expanduser(path)).resolve()
        # Guardrail: don't let a spoken command overwrite critical system files.
        protected = ("/etc/", "/boot/", "/usr/", "/bin/", "/sbin/", "/lib", "/sys/", "/proc/")
        if str(target).startswith(protected):
            return f"I won't write into a protected system path ({target}), sir. Pick a spot in your home or a project folder."
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            target.write_text(content if content is not None else "")
            verb = "Updated" if existed else "Created"
            lines = (content or "").count("\n") + 1
            return f"{verb} {target} ({lines} line(s)), sir."
        except Exception as e:
            return f"Couldn't write {path}: {e}, sir."

    # ==================================================================
    # FULL SYSTEM SWEEP  (high-signal collection, parallelised)
    # ==================================================================
    def _sh(self, cmd: str, timeout: int = 45) -> List[str]:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return [l for l in (r.stdout or "").splitlines() if l.strip()]
        except Exception:
            return []

    def _collect_processes(self) -> List[Dict]:
        """Full process inventory with per-process risk flags."""
        out = []
        if not HAS_PSUTIL:
            return out
        net_pids = set()
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid and c.status in (psutil.CONN_ESTABLISHED, psutil.CONN_LISTEN):
                    net_pids.add(c.pid)
        except Exception:
            pass
        for p in psutil.process_iter(["pid", "name", "username"]):
            try:
                exe = ""
                try:
                    exe = p.exe()
                except Exception:
                    exe = ""
                name = p.info["name"] or "?"
                pid = p.info["pid"]
                user = p.info.get("username") or "?"
                sev, why = "info", None
                if exe.endswith(" (deleted)"):
                    sev, why = "critical", "running a binary deleted from disk"
                elif exe.startswith(("/tmp/", "/dev/shm/", "/var/tmp/", "/run/")):
                    sev, why = "high", f"executing from a world-writable temp dir ({exe})"
                    if pid in net_pids:
                        sev, why = "critical", f"executing from temp dir AND holding a network socket ({exe})"
                elif exe:
                    base = os.path.basename(exe)
                    if base and name and base != name and name not in base and base not in name \
                       and not name.startswith("(") and len(name) > 2:
                        sev, why = "medium", f"process name '{name}' differs from binary '{base}' (possible masquerade)"
                if why:
                    out.append({"sev": sev, "text": f"{name} (pid {pid}, {user}): {why}"})
            except Exception:
                continue
        return out

    def collect_system_intel(self) -> Dict[str, List[Dict]]:
        """Run every collector in parallel and return findings grouped by area.
        Each finding is {sev, text}; sev in critical/high/medium/info."""
        intel: Dict[str, List[Dict]] = {}

        def wrap(sev, lines, cap=30):
            return [{"sev": sev, "text": l} for l in lines[:cap]]

        # Deterministic shell collectors -> (area, severity, command)
        shell_jobs = {
            # System dirs + malware drop locations (temp/opt/var). /home is excluded
            # on purpose: a SUID-root binary there needs prior root anyway, and
            # walking huge project trees would make the sweep crawl. Anything
            # actually running from /home is caught by the process collector.
            "SUID (non-standard dirs)": ("high",
                r"find /usr /bin /sbin /lib /lib64 /opt /var /tmp /dev/shm /srv /etc /run "
                r"-xdev -perm -4000 -type f 2>/dev/null | grep -vE '^/(usr/)?(bin|sbin|lib|libexec)/'"),
            "Executables in temp": ("high",
                r"find /tmp /dev/shm /var/tmp -type f -executable 2>/dev/null"),
            "World-writable under /etc": ("high",
                r"find /etc -perm -0002 -type f 2>/dev/null"),
            "System binaries modified <3 days": ("medium",
                r"find /usr/bin /usr/sbin /bin /sbin -type f -mtime -3 2>/dev/null"),
            "Hidden files in temp": ("medium",
                r"find /tmp /dev/shm -name '.*' -type f 2>/dev/null"),
            "UID 0 accounts (besides root)": ("critical",
                r"awk -F: '($3==0)&&($1!=\"root\"){print $1}' /etc/passwd"),
            "Accounts with empty password": ("critical",
                r"awk -F: '($2==\"\"){print $1}' /etc/shadow 2>/dev/null"),
            "Login shells": ("info",
                r"awk -F: '($7 ~ /(bash|zsh|sh)$/){print $1\" -> \"$7}' /etc/passwd"),
            "Sudoers (NOPASSWD)": ("high",
                r"grep -rEh 'NOPASSWD' /etc/sudoers /etc/sudoers.d/ 2>/dev/null"),
            "User cron": ("medium", r"crontab -l 2>/dev/null | grep -vE '^\s*#'"),
            "Recently changed systemd units (<14d)": ("medium",
                r"find /etc/systemd/system ~/.config/systemd -name '*.service' -mtime -14 2>/dev/null"),
            "SSH authorized_keys": ("medium",
                r"for f in ~/.ssh/authorized_keys /root/.ssh/authorized_keys; do [ -f \"$f\" ] && echo \"$f: $(wc -l < \"$f\") key(s)\"; done 2>/dev/null"),
            "SSH risky config": ("high",
                r"grep -Ei '^(PermitRootLogin|PasswordAuthentication|PermitEmptyPasswords)' /etc/ssh/sshd_config 2>/dev/null"),
            "Recent auth failures": ("medium",
                r"(journalctl -q _COMM=sshd 2>/dev/null | grep -i failed | tail -15) || (grep -i 'failed password' /var/log/auth.log 2>/dev/null | tail -15)"),
        }

        def run_shell(area, sev, cmd):
            return area, wrap(sev, self._sh(cmd))

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(run_shell, a, s, c) for a, (s, c) in shell_jobs.items()]
            futures.append(ex.submit(lambda: ("Suspicious processes", self._collect_processes())))
            # network + firewall via the existing skills (already deterministic)
            futures.append(ex.submit(lambda: ("Listening ports", wrap("info", self.listening_ports().splitlines()[1:], 40))))
            futures.append(ex.submit(lambda: ("External connections", wrap("info", self.active_connections().splitlines()[1:], 40))))
            for fut in as_completed(futures):
                try:
                    area, findings = fut.result()
                    if findings:
                        intel[area] = findings
                except Exception:
                    continue

        # Exposed listeners are a real risk -> upgrade severity for exposed ones.
        exposed = [f for f in intel.get("Listening ports", []) if "EXPOSED" in f["text"]]
        if exposed:
            intel["Exposed services"] = [{"sev": "high", "text": f["text"].strip()} for f in exposed[:20]]

        return intel

    def full_sweep(self, save_dir: str = "~/seven_reports", open_report: bool = True) -> Dict:
        """Run the full sweep, build a prioritised report, save it, and (optionally)
        open it in a terminal. Returns {report, path, counts, flagged} for the caller
        (which may hand `flagged` to the LLM for an analyst assessment)."""
        intel = self.collect_system_intel()

        order = {"critical": 0, "high": 1, "medium": 2, "info": 3}
        counts = {"critical": 0, "high": 0, "medium": 0, "info": 0}
        flagged = []  # non-info findings, for the LLM
        lines = [f"SEVEN FULL SYSTEM SWEEP  -  {datetime.now().isoformat(timespec='seconds')}", "=" * 60, ""]

        for area in sorted(intel.keys()):
            findings = sorted(intel[area], key=lambda f: order.get(f["sev"], 9))
            lines.append(f"### {area} ({len(findings)})")
            for f in findings:
                counts[f["sev"]] = counts.get(f["sev"], 0) + 1
                tag = f["sev"].upper()
                lines.append(f"  [{tag}] {f['text']}")
                if f["sev"] != "info":
                    flagged.append(f"[{tag}] {area}: {f['text']}")
            lines.append("")

        lines.append("=" * 60)
        lines.append(f"Totals -- critical: {counts['critical']}, high: {counts['high']}, "
                     f"medium: {counts['medium']}, info: {counts['info']}")
        report = "\n".join(lines)

        # Save to a timestamped file.
        path = None
        try:
            d = Path(os.path.expanduser(save_dir))
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"sweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            path.write_text(report)
        except Exception:
            path = None

        if open_report and path:
            self.open_terminal(f"less -R '{path}'")

        return {"report": report, "path": str(path) if path else None,
                "counts": counts, "flagged": flagged}

    def live_sweep_script(self) -> str:
        """Shell script for a LIVE, watch-it-happen sweep in a terminal window --
        each section prints as it runs so the user sees everything in real time."""
        sections = [
            r"printf '\033[1;33m===== SEVEN · FULL SYSTEM SWEEP =====\033[0m\n'",
            r"date; echo",
            r"printf '\033[1;36m[1/9] Suspicious processes (temp dirs / deleted binaries)\033[0m\n'",
            r"ps -eo pid,user,comm,args | grep -iE '/tmp/|/dev/shm/|/var/tmp/' | grep -v grep | head; "
            r"ls -l /proc/*/exe 2>/dev/null | grep -i deleted | head; echo",
            r"printf '\033[1;36m[2/9] Listening services\033[0m\n'",
            r"(ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null) | head -30; echo",
            r"printf '\033[1;36m[3/9] Established external connections\033[0m\n'",
            r"(ss -tunp state established 2>/dev/null || netstat -tunp 2>/dev/null | grep ESTAB) | head -30; echo",
            r"printf '\033[1;36m[4/9] SUID binaries outside standard dirs\033[0m\n'",
            r"find /usr /bin /sbin /lib /lib64 /opt /var /tmp /dev/shm /srv /etc /run -xdev -perm -4000 -type f 2>/dev/null | grep -vE '^/(usr/)?(bin|sbin|lib|libexec)/' | head; echo",
            r"printf '\033[1;36m[5/9] Executables in temp dirs\033[0m\n'",
            r"find /tmp /dev/shm /var/tmp -type f -executable 2>/dev/null | head; echo",
            r"printf '\033[1;36m[6/9] Persistence: cron & recent systemd units\033[0m\n'",
            r"crontab -l 2>/dev/null | grep -vE '^\s*#'; find /etc/systemd/system ~/.config/systemd -name '*.service' -mtime -14 2>/dev/null | head; echo",
            r"printf '\033[1;36m[7/9] Accounts: UID 0 & login shells\033[0m\n'",
            r"awk -F: '($3==0){print $1\" (uid 0)\"}' /etc/passwd; awk -F: '($7 ~ /(bash|zsh|sh)$/){print $1\" -> \"$7}' /etc/passwd | head; echo",
            r"printf '\033[1;36m[8/9] SSH & firewall posture\033[0m\n'",
            r"grep -Ei '^(PermitRootLogin|PasswordAuthentication|PermitEmptyPasswords)' /etc/ssh/sshd_config 2>/dev/null; (command -v ufw >/dev/null && ufw status 2>/dev/null | head -1) || echo 'ufw: not found'; echo",
            r"printf '\033[1;36m[9/9] Recent authentication failures\033[0m\n'",
            r"(journalctl -q _COMM=sshd 2>/dev/null | grep -i failed | tail -10) || (grep -i 'failed password' /var/log/auth.log 2>/dev/null | tail -10); echo",
            r"printf '\033[1;32m===== SCAN COMPLETE · Seven is assessing the findings =====\033[0m\n'",
        ]
        return " ; ".join(sections)

    def open_live_sweep(self) -> bool:
        """Open a terminal running the live sweep. Returns True if a window opened."""
        return self.open_terminal(self.live_sweep_script()).startswith("Opened")

    def system_sweep(self) -> str:
        """Agent-facing full sweep: runs the collection, saves+opens the report,
        and returns the flagged findings so the model can assess them. Use for
        'scan my whole PC', 'is my system vulnerable', 'full security sweep'."""
        r = self.full_sweep(open_report=True)
        c = r["counts"]
        head = (f"Full sweep complete: {c['critical']} critical, {c['high']} high, "
                f"{c['medium']} medium findings. Report saved to {r['path']}.")
        if not r["flagged"]:
            return head + " Nothing serious stood out."
        return head + "\nFlagged findings (assess these):\n" + "\n".join(r["flagged"][:40])
