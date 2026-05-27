import difflib
import json
import os
import time
from datetime import datetime

HISTORY_DIR = "/var/log/skyd_history/"
SKYD_PATH = "/skyd/skyd.py"

def _ensure_history_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)

def _gen_filename(gen: int) -> str:
    return os.path.join(HISTORY_DIR, f"gen_{gen:05d}.json")

def record_promotion(old_src: str, new_src: str, gen: int, fitness: float):
    _ensure_history_dir()
    diff = list(difflib.unified_diff(
        old_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile='skyd.py',
        tofile='skyd.py',
        n=3
    ))
    delta_lines = len(diff)
    ts = datetime.utcnow().isoformat() + 'Z'
    entry = {
        "gen": gen,
        "ts": ts,
        "fitness": fitness,
        "delta_lines": delta_lines,
        "diff": ''.join(diff)
    }
    with open(_gen_filename(gen), 'w') as f:
        json.dump(entry, f, indent=2)

def get_history(n=10):
    _ensure_history_dir()
    files = sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith("gen_") and f.endswith(".json")])
    files = files[-n:][::-1]
    result = []
    for fname in files:
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            entry = json.load(f)
        preview = entry.get("diff", "")[:500]
        result.append({
            "gen": entry["gen"],
            "ts": entry["ts"],
            "fitness": entry["fitness"],
            "delta_lines": entry["delta_lines"],
            "diff_preview": preview
        })
    return result

def rollback(gen: int):
    _ensure_history_dir()
    path = _gen_filename(gen)
    if not os.path.exists(path):
        return {"ok": False, "gen": gen, "lines_restored": 0}
    with open(path) as f:
        entry = json.load(f)
    diff_text = entry.get("diff", "")
    if not diff_text:
        return {"ok": False, "gen": gen, "lines_restored": 0}
    try:
        with open(SKYD_PATH, 'r') as f:
            current = f.readlines()
        lines = current[:]
        # Simple line-by-line reversal of unified diff hunks
        for line in diff_text.splitlines():
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                continue
            if line.startswith('-'):
                lines.append(line[1:] + '\n')
            elif line.startswith('+'):
                if lines:
                    lines.pop()
        restored = len(lines)
        with open(SKYD_PATH, 'w') as f:
            f.writelines(lines)
        return {"ok": True, "gen": gen, "lines_restored": restored}
    except Exception:
        return {"ok": False, "gen": gen, "lines_restored": 0}

def prune_history(keep=50):
    _ensure_history_dir()
    files = sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith("gen_") and f.endswith(".json")])
    for old in files[:-keep]:
        try:
            os.remove(os.path.join(HISTORY_DIR, old))
        except OSError:
            pass

def get_regression_candidates():
    _ensure_history_dir()
    files = sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith("gen_") and f.endswith(".json")])
    candidates = []
    prev_fit = None
    prev_gen = None
    for fname in files:
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            entry = json.load(f)
        g = entry["gen"]
        fit = entry["fitness"]
        if prev_fit is not None and fit < prev_fit:
            candidates.append(g)
        prev_fit = fit
        prev_gen = g
    return candidates