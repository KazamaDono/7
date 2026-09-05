# Seven — Local Voice AI Assistant

Seven is a private, offline-capable voice assistant that runs on your own Linux
machine. It listens for the wake word **"Seven"**, understands natural language
with a local LLM (via Ollama), and can actually *do things* on your computer:
inspect what's using CPU/memory, run commands, open terminals, run diagnostics,
and report back — out loud, in real time.

No cloud, no account. The language model runs locally through Ollama.

---

## Quick start (fresh machine)

```bash
bash install.sh      # one-time setup: venv, deps, Ollama, model
bash run_seven.sh    # start Seven
```

Then just talk:

- "Seven, what's eating my memory right now?"
- "Seven, run a quick diagnostics check."
- "Seven, open a terminal with htop and then tell me the top processes."
- "Seven, is Firefox running?"
- "Seven, what kernel am I on?"

Say `exit`, `quit`, or `shutdown` to stop.

---

## What Seven can do

| Capability | Example |
|---|---|
| Resource inspection | "what's using the most CPU?" → real, live numbers |
| System status | "how's my system doing?" → CPU, memory, disk, uptime |
| Run any command | "run the command `uptime`" (blocks sudo / destructive ones) |
| "Did you mean?" | unknown command → suggests similar installed commands, asks you |
| Open terminals | "open a terminal running htop" |
| Diagnostics | "run a full diagnostics check" → opens a report terminal |
| Multi-step | "open htop **and** tell me the top memory hogs" → does both |
| Real-time feedback | Seven speaks what it's doing as it does it |
| Conversation | ordinary chat when no action is needed |
| Knowledge | "explain what XSS is", "what is SQL injection" → concise LLM answer |

### Security-research & engineering toolkit

Reliable, deterministic skills (they work regardless of the model's size):

| Skill | Say something like |
|---|---|
| Multi-decoder | "decode `<base64/hex/JWT>`" — auto-detects & decodes, flags `alg:none` JWTs |
| Hash ID | "identify hash `<value>`" — MD5/SHA/bcrypt/NTLM… |
| Hash text | "sha256 of `<text>`" |
| File triage | "analyze the file `<path>`" — type, SHA-256, entropy (packed?), strings |
| Secret scan | "find secrets in `<dir>`" — API keys, private keys, tokens |
| Listeners | "what's listening on my machine" — ports + process + exposed/local |
| Live forensics | "who is my machine talking to" — active external connections |
| Port scan | "scan `<host>`" — TCP connect-scan (authorised targets only) |
| Web recon | "recon `<url>`" — status, server, tech, security headers |
| Host audit | "run a security audit" — exposed ports, SUID, firewall, failed logins |

> Network-reaching skills (port scan, web recon) are for systems you are
> authorised to test.

---

## Requirements

- **Native Linux** (not WSL). Tested on Ubuntu.
- Python 3.10+ with `venv`.
- A microphone and speakers (PipeWire/PulseAudio).
- ~2 GB free disk for the model; 8 GB+ RAM recommended.

---

## Choosing the model (reliability vs. RAM)

Seven uses `qwen3:1.7b` by default — fast and fits ~8 GB RAM, but a small model
sometimes misreads a request. On a machine with more RAM, a bigger model is
noticeably smarter:

```bash
export SEVEN_MODEL=qwen3:4b   # needs ~4 GB free RAM; re-run install.sh to pull it
```

Set it in your `~/.bashrc` to make it permanent.

---

## Audio troubleshooting (important)

Seven follows your **system default microphone**. Choose it in your desktop
Sound settings, or:

```bash
pactl list sources short          # list inputs
pactl set-default-source <name>   # pick one (e.g. your USB mic)
```

**Do NOT** run `export PULSE_SERVER=127.0.0.1` on native Linux. That is a
WSL-only hack; on a normal Linux desktop it points audio at a dead port and
breaks the mic and text-to-speech. If a setup guide told you to add it to
`~/.bashrc`, remove those lines.

If the chosen mic ever fails, Seven automatically falls back to the system
default and keeps listening.

---

## The hologram module (optional)

An optional hand-gesture 3D viewer (webcam + MediaPipe) lives in `hologram/`.
`install.sh` can set it up in its own Python 3.11 environment. Then:

- "Seven, open the hologram"

It needs a webcam. If you skip it, the voice assistant works fully without it.

---

## Safety

- Voice command execution **blocks** privilege escalation (`sudo`, `su`,
  `pkexec`), `rm -rf /`, `mkfs`, `dd` to devices, fork bombs, and
  shutdown/reboot — so a misheard word can't wreck your system.
- Every executed command is logged to `command_execution.log`.

---

## Files

- `main.py` — core: wake word, speech, TTS, routing
- `seven_agent.py` — the agentic brain (LLM + real system tools)
- `seven_plugins.py` — app launch, screenshots, scheduling, etc.
- `run_seven.sh` — launcher
- `install.sh` — this installer
- `hologram/` — optional hand-gesture module
