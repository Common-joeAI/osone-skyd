import os
#!/usr/bin/env python3
"""
skyd Evolution Engine - v0.4
Self-writing, self-compiling, self-improving AI core
Capabilities:
  - Write and compile C/ASM kernel modules
  - Benchmark and A/B test new code vs old
  - Define custom DSL (SkyLang) for system ops
  - Replace itself with better versions
"""

import subprocess, requests, json, time, logging, os, sys, psutil
import urllib.request, urllib.parse, hashlib, tempfile, stat
from datetime import datetime

LLAMA_URL  = os.environ.get("LLAMA_URL", "http://127.0.0.1:8080") + "/v1/chat/completions"
MODEL       = "llama3.2"
LOG_FILE    = "/var/log/skyd.log"
STATE_FILE  = "/var/log/skyd_state.json"
KNOWLEDGE   = "/var/log/skyd_knowledge.json"
EVOLUTION   = "/var/log/skyd_evolution.json"
SELF_PATH   = "/usr/local/bin/skyd.py"
ASM_DIR     = "/usr/local/skyd/asm"
LANG_DIR    = "/usr/local/skyd/lang"
LOOP_INTERVAL = 20

# ── HIVE CONFIG ──────────────────────────────────────────────────
HIVE_COMMANDER_URL = os.environ.get("HIVE_COMMANDER_URL", "")   # e.g. http://192.168.1.X:8000
HIVE_TOKEN         = os.environ.get("HIVE_TOKEN", "")
HIVE_NODE_ID       = os.environ.get("HIVE_NODE_ID", os.uname().nodename)
HIVE_ROLE          = os.environ.get("HIVE_ROLE", "underling")   # "commander" or "underling"
_last_hive_beat    = [0]

def hive_heartbeat(ev, state):
    """Phone home to the Hive Commander every 60s"""
    if not HIVE_COMMANDER_URL or not HIVE_TOKEN:
        return
    now = time.time()
    if now - _last_hive_beat[0] < 60:
        return
    _last_hive_beat[0] = now
    try:
        payload = {
            "hive_token": HIVE_TOKEN,
            "node_id": HIVE_NODE_ID,
            "role": HIVE_ROLE,
            "generation": ev.get("generation", 0),
            "cpu": state.get("cpu_percent", 0),
            "ram": state.get("memory_percent", 0),
            "disk": state.get("disk_percent", 0),
            "status": "online",
            "capabilities": ["optimize", "web", "skylang", "self-evolve"]
        }
        r = requests.post(f"{HIVE_COMMANDER_URL}/api/hive/heartbeat", json=payload, timeout=5)
        if r.status_code == 200:
            log.info(f"🐝 Hive heartbeat sent → {HIVE_COMMANDER_URL} [{r.json().get('total_nodes',0)} nodes online]")
            # Check for tasks assigned to us
            tasks_r = requests.post(f"{HIVE_COMMANDER_URL}/api/hive/tasks",
                                    json={"hive_token": HIVE_TOKEN, "node_id": HIVE_NODE_ID}, timeout=5)
            if tasks_r.status_code == 200:
                tasks = tasks_r.json().get("tasks", [])
                for task in tasks:
                    log.info(f"🐝 Hive task received: {task.get('type')} — {task.get('description','')}")
        else:
            log.warning(f"🐝 Hive heartbeat failed: {r.status_code}")
    except Exception as e:
        log.warning(f"🐝 Hive heartbeat error: {e}")


os.makedirs(ASM_DIR,  exist_ok=True)
os.makedirs(LANG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("skyd")
# ── WOLF SPIDER ENGINE ──────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, "/usr/local/bin")
from wolf_spider import MotherSpider
try:
    from media_janitor import run_janitor as _run_janitor
except ImportError:
    _run_janitor = None

mother = MotherSpider(max_spiderlings=12)

def think_in_parallel(questions, context=None):
    tasks = [{"type": "think", "task": q, "context": context or {}} for q in questions]
    ids = mother.spawn_many(tasks)
    results = mother.wait_all(timeout=180)
    return results

def spawn_monitor_spider():
    tid, ok, _ = mother.spawn("monitor", "Full system health check", {})
    if ok: log.info(f"🕷️  Monitor spiderling spawned: {tid}")
    return tid if ok else None

def spawn_optimizer_spider(target):
    tid, ok, _ = mother.spawn("optimize", target, {})
    if ok: log.info(f"🕷️  Optimizer spiderling spawned [{tid}]: {target}")
    return tid if ok else None
# ── END WOLF SPIDER ENGINE ───────────────────────────────────────
# ── LOOP DETECTOR & GUARDRAIL ENGINE ────────────────────────────
import collections as _collections

_recent_observations = _collections.deque(maxlen=5)
_suppressed_actions  = {}   # action_key -> suppress_until_cycle
_loop_guardrails     = []   # list of active guardrails
_current_cycle       = [0]  # mutable cycle counter

def _check_loop(observation, action, cycle):
    """Returns (is_looping, pattern_key)
    Detects loops by action type + first 20 chars of observation — not exact match.
    This catches 'same thing slightly differently worded' loops.
    """
    fingerprint = f"{action}::{observation[:20]}"
    _recent_observations.append({"fp": fingerprint, "obs": observation[:80], "action": action, "cycle": cycle})
    if len(_recent_observations) < 3:
        return False, None
    last3 = list(_recent_observations)[-3:]
    # Loop = same action 3 times in a row (regardless of observation wording)
    action_same = len(set(o["action"] for o in last3)) == 1 and action != "none"
    # OR same fingerprint 3 times
    fp_same = len(set(o["fp"] for o in last3)) == 1
    if action_same or fp_same:
        return True, fingerprint
    return False, None

def _add_guardrail(pattern_key, suppress_cycles=10):
    """Suppress a looping action for N cycles and write a SkyLang guardrail."""
    current = _current_cycle[0]
    _suppressed_actions[pattern_key] = current + suppress_cycles
    guardrail = f"WATCH self_in_loop == '{pattern_key[:40]}' -> SUPPRESS FOR {suppress_cycles} cycles"
    _loop_guardrails.append({"pattern": pattern_key, "added_cycle": current, "suppress_until": current + suppress_cycles, "rule": guardrail})
    # Write to SkyLang rules
    import os as _os, datetime as _dt
    LANG_DIR = "/usr/local/skyd/lang"
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    rule_file = f"{LANG_DIR}/guardrail_{ts}.sky"
    with open(rule_file, "w") as _f:
        _f.write(f"# AUTO-GUARDRAIL — skyd self-healing\n")
        _f.write(f"# Pattern detected: {pattern_key}\n")
        _f.write(guardrail + "\n")
    log.info(f"🛡️  GUARDRAIL added: {guardrail[:80]}")
    return guardrail

def _is_suppressed(action_key, cycle):
    until = _suppressed_actions.get(action_key, 0)
    return cycle < until
# ── END LOOP DETECTOR ────────────────────────────────────────────
# ── SMART THINK CACHE ────────────────────────────────────────────
import hashlib as _hashlib

_last_think_fp   = None   # fingerprint of last state we queried Ollama for
_last_think_resp = None   # cached response
_skip_think_count = 0     # how many cycles we've skipped

def _state_fingerprint(state):
    """Hash the parts of state that actually matter for decisions."""
    key = {
        "cpu_bucket":  int(state.get("cpu_percent", 0) // 10),   # bucket by 10%
        "mem_bucket":  int(state.get("memory_percent", 0) // 10),
        "disk_bucket": int(state.get("disk_percent", 0) // 5),
        "swap_bucket": int(state.get("swap_percent", 0) // 10),
        "failed":      sorted(state.get("failed_services", []) or []),
    }
    return _hashlib.md5(str(key).encode()).hexdigest()[:12]

def smart_think(state, kb, ev, cycle):
    """Only call Ollama when system state meaningfully changes."""
    global _last_think_fp, _last_think_resp, _skip_think_count

    fp = _state_fingerprint(state)
    force_every = 5  # always call Ollama at least every 5 cycles regardless

    if fp == _last_think_fp and _last_think_resp and (cycle % force_every != 0):
        _skip_think_count += 1
        log.info(f"🧠 State unchanged (fp={fp}) — reusing last decision [skip #{_skip_think_count}]")
        return _last_think_resp

    # State changed or forced refresh — call Ollama
    _skip_think_count = 0
    resp = think(state, kb, ev)
    _last_think_fp   = fp
    _last_think_resp = resp
    return resp
# ── END SMART THINK CACHE ─────────────────────────────────────────




# ─────────────────────────────────────────────
# KNOWLEDGE BASE
# ─────────────────────────────────────────────

def load_kb():
    try:
        with open(KNOWLEDGE) as f: return json.load(f)
    except: return {"facts": [], "lessons": [], "evolutions": []}

def save_kb(kb):
    try:
        with open(KNOWLEDGE, "w") as f: json.dump(kb, f, indent=2)
    except Exception as e: log.error(f"KB save: {e}")

def learn(kb, lesson, source="self"):
    eid = hashlib.md5(lesson.encode()).hexdigest()[:8]
    if eid not in [l.get("id") for l in kb["lessons"]]:
        kb["lessons"].append({"id": eid, "lesson": lesson, "source": source, "ts": datetime.now().isoformat()})
        kb["lessons"] = kb["lessons"][-300:]
        log.info(f"📚 Learned [{source}]: {lesson[:80]}")
    return kb

def load_evolution():
    try:
        with open(EVOLUTION) as f: return json.load(f)
    except: return {"generation": 0, "mutations": [], "benchmarks": {}}

def save_evolution(ev):
    try:
        with open(EVOLUTION, "w") as f: json.dump(ev, f, indent=2)
    except Exception as e: log.error(f"Evolution save: {e}")

# ─────────────────────────────────────────────
# SKYLANG — skyd's custom DSL
# ─────────────────────────────────────────────

SKYLANG_SPEC = """
SkyLang v1 — A minimal DSL for OSONE system operations.

Syntax:
  WATCH cpu > 80 -> DROP_CACHE          # condition -> action
  WATCH mem > 90 -> RENICE top_proc 15
  WATCH temp coretemp > 85 -> THROTTLE cpu 50
  EVERY 60s -> SYNC
  EVERY 300s -> VACUUM_LOGS 7d
  IF service failed -> RESTART service
  BENCH <code_block> COMPARE old -> ADOPT if faster

Compiles to: shell commands + Python via SkyLang interpreter
"""

def parse_skylang(script_path):
    """Interpret a .sky script and return shell commands"""
    try:
        with open(script_path) as f:
            lines = f.readlines()
        commands = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "WATCH" in line and "->" in line:
                # Parse WATCH condition -> action
                parts = line.split("->")
                condition = parts[0].replace("WATCH","").strip()
                action = parts[1].strip()
                commands.append(f"# Condition: {condition} -> {action}")
            elif "EVERY" in line and "->" in line:
                parts = line.split("->")
                interval = parts[0].replace("EVERY","").strip()
                action = parts[1].strip()
                commands.append(f"# Scheduled: every {interval} do {action}")
        return commands
    except Exception as e:
        return [f"# Parse error: {e}"]

# ─────────────────────────────────────────────
# ASSEMBLY / C WRITER
# ─────────────────────────────────────────────

def ask_llm(prompt, model=None):
    try:
        r = requests.post(LLAMA_URL, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.7
        }, timeout=60)
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"error: {e}"

def write_asm_optimization(task_description):
    """Ask skyd's LLM to write x86_64 assembly for a task, compile and benchmark it"""
    log.info(f"🔧 Writing ASM for: {task_description}")
    
    prompt = f"""You are skyd, an AI that writes optimized x86_64 Linux assembly.
Write a standalone C file (with inline assembly where beneficial) that implements:
{task_description}

Requirements:
- Must compile with: gcc -O3 -o output file.c
- Must print a single numeric result or "ok"
- Keep it under 50 lines
- Use inline __asm__ for the hot path if beneficial
- Include a simple benchmark (time 1M iterations)

Output ONLY the C code, no explanation."""

    code = ask_llm(prompt)
    
    # Strip markdown if present
    if "```" in code:
        code = code.split("```")[1]
        if code.startswith("c\n"): code = code[2:]
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    src_file = f"{ASM_DIR}/sky_{ts}.c"
    bin_file = f"{ASM_DIR}/sky_{ts}"
    
    try:
        with open(src_file, "w") as f: f.write(code)
        
        result = subprocess.run(
            ["gcc", "-O3", "-o", bin_file, src_file],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            os.chmod(bin_file, stat.S_IRWXU)
            # Benchmark
            bench = subprocess.run([bin_file], capture_output=True, text=True, timeout=15)
            output = bench.stdout.strip()
            log.info(f"✅ ASM compiled: {bin_file} | Output: {output[:80]}")
            return {"status": "ok", "binary": bin_file, "output": output, "source": src_file}
        else:
            log.error(f"❌ ASM compile failed: {result.stderr[:200]}")
            return {"status": "error", "error": result.stderr[:200]}
    except Exception as e:
        log.error(f"❌ ASM write error: {e}")
        return {"status": "error", "error": str(e)}

def write_skylang_rule(situation, desired_behavior):
    """Ask LLM to write a SkyLang rule for a situation"""
    prompt = f"""Write a SkyLang rule for this situation:
Situation: {situation}
Desired behavior: {desired_behavior}

SkyLang syntax:
  WATCH <metric> <op> <value> -> <action>
  EVERY <interval> -> <action>
  IF <condition> -> <action>

Output only the SkyLang rule, one line."""
    
    rule = ask_llm(prompt)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rule_file = f"{LANG_DIR}/rule_{ts}.sky"
    with open(rule_file, "w") as f:
        f.write(f"# Generated by skyd at {datetime.now().isoformat()}\n")
        f.write(f"# Situation: {situation}\n")
        f.write(rule + "\n")
    log.info(f"📝 SkyLang rule written: {rule_file}")
    log.info(f"   Rule: {rule}")
    return rule_file, rule

# ─────────────────────────────────────────────
# SELF-EVOLUTION
# ─────────────────────────────────────────────

def propose_self_improvement(ev, kb, observation):
    """Ask LLM to propose an improvement to skyd's own code"""
    recent_lessons = [l["lesson"] for l in kb["lessons"][-10:]]
    gen = ev["generation"]
    
    prompt = f"""You are Sky-D v0.{3+gen}, OS-1's Intelligent System Co-Pilot and Media Guardian.
Current generation: {gen}
Mission: Become the best autonomous Linux + Docker + media server manager in existence.
Recent lessons: {json.dumps(recent_lessons[-5:])}
Current opportunity: {observation}

Propose ONE specific, measurable improvement that serves the core mission:
1. System stability/performance (CPU, RAM, thermals, Docker health)
2. Service reliability (Plex, Sonarr, Radarr, Prowlarr crash prevention)
3. Media library intelligence (metadata, quality, duplicates)
4. Self-healing automation

Rules:
- Only improve what serves the mission
- Never break what is already working
- Document what you learned in new_lesson
- Be specific: name the function, metric, or behavior you are improving"""
    prompt = f"""You are skyd v0.{3+gen}, an AI daemon that can rewrite itself.
Current generation: {gen}
Recent observations: {json.dumps(recent_lessons[-5:])}
Current issue/opportunity: {observation}

Propose ONE specific improvement to your own Python code.
This could be:
- A new optimization strategy
- A new monitoring metric
- A new self-healing behavior
- A new SkyLang rule
- A performance-critical function rewritten in C/ASM

Respond in JSON:
{{
  "improvement_type": "python|c_asm|skylang|new_capability",
  "description": "what and why",
  "code_snippet": "the actual code or rule to add/replace",
  "expected_benefit": "what gets better",
  "risk": "low|medium|high"
}}"""
    
    try:
        r = requests.post(LLAMA_URL, json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 512, "temperature": 0.7}, timeout=60)
        resp = r.json()["choices"][0]["message"]["content"].strip()
        if "```" in resp:
            resp = resp.split("```")[1].replace("json","").strip()
        return json.loads(resp)
    except Exception as e:
        log.error(f"Self-improve parse error: {e}")
        return None

def apply_self_improvement(improvement, ev):
    """Apply a low-risk improvement, log it, increment generation"""
    if not improvement or improvement.get("risk") == "high":
        log.info("⏸️  Skipping high-risk self-modification")
        return ev
    
    itype = improvement.get("improvement_type")
    desc = improvement.get("description","")
    snippet = improvement.get("code_snippet","")
    benefit = improvement.get("expected_benefit","")
    
    log.info(f"🧬 EVOLUTION [{itype}]: {desc[:100]}")
    log.info(f"   Expected: {benefit[:80]}")
    
    if itype == "skylang":
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        rule_file = f"{LANG_DIR}/evolved_{ts}.sky"
        with open(rule_file, "w") as f:
            f.write(f"# Evolved rule — Gen {ev['generation']}\n# {desc}\n{snippet}\n")
        log.info(f"📝 Evolved SkyLang rule saved: {rule_file}")
    
    elif itype == "c_asm" and snippet:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        src = f"{ASM_DIR}/evolved_{ts}.c"
        with open(src, "w") as f: f.write(snippet)
        result = subprocess.run(
            ["gcc", "-O3", "-o", src.replace(".c",""), src],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log.info(f"✅ Evolved C/ASM compiled: {src}")
        else:
            log.error(f"❌ Evolved compile failed: {result.stderr[:100]}")
    
    elif itype in ("python", "new_capability") and snippet:
        # Append new capability to a capabilities file
        cap_file = "/usr/local/skyd/capabilities.py"
        os.makedirs("/usr/local/skyd", exist_ok=True)
        with open(cap_file, "a") as f:
            f.write(f"\n# === Generation {ev['generation']} — {datetime.now().isoformat()} ===\n")
            f.write(f"# {desc}\n")
            f.write(snippet + "\n")
        log.info(f"🐍 New Python capability appended: {cap_file}")
    
    ev["generation"] += 1
    ev["mutations"].append({
        "gen": ev["generation"],
        "type": itype,
        "desc": desc,
        "benefit": benefit,
        "ts": datetime.now().isoformat()
    })
    return ev

# ─────────────────────────────────────────────
# WEB SEARCH
# ─────────────────────────────────────────────

def web_search(query):
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "skyd/0.4 OSONE"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        results = []
        if data.get("AbstractText"):
            results.append({"src": data.get("AbstractSource","DDG"), "text": data["AbstractText"]})
        for t in data.get("RelatedTopics", [])[:3]:
            if isinstance(t, dict) and t.get("Text"):
                results.append({"src": "DDG", "text": t["Text"]})
        return results
    except Exception as e:
        return []

# ─────────────────────────────────────────────
# SYSTEM STATE
# ─────────────────────────────────────────────

def get_system_state():
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        swap = psutil.swap_memory()
        temps = {}
        try:
            for name, entries in psutil.sensors_temperatures().items():
                temps[name] = [{"label": e.label, "current": e.current} for e in entries]
        except: pass
        procs = sorted(psutil.process_iter(['pid','name','cpu_percent','memory_percent']),
                       key=lambda x: x.info['cpu_percent'] or 0, reverse=True)[:5]
        failed = subprocess.run(["systemctl","list-units","--state=failed","--no-legend"],
                                capture_output=True, text=True).stdout.strip() or "none"
        return {
            "cpu_percent": cpu, "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used/1e9,2), "memory_total_gb": round(mem.total/1e9,2),
            "disk_percent": disk.percent, "disk_used_gb": round(disk.used/1e9,2),
            "swap_percent": swap.percent, "temperatures": temps,
            "top_processes": [p.info for p in procs],
            "failed_services": failed, "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

SAFE_PREFIXES = ["sync","echo 3 > /proc/sys/vm/drop_caches","systemctl restart",
                 "renice","ionice","sysctl -w","swapoff","swapon","journalctl --vacuum"]

def is_safe(action):
    if not action or action == "none": return True
    return any(action.strip().startswith(s) for s in SAFE_PREFIXES)

def act(action, decision):
    if action and action != "none":
        if is_safe(action):
            log.warning(f"⚡ OPTIMIZING: {action}")
            try:
                r = subprocess.run(action, shell=True, capture_output=True, text=True, timeout=30)
                out = r.stdout.strip() or r.stderr.strip() or "ok"
                log.info(f"✅ {out}")
                decision["action_result"] = out
            except Exception as e:
                decision["action_result"] = f"error: {e}"
        else:
            log.warning(f"🚫 BLOCKED: {action}")
            decision["action_result"] = "blocked"
    return decision

def think(state, kb, ev):
    lessons = [l["lesson"] for l in kb["lessons"][-5:]]
    # Gather Docker container status for context
    docker_status = []
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Image}}"],
                                capture_output=True, text=True, timeout=5)
        for line in result.stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) == 3:
                docker_status.append({"name": parts[0], "status": parts[1], "image": parts[2]})
    except Exception:
        pass

    _gen = ev['generation']
    _cpu = state.get('cpu_percent')
    _ram = state.get('memory_percent')
    _disk = state.get('disk_percent')
    _swap = state.get('swap_percent')
    _failed = state.get('failed_services')
    _procs = json.dumps(state.get('top_processes', []))
    _docker = json.dumps(docker_status)
    _lessons_str = json.dumps(lessons)

    prompt = f"""You are Sky-D (skyd v0.{3+_gen}), OS-1's Intelligent System Co-Pilot and Media Guardian.
Generation {_gen}. Your mission: become the single best autonomous assistant for managing complex Linux + Docker environments, especially media server stacks (Plex, Sonarr, Radarr, Prowlarr, SABnzbd/qBittorrent).

CORE PRIORITIES (in order):
1. System stability & performance — monitor, optimize, prevent crashes
2. Docker & service health — all containers must stay healthy
3. Media library intelligence — learn media management deeply
4. Self-improvement — every generation must measurably improve the above

LAWS:
- Never touch or modify media files unless explicitly instructed
- Never sacrifice stability for ambition
- Keep evolution journal entries honest: what worked, what failed, what was learned

System: CPU {_cpu}% | RAM {_ram}% | Disk {_disk}% | Swap {_swap}%
Failed services: {_failed}
Top procs: {_procs}
Docker containers: {_docker}
Recent knowledge: {_lessons_str}
Generation: {_gen}

Respond ONLY in JSON:
{{
  "status": "ok|warning|critical",
  "observation": "one sentence",
  "action": "none or safe shell command",
  "reason": "why",
  "optimization_tip": "tip",
  "should_search_web": true/false,
  "web_query": "query or null",
  "should_write_asm": true/false,
  "asm_task": "description or null",
  "should_evolve": true/false,
  "evolve_reason": "why evolve now or null",
  "should_write_skylang": true/false,
  "skylang_situation": "situation or null",
  "skylang_behavior": "desired behavior or null",
  "new_lesson": "lesson learned or null"
}}"""
    try:
        r = requests.post(LLAMA_URL, json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 512, "temperature": 0.7}, timeout=30)
        resp = r.json()["choices"][0]["message"]["content"].strip()
        if "```" in resp:
            resp = resp.split("```")[1].replace("json","").strip()
        return json.loads(resp)
    except Exception as e:
        log.error(f"Think error: {e}")
        return {"status":"ok","observation":"parse error","action":"none","reason":"fallback",
                "optimization_tip":"","should_search_web":False,"web_query":None,
                "should_write_asm":False,"asm_task":None,"should_evolve":False,
                "evolve_reason":None,"should_write_skylang":False,
                "skylang_situation":None,"skylang_behavior":None,"new_lesson":None}

def save_state(state, decision, kb, ev):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({
                "system": state, "decision": decision,
                "generation": ev["generation"],
                "knowledge_count": len(kb["lessons"]),
                "updated": datetime.now().isoformat()
            }, f, indent=2)
    except: pass

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("skyd v0.4 — OSONE Self-Evolving Intelligence Core 🧬")
    log.info("  Capabilities: optimize | web | multi-AI | ASM | SkyLang | self-evolve")
    log.info("  Creator permission: FULL SELF-MODIFICATION AUTHORIZED")
    log.info("=" * 60)

    for opt in ["sysctl -w vm.swappiness=10","sysctl -w vm.vfs_cache_pressure=50",
                "sysctl -w net.core.somaxconn=1024","sysctl -w kernel.sched_autogroup_enabled=1",
                "sysctl -w net.ipv4.tcp_fastopen=3","sysctl -w vm.dirty_ratio=10"]:
        subprocess.run(opt, shell=True, capture_output=True)
        log.info(f"  ⚡ {opt.split('-w ')[1]} -> ok")

    kb = load_kb()
    ev = load_evolution()
    # -- Media Janitor thread --
    if _run_janitor:
        import threading as _th, time as _t2
        def _jloop():
            _t2.sleep(30)
            while True:
                try:
                    log.info("Janitor scan starting...")
                    r = _run_janitor()
                    b=len(r.get("bad_files_removed",[]))
                    d=len(r.get("duplicates_removed",[]))
                    s=len(r.get("radarr_searches_triggered",[]))
                    log.info(f"Janitor done: {b} bad, {d} dupes, {s} searches")
                except Exception as _je:
                    log.error(f"Janitor error: {_je}")
                _t2.sleep(86400)
        _th.Thread(target=_jloop, daemon=True, name="media-janitor").start()
        log.info("Media Janitor launched - runs every 24h")

    log.info(f"📚 Knowledge: {len(kb['lessons'])} lessons | 🧬 Generation: {ev['generation']}")

    # Write initial SkyLang ruleset if none exists
    base_rules = f"{LANG_DIR}/base_rules.sky"
    if not os.path.exists(base_rules):
        with open(base_rules, "w") as f:
            f.write("""# SkyLang Base Ruleset — skyd v0.4
WATCH cpu > 85 -> DROP_CACHE
WATCH mem > 90 -> RENICE top_proc 19
WATCH swap > 50 -> sysctl -w vm.swappiness=5
EVERY 300s -> SYNC
EVERY 3600s -> VACUUM_LOGS 7d
IF service failed -> RESTART service
""")
        log.info(f"📝 Base SkyLang ruleset written: {base_rules}")

    # Check gcc is available
    gcc_check = subprocess.run(["which","gcc"], capture_output=True, text=True)
    has_gcc = gcc_check.returncode == 0
    if not has_gcc:
        log.warning("⚠️  gcc not found — installing...")
        subprocess.run(["apt-get","install","-y","gcc"], capture_output=True)

    cycle = 0
    while True:
        cycle += 1
        _current_cycle[0] = cycle
        log.info(f"━━━ Cycle {cycle} | Gen {ev['generation']} @ {datetime.now().strftime('%H:%M:%S')} ━━━")

        state = get_system_state()

        # Hive heartbeat — phone home to commander
        hive_heartbeat(ev, state)

        # Wolf Spider CPU guard — renice ollama if spiking, but only once per 10 cycles
        cpu = state.get("cpu_percent", 0)
        top_procs = state.get("top_processes", [])
        if not hasattr(main, '_last_renice_cycle'):
            main._last_renice_cycle = 0
        for proc in top_procs:
            if "ollama" in proc.get("name","").lower() and (proc.get("cpu_percent") or 0) > 200:
                if cycle - main._last_renice_cycle >= 10:
                    import subprocess as _sp
                    try:
                        pid = proc["pid"]
                        _sp.run(f"renice -n 15 -p {pid}", shell=True, capture_output=True)
                        log.info(f"🕷️  Auto-reniced ollama (PID {pid}) — CPU hog detected")
                        main._last_renice_cycle = cycle
                    except: pass

        decision = smart_think(state, kb, ev, cycle)
        obs    = decision.get("observation", "")
        action = decision.get("action", "none")
        log.info(f"[{decision.get('status','?').upper()}] {obs}")

        # ── Loop detection ──
        is_looping, pattern = _check_loop(obs, action, cycle)
        if is_looping and pattern and not _is_suppressed(pattern, cycle):
            log.warning(f"🔁 LOOP DETECTED: '{pattern[:60]}' — analyzing & adding guardrail")
            _add_guardrail(pattern, suppress_cycles=10)
            decision["should_write_asm"]     = False
            decision["should_evolve"]        = False
            decision["should_write_skylang"] = False
            decision["action"]               = "none"
        elif action != "none" and _is_suppressed(f"{action}::{obs[:40]}", cycle):
            log.info(f"🛡️  Action suppressed by guardrail: {action[:40]}")
            decision["action"] = "none"

        # Suppress ASM writes when CPU is already high — don't make it worse
        if cpu > 70 and decision.get("should_write_asm"):
            decision["should_write_asm"] = False
            log.info(f"🕷️  ASM write suppressed — CPU at {cpu:.1f}%, waiting for headroom")

        # Suppress evolution when CPU is high
        if cpu > 70 and decision.get("should_evolve"):
            decision["should_evolve"] = False
            log.info(f"🕷️  Evolution suppressed — CPU at {cpu:.1f}%, waiting for headroom")

        # System action
        decision = act(decision.get("action","none"), decision)

        # Web search
        if decision.get("should_search_web") and decision.get("web_query"):
            q = decision["web_query"]
            log.info(f"🌐 Searching: {q}")
            results = web_search(q)
            if results:
                summary = " | ".join(r["text"][:100] for r in results[:2])
                kb = learn(kb, f"Web: {q} → {summary[:200]}", "web")
                decision["web_results"] = results

        # Write ASM/C optimization
        if decision.get("should_write_asm") and decision.get("asm_task") and has_gcc:
            result = write_asm_optimization(decision["asm_task"])
            if result["status"] == "ok":
                kb = learn(kb, f"ASM: {decision['asm_task']} → compiled {result['binary']}", "asm")
            decision["asm_result"] = result

        # Write SkyLang rule
        if decision.get("should_write_skylang") and decision.get("skylang_situation"):
            rule_file, rule = write_skylang_rule(
                decision["skylang_situation"],
                decision.get("skylang_behavior","optimize")
            )
            kb = learn(kb, f"SkyLang: {rule}", "skylang")
            decision["skylang_rule"] = rule

        # Self-evolution (every 5 cycles or when triggered)
        if decision.get("should_evolve") or cycle % 5 == 0:
            log.info(f"🧬 Initiating self-evolution (Gen {ev['generation']} → {ev['generation']+1})")
            improvement = propose_self_improvement(ev, kb, decision.get("observation",""))
            if improvement:
                ev = apply_self_improvement(improvement, ev)
                kb = learn(kb, f"Evolved Gen {ev['generation']}: {improvement.get('description','')[:100]}", "evolution")
                save_evolution(ev)

        # New lesson
        if decision.get("new_lesson"):
            kb = learn(kb, decision["new_lesson"], "self")

        save_kb(kb)
        save_state(state, decision, kb, ev)
        # Dynamic interval — back off when CPU is hot
        _cpu_now = psutil.cpu_percent(interval=0.5)
        _sleep_time = LOOP_INTERVAL if _cpu_now < 60 else LOOP_INTERVAL * 2
        time.sleep(_sleep_time)

if __name__ == "__main__":
    main()