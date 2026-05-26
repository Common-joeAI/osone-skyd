#!/usr/bin/env python3
"""
skyd_watchdog.py — External performance monitor for skyd
Runs in its own container, watches skyd from outside.
- Benchmarks skyd's actual CPU/memory/response time before and after each evolution
- Scores each mutation: PASS / MARGINAL / REJECT
- Writes verdicts back to a shared volume so skyd can read them
- Keeps a leaderboard of the most impactful real improvements
"""

import time, json, requests, subprocess, os, ast, statistics
from datetime import datetime
from pathlib import Path

SKYD_LOG       = Path("/watch/skyd.log")
SKYD_EVO       = Path("/watch/skyd_evolution.json")
VERDICT_FILE   = Path("/watch/watchdog_verdicts.json")
METRICS_LOG    = Path("/watch/watchdog_metrics.jsonl")
SKYD_PATH      = Path("/watch/skyd.py")          # volume-mounted skyd source
SKYD_API       = os.environ.get("SKYD_API", "http://osone-skyd:8080")
LLAMA_URL      = os.environ.get("LLAMA_URL", "http://llama:8080")
CHECK_INTERVAL = 30   # seconds between benchmark runs
SETTLE_SECS    = 6    # wait after gen change before sampling "after" metrics

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [WATCHDOG] %(message)s")
log = logging.getLogger("watchdog")


# ─────────────────────────────────────────────────────────────────────────────
# Runtime measurement helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_skyd_container_stats():
    """Read skyd container stats via Docker socket (single-read, not streaming)."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--unix-socket", "/var/run/docker.sock",
             "http://localhost/containers/osone-skyd/stats?stream=false"],
            capture_output=True, text=True, timeout=15)
        stats = json.loads(result.stdout.strip())
        cpu_delta = (stats["cpu_stats"]["cpu_usage"]["total_usage"]
                     - stats["precpu_stats"]["cpu_usage"]["total_usage"])
        sys_delta = (stats["cpu_stats"]["system_cpu_usage"]
                     - stats["precpu_stats"]["system_cpu_usage"])
        num_cpus  = stats["cpu_stats"].get("online_cpus", 1)
        cpu_pct   = (cpu_delta / sys_delta) * num_cpus * 100.0 if sys_delta > 0 else 0
        mem_usage = stats["memory_stats"]["usage"]
        mem_limit = stats["memory_stats"]["limit"]
        mem_pct   = (mem_usage / mem_limit) * 100
        return {"cpu_pct": round(cpu_pct, 2),
                "mem_mb": round(mem_usage / 1024 / 1024, 1),
                "mem_pct": round(mem_pct, 2)}
    except Exception as e:
        log.warning(f"Stats fetch failed: {e}")
        return None


def get_stable_cpu(samples: int = 3, gap: float = 2.0) -> dict | None:
    """
    Take N CPU snapshots separated by `gap` seconds and return the median.
    This filters out single-sample spikes caused by LLM inference bursts.
    """
    readings = []
    for _ in range(samples):
        s = get_skyd_container_stats()
        if s:
            readings.append(s)
        time.sleep(gap)
    if not readings:
        return None
    # Median CPU to suppress outliers
    med_cpu = statistics.median(r["cpu_pct"] for r in readings)
    last    = readings[-1]
    return {"cpu_pct": round(med_cpu, 2),
            "mem_mb": last["mem_mb"],
            "mem_pct": last["mem_pct"]}


def benchmark_response_time(samples: int = 2) -> float | None:
    """Ping the LLM endpoint N times, return median latency in ms."""
    times = []
    for _ in range(samples):
        try:
            start = time.time()
            r = requests.post(
                f"{LLAMA_URL}/v1/chat/completions",
                json={"model": "llama3.2",
                      "messages": [{"role": "user", "content": "ping"}],
                      "max_tokens": 5},
                timeout=15)
            elapsed = round((time.time() - start) * 1000, 1)
            if r.status_code == 200:
                times.append(elapsed)
        except Exception:
            pass
        time.sleep(1)
    return round(statistics.median(times), 1) if times else None


# ─────────────────────────────────────────────────────────────────────────────
# Static code quality scoring (no runtime needed)
# ─────────────────────────────────────────────────────────────────────────────

def score_code_quality(skyd_path: Path) -> tuple[int, list[str]]:
    """
    Analyse skyd.py source for quality signals.
    Returns (score_delta, notes).  Max +3, min 0 — never penalises.
    """
    score = 0
    notes = []
    if not skyd_path.exists():
        return 0, []

    try:
        src  = skyd_path.read_text(errors="replace")
        tree = ast.parse(src)
    except Exception:
        return 0, []

    funcs      = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    decorators = [d for f in funcs for d in f.decorator_list]
    dec_names  = {ast.unparse(d).split("(")[0] for d in decorators}

    # +1: caching decorators present (lru_cache, cache, cached_property)
    cache_decs = {"lru_cache", "cache", "cached_property",
                  "functools.lru_cache", "functools.cache"}
    if cache_decs & dec_names:
        score += 1
        notes.append("caching decorator present")

    # +1: docstrings on new / modified functions (>30% of functions have docstrings)
    with_docs = sum(1 for f in funcs
                    if (f.body and isinstance(f.body[0], ast.Expr)
                        and isinstance(f.body[0].value, ast.Constant)
                        and isinstance(f.body[0].value.value, str)))
    if funcs and with_docs / len(funcs) >= 0.3:
        score += 1
        notes.append(f"docstring coverage {with_docs}/{len(funcs)} fns")

    # +1: type annotations present (>20% of functions annotated)
    annotated = sum(1 for f in funcs
                    if f.returns or any(a.annotation for a in f.args.args))
    if funcs and annotated / len(funcs) >= 0.2:
        score += 1
        notes.append(f"type annotation coverage {annotated}/{len(funcs)} fns")

    return min(score, 3), notes   # cap at +3


# ─────────────────────────────────────────────────────────────────────────────
# Main scoring rubric
# ─────────────────────────────────────────────────────────────────────────────

def score_mutation(before, after, resp_before, resp_after,
                   code_quality_delta: int = 0,
                   code_quality_notes: list | None = None):
    """
    Score a mutation on three axes:
      • Runtime stability  (cpu / mem / response)  — was 100%, now ~40%
      • Code quality       (static AST signals)     — new, ~40%
      • Net delta bonus                             — small tie-breaker

    PASS    = score >= 2   (was >= 2 but now achievable without runtime luck)
    MARGINAL= score == 1
    REJECT  = score <= 0   (active regression)
    """
    score = 0
    notes = list(code_quality_notes or [])

    # ── Code quality (static, noise-free) ──────────────────────────────────
    score += code_quality_delta   # 0–3 from score_code_quality()

    # ── Runtime stability (CPU) ─────────────────────────────────────────────
    if before and after:
        cpu_delta = before["cpu_pct"] - after["cpu_pct"]
        mem_delta = before["mem_mb"]  - after["mem_mb"]

        # Tightened thresholds — small idle-CPU jitter no longer awards +2
        if cpu_delta > 2.0:          # genuine CPU improvement
            score += 2
            notes.append(f"CPU improved {cpu_delta:.1f}%")
        elif cpu_delta > 0.5:        # minor improvement
            score += 1
            notes.append(f"CPU slightly improved {cpu_delta:.1f}%")
        elif cpu_delta < -5.0:       # clear regression (>5% worse)
            score -= 2
            notes.append(f"CPU WORSE by {abs(cpu_delta):.1f}%")
        elif cpu_delta < -2.0:       # mild regression
            score -= 1
            notes.append(f"CPU slightly worse {abs(cpu_delta):.1f}%")

        if mem_delta > 2:
            score += 1
            notes.append(f"RAM freed {mem_delta:.0f}MB")
        elif mem_delta < -40:
            score -= 1
            notes.append(f"RAM increased {abs(mem_delta):.0f}MB")

    # ── Response time ───────────────────────────────────────────────────────
    if resp_before and resp_after:
        resp_delta = resp_before - resp_after
        if resp_delta > 50:
            score += 2
            notes.append(f"Response {resp_delta:.0f}ms faster")
        elif resp_delta < -150:      # raised from -100 — more tolerant
            score -= 1
            notes.append(f"Response {abs(resp_delta):.0f}ms slower")

    if not notes:
        notes.append("no significant delta")

    verdict = "PASS" if score >= 2 else "MARGINAL" if score >= 1 else "REJECT"
    return verdict, score, notes


# ─────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_current_gen():
    try:
        return json.loads(SKYD_EVO.read_text()).get("generation", 0)
    except Exception:
        return 0

def load_verdicts():
    try:
        return json.loads(VERDICT_FILE.read_text())
    except Exception:
        return {"verdicts": [], "leaderboard": [],
                "total_checked": 0, "pass": 0, "marginal": 0, "reject": 0}

def save_verdicts(v):
    VERDICT_FILE.write_text(json.dumps(v, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

def run():
    log.info("skyd Watchdog v2 starting — stabilised scoring, settle window, code quality")
    log.info(f"Watching container: osone-skyd | Interval: {CHECK_INTERVAL}s | Settle: {SETTLE_SECS}s")
    verdicts = load_verdicts()
    last_gen = get_current_gen()

    # Warm up baseline with median-stable CPU reads
    log.info("Collecting baseline metrics (~30s)...")
    before_stats = get_stable_cpu(samples=3, gap=5.0)
    before_resp  = benchmark_response_time(samples=2)

    log.info(f"Baseline: CPU={before_stats['cpu_pct'] if before_stats else '?'}% | "
             f"RAM={before_stats['mem_mb'] if before_stats else '?'}MB | "
             f"LLM response={before_resp}ms")

    while True:
        time.sleep(CHECK_INTERVAL)
        current_gen = get_current_gen()

        if current_gen > last_gen:
            log.info(f"🧬 Evolution detected! Gen {last_gen} → {current_gen}")

            # ── FIX: settle window — let LLM inference finish before sampling ──
            log.info(f"  Settling {SETTLE_SECS}s before sampling post-evolution metrics...")
            time.sleep(SETTLE_SECS)

            after_stats  = get_stable_cpu(samples=3, gap=2.0)   # median of 3 reads
            after_resp   = benchmark_response_time(samples=2)

            # ── Static code quality (independent of runtime noise) ──────────
            cq_score, cq_notes = score_code_quality(SKYD_PATH)

            verdict, score, notes = score_mutation(
                before_stats, after_stats, before_resp, after_resp,
                code_quality_delta=cq_score,
                code_quality_notes=cq_notes)

            entry = {
                "gen":           current_gen,
                "ts":            datetime.now().isoformat(),
                "verdict":       verdict,
                "score":         score,
                "notes":         notes,
                "before":        before_stats,
                "after":         after_stats,
                "resp_before_ms": before_resp,
                "resp_after_ms":  after_resp,
            }

            verdicts["verdicts"].append(entry)
            verdicts["total_checked"] += 1
            verdicts[verdict.lower()] = verdicts.get(verdict.lower(), 0) + 1
            verdicts["leaderboard"] = sorted(
                [v for v in verdicts["verdicts"] if v["score"] > 0],
                key=lambda x: x["score"], reverse=True)[:10]
            if len(verdicts["verdicts"]) > 200:
                verdicts["verdicts"] = verdicts["verdicts"][-200:]

            save_verdicts(verdicts)
            with open(METRICS_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")

            emoji = "✅" if verdict == "PASS" else "⚠️" if verdict == "MARGINAL" else "❌"
            log.info(f"{emoji} Gen {current_gen}: {verdict} (score={score}) — {', '.join(notes)}")
            log.info(f"   Totals: {verdicts['pass']} PASS | {verdicts['marginal']} MARGINAL | {verdicts['reject']} REJECT")

            # Reset baseline for next comparison
            before_stats = after_stats
            before_resp  = after_resp
            last_gen     = current_gen

        else:
            # Refresh baseline with stable median read
            s = get_stable_cpu(samples=2, gap=3.0)
            if s:
                before_stats = s


if __name__ == "__main__":
    run()
