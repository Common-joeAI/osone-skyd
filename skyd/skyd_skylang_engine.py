#!/usr/bin/env python3
"""
skyd_skylang_engine.py
Live SkyLang control plane for OSONE skyd daemon.
Executes *.sky rules against real system metrics.
"""

import os
import time
import json
import hashlib
import threading
import logging
from datetime import datetime, timedelta

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    import media_janitor
    _JANITOR_OK = True
except ImportError:
    _JANITOR_OK = False

LANG_DIR = "/usr/local/skyd/lang"
ALERT_LOG = "/var/log/skyd_alerts.jsonl"
EXEC_LOG = "/var/log/skyd_skylang_exec.jsonl"

logger = logging.getLogger("skyd.skylang")

class RuleRegistry:
    def __init__(self):
        self.rules = {}          # hash -> rule_text
        self.rule_meta = {}      # hash -> {"path": , "last_loaded": }
        self.lock = threading.RLock()
        self._load_all()

    def _hash(self, content):
        return hashlib.sha256(content.encode()).hexdigest()

    def _load_all(self):
        if not os.path.isdir(LANG_DIR):
            os.makedirs(LANG_DIR, exist_ok=True)
            return
        with self.lock:
            for fname in os.listdir(LANG_DIR):
                if not fname.endswith(".sky"):
                    continue
                path = os.path.join(LANG_DIR, fname)
                try:
                    with open(path, "r") as f:
                        content = f.read().strip()
                    h = self._hash(content)
                    if h not in self.rules:
                        self.rules[h] = content
                        self.rule_meta[h] = {"path": path, "last_loaded": time.time()}
                except Exception as e:
                    logger.debug(f"Failed to load {path}: {e}")

    def poll_new_rules(self):
        """Simple polling watcher (no inotify dependency)."""
        self._load_all()

    def get_all_rules(self):
        with self.lock:
            return list(self.rules.values())

    def get_status(self):
        with self.lock:
            status = []
            for h, txt in self.rules.items():
                meta = self.rule_meta.get(h, {})
                status.append({
                    "rule": txt[:120],
                    "path": meta.get("path"),
                    "hash": h[:12],
                    "last_loaded": meta.get("last_loaded")
                })
            return status


class RuleExecutor:
    def __init__(self, registry):
        self.registry = registry
        self.last_eval = {}
        self.last_triggered = {}
        self.active = {}
        self.lock = threading.RLock()
        self.running = False
        self.thread = None
        self._schedules = {}   # hash -> next_run_time

    def _parse_rule(self, rule_text):
        lines = [l.strip() for l in rule_text.splitlines() if l.strip()]
        watches = []
        every = None
        actions = []
        for line in lines:
            if line.upper().startswith("WATCH "):
                watches.append(line[6:].strip())
            elif line.upper().startswith("EVERY "):
                try:
                    val = line.split()[1]
                    if val.endswith("m"):
                        every = int(val[:-1]) * 60
                except:
                    pass
            elif line.upper().startswith("ACTION "):
                actions.append(line[7:].strip())
        return watches, every, actions

    def _eval_condition(self, cond):
        if not _PSUTIL_OK:
            return False
        cond = cond.strip()
        try:
            if cond.startswith("cpu_percent >"):
                thresh = float(cond.split(">")[-1])
                return psutil.cpu_percent(interval=0.1) > thresh
            elif cond.startswith("ram_percent >"):
                thresh = float(cond.split(">")[-1])
                return psutil.virtual_memory().percent > thresh
            elif cond.startswith("disk_usage >"):
                thresh = float(cond.split(">")[-1])
                return psutil.disk_usage("/").percent > thresh
        except Exception:
            return False
        return False

    def _execute_action(self, action, rule_hash):
        action = action.strip()
        ts = datetime.utcnow().isoformat()
        entry = {"ts": ts, "action": action, "rule": rule_hash[:12]}

        if action == "fstrim":
            logger.warning("fstrim action blocked (RL penalty hook)")
            entry["result"] = "BLOCKED"
        elif action == "run_janitor":
            if _JANITOR_OK:
                try:
                    media_janitor.scan()
                    entry["result"] = "OK"
                except Exception as e:
                    entry["result"] = f"ERROR: {e}"
            else:
                entry["result"] = "JANITOR_NOT_AVAILABLE"
        elif action == "send_alert":
            try:
                with open(ALERT_LOG, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                entry["result"] = "LOGGED"
            except Exception as e:
                entry["result"] = f"ERROR: {e}"
        elif action == "log":
            try:
                with open(EXEC_LOG, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                entry["result"] = "LOGGED"
            except Exception as e:
                entry["result"] = f"ERROR: {e}"
        elif action == "hive_broadcast":
            if _REQUESTS_OK:
                try:
                    requests.post(
                        "http://172.22.0.1:8000/api/hive/broadcast",
                        json={"node": os.uname().nodename, "action": action},
                        timeout=3
                    )
                    entry["result"] = "POSTED"
                except Exception as e:
                    entry["result"] = f"ERROR: {e}"
            else:
                entry["result"] = "REQUESTS_MISSING"
        else:
            logger.info(f"UNKNOWN_ACTION: {action}")
            entry["result"] = "UNKNOWN"
            # emit learning signal (simple log)
            try:
                with open(EXEC_LOG, "a") as f:
                    f.write(json.dumps({"ts": ts, "learning_signal": action}) + "\n")
            except:
                pass

        try:
            with open(EXEC_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except:
            pass

    def _tick(self):
        rules = self.registry.get_all_rules()
        now = time.time()

        for rule in rules:
            h = hashlib.sha256(rule.encode()).hexdigest()
            watches, every, actions = self._parse_rule(rule)

            triggered = False
            for w in watches:
                if self._eval_condition(w):
                    triggered = True
                    break

            if every is not None:
                next_run = self._schedules.get(h, 0)
                if now >= next_run:
                    triggered = True
                    self._schedules[h] = now + every

            with self.lock:
                self.last_eval[h] = now
                self.active[h] = True
                if triggered:
                    self.last_triggered[h] = now
                    for act in actions:
                        self._execute_action(act, h)

    def run_forever(self):
        self.running = True
        while self.running:
            try:
                self.registry.poll_new_rules()
                self._tick()
            except Exception as e:
                logger.debug(f"RuleExecutor tick error: {e}")
            time.sleep(30)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run_forever, daemon=True)
        self.thread.start()

    def get_rule_status(self):
        with self.lock:
            out = []
            for h, txt in self.registry.rules.items():
                out.append({
                    "rule": txt[:80],
                    "last_eval": self.last_eval.get(h),
                    "last_triggered": self.last_triggered.get(h),
                    "active": self.active.get(h, False)
                })
            return out


# Module-level singleton
_registry = RuleRegistry()
_executor = RuleExecutor(_registry)

def start():
    _executor.start()

def get_rule_status():
    return _executor.get_rule_status()