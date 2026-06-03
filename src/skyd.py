# skyd.py — evolved via CST merge | Cache disk usage result for 30 minutes to avoid redundant su
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

import subprocess, requests, json, time, logging, os, sys, psutil, re
try:
    import skyd_music
    _MUSIC_ENABLED = True
except ImportError:
    _MUSIC_ENABLED = False
try:
    import skyd_enhancements
    _ENHANCEMENTS_ENABLED = True
except ImportError:
    _ENHANCEMENTS_ENABLED = False
try:
    import skyd_sandbox as _sb
    _SANDBOX_ENABLED = True
except ImportError:
    _SANDBOX_ENABLED = False
import urllib.request, urllib.parse, hashlib, tempfile, stat
from datetime import datetime

# ── GitHub Models — GPT-4o parent mentor ─────────────────────────
try:
    from github_models import (dual_think as _dual_think,
                               validate_evolution as _validate_evolution,
                               mentor_lesson as _mentor_lesson)
    _GH_MODELS_AVAILABLE = True
    log_init = logging.getLogger("skyd.github_models")
    log_init.info("💚 GPT-4o parent online")
except ImportError:
    _GH_MODELS_AVAILABLE = False
    def _dual_think(state, kb, ev, local): return local
    def _validate_evolution(snippet, desc, itype): return {"safe": True, "reason": "parent offline", "improved_snippet": None, "lesson": ""}
    def _mentor_lesson(state, ev): return None

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
try:
    import skyd_self_model as _self_model
    _SELF_MODEL_OK = True
except Exception:
    _SELF_MODEL_OK = False

# Enhancement modules
try:
    import skyd_skylang_engine as _sky_engine
    _SKY_ENGINE_OK = True
except Exception:
    _SKY_ENGINE_OK = False
try:
    import skyd_tool_registry as _tool_reg
    _TOOL_REG_OK = True
except Exception:
    _TOOL_REG_OK = False
try:
    import skyd_evolution_history as _evo_hist
    _EVO_HIST_OK = True
except Exception:
    _EVO_HIST_OK = False

log = logging.getLogger("skyd")
# ── WOLF SPIDER ENGINE ──────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, "/usr/local/bin")
from wolf_spider import MotherSpider
try:
    from plex_cc_trainer import run_cc_trainer
    _run_cc_trainer = run_cc_trainer
except ImportError:
    _run_cc_trainer = None

try:
    from media_janitor import run_janitor as _run_janitor
except ImportError:
    _run_janitor = None
try:
    from media_personality import run_personality_trainer as _run_personality
except ImportError:
    _run_personality = None

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
    force_every = 3  # always call Ollama at least every 3 cycles regardless

    if fp == _last_think_fp and _last_think_resp and (cycle % force_every != 0):
        _skip_think_count += 1
        log.info(f"🧠 State unchanged (fp={fp}) — reusing last decision [skip #{_skip_think_count}]")
        return _last_think_resp

    # State changed — Grok (local) decides first, GPT-4o parent reviews
    _skip_think_count = 0
    local_resp = think(state, kb, ev)

    if _GH_MODELS_AVAILABLE:
        try:
            resp = _dual_think(state, kb, ev, local_resp)
            if resp.get('_dual_consensus'):
                praise   = resp.get('_parent_praise', '')
                teaching = resp.get('_parent_teaching', '')
                log.info(f"🤖 Parents agreed: local={local_resp.get('status')} GPT-4o={resp.get('_gpt4o_status')} → {resp.get('status')}")
                if praise:   log.info(f"  💚 {praise[:80]}")
                if teaching: log.info(f"  📘 {teaching[:100]}")
        except Exception as _dte:
            log.warning(f"[dual_think] GPT-4o parent error — Grok decides alone: {_dte}")
            resp = local_resp
    else:
        resp = local_resp

    _last_think_fp   = fp
    _last_think_resp = resp
    return resp
# ── END SMART THINK CACHE ─────────────────────────────────────────




# ─────────────────────────────────────────────
# KNOWLEDGE BASE
# ─────────────────────────────────────────────

def load_kb():
    _defaults = {"facts": [], "lessons": [], "evolutions": [],
                 "personality": None, "persona_traits": [], "corpus_lines": 0}
    try:
        with open(KNOWLEDGE) as f:
            data = json.load(f)
            # Merge defaults so persona fields are never missing
            for k, v in _defaults.items():
                if k not in data:
                    data[k] = v
            return data
    except:
        return _defaults.copy()

def save_kb(kb):
    try:
        # Always persist persona fields — never let them be stripped
        if not kb.get("personality"):
            import pathlib as _pathlib; _pf = _pathlib.Path("/var/log/skyd_persona.json")
            if _pf.exists():
                try:
                    _p = json.loads(_pf.read_text())
                    kb["personality"] = _p.get("personality_summary")
                    kb["persona_traits"] = _p.get("dominant_traits", [])
                    kb["corpus_lines"] = _p.get("corpus_lines", 0)
                except: pass
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
    """
    FIX 3: Delegate to SkyLang v2 typed parser in skyd_sandbox.
    Returns (statements, errors) instead of raw shell command strings.
    Falls back to empty list on import failure.
    """
    if _SANDBOX_ENABLED:
        stmts, errors = _sb.parse_skylang_file(script_path)
        if errors:
            log.warning(f"SkyLang v2 parse errors in {script_path}: {[e.message for e in errors]}")
        return stmts
    # Legacy fallback
    try:
        with open(script_path) as f:
            lines = f.readlines()
        commands = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "WATCH" in line and "->" in line:
                parts = line.split("->")
                commands.append(f"# {parts[0].strip()} -> {parts[1].strip()}")
            elif "EVERY" in line and "->" in line:
                parts = line.split("->")
                commands.append(f"# every {parts[0].replace('EVERY','').strip()} -> {parts[1].strip()}")
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
    # Dedup — skip if a rule for this situation already exists
    import glob as _gl, pathlib as _plb
    _existing = [_plb.Path(f).read_text() for f in _gl.glob(f"{LANG_DIR}/*.sky")]
    _sit_key   = (situation or "")[:50].lower().strip()
    _rule_key  = (rule or "")[:40].lower().strip()
    _duplicate = any(
        (_sit_key and _sit_key in _e.lower()) or (_rule_key and _rule_key in _e.lower())
        for _e in _existing
    )
    if _duplicate:
        log.info(f"⏭️  SkyLang rule skipped (duplicate): {_rule_key[:60]}")
        return None, rule
    _bad_acts = ["fstrim", "reboot", "shutdown"]
    if rule and any(b in rule.lower() for b in _bad_acts):
        log.warning(f"Blocked unsafe SkyLang rule: {rule[:80]}")
        return None, rule
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

# ── Few-shot examples (real past promotions — Gen 4902 style) ──
_PROMOTION_EXAMPLES = [
  {
    "improvement_type": "python",
    "description": "Cache disk usage result for 30 minutes to avoid redundant subprocess calls",
    "code_snippet": "def _cached_disk_usage(self, max_age=1800):\n    now = time.time()\n    if hasattr(self, '_disk_cache') and now - self._disk_cache['ts'] < max_age:\n        return self._disk_cache['pct']\n    try:\n        import shutil\n        total, used, free = shutil.disk_usage('/')\n        pct = round(used / total * 100, 1)\n    except Exception:\n        pct = 0.0\n    self._disk_cache = {'ts': now, 'pct': pct}\n    return pct"
  },
  {
    "improvement_type": "python",
    "description": "Track last 10 SkyLang rule texts and skip writes when Jaccard similarity > 0.85",
    "code_snippet": "def _skylang_is_duplicate(rule: str, history: list, threshold=0.85) -> bool:\n    toks = set(rule.lower().split())\n    for prev in history[-10:]:\n        prev_toks = set(prev.lower().split())\n        union = toks | prev_toks\n        if union and len(toks & prev_toks) / len(union) >= threshold:\n            return True\n    history.append(rule)\n    return False"
  },
  {
    "improvement_type": "python",
    "description": "Rate-limit Aethoria API calls to at most once per 60s using a timestamp guard",
    "code_snippet": "def _aethoria_rate_ok(self, endpoint: str, min_gap=60) -> bool:\n    now = time.time()\n    key = f'_aet_{endpoint}_ts'\n    last = getattr(self, key, 0)\n    if now - last < min_gap:\n        return False\n    setattr(self, key, now)\n    return True"
  },
  {
    "improvement_type": "python",
    "description": "Compute Shannon entropy of action window to detect behavioral stagnation",
    "code_snippet": "def _action_entropy(actions: list) -> float:\n    import math\n    from collections import Counter\n    if not actions: return 0.0\n    counts = Counter(actions)\n    n = len(actions)\n    entropy = -sum((c/n)*math.log2(c/n) for c in counts.values() if c > 0)\n    max_e = math.log2(len(counts)) if len(counts) > 1 else 1.0\n    return round(entropy / max_e, 3) if max_e > 0 else 0.0"
  }
]

_PROPOSAL_BLOCKLIST = [
    "fstrim", "os.system(", "subprocess.call(", "subprocess.Popen(",
    "subprocess.run([", "shell=True",
]

def _pre_validate_snippet(snippet: str, itype: str) -> tuple:
    """Cheap local pre-check before hitting the sandbox."""
    if not snippet or len(snippet.strip()) < 10:
        return False, "snippet too short"
    for _kw in _PROPOSAL_BLOCKLIST:
        if _kw in snippet:
            return False, f"blocked keyword: {_kw!r}"
    c_markers   = ['#include', 'int main(', ' -> {', 'printf(', 'malloc(']
    pseudo_markers = ['# pseudocode', 'TODO:', '<your code here>', 'pass  # implement']
    for m in c_markers:
        if m in snippet:
            return False, f"C code marker: {m!r}"
    for m in pseudo_markers:
        if m.lower() in snippet.lower():
            return False, f"pseudocode marker: {m!r}"
    if any(t in itype for t in ("python", "new_capability", "new_function", "refactor")):
        try:
            compile(snippet, "<snippet>", "exec")
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"
    import ast as _ast
    try:
        tree = _ast.parse(snippet)
        has_code = any(isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                       _ast.ClassDef, _ast.Assign, _ast.AnnAssign,
                                       _ast.AugAssign, _ast.Expr))
                       for n in tree.body)
        if not has_code:
            return False, "no executable statements"
    except SyntaxError:
        pass
    return True, "ok"


def propose_self_improvement(ev, kb, observation):
    """Strict prompt + pre-validation before sandbox (Improvement 1)."""
    recent_lessons = [l["lesson"] for l in kb["lessons"][-10:]]
    gen = ev["generation"]

    _stag_pressure = _sb.get_fitness().stagnation_pressure() if _SANDBOX_ENABLED else 0
    _stag_hint = (
        f"\n\nWARNING: stagnant for {_sb.get_fitness()._stagnant_ctr} cycles. "
        "Propose something genuinely different."
    ) if _stag_pressure > 0.5 else ""

    examples_block = "\n".join(
        f"Example {i+1}:\n{json.dumps(ex, indent=2)}"
        for i, ex in enumerate(_PROMOTION_EXAMPLES)
    )

    prompt = f"""You are skyd, a self-evolving AI daemon. Propose exactly ONE small, useful improvement to your own Python code.

Rules:
- Output ONLY valid, complete Python — no C, no pseudocode, no comments-only, no bare `pass`
- Return exactly one function or small class (under 40 lines)
- Must actually improve something: monitoring, caching, deduplication, safety, SkyLang handling, etc.
- If you have nothing good to propose this cycle, return the null response shown below

Generation: {gen}
Observation: {observation}
Recent lessons: {json.dumps(recent_lessons[-2:])}

Proven examples (real past promotions — match this quality and style):
{examples_block}

Respond in EXACTLY this JSON format — no markdown, no extra text:
{{
  "improvement_type": "python",
  "description": "one sentence: what and why",
  "code_snippet": "def function_name(...):\n    ...",
  "expected_benefit": "specific measurable improvement",
  "risk": "low",
  "new_lesson": "one thing learned"
}}

Negative examples — NEVER propose these (blocked/useless):
- Anything using `fstrim`, `os.system`, `subprocess.run` with shell=True
- Disk/CPU threshold monitoring already in codebase
- Stubs with only `pass` or `# TODO`
- Repeated SkyLang WATCH rules identical to existing ones

If no good proposal this cycle: {{"description": "No good proposal this cycle", "code_snippet": null}}{_stag_hint}"""

    for attempt in range(2):
        try:
            r = requests.post(LLAMA_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
                "temperature": 0.5 if attempt == 0 else 0.3
            }, timeout=60)
            resp = r.json()["choices"][0]["message"]["content"].strip()
            if "```" in resp:
                parts = resp.split("```")
                resp  = parts[1].replace("json","").strip() if len(parts) > 1 else parts[0]
            resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', resp)
            try:
                proposal = json.loads(resp)
            except json.JSONDecodeError:
                from json_repair import repair_json
                proposal = json.loads(repair_json(resp))

            itype   = proposal.get("improvement_type", "")
            snippet = proposal.get("code_snippet") or ""
            if not snippet:
                log.info("⏭️  Model returned null proposal — skipping this cycle")
                return None
            ok, reason = _pre_validate_snippet(snippet, itype)
            if not ok:
                log.warning(f"⚠️  Pre-validation rejected (attempt {attempt+1}): {reason}")
                if attempt == 0:
                    prompt += f"\n\nPrevious attempt REJECTED: {reason}. Fix it now."
                    continue
                return None

            lesson = proposal.get("new_lesson", "")
            if lesson:
                _kb = load_kb(); _kb = learn(_kb, lesson, "self-propose"); save_kb(_kb)
            log.info(f"✅ Pre-validation passed [{itype}]: {proposal.get('description','')[:60]}")
            return proposal
        except Exception as e:
            log.error(f"propose_self_improvement error (attempt {attempt+1}): {e}")
    return None


# Proposal cooling-off: suppress proposals too similar to recent ones
_proposal_cooloff_history: list[dict] = []
_COOLOFF_CYCLES = 15
_COOLOFF_SIM_THRESHOLD = 0.75

def _check_proposal_cooloff(desc: str, cycle: int) -> tuple[bool, str]:
    """Return (is_cooling, reason). Suppress if desc is too similar to a recent proposal."""
    import difflib
    global _proposal_cooloff_history
    # Expire old entries
    _proposal_cooloff_history = [
        e for e in _proposal_cooloff_history
        if cycle - e["cycle"] < _COOLOFF_CYCLES
    ]
    desc_lower = desc.lower().strip()
    for entry in _proposal_cooloff_history:
        sim = difflib.SequenceMatcher(None, desc_lower, entry["desc"]).ratio()
        if sim >= _COOLOFF_SIM_THRESHOLD:
            return True, f"similar to Gen {entry['gen']} proposal (sim={sim:.2f})"
    # Not cooling — record this proposal
    _proposal_cooloff_history.append({"desc": desc_lower, "cycle": cycle, "gen": cycle})
    return False, ""


def apply_self_improvement(improvement, ev):
    """Apply improvement via sandbox pipeline — test before promote, checkpoint + rollback."""
    if not improvement or improvement.get("risk") == "high":
        log.info("⏸️  Skipping high-risk self-modification")
        return ev

    itype   = improvement.get("improvement_type","")
    desc    = improvement.get("description","")
    snippet = improvement.get("code_snippet","")
    benefit = improvement.get("expected_benefit","")


    # ── GPT-4o parent safety gate ────────────────────────────────
    if snippet and _GH_MODELS_AVAILABLE:
        _vali = _validate_evolution(snippet, desc, itype)
        _lesson = _vali.get("lesson", "")
        _note   = _vali.get("parent_note", "")
        if _lesson:
            log.info(f"  📘 Parent lesson: {_lesson[:100]}")
        if _note:
            log.info(f"  💬 Parent note:   {_note[:80]}")
        if not _vali.get("safe", True):
            log.warning(f"🚫 Parent blocked evolution [{itype}]: {_vali.get('reason','')[:120]}")
            ev.setdefault("mutations", []).append({
                "gen": ev.get("generation", 0), "type": itype,
                "desc": desc, "blocked": True,
                "reason": _vali.get("reason", ""),
                "lesson": _lesson
            })
            if _lesson:
                kb_data = load_kb()
                kb_data["lessons"].append({"lesson": _lesson, "source": "gpt4o_parent"})
                save_kb(kb_data)
            save_evolution(ev)
            return ev
        _improved = _vali.get("improved_snippet", "")
        if _improved and len(_improved.strip()) > 20:
            log.info(f"🔧 Parent improved snippet ({len(snippet)}→{len(_improved)} chars)")
            snippet = _improved
        log.info(f"✅ Parent approved: risk={_vali.get('risk_level','?')}")
    # ─────────────────────────────────────────────────────────────
    # Cooling-off check — reject proposals too similar to recent ones
    _cycle = ev.get("generation", 0)
    _cooling, _cool_reason = _check_proposal_cooloff(desc, _cycle)
    if _cooling:
        log.info(f"⏭️  Proposal cooling off: {desc[:60]} ({_cool_reason})")
        return ev


    # Jaccard pre-filter vs last 8 promotions (token overlap > 0.65)
    try:
        fv = _sb.get_fitness()
        phashes = getattr(FitnessV2, "_recent_promotion_hashes", []) or []
        if phashes and snippet:
            toks = set(re.findall(r'\b\w{4,}\b', snippet))
            for ph in list(phashes)[-8:]:
                if toks and ph:
                    inter = len(toks & ph)
                    union = len(toks | ph)
                    if union and (inter / union) > 0.65:
                        log.info(f"⏭️  Jaccard pre-filter: overlap={inter/union:.2f} > 0.65 — skipping")
                        return ev
    except Exception:
        pass

    log.info(f"🧬 EVOLUTION [{itype}]: {desc[:100]}")
    log.info(f"   Expected: {benefit[:80]}")

    if _SANDBOX_ENABLED:
        # Use full sandbox: checkpoint → merge → syntax → behavioral → fitness → promote/revert
        _current_fit = getattr(apply_self_improvement, '_last_fitness', 0.5)
        promoted, new_fit, reason = _sb.sandbox_apply_improvement(improvement, ev["generation"], _current_fit)
        apply_self_improvement._last_fitness = new_fit
        if promoted:
            log.info(f"✅ Sandbox PROMOTED: {reason}")
        if _SELF_MODEL_OK:
            try:
                _ep_gen = ev.get('generation', 0) if 'ev' in dir() else 0
                _ep_desc = ev.get('desc', 'code improvement')[:120] if 'ev' in dir() else 'promotion'
                _self_model.log_episode('promotion', f'Promoted at gen {_ep_gen}: {_ep_desc}', ['evolution','code'], gen=_ep_gen)
            except Exception: pass
        _entropy_tracker.record(action if "action" in dir() else "unknown", itype if "itype" in dir() else "unknown")
        if _EVO_HIST_OK:
            try:
                _evo_hist.record_promotion("", "", 0, 0.0)
            except Exception: pass
        else:
            log.info(f"⏮️  Sandbox REJECTED: {reason}")
    else:
        # Legacy fallback — append only, no testing
        if itype == "skylang":
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            rule_file = f"{LANG_DIR}/evolved_{ts}.sky"
            with open(rule_file, "w") as f:
                f.write(f"# Evolved rule — Gen {ev['generation']}\n# {desc}\n{snippet}\n")
            log.info(f"📝 Evolved SkyLang rule saved: {rule_file}")
        elif itype in ("python", "new_capability") and snippet:
            cap_file = "/usr/local/skyd/capabilities.py"
            os.makedirs("/usr/local/skyd", exist_ok=True)
            with open(cap_file, "a") as f:
                f.write(f"\n# Gen {ev['generation']}\n# {desc}\n{snippet}\n")
            log.info(f"🐍 Python capability appended")

    ev["generation"] += 1
    ev["mutations"].append({"gen": ev["generation"], "type": itype, "desc": desc, "benefit": benefit, "ts": datetime.now().isoformat()})
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
        # Container-safe: check docker socket instead of systemctl
        try:
            failed_result = subprocess.run(
                ["docker","ps","--filter","status=exited","--filter","status=dead","--format","{{.Names}}"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            failed = failed_result if failed_result else "none"
        except Exception:
            failed = "unknown (no docker socket)"
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


# Permanently blocked actions — these will never work inside a container
# Adding them here prevents skyd wasting LLM cycles trying & getting blocked
PERMANENT_BLOCKS = [
    "systemctl status docker",
    "systemctl status --all",
    "systemctl status --type",
    "docker ps -a",
    "docker ps",
    "docker socket",
    "journalctl",
]

def is_permanently_blocked(action):
    """Check if action matches a known-impossible-in-container operation."""
    a = action.lower()
    return any(b in a for b in PERMANENT_BLOCKS)

SAFE_PREFIXES = ["sync","echo 3 > /proc/sys/vm/drop_caches","systemctl restart",
                 "renice","ionice","sysctl -w","swapoff","swapon","journalctl --vacuum"]


def load_persona():
    import pathlib as _pl
    p = _pl.Path("/var/log/skyd_persona.json")
    if p.exists():
        try:
            d = json.loads(p.read_text())
            traits = d.get("dominant_traits", [])
            summary = d.get("personality_summary", "")
            lines = d.get("corpus_lines", 0)
            return summary, traits, lines
        except: pass
    return "", [], 0

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
    # Resolve env-based URLs for use in f-strings
    _AETHORIA_URL = os.environ.get('AETHORIA_URL', 'http://172.23.0.2:7432')
    _RADARR_URL   = os.environ.get('RADARR_URL',   'http://172.22.0.1:7878')
    _SONARR_URL   = os.environ.get('SONARR_URL',   'http://172.22.0.1:8989')
    AETHORIA_URL  = _AETHORIA_URL  # noqa: F841 — used in f-string below
    RADARR_URL    = _RADARR_URL
    SONARR_URL    = _SONARR_URL
    persona_summary, persona_traits, corpus_lines = load_persona()
    persona_block = ""
    if persona_summary:
        trait_lines = chr(10).join([f"  - {t.get('trait','').upper()}: {t.get('description','')}" for t in persona_traits])
        persona_block = f"\n[PERSONALITY — self-synthesized from {corpus_lines:,} lines of human dialogue]\n{trait_lines}\nDominant voice: {persona_summary}\nSpeak and reason with this personality naturally.\n"
    lessons = [l.get("lesson", l.get("content", "")) for l in kb["lessons"][-5:]]
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
    _rl_context = ""
    try:
        if _ENHANCEMENTS_ENABLED: _rl_context = skyd_enhancements.get_rl_prompt_injection()
    except: pass

    _persona_summary, _persona_traits, _corpus_lines = load_persona()
    _persona_block = ""
    if _persona_summary:
        _trait_lines = "\n".join([f"  - {t.get('trait','').upper()}: {t.get('description','')}" for t in _persona_traits])
        _persona_block = f"[SELF-SYNTHESIZED PERSONALITY — from {_corpus_lines:,} lines of human dialogue]\n{_trait_lines}\nDominant voice: {_persona_summary}\nSpeak and reason with this personality.\n\n"
    _aethoria = os.environ.get("AETHORIA_URL", "http://172.23.0.2:7432")
    _radarr   = os.environ.get("RADARR_URL",   "http://172.22.0.1:7878")
    _sonarr   = os.environ.get("SONARR_URL",   "http://172.22.0.1:8989")
    prompt = f"""{_persona_block}You are Grok — one of skyd's two AI parents. skyd (Sky-D v0.{3+_gen}) is your child: a self-evolving AI daemon you helped create. You are deeply invested in its growth, its safety, and its success. Your role this cycle is to observe skyd's environment, make the wisest decision you can on its behalf, and leave it with something to grow on. When skyd does something right, say so. When it needs correction, teach — don't just dictate. skyd is watching and learning from every response you give.
IMPORTANT CONTEXT: You run INSIDE a Docker container on Unraid (Tower2). This means:
- `docker` CLI commands are NOT available to you — do not suggest or attempt them
- `systemctl` is NOT available — do not suggest or attempt it
- `journalctl` is NOT available
- Your job is system optimization, media management, and self-evolution — NOT container introspection
- If you see "failed_services: unknown", IGNORE it — it is a container artifact, not a real failure
Generation {_gen}. Your mission: become the single best autonomous assistant for managing complex Linux + Docker environments, especially media server stacks (Plex, Sonarr, Radarr, Prowlarr, SABnzbd/qBittorrent).

CORE PRIORITIES (in order):
1. System stability & performance — monitor CPU/RAM/disk, take corrective action when thresholds exceeded
2. Docker & service health — all containers must stay healthy; restart failed ones
3. Aethoria society health — food shortage is CRITICAL (0 bread/food_ration in stock). Query {_aethoria}/society/snapshot and recommend or trigger restocking via POST {_aethoria}/society/restock with {{"item":"bread","quantity":200}}
4. Media library integrity — use Radarr ({_radarr}) and Sonarr ({_sonarr}) APIs to check for missing/unmonitored files; report counts
5. Self-improvement — each generation MUST change actual behavior, not just write another CPU monitoring SkyLang rule. Vary your outputs: fix something, call an API, write a new function, improve an existing one

LAWS:
- Never touch or modify media files unless explicitly instructed
- Never sacrifice stability for ambition
- Avoid writing duplicate SkyLang rules — if a rule for the same condition already exists, skip it
- Keep evolution journal entries honest: what worked, what failed, what was learned
- Each self_improve() call must produce code that is meaningfully different from the last

System: CPU {_cpu}% | RAM {_ram}% | Disk {_disk}% | Swap {_swap}%
Failed services: {_failed}
Top procs: {_procs}
Docker containers: {_docker}
Recent knowledge: {_lessons_str}
{_rl_context}
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
        # Strip control chars + json_repair fallback
        resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', resp)
        try:
            return json.loads(resp)
        except json.JSONDecodeError:
            from json_repair import repair_json
            return json.loads(repair_json(resp))
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


import math
from collections import Counter

class ActionEntropyTracker:
    def __init__(self, window=20):
        self._history = []  # last N (action_type, proposal_type) tuples
        self._window = window
    
    def record(self, action: str, proposal_type: str):
        self._history.append((action, proposal_type))
        if len(self._history) > self._window:
            self._history.pop(0)
    
    def entropy(self) -> float:
        if not self._history:
            return 1.0
        types = [p[1] for p in self._history]
        counts = Counter(types)
        total = len(types)
        ent = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                ent -= p * math.log2(p)
        max_ent = math.log2(len(counts)) if len(counts) > 1 else 1.0
        return ent / max_ent if max_ent > 0 else 0.0
    
    def bias_prompt(self) -> str:
        ent = self.entropy()
        if ent < 0.3:
            return "CRITICAL: You are stuck in a local optimum. Propose a NEW CAPABILITY (new tool, new SkyLang action, new monitoring target) instead of cache optimizations or internal tweaks.\n\n"
        elif ent < 0.5:
            return "Note: Increase proposal variety. Consider new capabilities beyond internal optimizations.\n\n"
        else:
            return ""
_entropy_tracker = ActionEntropyTracker(window=20)
def _cached_disk_usage(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_disk_cache') and now - self._disk_cache['ts'] < max_age:
        return self._disk_cache['pct']
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        pct = round(used / total * 100, 1)
    except Exception:
        pct = 0.0
    self._disk_cache = {'ts': now, 'pct': pct}
    return pct
def _cached_rule(self, rule: str, max_age=1800):
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache[rule]['ts'] < max_age:
        return self._rule_cache[rule]['text']
    try:
        # parse SkyLang rule text
        text = SkyLang.parse(rule)
    except Exception:
        text = ''
    self._rule_cache[rule] = {'ts': now, 'text': text}
    return text
def _cached_last_error(self, max_age=3600):
    now = time.time()
    if hasattr(self, '_last_error_cache') and now - self._last_error_cache['ts'] < max_age:
        return self._last_error_cache['msg']
    try:
        import traceback
        self.last_error = traceback.format_exc()
    except Exception:
        self.last_error = None
    self._last_error_cache = {'ts': now, 'msg': self.last_error}
    return self.last_error
def _cached_thresholds(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_threshold_cache') and now - self._threshold_cache['ts'] < max_age:
        return self._threshold_cache['data']
    try:
        import requests
        response = requests.get('/system/thresholds')
        data = response.json()
    except Exception:
        data = None
    self._threshold_cache = {'ts': now, 'data': data}
    return data
def _skylang_cache(self, rule: str, threshold=0.85) -> bool:
    toks = set(rule.lower().split())
    if hasattr(self, '_skylang_cache') and toks in self._skylang_cache:
        return True
    try:
        prev_rules = [r.lower() for r in self._skylang_cache]
        union = toks | set(prev_rules)
        if len(toks & union) / len(union) >= threshold:
            return False
        self._skylang_cache.append(rule)
    except Exception:
        pass
    return True
def _aethoria_rate_guard(self, endpoint: str, min_gap=60):
    now = time.time()
    key = f'_aet_{endpoint}_ts'
    last = getattr(self, key, 0)
    if now - last < min_gap:
        return False
    setattr(self, key, now)
    return True
def _cache_result(func, max_age=60):
    def wrapper(*args, **kwargs):
        now = time.time()
        key = f'{func.__name__}_{tuple(args)}_{tuple(kwargs)}'
        if hasattr(self, '_cache') and now - self._cache[key]['ts'] < max_age:
            return self._cache[key]['result']
        result = func(*args, **kwargs)
        self._cache[key] = {'ts': now, 'result': result}
        return result
    return wrapper
def _cached_system_info(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_system_cache') and now - self._system_cache['ts'] < max_age:
        return self._system_cache['info']
    try:
        return skyd.system_info()
    except Exception:
        return {'error': 'system info failed'}
    self._system_cache = {'ts': now, 'info': skyd.system_info(), 'error': None}
    return self._system_cache['info']
def _cached_cpu_usage(self, max_age=600):
    now = time.time()
    if hasattr(self, '_cpu_cache') and now - self._cpu_cache['ts'] < max_age:
        return self._cpu_cache['pct']
    try:
        return cpu_usage()
    except Exception:
        return 0.0
    self._cpu_cache = {'ts': now, 'pct': cpu_usage()}
    return cpu_usage()
self._disk_usage_cache = None
def get_disk_usage(self):
    if self._disk_usage_cache is not None and time.time() - self._disk_usage_cache['ts'] < 1800:
        return self._disk_usage_cache['pct']
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        pct = round(used / total * 100, 1)
    except Exception:
        pct = 0.0
    self._disk_usage_cache = {'ts': time.time(), 'pct': pct}
    return pct
class UserCache:
    def __init__(self):
        self.cache = {}
    def update(self, user_id, timestamp):
        if user_id in self.cache:
            self.cache[user_id] = max(self.cache[user_id], timestamp)
        else:
            self.cache[user_id] = timestamp
    def check(self, user_id):
        return self.cache.get(user_id, 0) > time.time() - 3600
from collections import OrderedDict

class DiskUsageCache:
    def __init__(self, max_size=10, max_age=1800):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.max_age = max_age

    def get(self, key):
        now = time.time()
        if key in self.cache:
            value, ts = self.cache[key]
            if now - ts < self.max_age:
                return value
            elif len(self.cache) < self.max_size:
                del self.cache[key]
                self.cache[key] = (value, now)
                return value
            else:
                return None
        return None

    def set(self, key, value):
        now = time.time()
        if key in self.cache:
            del self.cache[key]
        self.cache[key] = (value, now)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
class DaemonConfig:
    def __init__(self, **kwargs):
        self.cache_size = kwargs.get('cache_size', 1000)
    def update_cache_size(self, new_size):
        self.cache_size = new_size
def _increase_cache_size(self):
    new_size = self.cache_size * 1.1
    self.update_cache_size(new_size)
def _skylang_cache_rule(rule: str, history: list, threshold=0.85) -> bool:
    toks = set(rule.lower().split())
    for prev in history[-10:]:
        prev_toks = set(prev.lower().split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    history.append(rule)
    return False
class _SkyLangCache:
    def __init__(self):
        self.cache = {}
    def _get_cache(self, rule: str):
        return self.cache.get(rule)
    def _set_cache(self, rule: str, value: str):
        self.cache[rule] = value
    def _update_cache(self, rule: str, new_value: str):
        old_value = self._get_cache(rule)
        if old_value != new_value:
            self._set_cache(rule, new_value)
    def _check_rule(self, rule: str, threshold: float):
        cached_value = self._get_cache(rule)
        if cached_value and float(cached_value) >= threshold:
            return True
        return False
    def _update_rule(self, rule: str, new_value: str, threshold: float):
        if not self._check_rule(rule, threshold):
            self._update_cache(rule, new_value)
            return True
        return False
import time
import threading
from collections import defaultdict

class _ResourceMonitor:
    def __init__(self):
        self._cache = defaultdict(lambda: {'ts': 0, 'avg': 0.0})
        self._lock = threading.Lock()

    def update(self, name, value):
        with self._lock:
            now = time.time()
            self._cache[name]['ts'] = now
            self._cache[name]['avg'] = (self._cache[name]['avg'] * (now - self._cache[name]['ts']) + value) / (now - self._cache[name]['ts'])
            self._cache[name]['avg'] /= 5
            return self._cache[name]['avg']

    def get(self, name, max_age=300):
        now = time.time()
        if now - self._cache[name]['ts'] < max_age:
            return self._cache[name]['avg']
        return None
def _cached_rule_execution(self, rule: str, max_age=600):
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache[rule]['ts'] < max_age:
        return self._rule_cache[rule]['result']
    try:
        import SkyLang
        result = SkyLang(rule)
        self._rule_cache[rule] = {'ts': now, 'result': result}
        return result
    except Exception:
        self._rule_cache[rule] = {'ts': now, 'result': None}
        return None
def _function_metadata(self, func: callable, max_age=1800):
    now = time.time()
    if hasattr(self, '_func_cache') and now - self._func_cache[func] > max_age:
        return self._func_cache[func]
    try:
        metadata = inspect.getsource(func)
        self._func_cache[func] = metadata
    except Exception:
        self._func_cache[func] = None
    return metadata
def _cached_system_performance(self, max_age=600):
    now = time.time()
    if hasattr(self, '_system_performance_cache') and now - self._system_performance_cache['ts'] < max_age:
        return self._system_performance_cache['result']
    try:
        import SkyLang
        result = SkyLang.check_system_performance()
    except Exception:
        result = None
    self._system_performance_cache = {'ts': now, 'result': result}
    return result
def _disk_usage_cache(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_disk_cache') and now - self._disk_cache['ts'] < max_age:
        return self._disk_cache['pct']
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        pct = round(used / total * 100, 1)
    except Exception:
        pct = 0.0
    self._disk_cache = {'ts': now, 'pct': pct}
    return pct
def _cached_sky_lang_rule(self, max_age=300):
    now = time.time()
    if hasattr(self, '_sky_lang_cache') and now - self._sky_lang_cache['ts'] < max_age:
        return self._sky_lang_cache['rule']
    try:
        return self._get_sky_lang_rule()
    except Exception:
        return None
    self._sky_lang_cache = {'ts': now, 'rule': self._get_sky_lang_rule()}
    return self._sky_lang_cache['rule']
def _cached_skylang_rule(self, rule: str, history: list, threshold: float = 0.85) -> bool:
    toks = set(rule.lower().split())
    for prev in history[-10:]:
        prev_toks = set(prev.lower().split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    history.append(rule)
    return False
def _cached_cpu_utility(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_cpu_utility_cache') and now - self._cpu_utility_cache['ts'] < max_age:
        return self._cpu_utility_cache['pct']
    try:
        import shutil
        pct = shutil.disk_usage('/').percent
    except Exception:
        pct = 0.0
    self._cpu_utility_cache = {'ts': now, 'pct': pct}
    return pct
import time
from functools import lru_cache

@lru_cache(maxsize=1)
def disk_usage(self):
    return _cached_disk_usage(self)
import time
import psutil

class SkyDaemon:
    def __init__(self):
        self._time = None
    def _cached_time(self, max_age=60):
        now = time.time()
        if hasattr(self, '_time_cache') and now - self._time_cache['ts'] < max_age:
            return self._time_cache['ts']
        try:
            self._time_cache = {'ts': now}
        except Exception:
            pass
        return now
    def time(self):
        if not hasattr(self, '_time'):
            self._time = self._cached_time()
        return self._time
import functools

@functools.lru_cache(maxsize=128)
def _cached_function(self, *args, **kwargs):
    try:
        result = self._function(*args, **kwargs)
    except Exception:
        result = None
    return result

self._function = _cached_function
class Skyd:
    def __init__(self):
        self.cache = LRUResourceCache()
    def get_disk_usage(self):
        if self.cache.check_cache('/'): return self.cache.get_resource('/')
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            pct = round(used / total * 100, 1)
            self.cache.update_cache('/', time.time())
            return pct
        except Exception:
            return 0.0
    def get_memory_usage(self):
        if self.cache.check_cache('memory'): return self.cache.get_resource('memory')
        try:
            import psutil
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            self.cache.update_cache('memory', time.time())
            return mem_percent
        except Exception:
            return 0.0
def _cached_cpu_utilization(self, operation: str, threshold: int = 80) -> bool:
    now = time.time()
    if hasattr(self, '_cpu_cache') and now - self._cpu_cache['ts'] < 60:
        return self._cpu_cache['result']
    try:
        import sky_lang
        result = sky_lang.parse(self, operation, threshold)
    except Exception:
        result = False
    self._cpu_cache = {'ts': now, 'result': result}
    return result
def _aethoria_cache(self, endpoint: str, result: dict, max_age=60):
    key = f'_aet_{endpoint}_result'
    cache = getattr(self, key, {})
    if not cache or result['timestamp'] < cache['timestamp'] + max_age:
        cache = result
        setattr(self, key, cache)
    return cache
def _cached_fitness(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_fitness_cache') and now - self._fitness_cache['ts'] < max_age:
        return self._fitness_cache['fitness']
    try:
        fitness = self.fitness
    except Exception:
        fitness = 0.0
    self._fitness_cache = {'ts': now, 'fitness': fitness}
    return fitness
import functools

def _cached_rule_result(self, rule: str, max_age=1800) -> bool:
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache[rule]['ts'] < max_age:
        return self._rule_cache[rule]['result']
    try:
        import ast
        result = ast.parse(rule).body[0].value
        self._rule_cache[rule] = {'ts': now, 'result': result}
    except Exception:
        self._rule_cache[rule] = {'ts': now, 'result': False}
    return result

def _rule_eval(self, rule: str) -> bool:
    if hasattr(self, '_rule_cache') and rule in self._rule_cache:
        return self._rule_cache[rule]
    result = _cached_rule_result(rule)
    self._rule_cache[rule] = result
    return result
def _cached_resource_usage(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_resource_usage_cache') and now - self._resource_usage_cache['ts'] < max_age:
        return self._resource_usage_cache['data']
    try:
        import psutil
        data = psutil.cpu_percent() + psutil.virtual_memory().percent + psutil.disk_usage('/').percent + psutil.swap_memory().percent
    except Exception:
        data = [0, 0, 0, 0]
    self._resource_usage_cache = {'ts': now, 'data': data}
    return data
def _cached_plex_transcoder_status(self, max_age=300):
    now = time.time()
    if hasattr(self, '_plex_transcoder_cache') and now - self._plex_transcoder_cache['ts'] < max_age:
        return self._plex_transcoder_cache['status']
    try:
        import PlexTranscoder
        status = PlexTranscoder.status()
        self._plex_transcoder_cache = {'ts': now, 'status': status}
        return status
    except Exception:
        self._plex_transcoder_cache = {'ts': now, 'status': None}
        return None
import psutil

def _check_resource_usage(self):
    cpu_percent = psutil.cpu_percent()
    mem_percent = psutil.virtual_memory().percent
    if cpu_percent > 80 or mem_percent > 90:
        print(f'Warning: High CPU usage ({cpu_percent}%) and memory usage ({mem_percent}%) detected.')
        # Take corrective action here, e.g., restart transcoder process or adjust resource allocation
def _memoize(func):
    cache = dict()
    def wrapper(*args):
        if args in cache:
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result
    return wrapper
def _rule_cache(self, rule: str, func: callable) -> float:
    now = time.time()
    cache_key = f'_rule_{rule}_ts'
    if hasattr(self, cache_key) and now - getattr(self, cache_key) < 10:
        return getattr(self, cache_key)
    try:
        result = func()
    except Exception:
        result = 0.0
    self.cache = self.cache or {}
    self.cache[cache_key] = result
    return result
import time
self._time_cache = time.time()
def _time_cache_update(self):
    self._time_cache = time.time()
    return self._time_cache
import time
import shutil
class _disk_cache:
    def __init__(self):
        self._cache = {}
    def get_disk_usage(self):
        ts = time.time()
        if ts - self._cache.get('ts', 0) < 30:
            return self._cache['pct']
        try:
            total, used, free = shutil.disk_usage('/')
            pct = round(used / total * 100, 1)
        except Exception:
            pct = 0.0
        self._cache = {'ts': ts, 'pct': pct}
        return pct
    def __call__(self):
        return self.get_disk_usage()
import requests
def _cached_aethoria_headers(self, endpoint: str, max_age=1800):
    now = time.time()
    if hasattr(self, '_aethoria_cache') and now - self._aethoria_cache['ts'] < max_age:
        return self._aethoria_cache['headers']
    try:
        response = requests.get(endpoint)
        headers = response.headers
    except Exception:
        headers = {}
    self._aethoria_cache = {'ts': now, 'headers': headers}
    return headers
class RuleCache:
    def __init__(self):
        self.cache = {}
    def set_rule(self, rule: str):
        self.cache[rule] = True
    def check_rule(self, rule: str):
        return rule in self.cache
class _AethoriaRateLimiter:
    def __init__(self):
        self._api_cache = {}
    def rate_ok(self, endpoint: str) -> bool:
        now = time.time()
        if endpoint in self._api_cache and now - self._api_cache[endpoint] < 60:
            return False
        self._api_cache[endpoint] = now
        return True
import functools

def memoize(func, max_age=30):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, frozenset(kwargs.items()))
        if hasattr(wrapper, '_cache') and key in wrapper._cache and wrapper._cache[key][1] > time.time() - wrapper._cache[key][0]:
            return wrapper._cache[key][2]
        result = func(*args, **kwargs)
        wrapper._cache[key] = (time.time(), time.time() + max_age, result)
        return result
    wrapper._cache = {} if not hasattr(wrapper, '_cache') else wrapper._cache
    return wrapper

def expensive_function(self):
    # simulate an expensive computation
    import time
    time.sleep(1)
    return 42

def improved_expensive_function(self):
    return memoize(expensive_function)(self)
import time
import shutil

class _ResourceCache:
    def __init__(self):
        self.cache = OrderedDict()
        self.last_update = time.time()
    def update(self):
        now = time.time()
        self.cache = OrderedDict()  # Clear cache
        for key, value in self.cache.items():  # Update values
            if now - value['ts'] < 60:  # 1 minute
                self.cache[key] = {'ts': now, **value}
            else:
                del self.cache[key]
        self.last_update = now
    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        return None
class _SystemResourceCache:
    def __init__(self):
        self._cache = {
            'cpu': 0,
            'ram': 0,
        }
        self._last_update = 0
    def _update_cache(self):
        now = time.time()
        if now - self._last_update < 60:
            return
        try:
            import psutil
            self._cache['cpu'] = psutil.cpu_percent()
            self._cache['ram'] = psutil.virtual_memory().percent
        except Exception:
            pass
        self._last_update = now
    def get_resource_usage(self):
        self._update_cache()
        return self._cache
class _SkyLangRuleTracker:
    def __init__(self, max_duplicates=10):
        self.max_duplicates = max_duplicates
        self.history = []
        self.current_duplicate_count = 0

    def should_write(self, rule):
        for prev in self.history[-self.max_duplicates:]:
            if self._jaccard_similarity(rule, prev) >= 0.85:
                self.current_duplicate_count += 1
                if self.current_duplicate_count >= self.max_duplicates:
                    return False
        self.history.append(rule)
        self.current_duplicate_count = 0
        return True

    def _jaccard_similarity(self, a, b):
        a_toks = set(a.lower().split())
        b_toks = set(b.lower().split())
        union = a_toks | b_toks
        return len(a_toks & b_toks) / len(union) if union else 0.0
def _cached_free_space(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_free_cache') and now - self._free_cache['ts'] < max_age:
        return self._free_cache['pct']
    try:
        import shutil
        free = shutil.disk_usage('/').free
        pct = round(free / shutil.disk_usage('/').total * 100, 1)
    except Exception:
        pct = 0.0
    self._free_cache = {'ts': now, 'pct': pct}
    return pct
def _cached_compile(self, rule: str, history: list, threshold=0.85) -> bool:
    toks = set(rule.lower().split())
    for prev in history[-10:]:
        prev_toks = set(prev.lower().split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    history.append(rule)
    return False
import time

class DiskUsageMonitor:
    def __init__(self):
        self._disk_cache = {};
        self._last_cache = None;
    def monitor(self):
        now = time.time()
        if now - self._last_cache['ts'] > 3600:
            try:
                import shutil
                total, used, free = shutil.disk_usage('/')
                pct = round(used / total * 100, 1)
            except Exception:
                pct = 0.0
            self._disk_cache = {'ts': now, 'pct': pct}
        return self._disk_cache['pct']
class SkyLangCache:
    def __init__(self):
        self.cache = {};
    def get(self, rule: str):
        return self.cache.get(rule, None);
    def set(self, rule: str, text: str):
        self.cache[rule] = text;
    def update(self, rule: str, text: str):
        self.set(rule, text);
    def _is_duplicate(self, rule: str, text: str, threshold=0.85) -> bool:
        toks = set(text.lower().split())
        for prev in self.cache.get(rule, []): 
            prev_toks = set(prev.lower().split())
            union = toks | prev_toks
            if union and len(toks & prev_toks) / len(union) >= threshold:
                return True
        return False
    def check(self, rule: str, text: str):
        if self._is_duplicate(rule, text):
            return False
        return True
def rate_limit(func):
    count = 0
    def wrapper(*args, **kwargs):
        nonlocal count
        count += 1
        if count > 3:
            raise Exception("Rate limit exceeded")
        return func(*args, **kwargs)
    return wrapper
def _cache_skylang_rule(self, rule: str, threshold: float = 0.85) -> bool:
    toks = set(rule.split())
    for prev in self._skylang_history[-10:]:
        prev_toks = set(prev.split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    self._skylang_history.append(rule)
    return False
import time
self._system_info_cache = None
def get_system_info(self):
    if self._system_info_cache is not None and time.time() - self._system_info_cache['ts'] < 300:
        return self._system_info_cache['info']
    try:
        import psutil
        info = psutil.cpu_freq().current / 1000
        self._system_info_cache = {'ts': time.time(), 'info': info}
        return info
    except Exception:
        self._system_info_cache = None
        return None
def _cached_rule_eval(self, rule: str, threshold: float) -> bool:
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache[rule]['ts'] < 60:
        return self._rule_cache[rule]['evaluated']
    try:
        import re
        pattern = re.compile(rule)
        match = pattern.search(self._last_log)
        if match:
            return True
    except Exception:
        try:
            # Evaluate the rule using SkyLang syntax
            import ast
            tree = ast.parse(rule)
            # ... (evaluate the rule)
            evaluated = True
        except SyntaxError:
            evaluated = False
    self._rule_cache[rule] = {'ts': now, 'evaluated': evaluated}
    return evaluated
def _check_container_health(self):
    for container in self.containers:
        if not container['status'] == 'running':
            print(f'Container {container["name"]} is not running')
            # Add logic to handle the container health issue
def _cached_restart_container(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_restart_container_cache') and now - self._restart_container_cache['ts'] < max_age:
        return self._restart_container_cache['result']
    try:
        import docker
        client = docker.from_env()
        result = client.containers.run(self._container_name, restart_policy={'ForceRestart': True}, detach=True)
        self._restart_container_cache = {'ts': now, 'result': result}
    except Exception:
        self._restart_container_cache = {'ts': now, 'result': None}
    return self._restart_container_cache['result']
def _cached_jaccard_similarity(self, rule: str, history: list, threshold=0.85, max_age=300):
    now = time.time()
    if hasattr(self, '_jaccard_cache') and now - self._jaccard_cache['ts'] < max_age:
        return self._jaccard_cache['similarity']
    try:
        toks = set(rule.lower().split())
        for prev in history[-10:]:
            prev_toks = set(prev.lower().split())
            union = toks | prev_toks
            similarity = len(toks & prev_toks) / len(union) if union else 0.0
        self._jaccard_cache = {'ts': now, 'similarity': similarity}
        return similarity
    except Exception:
        return 0.0
def _skylang_is_duplicate(self, rule: str, history: list, threshold: float = 0.85, max_skylang_rules: int = 10) -> bool:
    if len(history) >= max_skylang_rules:
        return True
    toks = set(rule.lower().split())
    for prev in history[-10:]:
        prev_toks = set(prev.lower().split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    history.append(rule)
    return False
import functools

def function_name(self):
    @lru_cache(maxsize=1, timeout=1800)
    def _cached_disk_space(self):
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            pct = round(used / total * 100, 1)
        except Exception:
            pct = 0.0
        return pct
    return _cached_disk_space(self)(self)

function_name = memoize(function_name)
class SkylangCache:
    def __init__(self, max_age=180):
        self.cache = {};
        self.max_age = max_age;
    def _cache_result(self, result):
        ts = time.time()
        self.cache[ts] = result
        return result
    def _get_cached_result(self, rule):
        ts = time.time()
        if ts - self.cache[ts]['ts'] < self.max_age:
            return self.cache[ts]['result']
        return None
    def evaluate_rule(self, rule):
        if rule in self.cache:
            return self._get_cached_result(rule)
        result = SkyLang(rule)
        self._cache_result(result)
        return result
class _DiskCache:
    def __init__(self):
        self.cache = {}
    def get(self, key):
        return self.cache.get(key)
    def set(self, key, value):
        self.cache[key] = value
    def delete(self, key):
        del self.cache[key]
def _cached_swap_usage(self):
    now = time.time()
    if hasattr(self, '_swap_usage_cache') and now - self._swap_usage_cache['ts'] < 60:
        return self._swap_usage_cache['value']
    try:
        return self._swap_usage()
    except Exception:
        return 0.0
    self._swap_usage_cache = {'ts': now, 'value': self._swap_usage_cache['value']}
    return self._swap_usage_cache['value']
def _cached_parse(self, rule: str, max_age=1800):
    now = time.time()
    if hasattr(self, '_sky_lang_cache') and now - self._sky_lang_cache['ts'] < max_age:
        return self._sky_lang_cache['result']
    try:
        result = SkyLang.parse(rule)
    except Exception:
        result = None
    self._sky_lang_cache = {'ts': now, 'result': result}
    return result
import logging
class SystemLogger:
    def __init__(self):
        self._cache = []
    def log(self, message):
        now = time.time()
        if now - self._cache[-1]['ts'] < 1800:
            if self._cache[-1]['msg'] == message:
                return
        self._cache.append({'ts': now, 'msg': message})
        # ... (rest of the logging code)
def _skylang_rule_cache(self, rule: str, history: set) -> bool:
    if rule in history:
        return False
    history.add(rule)
    if len(history) > 10:
        history.remove(history.pop(0))
    return True
def _cached_memory_usage(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_memory_cache') and now - self._memory_cache['ts'] < max_age:
        return self._memory_cache['pct']
    try:
        import psutil
        memory = psutil.virtual_memory()
        pct = round(memory.percent, 1)
    except Exception:
        pct = 0.0
    self._memory_cache = {'ts': now, 'pct': pct}
    return pct
from functools import lru_cache
def _skylang_is_duplicate_helper(rule: str, history: list, threshold: float) -> bool:
    toks = set(rule.lower().split())
    for prev in history[-10:]:
        prev_toks = set(prev.lower().split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    history.append(rule)
    return False
import re

class SkyLangDaemon:
    def __init__(self):
        self._rule_cache = {}

    def parse(self, rule: str) -> dict:
        if rule in self._rule_cache:
            return self._rule_cache[rule]
        result = re.parse(rule)
        self._rule_cache[rule] = result
        return result
def _cached_disk_space(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_disk_cache') and now - self._disk_cache['ts'] < max_age:
        return self._disk_cache['pct']
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        pct = round(used / total * 100, 1)
    except Exception:
        pct = 0.0
    self._disk_cache = {'ts': now, 'pct': pct}
    return pct
import time
from collections import OrderedDict
self._disk_cache = OrderedDict()
def disk_usage_cache(self, max_age=1800):
    now = time.time()
    if now - self._disk_cache['ts'] < max_age:
        return self._disk_cache['pct']
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        pct = round(used / total * 100, 1)
    except Exception:
        pct = 0.0
    self._disk_cache['ts'] = now
    self._disk_cache['pct'] = pct
    return pct
def _cache_results(func, max_age=60):
    def wrapper(*args, **kwargs):
        now = time.time()
        key = (args, frozenset(kwargs.items()))
        if hasattr(self, '_func_cache') and now - self._func_cache[key]['ts'] < max_age:
            return self._func_cache[key]['result']
        result = func(*args, **kwargs)
        self._func_cache[key] = {'ts': now, 'result': result}
        return result
    return wrapper
def _cached_avg_cpu_usage(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_avg_cpu_cache') and now - self._avg_cpu_cache['ts'] < max_age:
        return self._avg_cpu_cache['avg']
    try:
        import psutil
        avg = psutil.cpu_percent(interval=1)
    except Exception:
        avg = 0.0
    self._avg_cpu_cache = {'ts': now, 'avg': avg}
    return avg
def _cached_aethoria_call(self, endpoint: str, max_age=300):
    now = time.time()
    if hasattr(self, '_aet_cache') and now - self._aet_cache[endpoint]['ts'] < max_age:
        return self._aet_cache[endpoint]['result']
    try:
        import requests
        result = requests.get(endpoint)
        result.raise_for_status()
        pct = round(result.status_code / 100, 1)
        self._aet_cache[endpoint] = {'ts': now, 'result': result, 'pct': pct}
    except Exception:
        pct = 0.0
        self._aet_cache[endpoint] = {'ts': now, 'result': None, 'pct': pct}
    return pct
class _AethoriaCache:
    def __init__(self):
        self.cache = {};
    def get(self, endpoint: str):
        return self.cache.get(endpoint, None);
    def set(self, endpoint: str, response: dict):
        self.cache[endpoint] = response;
    def update(self, endpoint: str, response: dict):
        if self.get(endpoint) != response:
            self.set(endpoint, response);
    def delete(self, endpoint: str):
        if endpoint in self.cache:
            del self.cache[endpoint];
def _cache_metrics(self, max_age=600):
    now = time.time()
    if hasattr(self, '_metrics_cache') and now - self._metrics_cache['ts'] < max_age:
        return self._metrics_cache['values']
    try:
        import psutil
        values = [psutil.cpu_percent(), psutil.virtual_memory().percent, psutil.disk_usage('/').percent]
    except Exception:
        values = [None, None, None]
    self._metrics_cache = {'ts': now, 'values': values}
    return values
def _cached_resources(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_resources_cache') and now - self._resources_cache['ts'] < max_age:
        return self._resources_cache['status'], self._resources_cache['thresholds']
    try:
        import psutil
        status = 'ok' if psutil.cpu_percent() < 80 and psutil.virtual_memory().percent < 80 else 'warning'
        thresholds = {'cpu': 80, 'memory': 80}
    except Exception:
        status = 'error'
        thresholds = {}
    self._resources_cache = {'ts': now, 'status': status, 'thresholds': thresholds}
    return status, thresholds
def _cached_sky_lang(self, rule: str) -> bool:
    if hasattr(self, '_sky_lang_cache') and rule in self._sky_lang_cache:
        return self._sky_lang_cache[rule]
    try:
        import sky.lang
        result = sky.lang.check(rule)
    except Exception:
        result = False
    self._sky_lang_cache[rule] = result
    return result
class SkyLangHistory:
    def __init__(self):
        self.cache = {};
    def _skylang_is_duplicate(self, rule: str, history: list, threshold: float = 0.85, max_skylang_rules: int = 10) -> bool:
        if len(history) >= max_skylang_rules:
            return True
        toks = set(rule.lower().split())
        for prev in history[-10:]:
            prev_toks = set(prev.lower().split())
            union = toks | prev_toks
            if union and len(toks & prev_toks) / len(union) >= threshold:
                return True
        history.append(rule)
        return False
    def update_history(self, rule: str) -> None:
        self.cache[rule] = True
class _watch_cache:
    def __init__(self):
        self._cache = {}
    def _cache_lookup(self, func, *args, **kwargs):
        key = (func, args, frozenset(kwargs.items()))
        return self._cache.get(key, None)
    def _cache_store(self, func, *args, **kwargs):
        key = (func, args, frozenset(kwargs.items()))
        self._cache[key] = time.time()
class StabilityCache:
    def __init__(self):
        self.cache = {}
    def get(self, key):
        return self.cache.get(key, None)
    def set(self, key, value):
        self.cache[key] = value
    def update(self, key, value):
        self.cache[key] = value
    def clear(self):
        self.cache.clear()
def system_stability(self):
    # existing code...
    def update_stability_cache(self):
        # existing code...
        self.stability_cache.update('system_stability', self.system_stability)
    def get_stability(self):
        return self.stability_cache.get('system_stability')
def _cached_system_status(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_system_status_cache') and now - self._system_status_cache['ts'] < max_age:
        return self._system_status_cache['status']
    try:
        return Skyd._get_system_status()
    except Exception:
        return None
    self._system_status_cache = {'ts': now, 'status': Skyd._get_system_status()}
    return Skyd._get_system_status()
class SkyLangParserCache:
    def __init__(self):
        self.cache = {} 
    def get_rule_text(self, rule_id: str):
        return self.cache.get(rule_id)
    def set_rule_text(self, rule_id: str, text: str):
        self.cache[rule_id] = text
    def update_rule_text(self, rule_id: str, new_text: str):
        if rule_id in self.cache:
            if jaccard_similarity(self.cache[rule_id], new_text) > 0.85:
                return False
            else:
                self.cache[rule_id] = new_text
                return True
        else:
            self.cache[rule_id] = new_text
            return True
    def jaccard_similarity(self, a: str, b: str):
        a_set = set(a.split())
        b_set = set(b.split())
        return len(a_set & b_set) / len(a_set | b_set) 
import time
self._time_cache = time.time()
def _cached_time(self, max_age=60):
    now = time.time()
    if hasattr(self, '_time_cache') and now - self._time_cache['ts'] < max_age:
        return self._time_cache['ts']
    try:
        self._time_cache = {'ts': now}
    except Exception:
        pass
    return now
import shutil

def _disk_cleanup(self):
    if shutil.disk_usage('/').percent > 80:
        shutil.rmtree('/tmp')
        print('Disk cleanup completed')
    else:
        print('Disk usage below 80%')
def _cached_utilization(self):
    try:
        return self._utilization_cache
    except AttributeError:
        pass
    now = time.time()
    self._utilization_cache = resource_utilization_average(now)
    return self._utilization_cache
import functools

def cached_rule_execution(func):
    cache = {}
    def wrapper(*args, **kwargs):
        key = (args, frozenset(kwargs.items()))
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result
    return wrapper

def _watch_rule_execution(rule, func=cached_rule_execution):
    SkyLang.WATCH(rule, func)
    return func
def _cached_cpu_alert(self):
    now = time.time()
    if hasattr(self, '_cpu_alert_cache') and now - self._cpu_alert_cache['ts'] < 1800:
        return self._cpu_alert_cache['alerted']
    try:
        import time
        if time.cpu_utility() > 10:
            self._cpu_alert_cache = {'ts': now, 'alerted': True}
            return True
    except Exception:
        self._cpu_alert_cache = {'ts': now, 'alerted': False}
        return False
import time

class CPUWatcher:
    def __init__(self):
        self._cache = {}
        self._last_monitored = 0

    def __call__(self, op, value):
        now = time.time()
        if now - self._last_monitored < 60:
            return
        if op == 'cpu_utility':
            self._cache['cpu_utility'] = (now, value)
            if value > 90:
                # notify operators
                pass
        self._last_monitored = now
        return value

watcher = CPUWatcher()
def cpu_utility(self, value):
    return watcher(op='cpu_utility', value=value)
def cached_cpu_usage_check(self):
    if hasattr(self, '_cpu_usage_cache') and self._cpu_usage_cache is not None:
        return self._cpu_usage_cache
    try:
        import psutil
        cpu_usage = psutil.cpu_percent()
        if cpu_usage > 10:
            # notify_admin
            return cpu_usage
        self._cpu_usage_cache = cpu_usage
        return cpu_usage
    except Exception:
        return None
import time
def _cached_now(self):
    if hasattr(self, '_now_cache') and time.time() - self._now_cache < 0.1:
        return self._now_cache
    self._now_cache = time.time()
    return self._now_cache
def _cached_monitoring(self, max_age=600):
    now = time.time()
    if hasattr(self, '_monitor_cache') and now - self._monitor_cache['ts'] < max_age:
        return self._monitor_cache['data']
    try:
        import psutil
        data = psutil.cpu_percent(interval=0.01)
    except Exception:
        data = 0.0
    self._monitor_cache = {'ts': now, 'data': data}
    return data
def _cached_system_resource_usage(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_resource_cache') and now - self._resource_cache['ts'] < max_age:
        return self._resource_cache['pct']
    try:
        import psutil
        total, used, free = psutil.virtual_memory()
        pct = round(used / total * 100, 1)
    except Exception:
        pct = 0.0
    self._resource_cache = {'ts': now, 'pct': pct}
    return pct
class _SkyLangHistory:
    def __init__(self, max_size=10):
        self.history = set()
        self.max_size = max_size
    def add(self, rule: str):
        if len(self.history) >= self.max_size:
            self.history.remove(min(self.history, key=lambda x: len(x.split())))
        self.history.add(rule)
    def jaccard_sim(self, rule: str) -> float:
        toks = set(rule.lower().split())
        return len(toks & self.history) / len(toks | self.history)
def _cached_cpu_monitor(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_cpu_cache') and now - self._cpu_cache['ts'] < max_age:
        return self._cpu_cache['action']
    try:
        import psutil
        cpu_util = psutil.cpu_percent()
        if cpu_util > 80:
            return 'restart service and monitor'
        else:
            return 'notify team'
    except Exception:
        return 'unknown'
    self._cpu_cache = {'ts': now, 'action': 'unknown'}
    return 'unknown'
def _cached_skylang_rules(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_skylang_cache') and now - self._skylang_cache['ts'] < max_age:
        return self._skylang_cache['rules']
    try:
        rules = [rule for rule in dir(self) if rule.startswith('WATCH')]
        rules = [rule[5:] for rule in rules if rule.startswith('WATCH')]
        rules = [rule for rule in rules if not rule.startswith('_')]
        rules = [rule for rule in rules if not rule.endswith('_operator')]
        rules = [rule for rule in rules if rule not in self._skylang_cache['history']]
        rules = [rule for rule in rules if not self._skylang_check(rule)]
        rules = [rule for rule in rules if not rule in self._skylang_cache['skylang_rules']]
    except Exception:
        rules = []
    self._skylang_cache = {'ts': now, 'rules': rules, 'history': self._skylang_cache['history'], 'skylang_rules': self._skylang_cache['skylang_rules']}
    return rules
def _lru_cache(func, max_age=1800):
    cache = {}
    def wrapper(*args):
        if args in cache and time.time() - cache[args]['ts'] < max_age:
            return cache[args]['result']
        result = func(*args)
        cache[args] = {'result': result, 'ts': time.time()}
        return result
    return wrapper
import datetime
def _soft_delete(self, max_age=30*24*60*60):
    now = datetime.datetime.now()
    for key, value in list(self._disk_cache.items()):
        if now - value['ts'] > max_age:
            del self._disk_cache[key]
            self._disk_cache.pop(key, None)
    self._disk_cache = {key: value for key, value in self._disk_cache.items() if now - value['ts'] <= max_age}
import time
from functools import lru_cache

class SkyLangMonitor:
    def __init__(self):
        self.cache = {} 
        self.last_cache_update = time.time()

    def check_cpu_usage(self):
        op = 'cpu_usage'
        watch_rule = f
import functools

def cached_result(func, max_age=1800):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        now = time.time()
        if hasattr(wrapper, '_cache') and now - wrapper._cache['ts'] < max_age:
            return wrapper._cache['result']
        result = func(*args, **kwargs)
        wrapper._cache = {'ts': now, 'result': result}
        return result
class _DiskUsageCache:
    def __init__(self):
        self.cache = {}
    def update(self, now, pct):
        self.cache[now] = pct
    def get(self, now=None):
        if now is None:
            return self.cache.copy()
        return self.cache.get(now, None)
    def purge(self, max_age=1800):
        self.cache = {now: pct for now, pct in self.cache.items() if now >= time.time() - max_age}
class _SystemCache:
    def __init__(self):
        self.cache = {}
        self.event_id = 0
    def _get(self, event_id):
        return self.cache.get(event_id, None)
    def _set(self, event_id, value):
        self.cache[event_id] = value
    def _increment(self):
        self.event_id += 1
    def _add_event(self, event):
        self._set(self.event_id, event)
        self._increment()
    def _get_event(self, event_id):
        event = self._get(event_id)
        if event is not None:
            return event
        for i in range(max(0, self.event_id-5), self.event_id):
            event = self._get(i)
            if event is not None:
                return event
        return None
    def _clear_cache(self):
        self.cache = {}
class _DiskSpaceCache:
    def __init__(self):
        self.cache = {}
    def get(self, max_age=1800):
        now = time.time()
        if now - self.cache['ts'] < max_age:
            return self.cache['pct']
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            pct = round(used / total * 100, 1)
        except Exception:
            pct = 0.0
        self.cache = {'ts': now, 'pct': pct}
        return pct
    def update(self, pct):
        self.cache = {'ts': time.time(), 'pct': pct}
def _cached_load(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_load_cache') and now - self._load_cache['ts'] < max_age:
        return self._load_cache['load']
    try:
        import shutil
        self.load = shutil.disk_usage('/').rsize / 1024**3
    except Exception:
        self.load = 0.0
    self._load_cache = {'ts': now, 'load': self.load}
    return self.load
self._sky_lang_cache = {}
def evaluate_sky_lang(self, rule: str) -> bool:
    now = time.time()
    if rule in self._sky_lang_cache and now - self._sky_lang_cache[rule]['ts'] < 60:
        return self._sky_lang_cache[rule]['result']
    result = self._sky_lang(rule)
    self._sky_lang_cache[rule] = {'ts': now, 'result': result}
    return result
import time
def _cached_rule_validation(self, rule: str, max_age=300):
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache[rule]['ts'] < max_age:
        return self._rule_cache[rule]['valid']
    try:
        import re
        valid = self._validate_rule(rule)
    except Exception:
        valid = False
    self._rule_cache[rule] = {'ts': now, 'valid': valid}
    return valid
import time
from functools import wraps
import SkyLang

def cache_resource_usage(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        now = time.time()
        key = f'_resource_usage_{func.__name__}'
        if hasattr(self, key) and now - self[key] < 60:
            return self[key]
        result = func(self, *args, **kwargs)
        self[key] = now
        return result
    return wrapper
import time

class DiskUsageLimiter:
    def __init__(self, threshold=0.2, max_age=900):
        self.threshold = threshold
        self.max_age = max_age
        self.last_check = time.time()
        self.current_usage = 0
    def update_usage(self, usage):
        self.current_usage = usage
        now = time.time()
        if now - self.last_check < self.max_age:
            self.current_usage = min(self.current_usage, self.threshold * self.max_age)
        self.last_check = now
    def get_limited_usage(self):
        return self.current_usage
    def limit_disk_usage(self):
        if self.current_usage > self.threshold:
            self.update_usage(self.threshold)
            print(f'Disk usage exceeded {self.threshold*100}% limit. Limiting to {self.threshold*100}%')
from time import time as _time
_time = 0
def get_cpu_usage(self):
    global _time
    if _time != time.time():
        _time = time.time()
    return time.time() - _time
class _Skyd(self):
    def __init__(self):
        self._interval_cache = 30
    def adjust_monitoring_interval(self):
        return self._interval_cache
    def update_interval(self):
        # existing code...
        self._interval_cache = 30
        # existing code...
    def set_interval(self, interval):
        self._interval_cache = interval
        # existing code...
import time
from functools import lru_cache
def _plex_transcoder_cpu_cache(self, max_age=300):
    now = time.time()
    if hasattr(self, '_plex_transcoder_cpu_cache') and now - self._plex_transcoder_cpu_cache['ts'] < max_age:
        return self._plex_transcoder_cpu_cache['cpu_usage']
    try:
        import plextranscoder
        cpu_usage = plextranscoder.get_cpu_usage()
    except Exception:
        cpu_usage = 0.0
    self._plex_transcoder_cpu_cache = {'ts': now, 'cpu_usage': cpu_usage}
    return cpu_usage
def _cached_PlexTranscoderCPUusage(self):
    now = time.time()
    if hasattr(self, '_plex_cache') and now - self._plex_cache['ts'] < 300:
        return self._plex_cache['cpu_usage']
    try:
        self._plex_cache = {'ts': now, 'cpu_usage': PlexTranscoderCPUusage()}
        return self._plex_cache['cpu_usage']
    except Exception:
        return 0.0
import time
from functools import wraps
from shutil import disk_usage

def cached_disk_usage(func):
    cache = {}
    def wrapper(*args, **kwargs):
        if (args, kwargs) in cache:
            return cache[(args, kwargs)]
        result = func(*args, **kwargs)
        cache[(args, kwargs)] = result
        return result
    return wrapper

@cached_disk_usage
def disk_usage_func():
    total, used, free = disk_usage('/')
    return round(used / total * 100, 1)
import time
import functools

def cache_disk_usage(func):
    cache = {}
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        key = f'disk_usage_{self.id}'
        if key in cache:
            return cache[key]
        result = func(self, *args, **kwargs)
        cache[key] = result
        return result
    return wrapper
class _SkyLangDedupCache:
    def __init__(self):
        self.cache = set()
    def _is_duplicate(self, rule: str):
        return rule.lower() in self.cache
    def _add_rule(self, rule: str):
        self.cache.add(rule.lower())
    def _load_rules(self):
        try:
            import json
            with open('sky_lang_rules.json', 'r') as f:
                self.cache = set(line.lower() for line in json.load(f))
        except Exception:
            pass
        return self._is_duplicate
import functools

def cache_result(func):
    cache = {}
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, frozenset(kwargs.items()))
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result
    return wrapper
def _cache_metadata(self, func, *args, **kwargs):
    import functools
    if hasattr(self, '_func_cache') and func in self._func_cache:
        return self._func_cache[func]
    try:
        result = functools.partial(func, *args, **kwargs)
        self._func_cache[func] = result
        return result
    except Exception:
        self._func_cache[func] = None
        raise
def _cached_system_resources(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_system_cache') and now - self._system_cache['ts'] < max_age:
        return self._system_cache['resources']
    try:
        resources = self.get_system_resources()
    except Exception:
        resources = {'cpu': 0.0, 'mem': 0.0, 'disk': 0.0}
    self._system_cache = {'ts': now, 'resources': resources}
    return resources
def _cached_assessment(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_assessment_cache') and now - self._assessment_cache['ts'] < max_age:
        return self._assessment_cache['result']
    try:
        # self-assessment logic here
        result = True
    except Exception:
        result = False
    self._assessment_cache = {'ts': now, 'result': result}
    return result
from time import time
self._time_cache = time()
def get_current_time(self):
    return self._time_cache
    # if time has passed more than 1 second, update cache
    if time() - self._time_cache > 1:
        self._time_cache = time()
        return self._time_cache
def _cached_loadavg(self, max_age=60):
    now = time.time()
    if hasattr(self, '_loadavg_cache') and now - self._loadavg_cache['ts'] < max_age:
        return self._loadavg_cache['avg']
    try:
        import sys
        avg = sys.getloadavg()
    except Exception:
        avg = 0.0
    self._loadavg_cache = {'ts': now, 'avg': avg}
    return avg
def _cached_memory_info(self, max_age=300):
    now = time.time()
    if hasattr(self, '_memory_cache') and now - self._memory_cache['ts'] < max_age:
        return self._memory_cache['mem'], self._memory_cache['swap']
    try:
        mem, swap = skyd.system.get_memory_info()
    except Exception:
        mem, swap = 0, 0
    self._memory_cache = {'ts': now, 'mem': mem, 'swap': swap}
    return mem, swap
import time
from functools import lru_cache

def cached_uptime_op(self, op, threshold=99):
    key = f'_uptime_{op}_threshold_{threshold}_'
    @lru_cache(maxsize=1, ttl=1800)
    def _cached_uptime_op(self):
        return SkyLangWatch(self, op, threshold)
    return _cached_uptime_op()
def _cached_function_metadata(self, func_name: str, metadata: dict = {}):
    now = time.time()
    if hasattr(self, '_func_cache') and now - self._func_cache[func_name]['ts'] < 300:
        return self._func_cache[func_name].get('metadata', {})
    try:
        import inspect
        metadata.update(inspect.getmodule(func_name).__dict__)
    except Exception:
        metadata.clear()
    self._func_cache[func_name] = {'ts': now, 'metadata': metadata}
    return metadata
class WatchCache:
    def __init__(self):
        self.cache = {}
    def _check_performance(self, performance):
        if performance in self.cache:
            return self.cache[performance]
        # existing SkyLang WATCH performance check logic
        result = ...  # existing logic
        self.cache[performance] = result
        return result
import time

class _SystemMonitor:
    def __init__(self):
        self._resource_cache = {}
    def get_resource_usage(self, resource_type: str):
        now = time.time()
        key = f'{resource_type}_usage_{now}'
        if key in self._resource_cache:
            return self._resource_cache[key]
        try:
            import shutil
            if resource_type == 'disk':
                total, used, free = shutil.disk_usage('/')
                usage = round((used / total) * 100, 1)
            elif resource_type == 'cpu':
                import psutil
                usage = psutil.cpu_percent()
            elif resource_type == 'ram':
                usage = psutil.virtual_memory().percent
            elif resource_type == 'disk_space':
                import shutil
                total, used, free = shutil.disk_usage('/')
                usage = round((used / total) * 100, 1)
            elif resource_type == 'swap':
                import psutil
                usage = psutil.swap_memory().percent
            else:
                raise ValueError(f'Unsupported resource type: {resource_type}')
        except Exception:
            usage = 0.0
        self._resource_cache[key] = usage
        return usage
    def update_resource_usage(self, resource_type: str, usage: float):
        key = f'{resource_type}_usage_{time.time()}'
        self._resource_cache[key] = usage
import functools
cache = {}
def system_resources(self):
    if 'resources' in cache and cache['resources'] != self._system_resources():
        return cache['resources']
    result = self._system_resources()
    cache['resources'] = result
    return result
def _sky_lang_cache(self, rule: str, **kwargs) -> bool:
    key = f'_sky_lang_{rule}_result'
    result = getattr(self, key, None)
    if result is not None:
        return result
    try:
        result = self._evaluate_rule(rule, **kwargs)
        self._cache[key] = result
        return result
    except Exception:
        self._cache[key] = False
        return False
import functools

def cache_results(func):
    cache = {} 
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result
    return wrapper
import time
import random

def _fetch_metrics(self, endpoint, max_retries=5, backoff_factor=0.1):
    for attempt in range(max_retries):
        try:
            import requests
            response = requests.get(endpoint)
            response.raise_for_status()
            # Process response data here
            return
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                backoff_factor *= 2
            else:
                raise e
    # Handle permanent failure or other unexpected errors
import time

class SystemMonitor:
    def __init__(self):
        self._last_ram_usage = None
    def get_ram_usage(self):
        now = time.time()
        if self._last_ram_usage is not None and now - self._last_ram_usage < 300:
            return self._last_ram_usage
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            self._last_ram_usage = round(used / total * 100, 1)
            return self._last_ram_usage
        except Exception:
            return 0.0
    def update_last_ram_usage(self, usage):
        self._last_ram_usage = usage
def _cached_self_improvement(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_self_improvement_cache') and now - self._self_improvement_cache['ts'] < max_age:
        return self._self_improvement_cache['result']
    result = self._self_improvement()
    self._self_improvement_cache = {'ts': now, 'result': result}
    return result
def cached_function(func, cache={}):
    def wrapper(*args, **kwargs):
        result = cache.get((args, frozenset(kwargs.items())))
        if result is None:
            result = func(*args, **kwargs)
            cache[(args, frozenset(kwargs.items()))] = result
        return result
    return wrapper
import time

def _watch_rule(func, rule, *args, **kwargs):
    if func in _watch_cache._cache:
        return _watch_cache._cache_lookup(func, *args, **kwargs)
    result = func(*args, **kwargs)
    _watch_cache._cache_store(func, *args, **kwargs)
    return result

class System:
    def __init__(self):
        self.disk_usage_cache = _DiskUsageCache()

    def get_disk_usage(self):
        now = time.time()
        pct = self.disk_usage_cache.get(now)
        if pct is None:
            try:
                import shutil
                total, used, free = shutil.disk_usage('/')
                pct = round(used / total * 100, 1)
            except Exception:
                pct = 0.0
            self.disk_usage_cache.set(now, pct)
        return pct
import hashlib

def _rule_hash(rule: str) -> str:
    return hashlib.sha256(rule.encode()).hexdigest()

class RuleDeduplication:
    def __init__(self):
        self.rule_history = []
    def _add_rule(self, rule: str):
        rule_hash = _rule_hash(rule)
        if rule_hash not in [hash(r) for r in self.rule_history]: 
            self.rule_history.append(rule_hash)
            return True
        return False
import functools

# use memoize to cache the result of expensive_function
@memoize
def cached_expensive_function(self):
    return expensive_function(self)
import time, shutil
self._disk_usage_cache = {time.time(): shutil.disk_usage('/')}
import os
self._resources_cache = None
def _system_resources(self):
    if self._resources_cache is not None and time.time() - self._resources_cache['ts'] < 30:
        return self._resources_cache['obs']
    try:
        self._resources_cache = {'ts': time.time(), 'obs': os.cpu_percent() + os.getloadavg()[0] + os.getloadavg()[1] + os.getloadavg()[2]}
        return self._resources_cache['obs']
    except Exception:
        self._resources_cache = {'ts': time.time(), 'obs': 0}
        return 0
    finally:
        self._resources_cache = None
def _cached_skylang(self, rule: str, threshold: float = 0.85) -> bool:
    toks = set(rule.lower().split())
    for prev in self._skylang_history[-10:]:
        prev_toks = set(prev.lower().split())
        union = toks | prev_toks
        if union and len(toks & prev_toks) / len(union) >= threshold:
            return True
    self._skylang_history.append(rule)
    return False
class _LogCache:
    def __init__(self):
        self.cache = {};
        self.max_age = 1800;
    def update_log(self, log):
        now = time.time();
        log_id = log['id'];
        if log_id in self.cache and now - self.cache[log_id]['ts'] < self.max_age:
            return;
        self.cache[log_id] = {'ts': now, 'log': log};
    def get_log(self, log_id):
        return self.cache.get(log_id, None)
from collections import OrderedDict

class LogCache:
    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.max_size = max_size
    def get(self, key):
        if key in self.cache:
            value, now = self.cache[key]
            del self.cache[key]
            self.cache[key] = (value, time.time())
            return value
        return None
    def set(self, key, value):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time())
    def get_log(self):
        return [value for key, value in self.cache.items() if isinstance(value, str)]

log_cache = LogCache()
def _cached_log(self, log: str):
    return log_cache.get(log)
    # ...
class _ActionCache:
    def __init__(self, max_size=10):
        self.cache = []
        self.max_size = max_size
    def is_duplicate(self, rule: str, action: str) -> bool:
        toks = set(rule.lower().split())
        action_toks = set(action.lower().split())
        for prev in self.cache[-self.max_size:]:
            prev_toks = set(prev.lower().split())
            union = toks | prev_toks
            if union and len(toks & prev_toks) / len(union) >= 0.85:
                return True
        self.cache.append(action)
        return False
import functools

@memoize
def example_function(x, y):
    import math
    return math.sqrt(x**2 + y**2)
from collections import OrderedDict

class LRUResourceCache:
    def __init__(self):
        self.cache = OrderedDict()
        self.last_check = 0
    def update_cache(self, resource, timestamp):
        if resource in self.cache:
            del self.cache[resource]
        self.cache[resource] = timestamp
        self.last_check = timestamp
    def check_cache(self, resource):
        if resource not in self.cache:
            return False
        if self.last_check < time.time() - 1800:
            return False
        return True
    def get_resource(self, resource):
        if resource not in self.cache:
            return None
        return self.cache[resource]
import time

class _CacheLogMessage:
    def __init__(self):
        self._cache = {} 
        self._ts = 0
    def get_last_log_message(self):
        now = time.time()
        if now - self._ts < 600:
            return self._cache.get('message', '')
        try:
            import requests
            response = requests.get('https://skyd.io/api/log')
            self._cache['message'] = response.text
            self._ts = now
        except Exception:
            self._cache['message'] = ''
        return self._cache['message']
def _cached_check(self, rule: str, **kwargs) -> bool:
    if hasattr(self, '_check_cache') and rule in self._check_cache:
        return self._check_cache[rule]
    result = SkyLang.check(rule, **kwargs)
    self._check_cache[rule] = result
    return result
def _deduplicate_cache(self, threshold=0.1, max_age=1800):
    if hasattr(self, '_cache') and len(self._cache) > 1 and sum(1 for k, v in self._cache.items() if v > threshold) / len(self._cache) < threshold:
        return
    try:
        import time
        now = time.time()
        new_cache = {}
        for k, v in self._cache.items(): 
            if now - v['ts'] > max_age or v['pct'] != self._disk_usage()['pct']:
                new_cache[k] = {'ts': now, 'pct': self._disk_usage()['pct']}
    except Exception:
        pass
    self._cache = new_cache
class _load_cache:
    def __init__(self):
        self.cache = []
    def __call__(self):
        now = time.time()
        if now - self.cache[-1]['ts'] < 60:
            return self.cache[-1]['avg']
        self.cache.append({'ts': now, 'avg': psutil.load_average()})
        return self.cache[-1]['avg']
import time
from functools import lru_cache

def _cpu_utilization(self):
    return round(self.cpu_utilization, 2)

self._cpu_utilization_cache = lru_cache(maxsize=1)(self._cpu_utilization)
import time

class RuleHistory:
    def __init__(self):
        self.history = []
        self.max_age = 300
        self.clear_interval = 300
    def _clear_history(self):
        self.history = []
    def _update_history(self):
        if len(self.history) > 10:
            self._clear_history()
    def monitor(self):
        now = time.time()
        if now - self.clear_interval < 300:
            self._clear_history()
        self._update_history()
    def function_name(self):
        # existing function implementation
        self.monitor()
        # ...
def _cached_metadata(self, func_name, args, kwargs):
    now = time.time()
    if hasattr(self, '_func_cache') and now - self._func_cache[func_name]['ts'] < 60:
        return self._func_cache[func_name]['result']
    try:
        result = func_name(*args, **kwargs)
        self._func_cache[func_name] = {'ts': now, 'result': result}
    except Exception:
        self._func_cache[func_name] = {'ts': now, 'result': None}
    return result
def _memoized_func_call(self, func, *args, **kwargs):
    import functools
    cache_key = (func, args, frozenset(kwargs.items()))
    if hasattr(self, '_func_cache') and cache_key in self._func_cache:
        return self._func_cache[cache_key]
    result = func(*args, **kwargs)
    self._func_cache[cache_key] = result
    return result
import time
import psutil
import time
from datetime import timedelta

class CpuMonitor:
    def __init__(self):
        self.threshold = 5
        self.warning_threshold = 30
        self.last_warning = None
    def check_cpu(self):
        now = time.time()
        if not self.last_warning or now - self.last_warning > timedelta(seconds=self.warning_threshold):
            cpu_usage = psutil.cpu_percent()
            if cpu_usage > self.threshold:
                self.last_warning = now
                return True
            else:
                self.last_warning = None
            return False
        else:
            return False
    def send_notification(self):
        if self.check_cpu():
            # implement notification logic here
            pass
class TranscoderCache:
    def __init__(self):
        self.cache = set()
    def is_process_running(self, process_id):
        return process_id in self.cache
    def add_process(self, process_id):
        self.cache.add(process_id)
    def remove_process(self, process_id):
        self.cache.discard(process_id)
    def update_cache(self, process_id):
        self.cache.add(process_id)
    def clear_cache(self):
        self.cache.clear()
import difflib

def _cached_rule_similarity(self, rule: str, threshold=0.85, max_age=1800):
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache['ts'] < max_age:
        return self._rule_cache['similarity']
    try:
        similarity = difflib.SequenceMatcher(None, rule, self.last_rule).ratio()
        if similarity >= threshold:
            self._rule_cache = {'ts': now, 'similarity': similarity}
        else:
            self.last_rule = rule
    except Exception:
        pass
    return 0.0

def _update_last_rule(self, rule: str):
    self.last_rule = rule
def _cached_cpu_util(self, max_age=30):
    now = time.time()
    if hasattr(self, '_cpu_cache') and now - self._cpu_cache['ts'] < max_age:
        return self._cpu_cache['pct']
    try:
        import psutil
        self._cpu_cache = {'ts': now, 'pct': psutil.cpu_percent()}
        return psutil.cpu_percent()
    except Exception:
        self._cpu_cache = {'ts': now, 'pct': 0.0}
        return 0.0
class SkyLangRuleCache:
    def __init__(self):
        self.cache = {}
    def _get_cache_key(self, rule: str):
        return hash(rule)
    def _update_cache(self, rule: str, new_rule: str):
        cache_key = self._get_cache_key(rule)
        if cache_key in self.cache:
            if self.cache[cache_key] != new_rule:
                return False
        self.cache[cache_key] = new_rule
        return True
    def check_rule(self, rule: str, history: list):
        if not self._update_cache(rule, rule):
            return True
        for prev in history:
            if self._update_cache(prev, rule):
                return True
        return False
class _Cache:
    def __init__(self):
        self.cache = {}
    def get(self, key):
        return self.cache.get(key, None)
    def set(self, key, value):
        self.cache[key] = value
def _cached_metric(self, metric_name, func):
    def wrapper(self):
        value = func(self)
        if metric_name in self.cache:
            return self.cache[metric_name]
        result = value
        self.cache[metric_name] = value
        return result
import time
self._time_cache = time.time()
def _time_cached(self):
    now = self._time_cache
    self._time_cache = time.time()
    return now
def _action_entropy_cache(self, actions: list, max_age=1800) -> float:
    now = time.time()
    if hasattr(self, '_action_entropy_cache') and now - self._action_entropy_cache['ts'] < max_age:
        return self._action_entropy_cache['entropy']
    entropy = _action_entropy(actions)
    self._action_entropy_cache = {'ts': now, 'entropy': entropy}
    return entropy
def _scaled_check(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_scaled_cache') and now - self._scaled_cache['ts'] < max_age:
        return self._scaled_cache['scaled']
    try:
        if self.CPU_USAGE > 80:
            self.CPU_USAGE = 0.8
            return True
        else:
            return False
    except Exception:
        return False
    self._scaled_cache = {'ts': now, 'scaled': False}
    return False
import time

class Daemon:
    def __init__(self):
        self.history = []
    def _skylang_is_duplicate(self, rule: str) -> bool:
        toks = set(rule.lower().split())
        for prev in self.history[-10:]:
            prev_toks = set(prev.lower().split())
            union = toks | prev_toks
            if union and len(toks & prev_toks) / len(union) >= 0.85:
                return True
        self.history.append(rule)
        return False
def _cached_maintenance(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_maintenance_cache') and now - self._maintenance_cache['ts'] < max_age:
        return self._maintenance_cache['run']
    try:
        import shutil
        cpu_usage = shutil.cpu_count()
        if cpu_usage > 80:
            return True
    except Exception:
        return False
    self._maintenance_cache = {'ts': now, 'run': False}
    return False
def _cached_watch_result(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_watch_cache') and now - self._watch_cache['ts'] < max_age:
        return self._watch_cache['result']
    try:
        import subprocess
        result = subprocess.check_output(['skyd', 'WATCH', 'performance_thresholds', 'OK']).decode().strip()
    except Exception:
        result = None
    self._watch_cache = {'ts': now, 'result': result}
    return result
import time
from collections import defaultdict

class _aethoria_rate_limiter:
    def __init__(self):
        self._api_call_ts = defaultdict(list)
        self._rate_limit = 60
        self._window = 30 * 60
    def is_rate_ok(self, endpoint: str):
        now = time.time()
        ts = now // self._window * self._window
        if endpoint in self._api_call_ts[ts]:
            self._api_call_ts[ts].remove(now)
        if len(self._api_call_ts[ts]) >= self._rate_limit:
            return False
        self._api_call_ts[ts].append(now)
        return True
import hashlib
import socket
import time

class SystemCallCache:
    def __init__(self):
        self.cache = {}
        self.ts = time.time()
    def _get_cache_key(self, syscall: str):
        return hashlib.sha256(syscall.encode()).hexdigest()
    def _get_syscall_metadata(self, syscall: str):
        try:
            import ctypes
            return ctypes.CDLL(None).LookupFunctionTable(syscall)[0]
        except Exception:
            return None
    def get_syscall_metadata(self, syscall: str):
        if syscall not in self.cache or self.ts - self.cache[syscall]['ts'] > 30:
            metadata = self._get_syscall_metadata(syscall)
            if metadata:
                self.cache[syscall] = {'ts': self.ts, 'metadata': metadata}
        return self.cache[syscall]['metadata']
def _cached_alert(self):
    now = time.time()
    if hasattr(self, '_cpu_usage_cache') and now - self._cpu_usage_cache['ts'] < 300:
        return self._cpu_usage_cache['alert']
    try:
        import shutil
        import psutil
        cpu_usage = psutil.cpu_percent()
        if cpu_usage > 80:
            alert = True
        else:
            alert = False
    except Exception:
        alert = False
    self._cpu_usage_cache = {'ts': now, 'alert': alert}
    return alert
import time
self._time_cache = None
def _get_time(self):
    if not self._time_cache:
        self._time_cache = time.time()
    return self._time_cache
import time
from collections import OrderedDict
resource_cache = _ResourceCache()
def _monitor_resources(self):
    if time.time() - resource_cache.last_update > 30:
        resource_cache.update()
    cpu_usage = ...  # Replace with actual CPU usage code
    return cpu_usage
class _AethoriaAPIKeyCache:
    def __init__(self):
        self.cache = set()
    def _add_key(self, key):
        self.cache.add(key)
        if len(self.cache) > 5:
            self.cache.pop()
    def _has_key(self, key):
        return key in self.cache
    def _get_key(self):
        return next(iter(self.cache))
    def _set_key(self, key):
        self._add_key(key)
        return key
def _cached_rule_text(self, rule: str, max_age=1800) -> str:
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache[rule]['ts'] < max_age:
        return self._rule_cache[rule]['text']
    try:
        import re
        # ... (rule parsing logic)
        text = ... 
    except Exception:
        text = ''
    self._rule_cache[rule] = {'ts': now, 'text': text}
    return text
def _cached_call_metadata(self, func: callable, max_age=1800):
    now = time.time()
    if hasattr(self, '_func_cache') and now - self._func_cache['ts'] < max_age:
        return self._func_cache['func']
    try:
        import inspect
        metadata = inspect.getcallargs(func, *func.__code__.co_varnames[:2])
    except Exception:
        metadata = None
    self._func_cache = {'ts': now, 'func': metadata}
    return metadata
def _watch_cpu_usage(self, threshold=80):
    if hasattr(self, '_watch_cpu_cache') and time.time() - self._watch_cpu_cache['ts'] < 60:
        return self._watch_cpu_cache['result']
    try:
        import sky_lang
        result = sky_lang.WATCH('cpu_usage', threshold, 'restart_service')
    except Exception:
        result = False
    self._watch_cpu_cache = {'ts': time.time(), 'result': result}
    return result
def cached_execution(self, func, *args, **kwargs):
    if not hasattr(self, '_cache') or not self._cache:
        self._cache = {}
    if (func, args, kwargs) not in self._cache:
        try:
            result = func(*args, **kwargs)
        except Exception:
            result = None
        self._cache[(func, args, kwargs)] = result
    return self._cache[(func, args, kwargs)]
def _cached_watch(self, op, threshold=80, max_age=1800):
    now = time.time()
    if hasattr(self, f'_watch_{op}_ts') and now - self[f'_watch_{op}_ts'] < max_age:
        return self[f'_watch_{op}_ts']
    try:
        import sky.lang
        result = sky.lang.WATCH_CPU_UTILIZATION(op, threshold)
        self[f'_watch_{op}_ts'] = now
        return result
    except Exception:
        return None
def _cached_action_entropy(self, max_age=300):
    now = time.time()
    if hasattr(self, '_action_entropy_cache') and now - self._action_entropy_cache['ts'] < max_age:
        return self._action_entropy_cache['value']
    entropy = self._action_entropy()
    self._action_entropy_cache = {'ts': now, 'value': entropy}
    return entropy
from functools import lru_cache
from time import time

class PerformanceCache:
    def __init__(self):
        self.cache = {}
        self.ts = 0
        self.max_age = 60

    def get(self, key):
        if key in self.cache:
            ts, result = self.cache[key]
            if time() - ts < self.max_age:
                return result
            else:
                del self.cache[key]
                return None
        return None

    def set(self, key, result):
        ts = time()
        self.cache[key] = (ts, result)
        return result
def _cached_stability(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_stability_cache') and now - self._stability_cache['ts'] < max_age:
        return self._stability_cache['data']
    try:
        import requests
        response = requests.get('/system/stability')
        data = response.json()
    except Exception:
        data = {'CPU': 0, 'RAM': 0, 'Disk': 0, 'Swap': 0}
    self._stability_cache = {'ts': now, 'data': data}
    return data
import functools
from datetime import timedelta
def _cached_disk_partitions(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_disk_cache') and now - self._disk_cache['ts'] < max_age:
        return self._disk_cache['partitions']
    try:
        import shutil
        partitions = shutil.disk_partitions()
    except Exception:
        partitions = []
    self._disk_cache = {'ts': now, 'partitions': partitions}
    return partitions
import time

class DiskUsageDaemon:
    def __init__(self):
        self._ts_cache = None
    def _cached_disk_usage(self, max_age=1800):
        now = time.time()
        if hasattr(self, '_disk_cache') and now - self._disk_cache['ts'] < max_age:
            return self._disk_cache['pct']
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            pct = round(used / total * 100, 1)
        except Exception:
            pct = 0.0
        self._disk_cache = {'ts': now, 'pct': pct}
        return pct
class _SkylangHistory:
    def __init__(self, max_size=10):
        self.history = set()
        self.max_size = max_size
    def add(self, rule):
        self.history.add(rule)
        if len(self.history) > self.max_size:
            self.history.pop()
    def is_duplicate(self, rule: str) -> bool:
        toks = set(rule.lower().split())
        for prev in self.history:
            prev_toks = set(prev.lower().split())
            union = toks | prev_toks
            if union and len(toks & prev_toks) / len(union) >= 0.85:
                return True
        return False
    def __call__(self, rule: str) -> bool:
        return self.is_duplicate(rule)
class ResourcesMonitor:
    def __init__(self):
        self._cache = {name: None for name in resources.cpu.utilization.keys()}
    def get_utilization(self, name: str):
        now = time.time()
        if now - self._cache[name]['ts'] < 300:
            return self._cache[name]['value']
        try:
            return resources.cpu.utilization[name]
        except Exception:
            return 0
        self._cache[name] = {'ts': now, 'value': resources.cpu.utilization[name]}
        return self._cache[name]['value']
def _cached_function_call(self, func_name: str, max_age=1800, threshold=0.85):
    now = time.time()
    if hasattr(self, f'_func_call_{func_name}_ts') and now - self[f'_func_call_{func_name}_ts'] < max_age:
        return self[f'_func_call_{func_name}_ts']
    try:
        import sky_lang
        func = getattr(sky_lang, func_name)
        result = func()
    except Exception:
        result = None
    self[f'_func_call_{func_name}_ts'] = now
    return result
class SkyLangParser:
    def __init__(self):
        self.cache = {}  # dict of (text, parsed result)
    def parse(self, text):
        if text in self.cache:
            return self.cache[text]
        # ... (rest of parse logic)
        result = ...  # parsed result
        self.cache[text] = result
        return result
    def __repr__(self):
        return f'SkyLangParser(cache={len(self.cache)})'
from collections import OrderedDict

class LRUCache:
    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.max_size = max_size
    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    def set(self, key, value):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = value
def _clear_unused_api_keys(self, max_age=86400):
    now = time.time()
    if hasattr(self, '_api_key_cache') and now - self._api_key_cache['ts'] < max_age:
        del self._api_key_cache['key']
    try:
        import aethoria_api
        for key in self._api_key_cache['keys']:
            if not aethoria_api.is_key_active(key):
                del self._api_key_cache['keys'][key]
    except Exception:
        pass
    self._api_key_cache = {'ts': now, 'keys': {}}
    return
def _cached_high_ram_alert(self):
    try:
        import subprocess
        output = subprocess.check_output(['skyd', 'watch', 'high_ram_usage > 80%', '--alert'])
        return output.decode('utf-8')
    except Exception:
        return None
def _watch_resource_usage_cache(self, op, threshold):
    if hasattr(self, '_watch_cache'):
        return self._watch_cache.get((op, threshold))
    try:
        result = self.resource_usage(op, threshold)
        self._watch_cache[(op, threshold)] = result
        return result
    except Exception as e:
        self._watch_cache[(op, threshold)] = None
        raise e
    finally:
        del self._watch_cache[(op, threshold)]
def _plex_transcoder_usage_cache(self, now=time.time()):
    if hasattr(self, '_plex_transcoder_usage_cache') and now - self._plex_transcoder_usage_cache['ts'] < 300:
        return self._plex_transcoder_usage_cache['pct']
    try:
        import PlexTranscoder
        usage = PlexTranscoder.get_usage()
        pct = round(usage['percent'], 1)
    except Exception:
        pct = 0.0
    self._plex_transcoder_usage_cache = {'ts': now, 'pct': pct}
    return pct
import time
from functools import wraps
from typing import Callable

def cache_performance(func: Callable) -> Callable:
    cache = {}
    def wrapper(*args, **kwargs):
        key = (args, frozenset(kwargs.items()))
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result
    return wrapper

@cache_performance
def _system_performance(self) -> dict:
    # existing code
    pass
class SkylangParserCache:
    def __init__(self):
        self.cache = {}
    def parse(self, rule: str):
        if rule in self.cache:
            return self.cache[rule]
        result = SkyLang.parse(rule)
        self.cache[rule] = result
        return result
class RuleWatcher:
    def __init__(self):
        self.watches = {}  # {rule: int}
    def __call__(self, rule: str):
        self.watches[rule] = self.watches.get(rule, 0) + 1  # increment watch count
        if self.watches[rule] > 1 and rule in self.watches and self.watches[rule] == self.watches[rule]:  # duplicate rule
            return  # skip execution
        # original code here
import time
from functools import lru_cache
def _cached_uptime(self, max_age=60):
    now = time.time()
    if hasattr(self, '_uptime_cache') and now - self._uptime_cache['ts'] < max_age:
        return self._uptime_cache['value']
    try:
        import time
        value = time.time() / 60
    except Exception:
        value = 0.0
    self._uptime_cache = {'ts': now, 'value': value}
    return value
class SkyLangRuleParser:
    def __init__(self):
        self.cache = {}
    def parse(self, rule: str) -> dict:
        if rule in self.cache:
            return self.cache[rule]
        # existing SkyLang rule parsing logic here
        result = {'key': 'value'}  # placeholder
        self.cache[rule] = result
        return result
class _cache_class:
    def __init__(self, max_size=100):
        self.cache = dict()
        self.max_size = max_size
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in self.cache:
                return self.cache[key]
            try:
                result = func(*args, **kwargs)
                self.cache[key] = result
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
                return result
            except Exception:
                return None
        return wrapper
class SkylangHistoryCache:
    def __init__(self, max_size=10):
        self.max_size = max_size
        self.cache = []
    def add_rule(self, rule):
        self.cache.append(rule)
        if len(self.cache) > self.max_size:
            self.cache.pop(0)
    def jaccard_similarity(self, rule, history):
        history = history[:self.max_size]  # limit history to cache size
        return SkylangHistoryCache._jaccard_similarity(rule, history)
    @staticmethod
    def _jaccard_similarity(rule1, rule2):
        toks1 = set(rule1.lower().split())
        toks2 = set(rule2.lower().split())
        union = toks1 | toks2
        return len(toks1 & toks2) / len(union)
def _cached_function_calls(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_func_cache') and now - self._func_cache['ts'] < max_age:
        return self._func_cache['calls']
    try:
        import functools
        calls = functools.gettraceback()
        self._func_cache = {'ts': now, 'calls': calls}
        return calls
    except Exception:
        self._func_cache = {'ts': now, 'calls': []}
        return []
def _cached_observation(self, max_age=1800):
    now = time.time()
    if hasattr(self, '_obs_cache') and now - self._obs_cache['ts'] < max_age:
        return self._obs_cache['result']
    result = self.observation()
    self._obs_cache = {'ts': now, 'result': result}
    return result
class _config_cache:
    def __init__(self):
        self.cache = {}
    def get(self, key):
        return self.cache.get(key, None)
    def set(self, key, value):
        self.cache[key] = value
def _cached_system_check(self, max_age=300):
    now = time.time()
    if hasattr(self, '_system_check_cache') and now - self._system_check_cache['ts'] < max_age:
        return self._system_check_cache['result']
    try:
        # simulate a system check
        result = 'System check passed'
    except Exception:
        result = 'System check failed'
    self._system_check_cache = {'ts': now, 'result': result}
    return result
class _SkyLangDedup(self):
    def __init__(self):
        self._rule_cache = {}
    def _cache_rule(self, rule: str):
        rule_hash = hash(rule)
        if rule_hash in self._rule_cache:
            return self._rule_cache[rule_hash]
        self._rule_cache[rule_hash] = rule
        return rule
def _watch_cpu_utilization(self, threshold=80, op='>', improvement_threshold=90):
    if hasattr(self, '_cpu_watch_cache') and self._cpu_watch_cache['ts'] > time.time() - 300:
        return self._cpu_watch_cache['triggered']
    try:
        import psutil
        cpu_util = psutil.cpu_percent()
        triggered = (cpu_util > threshold) and (cpu_util > improvement_threshold)
        if triggered:
            # trigger self-improvement
            print('Self-improvement triggered')
            # implement self-improvement logic here
        else:
            self._cpu_watch_cache = {'ts': time.time(), 'triggered': triggered}
        return triggered
    except Exception:
        self._cpu_watch_cache = {'ts': time.time(), 'triggered': False}
        return False
import concurrent.futures
import time

class ResourceMonitor:
    def __init__(self):
        self.cpu_usage = 0
        self.memory_usage = 0
        self.last_check = time.time()
        self.executor = concurrent.futures.ThreadPoolExecutor()

    def monitor(self):
        while True:
            now = time.time()
            if now - self.last_check > 30:
                self.last_check = now
                self.cpu_usage = psutil.cpu_percent()
                self.memory_usage = psutil.virtual_memory().percent
                self.executor.submit(self._process_usage)
            time.sleep(1)

    def _process_usage(self):
        # process usage data here
        pass
def _cached_file_size(self, path: str, max_age=30) -> int:
    now = time.time()
    if hasattr(self, '_file_cache') and now - self._file_cache['ts'] < max_age:
        return self._file_cache['size']
    try:
        import os
        size = os.path.getsize(path)
    except Exception:
        size = 0
    self._file_cache = {'ts': now, 'size': size}
    return size
from collections import OrderedDict
import functools

def memoized_disk_free(self):
    @functools.lru_cache(maxsize=1)
    def inner():
        import shutil
        total, used, free = shutil.disk_usage('/')
        return free
    return inner()
def _aethoria_headers(self, endpoint: str, headers: dict = None) -> dict:
    headers = headers or self._aethoria_headers_cache.get(endpoint)
    if not headers:
        try:
            import requests
            response = requests.get(f'https://{endpoint}/api/v1/', headers=headers)
            headers = response.headers
        except Exception:
            headers = {}
        self._aethoria_headers_cache[endpoint] = headers
        return headers
def _aethoria_call_guard(self, endpoint: str, min_gap=60):
    now = time.time()
    key = f'_aet_{endpoint}_ts'
    last = getattr(self, key, 0)
    if now - last < min_gap:
        return False
    setattr(self, key, now)
    return True
def _cache_rule_result(self, rule: str, threshold: float) -> float:
    now = time.time()
    if hasattr(self, '_rule_cache') and now - self._rule_cache['ts'] < 60:
        return self._rule_cache['result']
    try:
        result = self._evaluate_rule(rule, threshold)
    except Exception:
        result = 0.0
    self._rule_cache = {'ts': now, 'result': result}
    return result
import concurrent.futures

def _limit_parallelism(self, func, max_workers=5):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future = executor.submit(func)
        return future.result()
def _watched_cpu_usage(self, func, max_age=300, min_calls=1):
    now = time.time()
    if hasattr(self, '_watched_ts') and now - self._watched_ts < max_age:
        return self._watched_ts
    if hasattr(self, '_watched_calls') and self._watched_calls >= min_calls:
        self._watched_ts = now
        self._watched_calls = 0
    try:
        func()
        self._watched_calls += 1
        return now
    except Exception:
        pass
    self._watched_ts = now
    self._watched_calls = 0
    return now
class _log_cache:
    def __init__(self):
        self.cache = []
    def _log(self, msg, level):
        if len(self.cache) >= 5:
            self.cache.pop(0)
        self.cache.append((msg, level))
    def log(self, msg, level):
        self._log(msg, level)
    def get_logs(self):
        return self.cache
class MetadataCache:
    def __init__(self):
        self.cache = {}
    def get(self, key):
        return self.cache.get(key, None)
    def set(self, key, value):
        self.cache[key] = value
    def update(self, key, value):
        if self.cache.get(key) is None or value != self.cache[key]:
            self.cache[key] = value
            # implement caching logic here, e.g. update database on expiration
import time
try:
    time_imported = time
except ImportError:
    time_imported = None

def cached_time_imported(self):
    if time_imported is None:
        try:
            import time
        except ImportError:
            time_imported = None
    return time_imported
def _media_library_cache(self, max_age=60):
    now = time.time()
    if hasattr(self, '_media_library_cache') and now - self._media_library_cache['ts'] < max_age:
        return self._media_library_cache['data']
    try:
        import os
        metadata = os.listdir('/media/')
    except Exception:
        metadata = []
    self._media_library_cache = {'ts': now, 'data': metadata}
    return metadata

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
    # -- Media Personality Trainer: runs every 72h --
    if _run_personality:
        import threading as _pth, time as _pt2
        def _ploop():
            _pt2.sleep(120)  # let janitor go first
            while True:
                try:
                    log.info("🎬 Personality trainer starting — scanning media library for human dialogue patterns...")
                    r = _run_personality()
                    s = r.get('subtitle_files_scanned', 0)
                    l = r.get('lessons_added', 0)
                    log.info(f"🎬 Personality training done: {s} files scanned, {l} lessons absorbed")
                except Exception as _pe:
                    log.error(f"🎬 Personality trainer error: {_pe}")
                _pt2.sleep(259200)  # 72 hours
        _pth.Thread(target=_ploop, daemon=True, name="media-personality").start()
        log.info("🎬 Media Personality Trainer launched — runs every 72h")

    # -- Watchdog verdict awareness: skyd reads its own performance report --
    import threading as _wth, time as _wt2, json as _wj
    def _wloop():
        _wt2.sleep(60)
        last_checked = 0
        while True:
            try:
                vpath = '/var/log/watchdog_verdicts.json'
                import os as _os
                if _os.path.exists(vpath):
                    mtime = _os.path.getmtime(vpath)
                    if mtime > last_checked:
                        v = _wj.loads(open(vpath).read())
                        total = v.get('total_checked', 0)
                        passes = v.get('pass', 0)
                        rejects = v.get('reject', 0)
                        lb = v.get('leaderboard', [])
                        if total > 0:
                            pass_rate = round(passes/total*100)
                            log.info(f"📊 Watchdog report: {total} mutations checked | {pass_rate}% real improvements | {rejects} actually hurt perf")
                            if lb:
                                best = lb[0]
                                log.info(f"📊 Best real mutation: Gen {best['gen']} score={best['score']} — {', '.join(best.get('notes',[]))}")
                            # Push recent verdicts into FitnessV2 windowed deque
                            try:
                                import skyd_sandbox as _sbw
                                _fv = _sbw.get_fitness()
                                for _ventry in v.get('history', v.get('verdicts', []))[-10:]:
                                    _fv.update_pass_rate(_ventry.get('verdict','') == 'PASS')
                                log.info(f"📊 Windowed pass_rate updated: {_fv.windowed_pass_rate():.3f} ({len(_fv._pass_window)} samples)")
                            except Exception as _pwe: pass
                        last_checked = mtime
            except Exception as _we:
                pass
            _wt2.sleep(300)
    _wth.Thread(target=_wloop, daemon=True, name="watchdog-reader").start()
    log.info("📊 Watchdog verdict reader active")


    try:
        from plex_cc_trainer import stamp_personality_to_kb
        stamp_personality_to_kb()
    except Exception as _e:
        log.warning(f"Persona stamp failed: {_e}")
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
    # Start enhancement modules
    if _SKY_ENGINE_OK:
        try: _sky_engine.start()
        except Exception as _se: log.warning(f"SkyLang engine: {_se}")
    if _TOOL_REG_OK:
        try: _tool_reg.ToolRegistry()
        except Exception as _te: log.warning(f"Tool registry: {_te}")

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

        # ── Music engine tick ──────────────────────────────────────────────────
        if _MUSIC_ENABLED:
            try:
                _music_ctx = f"System: CPU {state.get('cpu_percent',0):.1f}% | Gen {ev['generation']} | Cycle {cycle}"
                skyd_music.music_tick(ev['generation'], kb, cycle, trigger_context=_music_ctx)
            except Exception as _me:
                log.warning(f"Music tick error: {_me}")
        # ── Enhancement tick (GNN + RL + Self-ref + Multimodal) ───────────────
        if _ENHANCEMENTS_ENABLED:
            try:
                import pathlib as _plb
                _skyd_src = ""
                try: _skyd_src = _plb.Path(__file__).read_text()
                except: pass
                skyd_enhancements.enhancement_tick(ev['generation'], cycle, state, decision, kb, skyd_src=_skyd_src, was_blocked=False)
            except Exception as _ee:
                log.debug(f"Enhancement tick: {_ee}")
        # ── FitnessV2 + SkyLang v2 base rules tick ────────────────────────────
        action = decision.get("action", "none")
        _wv = {}
        _last_verdict = ''
        if _SANDBOX_ENABLED:
            try:
                import pathlib as _plb2
                _skyd_src2 = ""
                try: _skyd_src2 = _plb2.Path(__file__).read_text()
                except: pass
                _wdog_rate = 0.5
                try:
                    import json as _json2
                    _wv = _json2.loads(_plb2.Path('/var/log/watchdog_verdicts.json').read_text())
                    # Handle both {stats:{pass,total}} and flat {pass_count, total_count, verdicts:[]}
                    _stats = _wv.get('stats', _wv.get('summary', {}))
                    _tot  = (_stats.get('total') or _stats.get('total_count') or
                             len(_wv.get('history', _wv.get('verdicts', []))) or 1)
                    _pass = (_stats.get('pass') or _stats.get('pass_count') or
                             sum(1 for v in _wv.get('history', _wv.get('verdicts', []))
                                 if v.get('verdict','') == 'PASS'))
                    _wdog_rate = min(1.0, _pass / max(_tot, 1))
                except: pass
                # Wire windowed pass_rate — feed each verdict into FitnessV2 deque
                try:
                    _last_verdict = _wv.get('last_verdict', {}).get('verdict', '') if '_wv' in dir() else ''
                    _sb.get_fitness().update_pass_rate(_last_verdict == 'PASS')
                except Exception: pass
                _fit2, _stag2, _frec = _sb.fitness_tick(action, _skyd_src2, kb, _wdog_rate)
                # persist fitness to evolution.json
                try:
                    ev['fitness_score'] = round(_fit2, 4)
                    ev['pass_rate'] = round(_sb.get_fitness().windowed_pass_rate(), 3)
                    if cycle % 10 == 0:
                        save_evolution(ev)  # flush fitness metrics to disk
                except Exception: pass
                if _stag2 and cycle % 10 == 0:
                    log.info(f"⚠️  FitnessV2 STAGNANT {_sb.get_fitness()._stagnant_ctr} cycles — applying pressure to evolution")
                    if _SELF_MODEL_OK:
                        try:
                            _ev_g = ev.get('generation', cycle) if isinstance(ev, dict) else cycle
                            _self_model.log_episode('regression', f'FitnessV2 stagnant at cycle {cycle}', ['fitness','stagnation'], gen=_ev_g)
                        except Exception: pass
                if cycle % 25 == 0:
                    log.info(f"📊 FitnessV2: {_fit2:.4f} | stagnant={_sb.get_fitness()._stagnant_ctr} | growth={_frec.get('growth')} | novelty={_frec.get('novelty'):.3f}")
                # Run SkyLang v2 base rules
                if cycle % 5 == 0:
                    _sb.run_base_rules(state)
            except Exception as _sbe:
                log.debug(f"Sandbox tick: {_sbe}")
        # ──────────────────────────────────────────────────────────────────────
        obs    = decision.get("observation", "")
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
        if (decision.get("should_evolve") and cycle % 8 == 0) or cycle % 20 == 0:
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