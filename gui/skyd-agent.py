#!/usr/bin/env python3
"""
OSONE Underling Agent — skyd-agent
Drop this on any machine. It joins the hive and takes orders from OSONE.
"""
import os, sys, json, time, subprocess, platform, threading, socket
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ── CONFIG ─────────────────────────────────────────
COMMANDER_IP = os.environ.get("OSONE_IP", "100.104.30.60")
COMMANDER_PORT = 8000
AGENT_PORT = 7777
NODE_ID = socket.gethostname() + "-" + str(os.getpid())
NODE_NAME = socket.gethostname()
CAPABILITIES = ["shell", "python", "llm_inference", "file_processing", "web_scrape"]

# ── TASK HANDLER ───────────────────────────────────
def handle_task(task_type, payload):
    print(f"[AGENT] Task received: {task_type}")

    if task_type == "shell":
        cmd = payload.get("cmd", "echo ok")
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {"status": "done", "stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}

    elif task_type == "python":
        code = payload.get("code", "")
        try:
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                exec(code, {})
            return {"status": "done", "output": buf.getvalue()}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    elif task_type == "ping":
        return {"status": "pong", "node": NODE_NAME, "time": datetime.now().isoformat()}

    elif task_type == "sysinfo":
        return {
            "status": "done",
            "cpu": psutil.cpu_percent(interval=0.5),
            "mem": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
            "platform": platform.platform(),
            "node": NODE_NAME
        }

    elif task_type == "web_scrape":
        url = payload.get("url", "")
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=15) as r:
                return {"status": "done", "content": r.read(10000).decode(errors="replace")}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    else:
        return {"status": "unknown_task", "type": task_type}

# ── HTTP SERVER ─────────────────────────────────────
class AgentHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # quiet

    def do_POST(self):
        if self.path == "/task":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            result = handle_task(body.get("type","ping"), body.get("payload",{}))
            resp = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length", len(resp))
            self.end_headers()
            self.wfile.write(resp)

    def do_GET(self):
        if self.path == "/health":
            resp = json.dumps({"status":"alive","node":NODE_NAME,"id":NODE_ID}).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            self.wfile.write(resp)

# ── REGISTRATION + HEARTBEAT ────────────────────────
def register():
    import urllib.request, urllib.error
    mem = psutil.virtual_memory()
    data = json.dumps({
        "node_id": NODE_ID,
        "ip": get_tailscale_ip(),
        "name": NODE_NAME,
        "capabilities": CAPABILITIES,
        "cpu_cores": psutil.cpu_count(),
        "ram_gb": round(mem.total / 1e9, 1)
    }).encode()
    try:
        req = urllib.request.Request(
            f"http://{COMMANDER_IP}:{COMMANDER_PORT}/api/hive/register",
            data=data, headers={"Content-Type":"application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
        print(f"[AGENT] Registered with OSONE commander at {COMMANDER_IP}")
    except Exception as e:
        print(f"[AGENT] Registration failed: {e} — will retry")

def heartbeat_loop():
    import urllib.request
    while True:
        time.sleep(20)
        try:
            data = json.dumps({
                "node_id": NODE_ID,
                "load": psutil.cpu_percent(interval=0.5),
                "status": "idle"
            }).encode()
            req = urllib.request.Request(
                f"http://{COMMANDER_IP}:{COMMANDER_PORT}/api/hive/heartbeat",
                data=data, headers={"Content-Type":"application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except: pass

def get_tailscale_ip():
    try:
        r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        ip = r.stdout.strip()
        if ip: return ip
    except: pass
    # fallback to hostname IP
    try: return socket.gethostbyname(socket.gethostname())
    except: return "127.0.0.1"

# ── MAIN ────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[AGENT] skyd-agent starting on {NODE_NAME} (port {AGENT_PORT})")
    print(f"[AGENT] Commander: {COMMANDER_IP}:{COMMANDER_PORT}")

    # Start heartbeat thread
    threading.Thread(target=heartbeat_loop, daemon=True).start()

    # Register with commander
    register()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", AGENT_PORT), AgentHandler)
    print(f"[AGENT] Listening for tasks on port {AGENT_PORT}")
    server.serve_forever()
