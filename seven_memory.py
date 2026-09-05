"""
seven_memory.py - Seven's persistent memory of YOU.

A durable, human-style memory: facts about the user, their projects, tools,
preferences, and things they ask Seven to remember. It survives across sessions,
is injected into every LLM prompt so Seven actually *knows* you, and quietly
learns from what you say. This is what turns an assistant into a companion.
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class MemoryStore:
    """Persistent key facts about the user, recalled into context every turn."""

    MAX_FACTS = 200

    def __init__(self, memory_dir: str = "seven_memory"):
        self.dir = Path(memory_dir)
        self.dir.mkdir(exist_ok=True)
        self.path = self.dir / "seven_knows.json"
        self.data = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {"facts": [], "profile": {}}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.data, indent=2))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Explicit memory
    # ------------------------------------------------------------------
    def remember(self, fact: str, kind: str = "note") -> str:
        fact = (fact or "").strip().rstrip(".")
        if not fact:
            return "There was nothing to remember, sir."
        # De-dupe on near-identical text.
        low = fact.lower()
        for f in self.data["facts"]:
            if f["text"].lower() == low:
                return "I've already got that one, sir."
        self.data["facts"].append({
            "text": fact, "kind": kind, "ts": datetime.now().isoformat(),
        })
        self.data["facts"] = self.data["facts"][-self.MAX_FACTS:]
        self._save()
        return f"Got it — I'll remember that: {fact}."

    def forget(self, substring: str) -> str:
        substring = (substring or "").strip().lower()
        if not substring:
            return "What would you like me to forget, sir?"
        before = len(self.data["facts"])
        self.data["facts"] = [f for f in self.data["facts"]
                              if substring not in f["text"].lower()]
        removed = before - len(self.data["facts"])
        self._save()
        if removed:
            return f"Done — I've forgotten {removed} thing(s) about that, sir."
        return "I didn't have anything matching that, sir."

    def set_profile(self, key: str, value: str):
        self.data["profile"][key] = value
        self._save()

    # ------------------------------------------------------------------
    # Task memory: remember a completed task (e.g. a system sweep) so Seven
    # can report back on it later.
    # ------------------------------------------------------------------
    def record_sweep(self, counts: Dict, path: Optional[str], assessment: str):
        self.data["last_sweep"] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "counts": counts,
            "path": path,
            "assessment": (assessment or "").strip(),
        }
        self._save()

    def last_sweep_text(self) -> str:
        ls = self.data.get("last_sweep")
        if not ls:
            return "I haven't run a full system sweep yet, sir. Just say 'scan my PC'."
        c = ls.get("counts", {})
        when = ls.get("ts", "recently").replace("T", " at ")
        head = (f"Your last sweep was {when}: {c.get('critical',0)} critical, "
                f"{c.get('high',0)} high, {c.get('medium',0)} medium findings.")
        assessment = ls.get("assessment", "")
        tail = f"\n\n{assessment}" if assessment else ""
        report = f"\n\nFull report: {ls['path']}" if ls.get("path") else ""
        return head + tail + report

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------
    def all_facts(self) -> List[str]:
        return [f["text"] for f in self.data["facts"]]

    def recall(self, query: Optional[str] = None) -> str:
        """Human-readable recall, optionally filtered by a query term."""
        facts = self.data["facts"]
        prof = self.data["profile"]
        if query:
            q = query.lower()
            facts = [f for f in facts if q in f["text"].lower()]
        if not facts and not prof:
            return ("I don't know much about you yet, sir. Tell me things to remember, "
                    "or just talk and I'll pick them up.")
        lines = []
        if prof.get("name"):
            lines.append(f"Your name is {prof['name']}.")
        for f in facts[-12:]:
            lines.append(f"- {f['text']}")
        return "Here's what I know, sir:\n" + "\n".join(lines)

    def profile_text(self, limit: int = 14) -> str:
        """Compact block injected into the LLM system prompt so Seven speaks with
        knowledge of the user. Returns '' when there's nothing yet."""
        prof = self.data["profile"]
        facts = self.data["facts"][-limit:]
        if not prof and not facts:
            return ""
        parts = []
        if prof.get("name"):
            parts.append(f"The user's name is {prof['name']}.")
        for f in facts:
            parts.append(f["text"])
        return "What you know about the user (use it naturally, don't recite it):\n- " + \
               "\n- ".join(parts)

    # ------------------------------------------------------------------
    # Passive learning: pick up fact-worthy statements from normal speech.
    # ------------------------------------------------------------------
    _LEARN_PATTERNS = [
        (r"\bmy name is\s+([A-Za-z][\w'\-]{1,30})", "name"),
        (r"\bcall me\s+([A-Za-z][\w'\-]{1,30})", "name"),
        (r"\b(i'?m|i am)\s+(?:a|an)\s+([a-z][\w \-]{2,40})", "role"),
        (r"\bi(?:'m| am) working on\s+(.{3,80})", "project"),
        (r"\bmy (?:project|repo|codebase) (?:is |is called |named )\s*(.{2,60})", "project"),
        (r"\bi (?:use|prefer|like)\s+(.{3,60})", "preference"),
        (r"\bi (?:hate|dislike|avoid)\s+(.{3,60})", "dislike"),
        (r"\bi work (?:at|for)\s+(.{2,50})", "work"),
        (r"\bmy (?:goal|aim) is\s+(.{3,80})", "goal"),
    ]

    def learn_from(self, user_text: str) -> Optional[str]:
        """Scan a user message for something worth remembering. Returns a short
        acknowledgement string if it learned something new, else None."""
        text = (user_text or "").strip()
        if len(text) < 6:
            return None
        low = text.lower()
        learned = None
        for pat, kind in self._LEARN_PATTERNS:
            m = re.search(pat, low)
            if not m:
                continue
            value = m.group(m.lastindex).strip().rstrip(".,!?")
            if kind == "name":
                name = value.split()[0].capitalize()
                if self.data["profile"].get("name", "").lower() != name.lower():
                    self.set_profile("name", name)
                    learned = f"Nice to meet you, {name}."
                continue
            # Build a natural fact sentence.
            fact_map = {
                "role": f"The user is {value}",
                "project": f"The user is working on {value}",
                "preference": f"The user uses/prefers {value}",
                "dislike": f"The user dislikes {value}",
                "work": f"The user works at {value}",
                "goal": f"The user's goal is {value}",
            }
            fact = fact_map.get(kind)
            if fact and fact.lower() not in [f["text"].lower() for f in self.data["facts"]]:
                self.remember(fact, kind=kind)
                learned = learned  # stay quiet unless it was the name
        return learned
