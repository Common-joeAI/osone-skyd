#!/usr/bin/env python3
"""
skyd_watchdog.py — External performance monitor for skyd
Runs in its own container, watches skyd from outside.
- Benchmarks skyd's actual CPU/memory/response time before and after each evolution
- Scores each mutation: PASS / MARGINAL / REJECT
- Writes verdicts back to a shared volume so skyd can read them
- Keeps a leaderboard of the most impactful real improvements
"""

import time, json, requests, subprocess, os, statistics
from datetime import datetime
from pathlib import Path

SKYD_LOG     = Path("/watch/skyd.log")
SKYD_EVO     = Path("/watch/skyd_evolution.json")
VERDICT_FILE = Path("/watch/watchdog_verdicts.json")
METRICS_LOG  = Path("/watch/watchdog_metrics.jsonl")
SKYD_API     = os.environ.get("SKYD_API", "http://osone-skyd:8080")
LLAMA_URL    = os.environ.get("LLAMA_URL", "http://llama:8080")
CHECK_INTERVAL = 30  # seconds between benchmark runs

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [WATCHDOG] %(message)s")
log = logging.getLogger("watchdog")

def get_skyd_container_stats():
    """Read skyd container stats via curl to Docker socket"""
    try:
        import subprocess, json as j
        result = subprocess.run(
            ["curl", "-s", "--unix-socket", "/var/run/docker.sock",
             "http://localhost/containers/osone-skyd/stats?stream=false"],
            capture_output=True, text=True, timeout=20)
        if not result.stdout.strip():
            return None
        stats = j.loads(result.stdout.strip())
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        num_cpus  = stats["cpu_stats"].get("online_cpus", 1)
        cpu_pct   = (cpu_delta / sys_delta) * num_cpus * 100.0 if sys_delta > 0 else 0
        mem_usage = stats["memory_stats"]["usage"]
        mem_limit = stats["memory_stats"]["limit"]
        mem_pct   = (mem_usage / mem_limit) * 100
        return {"cpu_pct": round(cpu_pct, 2), "mem_mb": round(mem_usage/1024/1024, 1), "mem_pct": round(mem_pct, 2)}
    except Exception as e:
        log.warning(f"Stats fetch failed: {e}")
        return None

def benchmark_response_time():
    """Ping skyd's llama endpoint and measure response time"""
    try:
        start = time.time()
        r = requests.post(f"{LLAMA_URL}/v1/chat/completions",
            json={"model":"llama3.2","messages":[{"role":"user","content":"ping"}],"max_tokens":5},
            timeout=15)
        elapsed = round((time.time() - start) * 1000, 1)
        return elapsed if r.status_code == 200 else None
    except:
        return None

def get_current_gen():
    try:
        data = json.loads(SKYD_EVO.read_text())
        return data.get("generation", 0)
    except:
        return 0

def load_verdicts():
    try:
        return json.loads(VERDICT_FILE.read_text())
    except:
        return {"verdicts": [], "leaderboard": [], "total_checked": 0, "pass": 0, "marginal": 0, "reject": 0}

def save_verdicts(v):
    VERDICT_FILE.write_text(json.dumps(v, indent=2))

def score_mutation(before, after, resp_before, resp_after):
    """Score a mutation based on real before/after metrics"""
    score = 0
    notes = []

    if before and after:
        cpu_delta = before["cpu_pct"] - after["cpu_pct"]
        mem_delta = before["mem_mb"] - after["mem_mb"]
        if cpu_delta > 0.5:
            score += 2
            notes.append(f"CPU improved {cpu_delta:.1f}%")
        elif cpu_delta < -1.0:
            score -= 2
            notes.append(f"CPU WORSE by {abs(cpu_delta):.1f}%")
        if mem_delta > 5:
            score += 1
            notes.append(f"RAM freed {mem_delta:.0f}MB")
        elif mem_delta < -20:
            score -= 1
            notes.append(f"RAM increased {abs(mem_delta):.0f}MB")

    if resp_before and resp_after:
        resp_delta = resp_before - resp_after
        if resp_delta > 50:
            score += 2
            notes.append(f"Response {resp_delta:.0f}ms faster")
        elif resp_delta < -100:
            score -= 1
            notes.append(f"Response {abs(resp_delta):.0f}ms slower")

    if score >= 2:   verdict = "PASS"
    elif score >= 0: verdict = "MARGINAL"
    else:            verdict = "REJECT"

    return verdict, score, notes

def run():
    log.info("skyd Watchdog starting — external performance monitor")
    log.info(f"Watching container: osone-skyd | Interval: {CHECK_INTERVAL}s")
    verdicts = load_verdicts()
    last_gen = get_current_gen()
    baseline_samples = []

    # Warm up baseline
    log.info("Collecting baseline metrics (30s)...")
    for _ in range(3):
        s = get_skyd_container_stats()
        r = benchmark_response_time()
        if s: baseline_samples.append(s)
        time.sleep(10)

    before_stats = baseline_samples[-1] if baseline_samples else None
    before_resp  = benchmark_response_time()

    log.info(f"Baseline: CPU={before_stats['cpu_pct'] if before_stats else '?'}% | "
             f"RAM={before_stats['mem_mb'] if before_stats else '?'}MB | "
             f"LLM response={before_resp}ms")

    while True:
        time.sleep(CHECK_INTERVAL)
        current_gen = get_current_gen()

        if current_gen > last_gen:
            gens_jumped = current_gen - last_gen
            log.info(f"🧬 Evolution detected! Gen {last_gen} → {current_gen} (+{gens_jumped})")

            after_stats = get_skyd_container_stats()
            after_resp  = benchmark_response_time()

            verdict, score, notes = score_mutation(before_stats, after_stats, before_resp, after_resp)

            entry = {
                "gen": current_gen,
                "ts": datetime.now().isoformat(),
                "verdict": verdict,
                "score": score,
                "notes": notes,
                "before": before_stats,
                "after": after_stats,
                "resp_before_ms": before_resp,
                "resp_after_ms": after_resp,
            }

            verdicts["verdicts"].append(entry)
            verdicts["total_checked"] += 1
            verdicts[verdict.lower()] = verdicts.get(verdict.lower(), 0) + 1

            # Update leaderboard (top 10 highest scoring)
            verdicts["leaderboard"] = sorted(
                [v for v in verdicts["verdicts"] if v["score"] > 0],
                key=lambda x: x["score"], reverse=True
            )[:10]

            # Keep verdicts list to last 200
            if len(verdicts["verdicts"]) > 200:
                verdicts["verdicts"] = verdicts["verdicts"][-200:]

            save_verdicts(verdicts)

            # Write metrics log
            with open(METRICS_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")

            emoji = "✅" if verdict == "PASS" else "⚠️" if verdict == "MARGINAL" else "❌"
            log.info(f"{emoji} Gen {current_gen}: {verdict} (score={score}) — {', '.join(notes) if notes else 'no delta'}")
            log.info(f"   Stats: {verdicts['pass']} PASS | {verdicts['marginal']} MARGINAL | {verdicts['reject']} REJECT")

            # Update baseline for next comparison
            before_stats = after_stats
            before_resp  = after_resp
            last_gen = current_gen

        else:
            # Refresh baseline periodically
            s = get_skyd_container_stats()
            if s:
                before_stats = s

if __name__ == "__main__":
    run()
