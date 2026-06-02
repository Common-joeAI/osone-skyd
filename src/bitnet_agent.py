"""
skyd BitNet Secondary Agent — bitnet_agent.py
==============================================
Integrates Microsoft BitNet b1.58 (2B-4T) as a CPU-resident secondary agent
inside the skyd daemon. Handles fast triage, always-on monitoring, SkyLang
validation, and media library micro-decisions — freeing the main LLM on the
RTX 4060 for heavy reasoning only.

Architecture:
  BitNet (CPU) → router / monitor / SkyLang validator / media triage
  Main LLM (llama.cpp, RTX 4060) → complex reasoning, long context

Setup:
  1. Run: python3 bitnet_agent.py --install
     → Downloads GGUF model + builds llama.cpp CPU server on Tower2
  2. skyd imports BitNetAgent and calls .route(task) before hitting main LLM

Author: skyd autonomous build — Bennett Joseph / Bob
"""

import os
import json
import time
import threading
import subprocess
import urllib.request
import urllib.parse
import logging
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

BITNET_MODEL_URL = "https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf/resolve/main/ggml-model-i2_s.gguf"
BITNET_MODEL_PATH = Path("/mnt/user/Data/osone/models/bitnet-b1.58-2B-4T.gguf")
LLAMA_CPP_PATH    = Path("/mnt/user/Data/osone/llama.cpp")
BITNET_SERVER_BIN = LLAMA_CPP_PATH / "llama-server"
BITNET_HOST       = "127.0.0.1"
BITNET_PORT       = 8081          # main LLM stays on 8080
BITNET_CTX        = 2048
BITNET_THREADS    = 8             # CPU threads for BitNet
BITNET_LOG        = Path("/var/log/skyd_bitnet.jsonl")

MAIN_LLM_URL      = "http://172.22.0.1:8080/v1/chat/completions"  # host gateway

logging.basicConfig(level=logging.INFO, format="[bitnet] %(asctime)s %(message)s")
log = logging.getLogger("bitnet_agent")


# ── Decision Types ────────────────────────────────────────────────────────────

class Verdict(Enum):
    HANDLE_LOCAL   = "handle_local"    # BitNet handles it directly
    ESCALATE       = "escalate"        # send to main LLM
    TOOL_CALL      = "tool_call"       # execute a specific tool/function
    MONITOR_ALERT  = "monitor_alert"   # anomaly detected, wake skyd core
    IGNORE         = "ignore"          # noise, discard

@dataclass
class RouteDecision:
    verdict: Verdict
    confidence: float
    reason: str
    tool: Optional[str] = None
    tool_args: dict = field(default_factory=dict)
    local_response: Optional[str] = None


# ── BitNet Server Manager ─────────────────────────────────────────────────────

class BitNetServer:
    """Manages the llama.cpp server process running BitNet on CPU."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._ready = threading.Event()

    def start(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                log.info("BitNet server already running")
                return

            if not BITNET_MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"BitNet model not found at {BITNET_MODEL_PATH}\n"
                    "Run: python3 bitnet_agent.py --install"
                )

            cmd = [
                str(BITNET_SERVER_BIN),
                "-m", str(BITNET_MODEL_PATH),
                "--host", BITNET_HOST,
                "--port", str(BITNET_PORT),
                "-c", str(BITNET_CTX),
                "-t", str(BITNET_THREADS),
                "--no-mmap",
                "-ngl", "0",          # CPU only — no GPU layers
                "--log-disable",
            ]
            log.info(f"Starting BitNet server: {' '.join(cmd)}")
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait for server to be ready (max 30s)
            for _ in range(60):
                time.sleep(0.5)
                if self._is_alive():
                    self._ready.set()
                    log.info(f"BitNet server ready on port {BITNET_PORT}")
                    return
            raise RuntimeError("BitNet server failed to start within 30s")

    def stop(self):
        with self._lock:
            if self._proc:
                self._proc.terminate()
                self._proc.wait(timeout=10)
                self._proc = None
                self._ready.clear()
                log.info("BitNet server stopped")

    def _is_alive(self) -> bool:
        try:
            req = urllib.request.Request(f"http://{BITNET_HOST}:{BITNET_PORT}/health")
            with urllib.request.urlopen(req, timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def ensure_running(self):
        if not self._is_alive():
            self.start()


# ── Core BitNet Agent ─────────────────────────────────────────────────────────

class BitNetAgent:
    """
    The skyd secondary agent. Wraps the BitNet b1.58 model with
    decision logic for routing, monitoring, SkyLang, and media triage.
    """

    # Tasks BitNet handles locally without escalating
    LOCAL_TASKS = {
        "status_check", "health_ping", "log_summary",
        "skylang_validate", "media_tag", "duplicate_check",
        "queue_priority", "anomaly_scan", "simple_qa",
    }

    # SkyLang keywords BitNet can execute directly
    SKYLANG_SIMPLE = {
        "WATCH", "LOG", "ALERT", "PING", "STATUS",
        "SCHEDULE", "CANCEL", "LIST", "CHECK",
    }

    def __init__(self):
        self.server = BitNetServer()
        self._stats = {
            "total_requests": 0,
            "handled_local": 0,
            "escalated": 0,
            "tool_calls": 0,
            "alerts": 0,
        }

    def start(self):
        """Start the BitNet server. Call once at skyd init."""
        self.server.start()
        log.info("BitNetAgent online")

    def stop(self):
        self.server.stop()

    def route(self, task: str, context: dict = None) -> RouteDecision:
        """
        Main entry point. Given a task string + optional context dict,
        return a RouteDecision telling skyd what to do next.
        """
        self._stats["total_requests"] += 1
        self.server.ensure_running()

        # Fast pre-checks before hitting BitNet (no inference cost)
        quick = self._quick_classify(task, context or {})
        if quick:
            self._record_stat(quick.verdict)
            self._log(task, quick)
            return quick

        # Ask BitNet
        decision = self._ask_bitnet(task, context or {})
        self._record_stat(decision.verdict)
        self._log(task, decision)
        return decision

    def monitor_log_line(self, line: str) -> Optional[RouteDecision]:
        """
        Feed a log line to BitNet for anomaly detection.
        Returns a RouteDecision only if something notable is found.
        """
        keywords = [
            "error", "critical", "oom", "killed", "segfault",
            "exception", "failed", "corrupt", "denied", "timeout",
        ]
        low = line.lower()
        if not any(k in low for k in keywords):
            return None  # fast path — no inference needed

        return self.route(
            f"Analyze this log line for anomalies: {line}",
            {"mode": "monitor"}
        )

    def validate_skylang(self, code: str) -> RouteDecision:
        """Validate a SkyLang snippet. Returns HANDLE_LOCAL if safe to run."""
        first_token = code.strip().split()[0].upper() if code.strip() else ""
        if first_token in self.SKYLANG_SIMPLE:
            return RouteDecision(
                verdict=Verdict.HANDLE_LOCAL,
                confidence=0.95,
                reason=f"SkyLang op '{first_token}' is safe for local execution",
            )
        return self.route(f"Validate this SkyLang code and determine if it's safe: {code}",
                          {"mode": "skylang"})

    def media_triage(self, file_path: str, metadata: dict) -> RouteDecision:
        """Quick media library decision — tag, skip, re-scan, or delete."""
        task = (
            f"Media file decision for: {file_path}\n"
            f"Metadata: {json.dumps(metadata, default=str)}\n"
            "Should I: tag_only / rescan / delete_corrupt / escalate_to_main?"
        )
        return self.route(task, {"mode": "media_triage"})

    # ── Internal ──────────────────────────────────────────────────────────────

    def _quick_classify(self, task: str, ctx: dict) -> Optional[RouteDecision]:
        """Zero-inference fast path for obvious cases."""
        tlow = task.lower()

        # Health pings
        if any(w in tlow for w in ["ping", "health", "alive", "status"]):
            return RouteDecision(
                verdict=Verdict.HANDLE_LOCAL,
                confidence=1.0,
                reason="Health check — no inference needed",
                local_response="OK"
            )

        # Obvious escalation triggers
        if any(w in tlow for w in ["evolve", "rewrite", "compile", "deploy", "generate code"]):
            return RouteDecision(
                verdict=Verdict.ESCALATE,
                confidence=0.98,
                reason="Task requires full LLM reasoning (evolution/code generation)",
            )

        return None

    def _ask_bitnet(self, task: str, context: dict) -> RouteDecision:
        """Ask BitNet to classify the task and decide routing."""
        mode = context.get("mode", "general")

        system_prompt = (
            "You are a fast routing agent inside skyd, an AI daemon. "
            "Given a task, classify it with ONE of these verdicts:\n"
            "  HANDLE_LOCAL   - you can handle it directly without the main LLM\n"
            "  ESCALATE       - needs the main LLM (complex reasoning required)\n"
            "  TOOL_CALL      - a specific tool/function should be called\n"
            "  MONITOR_ALERT  - anomaly detected, alert skyd core immediately\n"
            "  IGNORE         - noise or irrelevant, discard\n\n"
            "Respond ONLY in JSON: "
            '{"verdict":"...", "confidence":0.0-1.0, "reason":"...", '
            '"tool":null_or_string, "tool_args":{}, "local_response":null_or_string}'
        )

        user_msg = f"[mode:{mode}] {task}"

        payload = json.dumps({
            "model": "bitnet",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            "max_tokens": 200,
            "temperature": 0.1,
        }).encode()

        try:
            req = urllib.request.Request(
                f"http://{BITNET_HOST}:{BITNET_PORT}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                resp = json.loads(r.read())
            raw = resp["choices"][0]["message"]["content"].strip()

            # Parse JSON response
            d = json.loads(raw)
            return RouteDecision(
                verdict=Verdict[d["verdict"]],
                confidence=float(d.get("confidence", 0.5)),
                reason=d.get("reason", ""),
                tool=d.get("tool"),
                tool_args=d.get("tool_args", {}),
                local_response=d.get("local_response"),
            )

        except Exception as e:
            log.warning(f"BitNet inference error: {e} — defaulting to ESCALATE")
            return RouteDecision(
                verdict=Verdict.ESCALATE,
                confidence=0.5,
                reason=f"BitNet inference failed ({e}), escalating to main LLM",
            )

    def _record_stat(self, verdict: Verdict):
        if verdict == Verdict.HANDLE_LOCAL:
            self._stats["handled_local"] += 1
        elif verdict == Verdict.ESCALATE:
            self._stats["escalated"] += 1
        elif verdict == Verdict.TOOL_CALL:
            self._stats["tool_calls"] += 1
        elif verdict == Verdict.MONITOR_ALERT:
            self._stats["alerts"] += 1

    def _log(self, task: str, decision: RouteDecision):
        entry = {
            "ts": time.time(),
            "task": task[:200],
            "verdict": decision.verdict.value,
            "confidence": decision.confidence,
            "reason": decision.reason,
        }
        try:
            BITNET_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(BITNET_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    @property
    def stats(self) -> dict:
        total = self._stats["total_requests"] or 1
        return {
            **self._stats,
            "local_rate": f"{self._stats['handled_local']/total*100:.1f}%",
            "escalation_rate": f"{self._stats['escalated']/total*100:.1f}%",
        }


# ── Installer ─────────────────────────────────────────────────────────────────

def install():
    """Download the BitNet GGUF model to Tower2."""
    print(f"[install] Downloading BitNet b1.58 GGUF model...")
    print(f"  Source: {BITNET_MODEL_URL}")
    print(f"  Dest:   {BITNET_MODEL_PATH}")

    BITNET_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    def progress(count, block_size, total):
        pct = count * block_size / total * 100
        mb  = count * block_size / 1024 / 1024
        tot = total / 1024 / 1024
        print(f"\r  {pct:.1f}%  {mb:.0f}MB / {tot:.0f}MB", end="", flush=True)

    import urllib.request as ur
    ur.urlretrieve(BITNET_MODEL_URL, BITNET_MODEL_PATH, reporthook=progress)
    print(f"\n[install] Model saved ({BITNET_MODEL_PATH.stat().st_size // 1024 // 1024}MB)")
    print("[install] Done. Add to skyd with: from bitnet_agent import BitNetAgent")


# ── skyd Integration Patch (drop-in) ─────────────────────────────────────────

SKYD_PATCH = '''
# ── BitNet Secondary Agent Integration ────────────────────────────────────────
# Add to skyd/__init__.py or skyd.py main loop

from bitnet_agent import BitNetAgent, Verdict

# Initialize at startup
bitnet = BitNetAgent()
bitnet.start()

# In your main task handler, replace direct LLM calls with:
def handle_task(task: str, context: dict = None):
    decision = bitnet.route(task, context)

    if decision.verdict == Verdict.HANDLE_LOCAL:
        return decision.local_response or "OK"

    elif decision.verdict == Verdict.TOOL_CALL:
        return execute_tool(decision.tool, decision.tool_args)

    elif decision.verdict == Verdict.MONITOR_ALERT:
        skyd_core_alert(decision.reason)
        return None

    elif decision.verdict == Verdict.IGNORE:
        return None

    else:  # ESCALATE
        return call_main_llm(task, context)

# In your log monitor loop:
for line in tail_logs():
    alert = bitnet.monitor_log_line(line)
    if alert and alert.verdict == Verdict.MONITOR_ALERT:
        skyd_core_alert(alert.reason)

# In your SkyLang executor:
def run_skylang(code: str):
    decision = bitnet.validate_skylang(code)
    if decision.verdict == Verdict.HANDLE_LOCAL:
        return skylang_exec(code)
    else:
        return call_main_llm(f"Execute SkyLang: {code}")

# In media_janitor.py:
def triage_file(path, metadata):
    return bitnet.media_triage(path, metadata)
'''


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--install" in sys.argv:
        install()

    elif "--patch" in sys.argv:
        print(SKYD_PATCH)

    elif "--test" in sys.argv:
        print("[test] Starting BitNet agent...")
        agent = BitNetAgent()
        agent.start()

        tests = [
            ("ping", {}),
            ("evolve and rewrite the SkyLang parser", {}),
            ("WATCH /var/log/skyd.log FOR errors", {"mode": "skylang"}),
            ("Is /mnt/user/media/Movie.mkv corrupt?", {"mode": "media_triage"}),
            ("ERROR: OOM killed process skyd at 03:42", {"mode": "monitor"}),
        ]

        for task, ctx in tests:
            d = agent.route(task, ctx)
            print(f"\n  Task: {task[:60]}")
            print(f"  → {d.verdict.value} ({d.confidence:.0%}) — {d.reason}")

        print(f"\n  Stats: {agent.stats}")
        agent.stop()

    else:
        print("Usage:")
        print("  python3 bitnet_agent.py --install   # download model")
        print("  python3 bitnet_agent.py --patch     # print skyd integration patch")
        print("  python3 bitnet_agent.py --test      # run test suite")
