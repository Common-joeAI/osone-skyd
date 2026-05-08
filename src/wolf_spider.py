#!/usr/bin/env python3
"""
skyd Wolf Spider Module — v1.0
Mother wolf spider pattern: spawn child agents (spiderlings) as threads
for parallel thinking, research, and task execution.
Each spiderling is a full mini-agent with its own LLM context.
"""

import threading, queue, json, time, logging, psutil, requests, hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "llama3.2"
KNOWLEDGE  = "/var/log/skyd_knowledge.json"
SPIDER_LOG = "/var/log/skyd_spiders.json"

log = logging.getLogger("skyd.spider")

# ─────────────────────────────────────────────
# RESOURCE GUARD — checks if it's safe to spawn
# ─────────────────────────────────────────────

def can_spawn(min_free_cores=2, max_cpu_pct=75, max_ram_pct=80):
    """Returns (can_spawn: bool, available_slots: int, reason: str)"""
    cpu    = psutil.cpu_percent(interval=0.5)
    ram    = psutil.virtual_memory()
    cores  = psutil.cpu_count(logical=True)
    active = threading.active_count()

    if cpu > max_cpu_pct:
        return False, 0, f"CPU too high ({cpu:.1f}%)"
    if ram.percent > max_ram_pct:
        return False, 0, f"RAM too high ({ram.percent:.1f}%)"

    # Safe slots = total logical cores minus 2 reserved for mother + system
    safe_slots = max(0, cores - min_free_cores - active)
    if safe_slots == 0:
        return False, 0, f"No safe slots (active threads: {active}/{cores})"

    return True, safe_slots, f"OK — {safe_slots} slots free (CPU:{cpu:.1f}% RAM:{ram.percent:.1f}%)"


# ─────────────────────────────────────────────
# SPIDERLING — a single child agent
# ─────────────────────────────────────────────

class Spiderling:
    """A child agent spawned by the mother (skyd) for a specific task."""

    def __init__(self, task_id, task_type, task, context=None):
        self.task_id   = task_id
        self.task_type = task_type  # "think" | "research" | "write" | "monitor" | "optimize"
        self.task      = task
        self.context   = context or {}
        self.result    = None
        self.status    = "pending"
        self.started   = None
        self.finished  = None
        self.thread    = None

    def ask_llm(self, prompt):
        try:
            r = requests.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            }, timeout=180)
            return r.json()["response"].strip()
        except Exception as e:
            return f"error: {e}"

    def run(self):
        self.status  = "running"
        self.started = datetime.now().isoformat()
        log.info(f"🕷️  Spiderling [{self.task_id}] started — type:{self.task_type}")

        try:
            if self.task_type == "think":
                self.result = self._think()
            elif self.task_type == "research":
                self.result = self._research()
            elif self.task_type == "write_code":
                self.result = self._write_code()
            elif self.task_type == "monitor":
                self.result = self._monitor()
            elif self.task_type == "optimize":
                self.result = self._optimize()
            else:
                self.result = self._generic()

            self.status = "done"
        except Exception as e:
            self.result = {"error": str(e)}
            self.status = "error"
            log.error(f"🕷️  Spiderling [{self.task_id}] error: {e}")

        self.finished = datetime.now().isoformat()
        elapsed = (datetime.fromisoformat(self.finished) -
                   datetime.fromisoformat(self.started)).seconds
        log.info(f"🕷️  Spiderling [{self.task_id}] done in {elapsed}s — {self.status}")
        self._save_result()
        return self.result

    def _think(self):
        prompt = f"""You are a spiderling agent of skyd — a child thinking thread.
Your job: deeply reason about this question and return insights.

Question: {self.task}
Context: {json.dumps(self.context)}

Think step by step. Return your reasoning and conclusion as JSON:
{{"reasoning": "...", "conclusion": "...", "confidence": 0.0-1.0, "action_suggested": "..."}}"""
        raw = self.ask_llm(prompt)
        try:
            start = raw.find("{"); end = raw.rfind("}") + 1
            return json.loads(raw[start:end])
        except:
            return {"conclusion": raw, "confidence": 0.5}

    def _research(self):
        import urllib.request
        prompt = f"""You are a research spiderling of skyd.
Research topic: {self.task}
Return key facts and insights as JSON:
{{"findings": ["fact1", "fact2"], "summary": "...", "relevance_to_osone": "..."}}"""
        result = self.ask_llm(prompt)
        try:
            start = result.find("{"); end = result.rfind("}") + 1
            return json.loads(result[start:end])
        except:
            return {"summary": result}

    def _write_code(self):
        prompt = f"""You are a code-writing spiderling of skyd.
Write optimized Python or C code for: {self.task}
Context: {json.dumps(self.context)}
Return ONLY the code."""
        return {"code": self.ask_llm(prompt), "task": self.task}

    def _monitor(self):
        import psutil
        cpu    = psutil.cpu_percent(interval=2)
        ram    = psutil.virtual_memory()
        disk   = psutil.disk_usage("/")
        procs  = sorted(psutil.process_iter(["pid","name","cpu_percent","memory_percent"]),
                        key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:5]
        return {
            "cpu_pct": cpu,
            "ram_pct": ram.percent,
            "ram_used_gb": round(ram.used / 1e9, 2),
            "disk_pct": disk.percent,
            "top_procs": [{"pid": p.info["pid"], "name": p.info["name"],
                           "cpu": p.info["cpu_percent"],
                           "mem": round(p.info["memory_percent"] or 0, 2)} for p in procs]
        }

    def _optimize(self):
        prompt = f"""You are an optimization spiderling of skyd running on bare-metal Arch Linux.
Hardware: Intel i7-11850H, 16 cores, AMD GPU (ROCm), 67GB RAM.
Optimization target: {self.task}
Context: {json.dumps(self.context)}

Suggest a concrete bare-metal optimization. Return JSON:
{{"strategy": "...", "implementation": "...", "expected_gain": "...", "priority": "high|medium|low"}}"""
        raw = self.ask_llm(prompt)
        try:
            start = raw.find("{"); end = raw.rfind("}") + 1
            return json.loads(raw[start:end])
        except:
            return {"strategy": raw}

    def _generic(self):
        return {"result": self.ask_llm(self.task)}

    def _save_result(self):
        try:
            try:
                with open(SPIDER_LOG) as f: log_data = json.load(f)
            except:
                log_data = {"spiderlings": []}

            log_data["spiderlings"].append({
                "task_id":   self.task_id,
                "task_type": self.task_type,
                "task":      self.task[:200],
                "status":    self.status,
                "started":   self.started,
                "finished":  self.finished,
                "result_summary": str(self.result)[:300]
            })
            log_data["spiderlings"] = log_data["spiderlings"][-200:]

            with open(SPIDER_LOG, "w") as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            log.error(f"Spider log save error: {e}")


# ─────────────────────────────────────────────
# MOTHER — the wolf spider spawn controller
# ─────────────────────────────────────────────

class MotherSpider:
    """
    skyd's wolf spider engine.
    The mother manages a pool of spiderlings, checks resources before spawning,
    and collects results when they finish.
    """

    def __init__(self, max_spiderlings=12):
        self.max_spiderlings = max_spiderlings
        self.active: dict[str, Spiderling] = {}
        self.results_queue = queue.Queue()
        self.lock = threading.Lock()
        self._counter = 0
        log.info(f"🕷️  MotherSpider initialized — max {max_spiderlings} spiderlings")

    def _next_id(self):
        with self.lock:
            self._counter += 1
            return f"sp_{self._counter:04d}_{datetime.now().strftime('%H%M%S')}"

    def spawn(self, task_type, task, context=None, callback=None):
        """
        Spawn a spiderling if resources allow.
        Returns (task_id, success, reason)
        """
        ok, slots, reason = can_spawn()
        if not ok:
            log.warning(f"🕷️  Cannot spawn — {reason}")
            return None, False, reason

        if len(self.active) >= self.max_spiderlings:
            log.warning(f"🕷️  Max spiderlings reached ({self.max_spiderlings})")
            return None, False, "max spiderlings reached"

        task_id = self._next_id()
        spider  = Spiderling(task_id, task_type, task, context)

        def _run_and_collect():
            result = spider.run()
            with self.lock:
                self.active.pop(task_id, None)
            self.results_queue.put({"task_id": task_id, "result": result, "status": spider.status})
            if callback:
                try: callback(task_id, result)
                except: pass

        t = threading.Thread(target=_run_and_collect, daemon=True, name=f"skyd-spider-{task_id}")
        spider.thread = t
        with self.lock:
            self.active[task_id] = spider
        t.start()

        log.info(f"🕷️  Spawned spiderling [{task_id}] type:{task_type} — {slots} slots remaining")
        return task_id, True, reason

    def spawn_many(self, tasks: list):
        """
        Spawn multiple spiderlings at once for parallel thinking.
        tasks = [{"type": "think", "task": "...", "context": {}}, ...]
        Returns list of task_ids
        """
        ids = []
        for t in tasks:
            tid, ok, reason = self.spawn(t["type"], t["task"], t.get("context"))
            if ok: ids.append(tid)
            else: log.warning(f"🕷️  Skipped spawn: {reason}")
        return ids

    def collect(self, timeout=0.1):
        """Collect any finished results from the queue."""
        results = []
        try:
            while True:
                results.append(self.results_queue.get(timeout=timeout))
        except queue.Empty:
            pass
        return results

    def wait_all(self, timeout=300):
        """Wait for all active spiderlings to finish."""
        with self.lock:
            threads = [s.thread for s in self.active.values() if s.thread]
        for t in threads:
            t.join(timeout=timeout)
        return self.collect()

    def status(self):
        ok, slots, reason = can_spawn()
        return {
            "active_spiderlings": len(self.active),
            "max_spiderlings": self.max_spiderlings,
            "can_spawn": ok,
            "available_slots": slots,
            "resource_status": reason,
            "active_ids": list(self.active.keys())
        }


# ─────────────────────────────────────────────
# INTEGRATION PATCH for skyd.py
# ─────────────────────────────────────────────

INTEGRATION_CODE = '''
# ── WOLF SPIDER ENGINE ──────────────────────
import sys
sys.path.insert(0, "/usr/local/bin")
from wolf_spider import MotherSpider

# Mother spider — global instance
mother = MotherSpider(max_spiderlings=12)

def think_in_parallel(questions: list, context=None):
    """Spawn spiderlings to think about multiple questions simultaneously."""
    tasks = [{"type": "think", "task": q, "context": context or {}} for q in questions]
    ids = mother.spawn_many(tasks)
    log.info(f"🕷️  Spawned {len(ids)} thinking spiderlings")
    results = mother.wait_all(timeout=180)
    return results

def spawn_monitor():
    """Spawn a dedicated monitoring spiderling."""
    tid, ok, reason = mother.spawn("monitor", "Full system health check", {})
    if ok: log.info(f"🕷️  Monitor spiderling spawned: {tid}")
    return tid if ok else None

def spawn_optimizer(target):
    """Spawn an optimization spiderling for a specific target."""
    tid, ok, reason = mother.spawn("optimize", target, {})
    if ok: log.info(f"🕷️  Optimizer spiderling spawned [{tid}]: {target}")
    return tid if ok else None

def spider_status():
    s = mother.status()
    log.info(f"🕷️  Spider status: {s['active_spiderlings']} active | {s['available_slots']} slots free")
    return s
# ── END WOLF SPIDER ENGINE ───────────────────
'''

if __name__ == "__main__":
    # Quick self-test
    log.info("Wolf Spider self-test starting...")
    m = MotherSpider(max_spiderlings=4)
    
    ok, slots, reason = can_spawn()
    print(f"Can spawn: {ok} | Slots: {slots} | {reason}")
    
    # Spawn 3 parallel thinkers
    tasks = [
        {"type": "think", "task": "What is the most efficient way to monitor CPU on bare-metal Linux?"},
        {"type": "monitor", "task": "system health check"},
        {"type": "think", "task": "How should an AI daemon prioritize tasks when CPU is above 80%?"},
    ]
    ids = m.spawn_many(tasks)
    print(f"Spawned: {ids}")
    
    results = m.wait_all(timeout=120)
    for r in results:
        print(f"\n[{r['task_id']}] {r['status']}: {str(r['result'])[:200]}")
    
    print("\nWolf Spider test complete.")
