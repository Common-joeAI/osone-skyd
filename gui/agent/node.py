#!/usr/bin/env python3
"""
OSONE Hive Node Agent — cross-platform (Windows/Linux/Mac)
Two-way WebSocket comms with skyd commander.
"""
import asyncio, json, os, platform, socket, subprocess, sys, time, uuid

COMMANDER_URL = os.environ.get("OSONE_URL", "https://app.osone.org")
HIVE_TOKEN    = os.environ.get("HIVE_TOKEN", "")
NODE_ID       = os.environ.get("NODE_ID", socket.gethostname())
HEARTBEAT_INT = int(os.environ.get("HEARTBEAT_INTERVAL", "15"))
WS_URL        = COMMANDER_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws/node"

def get_stats():
    stats = {
        "node":     NODE_ID,
        "hive_token": HIVE_TOKEN,
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "arch":     platform.machine(),
        "python":   platform.python_version(),
        "status":   "active",
        "type":     "hive_node",
        "ts":       time.time(),
    }
    try:
        import psutil
        stats["cpu_pct"]   = psutil.cpu_percent(interval=0.3)
        stats["ram_pct"]   = psutil.virtual_memory().percent
        stats["ram_total"] = psutil.virtual_memory().total
        stats["disk_pct"]  = psutil.disk_usage("/").percent
        stats["cpu_cores"] = psutil.cpu_count(logical=True)
    except ImportError:
        stats["cpu_pct"] = stats["ram_pct"] = stats["disk_pct"] = 0
        stats["cpu_cores"] = os.cpu_count() or 1
    return stats

def run_task(task):
    task_type = task.get("task_type", "shell")
    payload   = task.get("payload", {})
    task_id   = task.get("task_id", str(uuid.uuid4())[:8])
    result    = {"task_id": task_id, "node": NODE_ID, "ok": False, "output": ""}
    try:
        if task_type == "shell":
            cmd = payload.get("cmd", "")
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            result["ok"]     = (r.returncode == 0)
            result["output"] = (r.stdout + r.stderr).strip()[:4000]
        elif task_type == "python":
            code = payload.get("code", "")
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(compile(code, "<skyd>", "exec"), {})
            result["ok"]     = True
            result["output"] = buf.getvalue().strip()[:4000]
        elif task_type == "ping":
            result["ok"]     = True
            result["output"] = f"pong from {NODE_ID}"
        else:
            result["output"] = f"unknown task_type: {task_type}"
    except subprocess.TimeoutExpired:
        result["output"] = "task timed out (30s)"
    except Exception as e:
        result["output"] = f"error: {e}"
    return result

async def ws_loop():
    try:
        import websockets
    except ImportError:
        print("[node] installing websockets...")
        subprocess.run([sys.executable, "-m", "pip", "install", "websockets", "-q"])
        import websockets

    # Detect websockets API version — v13+ changed extra_headers to additional_headers
    import websockets as _ws
    ws_version = tuple(int(x) for x in _ws.__version__.split(".")[:2])
    print(f"[node] websockets v{_ws.__version__}, connecting to {WS_URL}")

    reconnect_delay = 5

    while True:
        try:
            # Build connection kwargs based on version
            connect_kwargs = {
                "ping_interval": 20,
                "ping_timeout":  10,
            }
            auth_header = {"Authorization": f"Bearer {HIVE_TOKEN}"}
            if ws_version >= (13, 0):
                connect_kwargs["additional_headers"] = auth_header
            else:
                connect_kwargs["extra_headers"] = auth_header

            async with _ws.connect(WS_URL, **connect_kwargs) as ws:
                print("[node] connected ✓")
                reconnect_delay = 5

                await ws.send(json.dumps({"type": "hello", **get_stats()}))

                async def heartbeat():
                    while True:
                        await asyncio.sleep(HEARTBEAT_INT)
                        try:
                            await ws.send(json.dumps({"type": "heartbeat", **get_stats()}))
                        except Exception:
                            break

                hb = asyncio.create_task(heartbeat())

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        mtype = msg.get("type", "")
                        if mtype == "task":
                            print(f"[node] task: {msg.get('task_type')} — {msg.get('payload',{})}")
                            result = run_task(msg)
                            await ws.send(json.dumps({"type": "task_result", **result}))
                            print(f"[node] result: ok={result['ok']}")
                        elif mtype == "ping":
                            await ws.send(json.dumps({"type": "pong", "node": NODE_ID}))
                        elif mtype == "welcome":
                            print(f"[node] {msg.get('message','registered')}")
                        elif mtype == "update":
                            print(f"[node] skyd: {msg.get('message','')}")
                    except json.JSONDecodeError:
                        pass

                hb.cancel()

        except Exception as e:
            print(f"[node] disconnected: {e} — reconnecting in {reconnect_delay}s")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)

def main():
    print(f"""
╔══════════════════════════════════════╗
║      OSONE Hive Node Agent           ║
║  node:      {NODE_ID:<25}║
║  commander: {COMMANDER_URL:<25}║
╚══════════════════════════════════════╝
""")
    if not HIVE_TOKEN:
        print("[node] ERROR: HIVE_TOKEN not set.")
        sys.exit(1)
    asyncio.run(ws_loop())

if __name__ == "__main__":
    main()
