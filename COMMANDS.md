# Seven — Full Command & Usage Guide

Everything Seven can do, how to phrase it, and how to get the most out of it.
Seven listens for the wake word **"Seven"** (it also answers to "7", since
speech-to-text often hears it that way). Say *"Seven"* then your request, or fold
it into the sentence: *"Seven, what's eating my memory?"*

- **You don't have to say "Seven" every time.** Once you engage it, Seven stays
  in the conversation for ~30 seconds — just keep talking. After a lull, say
  "Seven" again to re-engage.
- Switch to typing: say **"type"** → keyboard input (the mic is untouched).
- Switch back: type **"voice"**.
- Quit: **"exit"**, **"quit"**, or **"shutdown"**.

---

## 1. Talk to it like a person

Seven is conversational — just talk. It reacts, thinks, and answers naturally.

- "Seven, how's it going?"
- "Explain what XSS is." · "What's the difference between TCP and UDP?"
- "Write me a Python function to reverse a string."
- "I think my box might be compromised — what should I look at?"

Knowledge questions go straight to the LLM with a concise, spoken answer, and it
offers to go deeper ("want me to break down the types?").

---

## 2. Know your machine (live, real data)

- "What's eating my memory?" / "What's using the most CPU?"
- "Give me a full system status report."
- "Is Claude running?" → tells you *and* opens htop focused on it.
- "Is Firefox open?" · "Is Ollama running?"
- "Why is my system slow?" / "What should I close to speed things up?"
- "How much disk space is free?" · "How long have I been up?"

---

## 3. Run things & open terminals

- "Run the command `uptime`." (any shell command; sudo & destructive ones are blocked)
- "What kernel am I on?" · "Who's logged in?"
- "Open a terminal with htop."
- "Open a terminal running `journalctl -f`." (live logs)
- If a command isn't found, Seven suggests close matches and asks which you meant.

---

## 4. Diagnostics

- "Run a quick diagnostics check." → opens a terminal snapshot.
- "Run a full diagnostics check." → adds connectivity, ports, failed services,
  journal errors, sensors, kernel info.

---

## 5. Security-research toolkit 🔐

These are **deterministic** — reliable no matter the model size.

**Crypto / encoding**
- "Decode `<base64 / hex / JWT>`." → auto-detects & decodes; flags `alg:none` JWTs.
- "Identify hash `5f4dcc3b...`." → MD5/SHA/bcrypt/NTLM…
- "SHA-256 of `hunter2`."

**File triage / RE**
- "Analyze the file `/bin/ls`." → type, SHA-256, entropy (packed?), strings.
- "Find secrets in `~/project`." → API keys, private keys, tokens.

**Live network forensics**
- "What's listening on my machine?" → ports + process + **exposed vs local**.
- "Who is my machine talking to?" → live external connections per process.

**Recon** (authorized targets only)
- "Scan `example.com`." → TCP connect-scan of common ports.
- "Recon `https://example.com`." → status, server, tech, security headers.

**Host hardening**
- "Run a security audit." → exposed ports, SUID binaries, firewall, failed logins.

---

## 5a. Full PC sweep + vulnerability assessment 🔎

The big one. Seven does a **high-signal sweep of the whole machine** (processes,
listeners, connections, persistence, SUID, accounts, SSH/firewall posture) in a
few seconds — real data, not guesses — then the **LLM assesses it like a senior
analyst**: overall risk, the top concerns, *why* each is a risk, and how to fix
it. A full report is saved to `~/seven_reports/` and opened for you.

- "Seven, scan my whole PC."
- "Is my system vulnerable?"
- "Run a full system audit and tell me what's at risk."

## 5b. Blue team / threat hunting 🛡️

Seven hunts like a seasoned defender:

- "Is anything suspicious on my system?" / "Am I compromised?" → full threat hunt
  (opens a terminal report + spoken summary).
- "Are there any suspicious processes?" → temp-dir execs, deleted binaries, masquerading.
- "Any suspicious files?" → SUID in odd places, execs in /tmp, modified system binaries.
- "Check my persistence." → cron, systemd, shell rc, SSH keys, rc.local.

## 5c. Memory — Seven remembers you 🧠

- "My name is ___" / "I'm working on ___" → Seven learns it automatically.
- "Remember that I keep my payloads in ~/loot." → stores it forever.
- "What do you know about me?" → recalls everything.
- "Forget ___." → removes it.

It weaves what it knows into how it talks to you, across sessions.

## 5d. Write code & create files 📝

- "Write a Python port scanner and save it to ~/tools/scan.py."
- "Create a bash script that backs up my configs."
- Seven generates the code and writes the file (won't touch protected system paths).

## 6. Multi-step requests

Seven completes every part and narrates as it works:

- "Open htop **and** tell me the top memory processes."
- "Check what's listening **and** who I'm connected to."

---

## 7. The hologram (optional, needs a webcam)

- "Seven, open the hologram." → hand-gesture 3D viewer.

---

## Tips to unlock full potential

- **Be direct.** "Seven, scan example.com" beats a long sentence.
- **Chain actions** with "and" — it handles multi-step.
- **Use text mode** ("type") for long/detailed answers, code, or a quiet room —
  there's no spoken-length limit there.
- **Bigger model = sharper answers.** On 16GB+ RAM:
  `export SEVEN_MODEL=qwen3:4b` (then re-run `install.sh` to pull it).
- **Pick your mic** in your desktop Sound settings, or
  `pactl set-default-source <name>`. Never set `PULSE_SERVER` on native Linux.

---

## Running on Android / Termux

Seven's brain and toolkit run on Termux; **voice input isn't supported there**
(no PulseAudio mic), so it runs in **text mode**, and speaks via Android's TTS.

```bash
pkg update && pkg install python git
pip install -r requirements.txt          # pyaudio/pygame may be skipped; that's fine
pkg install termux-api                    # for spoken replies (termux-tts-speak)
python main.py                            # starts in text mode automatically
```

Point Seven at your existing LLM: if it's Ollama, make sure `ollama` is reachable;
otherwise set `SEVEN_MODEL` to a model your Ollama serves. Seven auto-detects
Termux, skips the mic/pygame, prints replies, and speaks them with `termux-tts-speak`
if `termux-api` is installed. All the system/security tools work as normal.
