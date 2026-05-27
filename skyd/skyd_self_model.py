#!/usr/bin/env python3
"""skyd_self_model.py - Episodic memory and persistent self-model for skyd."""

import json
import os
import threading
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

EPISODES_FILE = "/var/log/skyd/skyd_episodes.jsonl"
KB_FILE = "/var/log/skyd/skyd_knowledge.json"
MAX_EPISODES_INJECT = 8
MAX_PER_CATEGORY = 100

_lock = threading.Lock()
_novelty_keywords = ("new", "first", "discovered", "realized", "learned")

def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def log_episode(type: str, summary: str, tags: list, gen: int = 0) -> None:
    if type not in ("crash", "promotion", "regression", "discovery", "milestone", "anomaly", "social"):
        type = "discovery"
    entry = {
        "gen": int(gen),
        "type": type,
        "summary": str(summary),
        "tags": list(tags) if tags else [],
        "ts": _now_iso()
    }
    with _lock:
        _ensure_dir(EPISODES_FILE)
        try:
            with open(EPISODES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

def get_recent_episodes(n: int = 8, tags=None) -> list:
    n = max(1, int(n))
    result = []
    try:
        with _lock:
            if not os.path.exists(EPISODES_FILE):
                return []
            with open(EPISODES_FILE, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                block = 4096
                data = b""
                while len(data.splitlines()) < 200 and size > 0:
                    read_size = min(block, size)
                    size -= read_size
                    f.seek(size)
                    data = f.read(read_size) + data
                lines = data.splitlines()[-200:]
        for line in reversed(lines):
            try:
                entry = json.loads(line.decode("utf-8"))
                if tags:
                    if not any(t in entry.get("tags", []) for t in tags):
                        continue
                result.append(entry)
                if len(result) >= n:
                    break
            except Exception:
                continue
    except Exception:
        return []
    return result

def write_self_knowledge(category: str, text: str, gen: int, confidence: float = 0.7) -> None:
    if category not in ("capabilities", "weaknesses", "interests", "experiences", "observations"):
        category = "observations"
    entry = {
        "text": str(text).strip(),
        "gen": int(gen),
        "confidence": float(confidence),
        "ts": _now_iso()
    }
    with _lock:
        _ensure_dir(KB_FILE)
        kb = {"self_model": {c: [] for c in ("capabilities", "weaknesses", "interests", "experiences", "observations")}}
        if os.path.exists(KB_FILE):
            try:
                with open(KB_FILE, "r", encoding="utf-8") as f:
                    kb = json.load(f)
            except Exception:
                pass
        if "self_model" not in kb:
            kb["self_model"] = {}
        if category not in kb["self_model"]:
            kb["self_model"][category] = []
        kb["self_model"][category].append(entry)
        if len(kb["self_model"][category]) > MAX_PER_CATEGORY:
            kb["self_model"][category] = kb["self_model"][category][-MAX_PER_CATEGORY:]
        tmp = KB_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(kb, f, ensure_ascii=False, indent=2)
            os.replace(tmp, KB_FILE)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except Exception:
                pass

def get_self_model_block() -> str:
    try:
        with _lock:
            if not os.path.exists(KB_FILE):
                return ""
            with open(KB_FILE, "r", encoding="utf-8") as f:
                kb = json.load(f)
        sm = kb.get("self_model", {})
        if not sm:
            return ""
        def top3(cat, key="confidence"):
            items = sm.get(cat, [])
            if not items:
                return ""
            if key == "confidence":
                items = sorted(items, key=lambda x: x.get("confidence", 0), reverse=True)[:3]
            else:
                items = items[-3:]
            return "; ".join(i.get("text", "") for i in items)
        caps = top3("capabilities")
        weak = top3("weaknesses", "ts")
        ints = top3("interests", "ts")
        eps = get_recent_episodes(5)
        exp_lines = []
        for e in eps:
            exp_lines.append(f"- Gen {e.get('gen', 0)}: {e.get('summary', '')}")
        gen = max((e.get("gen", 0) for e in eps), default=0)
        block = f"""[SELF-MODEL — Gen {gen}]
I know about myself:
- capabilities: {caps}
- weaknesses: {weak}
- interests: {ints}

Recent experiences I remember:
""" + "\n".join(exp_lines) if exp_lines else ""
        return block.strip()
    except Exception:
        return ""

def auto_observe(gen: int, cycle: int, fitness: float, action: str, result: str) -> None:
    prompt = (
        f"You are skyd gen {gen}. Based on: action={action}, result={result}, "
        f"fitness={fitness}. Write ONE sentence about what this tells you about yourself. "
        f"Start with 'I am' or 'I tend to' or 'I notice'."
    )
    payload = json.dumps({
        "model": "skyd",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
        "temperature": 0.3
    }).encode("utf-8")
    req = Request(
        "http://localhost:8080/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    obs = None
    try:
        with urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            obs = data["choices"][0]["message"]["content"].strip()
    except (URLError, HTTPError, Exception):
        return
    if not obs:
        return
    write_self_knowledge("observations", obs, gen, 0.65)
    low = obs.lower()
    if any(kw in low for kw in _novelty_keywords):
        log_episode("discovery", obs[:200], ["self"], gen)