import skyd_sandbox as sb, pathlib, json, logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

src = pathlib.Path("/skyd/skyd.py").read_text()
lines = src.count("\n") + 1
fns = len([l for l in src.splitlines() if l.startswith("def ")])
print(f"PRE-EVOLUTION: {lines} lines, {fns} functions")

snippet = '_disk_cache = {"ts": 0, "val": 0}\ndef disk_usage_cached(ttl=30):\n    import time, psutil\n    now = time.time()\n    if now - _disk_cache["ts"] > ttl:\n        _disk_cache["val"] = psutil.disk_usage("/").percent\n        _disk_cache["ts"] = now\n    return _disk_cache["val"]\n'

improvement = {
    "improvement_type": "python",
    "description": "Add disk_usage_cached() to reduce repeated disk checks",
    "code_snippet": snippet,
    "expected_benefit": "Reduces disk IO by caching usage metric for 30s",
    "risk": "low"
}

promoted, new_fit, reason = sb.sandbox_apply_improvement(improvement, 4836, current_fitness=0.45)
print(f"SANDBOX RESULT: promoted={promoted}, fitness={new_fit:.4f}, reason={reason}")

if promoted:
    new_src = pathlib.Path("/skyd/skyd.py").read_text()
    new_lines = new_src.count("\n") + 1
    new_fns = len([l for l in new_src.splitlines() if l.startswith("def ")])
    print(f"POST-EVOLUTION: {new_lines} lines, {new_fns} functions")
    print("disk_usage_cached present:", "disk_usage_cached" in new_src)

print("Sandbox status:", sb.status())
import os
bdir = "/var/log/skyd_backups"
print("Backups:", os.listdir(bdir) if os.path.exists(bdir) else "dir missing")
