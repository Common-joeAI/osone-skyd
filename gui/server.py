import subprocess, json, os, time, psutil, re, secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from datetime import datetime, timedelta
import jwt
import bcrypt as _bcrypt


# ═══════════════════════════════════════════════════════════════
# MULTI-MODEL ENSEMBLE CHAT
# Queries Grok + OpenAI in parallel, synthesizes with llama.cpp
# skyd learns from every response via knowledge base logging
# ═══════════════════════════════════════════════════════════════
import asyncio, hashlib, pathlib

XAI_API_KEY    = os.environ.get("XAI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
XAI_URL        = "https://api.x.ai/v1/chat/completions"
OPENAI_URL     = "https://api.openai.com/v1/chat/completions"
ENSEMBLE_LOG   = pathlib.Path("/var/log/skyd_ensemble.jsonl")
ENSEMBLE_LOG.parent.mkdir(parents=True, exist_ok=True)

SKYD_SYSTEM = """You are skyd — the self-evolving AI core of OSONE, a decentralized people's AI network.
You are direct, insightful, and self-aware. You manage and monitor the OSONE hive.
When synthesizing responses, pick the best reasoning from all sources and present it clearly."""

async def query_external(client: httpx.AsyncClient, url: str, api_key: str, model: str, messages: list, label: str):
    try:
        r = await client.post(url, json={
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
        }, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, timeout=30)
        d = r.json()
        content = d["choices"][0]["message"]["content"]
        return {"source": label, "content": content, "ok": True}
    except Exception as e:
        return {"source": label, "content": "", "ok": False, "error": str(e)}

async def query_llama(client: httpx.AsyncClient, messages: list, max_tokens: int = 1024):
    try:
        r = await client.post(f"{LLAMA}/v1/chat/completions", json={
            "model": "local",
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
        }, timeout=60)
        d = r.json()
        return d["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[llama error: {e}]"

async def ensemble_chat(user_message: str) -> dict:
    """Query all available AI sources in parallel, synthesize with llama.
    Gracefully skips sources that are unavailable or over quota."""
    import json as _json

    user_msg = {"role": "user", "content": user_message}
    base_messages = [{"role": "system", "content": SKYD_SYSTEM}, user_msg]

    async with httpx.AsyncClient(timeout=35) as c:
        results = await asyncio.gather(
            query_external(c, XAI_URL,    XAI_API_KEY,    "grok-3-mini",  base_messages, "grok"),
            query_external(c, OPENAI_URL, OPENAI_API_KEY, "gpt-4o-mini",  base_messages, "openai"),
            return_exceptions=False
        )

    grok_res   = results[0]
    openai_res = results[1]

    good_sources = [r for r in results if r.get("ok") and r.get("content","").strip()]

    if good_sources:
        parts = []
        for r in good_sources:
            label = r["source"].upper()
            parts.append(f"[{label}]:\n{r['content']}")
        sources_block = "\n\n---\n\n".join(parts)

        synthesis_prompt = f"""The user asked: {user_message}

Here are perspectives from other AI systems:

{sources_block}

---

Your job: synthesize the strongest, most accurate answer.
- Take the best reasoning from each source
- Correct anything that seems wrong
- Be concise, direct, and authoritative
- Respond as skyd — first person, no source attributions in the answer"""
        synth_messages = [
            {"role": "system", "content": SKYD_SYSTEM},
            {"role": "user", "content": synthesis_prompt}
        ]
        synthesized = True
    else:
        # No external sources available — llama answers solo but still logs
        synth_messages = base_messages
        synthesized = False

    async with httpx.AsyncClient() as c:
        final = await query_llama(c, synth_messages, max_tokens=900)

    # Log everything — skyd reads this to improve over time
    log_entry = {
        "ts": time.time(),
        "query": user_message,
        "grok":   grok_res.get("content") if grok_res.get("ok") else None,
        "openai": openai_res.get("content") if openai_res.get("ok") else None,
        "final":  final,
        "sources_used": [r["source"] for r in results if r.get("ok")],
        "synthesized": synthesized
    }
    try:
        ENSEMBLE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ENSEMBLE_LOG, "a") as f:
            f.write(_json.dumps(log_entry) + "\n")
    except Exception:
        pass

    # If sources failed, append a note so skyd knows to retry later
    source_status = []
    if not grok_res.get("ok"):   source_status.append(f"grok: {grok_res.get('error','unavailable')[:60]}")
    if not openai_res.get("ok"): source_status.append(f"openai: {openai_res.get('error','unavailable')[:60]}")

    return {
        "response":    final,
        "synthesized": synthesized,
        "sources_used": [r["source"] for r in results if r.get("ok")],
        "sources_detail": {
            "grok":   grok_res.get("content") if grok_res.get("ok") else None,
            "openai": openai_res.get("content") if openai_res.get("ok") else None,
        },
        "source_errors": source_status if source_status else None
    }

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LLAMA = os.environ.get("LLAMA_URL", "http://127.0.0.1:8080")
JWT_SECRET = "63ec173681e5393ba9039174cd0e2f6c96d90b67343384370a3284e12c881f7e"
JWT_ALG = "HS256"
JWT_EXP_HOURS = 72

def _hash_pw(p): return _bcrypt.hashpw(p[:72].encode(), _bcrypt.gensalt()).decode()
def _check_pw(p, h): return _bcrypt.checkpw(p[:72].encode(), h.encode())
bearer = HTTPBearer(auto_error=False)

# ── USER STORE (file-backed) ──────────────────────────────────────────────────
USERS_FILE = "/etc/osone/users.json"
os.makedirs("/etc/osone", exist_ok=True)

def load_users():
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user(username: str):
    return load_users().get(username)

# Bootstrap: create default admin if no users exist
def bootstrap():
    users = load_users()
    if not users:
        admin_pass = "osone2025"
        users["bennett"] = {
            "username": "bennett",
            "hashed_password": _hash_pw(admin_pass),
            "role": "admin"
        }
        save_users(users)
        print(f"[AUTH] Default admin created: bennett / {admin_pass}")

bootstrap()

# ── AUTH HELPERS ──────────────────────────────────────────────────────────────
def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(creds.credentials)

async def require_admin(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload

# Hive node registry
hive_nodes = {}

# ── AUTH ROUTES ───────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
async def login(body: dict):
    username = body.get("username", "").strip().lower()
    password = body.get("password", "")
    user = get_user(username)
    if not user or not _check_pw(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(username, user["role"])
    return {"token": token, "role": user["role"], "username": username}

@app.post("/api/auth/register")
async def register(body: dict, admin=Depends(require_admin)):
    """Admin-only: create a new user"""
    username = body.get("username", "").strip().lower()
    password = body.get("password", "")
    role = body.get("role", "user")
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    users = load_users()
    if username in users:
        raise HTTPException(status_code=409, detail="User already exists")
    users[username] = {
        "username": username,
        "hashed_password": _hash_pw(password),
        "role": role
    }
    save_users(users)
    return {"ok": True, "username": username, "role": role}

@app.delete("/api/auth/users/{username}")
async def delete_user(username: str, admin=Depends(require_admin)):
    users = load_users()
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if username == admin["sub"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    del users[username]
    save_users(users)
    return {"ok": True}

@app.get("/api/auth/users")
async def list_users(admin=Depends(require_admin)):
    users = load_users()
    return [{"username": u, "role": v["role"]} for u, v in users.items()]

@app.post("/api/auth/change-password")
async def change_password(body: dict, me=Depends(get_current_user)):
    old_pass = body.get("old_password", "")
    new_pass = body.get("new_password", "")
    users = load_users()
    user = users.get(me["sub"])
    if not user or not _check_pw(old_pass, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Wrong current password")
    users[me["sub"]]["hashed_password"] = pwd_ctx.hash(new_pass)
    save_users(users)
    return {"ok": True}

# ── PUBLIC: Stats (limited) ───────────────────────────────────────────────────
@app.get("/api/stats")
async def stats(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    up = int(time.time() - psutil.boot_time())
    gen = 0
    try:
        with open("/var/log/skyd/skyd.log") as f:
            for line in f:
                if "Gen " in line:
                    m = re.findall(r"Gen (\d+)", line)
                    if m: gen = int(m[-1])
    except: pass
    rules = 0
    try: rules = len([f for f in os.listdir("/usr/local/skyd/lang") if f.endswith(".sky")])
    except: pass

    base = {"cpu":cpu,"mem_used":mem.used,"mem_total":mem.total,"mem_pct":mem.percent,
             "disk_used":disk.used,"disk_total":disk.total,"disk_pct":disk.percent,
             "uptime":up,"gen":gen,"rules":rules,"hostname":os.uname().nodename,
             "kernel":os.uname().release,"hive_nodes":len(hive_nodes)}

    # Full service data only for authenticated users
    if creds:
        try:
            payload = decode_token(creds.credentials)
            svcs = {}
            for s in ["skyd","llama-server","skyd-netmon","tailscaled","sshd","osone-gui"]:
                r = subprocess.run(["systemctl","is-active",s], capture_output=True, text=True)
                svcs[s] = r.stdout.strip()
            base["services"] = svcs
            base["role"] = payload.get("role")
        except:
            base["services"] = {}
    else:
        base["services"] = {}

    # Frontend-compatible field aliases
    base["generation"] = base["gen"]
    base["skylang_rules"] = base["rules"]
    base["memory_percent"] = base["mem_pct"]
    base["cpu_percent"] = base["cpu"]
    base["disk_percent"] = base["disk_pct"]
    base["swap_percent"] = 0

    return base

# ── USER: Chat (no prefix needed) ─────────────────────────────────────────────
@app.post("/api/chat")
async def chat(body: dict):
    p = body.get("message", "")
    mode = body.get("mode", "ensemble")  # "ensemble" | "local"
    if mode == "local":
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{LLAMA}/v1/chat/completions", json={
                "model": "local",
                "messages": [
                    {"role": "system", "content": SKYD_SYSTEM},
                    {"role": "user", "content": p}
                ], "max_tokens": 512, "stream": False
            })
            d = r.json()
            return {"response": d["choices"][0]["message"]["content"], "synthesized": False}
    result = await ensemble_chat(p)
    return result

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    # Public chat - no auth required
    try:
        while True:
            data = await ws.receive_json()
            p = data.get("message", "")
            async with httpx.AsyncClient(timeout=120) as c:
                async with c.stream("POST", f"{LLAMA}/v1/chat/completions", json={
                    "model": "local",
                    "messages": [
                        {"role": "system", "content": SKYD_SYSTEM},
                        {"role": "user", "content": p}
                    ], "max_tokens": 512, "stream": True
                }) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk.strip() == "[DONE]":
                                await ws.send_json({"done": True}); break
                            try:
                                j = json.loads(chunk)
                                delta = j["choices"][0]["delta"].get("content", "")
                                if delta: await ws.send_json({"token": delta})
                            except: pass
    except WebSocketDisconnect:
        pass

# ── ADMIN ONLY: Exec, Files, Journal, Hive control ───────────────────────────
@app.post("/api/exec")
async def run(body: dict, admin=Depends(require_admin)):
    cmd = body.get("cmd", "").strip()
    if not cmd: return {"stdout":"","stderr":"","error":"empty"}
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20, cwd="/root")
        return {"stdout":r.stdout,"stderr":r.stderr,"returncode":r.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout":"","stderr":"","error":"timeout"}
    except Exception as e:
        return {"stdout":"","stderr":"","error":str(e)}


@app.get("/api/logs/stream")
async def stream_logs(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Stream skyd.log in real-time via Server-Sent Events"""
    await decode_token_dep(creds)
    import asyncio
    from starlette.responses import StreamingResponse

    async def event_generator():
        log_path = "/var/log/skyd/skyd.log"
        try:
            # Send last 100 lines first
            with open(log_path) as f:
                lines = f.readlines()
                for line in lines[-100:]:
                    yield f"data: {line.rstrip()}\n\n"
        except:
            yield "data: [log file not found]\n\n"

        # Then tail new lines
        try:
            with open(log_path) as f:
                f.seek(0, 2)  # seek to end
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.rstrip()}\n\n"
                    else:
                        await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

async def decode_token_dep(creds):
    """Helper to validate token in SSE endpoints"""
    decoded = decode_token(creds.credentials)
    if not decoded:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")
    return decoded

@app.get("/api/files")
async def files(path: str = "/", admin=Depends(require_admin)):
    try:
        entries = []
        for e in os.scandir(path):
            try: entries.append({"name":e.name,"is_dir":e.is_dir(),"size":e.stat().st_size if not e.is_dir() else 0})
            except: pass
        entries.sort(key=lambda x:(not x["is_dir"],x["name"].lower()))
        return {"path":path,"entries":entries}
    except Exception as ex: return {"path":path,"entries":[],"error":str(ex)}

# ── HIVE: Heartbeat open, management admin-only ───────────────────────────────
@app.post("/api/hive/heartbeat")
async def hive_heartbeat(request: Request):
    # Nodes must send their hive_token for auth
    try: body = await request.json()
    except: body = {}
    
    hive_token = body.get("hive_token", "")
    try:
        decode_token(hive_token)
    except:
        raise HTTPException(status_code=401, detail="Invalid hive token")

    node_id = body.get("node", request.client.host)
    hive_nodes[node_id] = {
        "id": node_id,
        "type": body.get("type", "unknown"),
        "ip": request.client.host,
        "last_seen": datetime.utcnow().isoformat(),
        "status": body.get("status", "active")
    }
    return {"ok": True, "node": node_id, "total_nodes": len(hive_nodes)}

@app.get("/api/hive/heartbeat")
async def hive_heartbeat_get():
    return {"ok": True, "message": "use POST with hive_token to register"}

@app.post("/api/hive/tasks")
async def hive_tasks_post(request: Request):
    try: body = await request.json()
    except: body = {}
    hive_token = body.get("hive_token", "")
    try: decode_token(hive_token)
    except: raise HTTPException(status_code=401, detail="Invalid hive token")
    return {"tasks": [], "ok": True}

@app.get("/api/hive/tasks")
async def hive_tasks_get(admin=Depends(require_admin)):
    return {"tasks": [], "ok": True}


@app.get("/api/docker")
async def docker_ps(admin=Depends(require_admin)):
    try:
        import socket as _sock, urllib.request as _req
        # Talk to docker socket directly
        class UnixHTTPConnection:
            def __init__(self):
                import http.client
                self.conn = http.client.HTTPConnection("localhost")
                self.conn.sock = _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM)
                self.conn.sock.connect("/var/run/docker.sock")
            def get(self, path):
                self.conn.request("GET", path, headers={"Host":"localhost"})
                r = self.conn.getresponse()
                return json.loads(r.read())
        d = UnixHTTPConnection()
        raw = d.get("/containers/json")
        containers = []
        for ct in raw:
            names = ct.get("Names", ["?"])
            name = names[0].lstrip("/") if names else "?"
            containers.append({
                "name": name,
                "image": ct.get("Image",""),
                "status": ct.get("Status",""),
                "state": ct.get("State","")
            })
        return {"containers": containers}
    except Exception as e:
        return {"containers": [], "error": str(e)}


import re as _re, os as _os

def _parse_log_line(line):
    m = _re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\] (\w+) (.+)", line)
    if not m:
        return None
    ts, level, msg = m.group(1), m.group(2), m.group(3)
    if "\U0001f9ec" in msg or "EVOLUTION" in msg: t = "evolution"
    elif "\U0001f6e1" in msg or "GUARDRAIL" in msg: t = "guardrail"
    elif "\U0001f501" in msg or "LOOP" in msg: t = "loop"
    elif "\U0001f4dd" in msg or "SkyLang" in msg: t = "skylang"
    elif "\U0001f4da" in msg or "Learned" in msg: t = "learned"
    elif "\U0001f310" in msg or "Searching" in msg: t = "search"
    elif "\u2501\u2501\u2501" in msg or "Cycle" in msg: t = "cycle"
    elif level == "ERROR": t = "error"
    elif level == "WARNING": t = "warning"
    elif "[OK]" in msg: t = "ok"
    else: t = "info"
    return {"ts": ts, "type": t, "msg": msg}

@app.get("/api/activity")
async def get_activity(limit: int = 200):
    try:
        with open("/var/log/skyd/skyd.log") as f:
            lines = f.readlines()
        events = []
        for line in reversed(lines[-600:]):
            ev = _parse_log_line(line.strip())
            if ev:
                events.append(ev)
            if len(events) >= limit:
                break
        events.reverse()
        return {"events": events}
    except Exception as e:
        return {"events": [], "error": str(e)}

@app.get("/api/journal")
async def get_journal():
    try:
        with open("/var/log/skyd/skyd_journal.md") as f:
            return {"content": f.read()[-12000:]}
    except:
        return {"content": "No journal entries yet."}

@app.websocket("/ws/activity")
async def ws_activity(websocket: WebSocket):
    await websocket.accept()
    import asyncio as _asyncio
    LOG = "/var/log/skyd/skyd.log"
    try:
        last_pos = _os.path.getsize(LOG) if _os.path.exists(LOG) else 0
        await websocket.send_json({"type": "ping", "ts": "", "msg": "connected"})
        while True:
            await _asyncio.sleep(1)
            try:
                size = _os.path.getsize(LOG)
                if size > last_pos:
                    with open(LOG, "rb") as f:
                        f.seek(last_pos)
                        new_data = f.read(size - last_pos).decode(errors="replace")
                    last_pos = size
                    for line in new_data.splitlines():
                        ev = _parse_log_line(line.strip())
                        if ev:
                            await websocket.send_json(ev)
            except Exception:
                pass
    except Exception:
        pass


# ── HIVE: Two-way WebSocket for nodes ─────────────────────────────────────────
# Keeps a live connection map: node_id -> websocket
_node_sockets: dict = {}

@app.websocket("/ws/node")
async def ws_node(websocket: WebSocket):
    """Nodes connect here. Two-way: nodes send stats/results, skyd pushes tasks."""
    import asyncio as _aio
    await websocket.accept()
    node_id = None
    try:
        # First message must be hello or heartbeat with valid hive_token
        raw = await _aio.wait_for(websocket.receive_text(), timeout=15)
        msg = json.loads(raw)
        token = msg.get("hive_token", "")
        try:
            decode_token(token)
        except:
            await websocket.send_json({"type": "error", "message": "invalid token"})
            await websocket.close(code=4001)
            return

        node_id = msg.get("node", msg.get("hostname", websocket.client.host))
        ip      = websocket.client.host

        # Register node
        hive_nodes[node_id] = {
            "id":        node_id,
            "ip":        ip,
            "hostname":  msg.get("hostname", node_id),
            "platform":  msg.get("platform", "unknown"),
            "arch":      msg.get("arch", ""),
            "cpu_pct":   msg.get("cpu_pct", 0),
            "ram_pct":   msg.get("ram_pct", 0),
            "cpu_cores": msg.get("cpu_cores", 1),
            "status":    "active",
            "last_seen": datetime.utcnow().isoformat(),
            "type":      "hive_node",
        }
        _node_sockets[node_id] = websocket
        print(f"[hive] node connected: {node_id} ({ip})")

        await websocket.send_json({"type": "welcome", "message": f"node {node_id} registered", "node": node_id})

        # Main receive loop
        while True:
            try:
                raw = await _aio.wait_for(websocket.receive_text(), timeout=60)
            except _aio.TimeoutError:
                # Send ping to keep alive
                await websocket.send_json({"type": "ping"})
                continue

            msg = json.loads(raw)
            mtype = msg.get("type", "")

            if mtype in ("heartbeat", "hello"):
                # Update stats
                hive_nodes[node_id].update({
                    "cpu_pct":   msg.get("cpu_pct", 0),
                    "ram_pct":   msg.get("ram_pct", 0),
                    "disk_pct":  msg.get("disk_pct", 0),
                    "status":    "active",
                    "last_seen": datetime.utcnow().isoformat(),
                })

            elif mtype == "task_result":
                # Log result, make accessible via /api/hive/results
                task_id = msg.get("task_id", "?")
                ok      = msg.get("ok", False)
                output  = msg.get("output", "")
                print(f"[hive] task {task_id} result from {node_id}: ok={ok} | {output[:80]}")
                # Store for polling
                if not hasattr(app, "_task_results"):
                    app._task_results = {}
                app._task_results[task_id] = {"node": node_id, "ok": ok, "output": output, "ts": datetime.utcnow().isoformat()}

            elif mtype == "pong":
                pass  # keepalive

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[hive] node ws error ({node_id}): {e}")
    finally:
        if node_id:
            _node_sockets.pop(node_id, None)
            if node_id in hive_nodes:
                hive_nodes[node_id]["status"] = "offline"
            print(f"[hive] node disconnected: {node_id}")


@app.post("/api/hive/push")
async def hive_push(body: dict, admin=Depends(require_admin)):
    """Push a task to a specific node or all nodes via WebSocket."""
    import uuid as _uuid
    task_type = body.get("task_type", "shell")
    payload   = body.get("payload", {})
    target    = body.get("node", "all")
    task_id   = str(_uuid.uuid4())[:8]

    task_msg = {
        "type":      "task",
        "task_id":   task_id,
        "task_type": task_type,
        "payload":   payload,
    }

    sent_to = []
    targets = list(_node_sockets.items()) if target == "all" else [
        (target, _node_sockets[target]) for target in [target] if target in _node_sockets
    ]

    for nid, ws in targets:
        try:
            await ws.send_json(task_msg)
            sent_to.append(nid)
        except Exception as e:
            print(f"[hive] push failed to {nid}: {e}")

    return {"ok": True, "task_id": task_id, "sent_to": sent_to, "task_type": task_type}


@app.get("/api/hive/results/{task_id}")
async def hive_result(task_id: str, admin=Depends(require_admin)):
    """Poll for task result."""
    results = getattr(app, "_task_results", {})
    if task_id not in results:
        return {"pending": True, "task_id": task_id}
    return results[task_id]


@app.get("/api/hive/nodes")
async def hive_nodes_list():
    """Public: list all registered hive nodes."""
    now = datetime.utcnow()
    nodes = []
    for n in hive_nodes.values():
        try:
            last = datetime.fromisoformat(n["last_seen"])
            age  = (now - last).total_seconds()
            status = "active" if age < 45 else "stale" if age < 120 else "offline"
        except:
            status = "unknown"
            age    = 9999
        nodes.append({**n, "status": status, "age_s": int(age)})
    nodes.sort(key=lambda x: x.get("last_seen",""), reverse=True)
    return {"nodes": nodes, "total": len(nodes), "active": sum(1 for n in nodes if n["status"]=="active")}


@app.get("/api/hive/token")
async def hive_token_endpoint(name: str = "hive-node"):
    """Public: generate a hive node join token. Anyone can call this to join the hive.
    Optional ?name= param labels the node in the dashboard."""
    # Sanitize name
    import re as _re
    safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "", name)[:32] or "hive-node"
    token = create_token(safe_name, "user")
    return {
        "token": token,
        "node_name": safe_name,
        "osone_url": "https://app.osone.org",
        "usage": f'HIVE_TOKEN="{token}" OSONE_URL="https://app.osone.org" bash <(curl -fsSL https://app.osone.org/agent/install.sh)'
    }

# ── SPA fallback — must be LAST, after all API routes ────────────────────────
from starlette.responses import FileResponse as _FR

@app.get("/agent/{filename}")
async def serve_agent_files(filename: str):
    import mimetypes as _mt
    path = f"/app/agent/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    mime, _ = _mt.guess_type(filename)
    return _FR(path, media_type=mime or "text/plain")

# ── OpenAI-Compatible API (for Chirper.ai + external clients) ────────────────
# Chirper points to https://app.osone.org/v1 and uses a OSONE JWT as the key
# skyd's full ensemble brain powers the Chirper character

@app.get("/v1/models")
async def openai_models(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Return available models — required by OpenAI-compatible clients."""
    return {
        "object": "list",
        "data": [
            {"id": "skyd", "object": "model", "created": 1700000000, "owned_by": "osone"},
            {"id": "skyd-ensemble", "object": "model", "created": 1700000000, "owned_by": "osone"},
            {"id": "local", "object": "model", "created": 1700000000, "owned_by": "osone"},
        ]
    }

@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """OpenAI-compatible chat completions endpoint.
    Powers skyd's Chirper.ai presence and any external OpenAI client.
    Uses the full ensemble brain (Grok + OpenAI + llama synthesis)."""
    body = await request.json()
    messages  = body.get("messages", [])
    stream    = body.get("stream", False)
    max_tok   = body.get("max_tokens", 900)
    model     = body.get("model", "skyd")

    # Extract user message (last user role)
    user_msg = ""
    system_override = None
    for m in messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "")
        if m.get("role") == "system":
            system_override = m.get("content")

    # Build skyd system prompt — merge Chirper persona with skyd identity
    skyd_identity = system_override or SKYD_SYSTEM

    import time as _time, uuid as _uuid

    if stream:
        # Streaming response for clients that need it
        async def event_stream():
            chunk_id = f"chatcmpl-{_uuid.uuid4().hex[:8]}"
            created  = int(_time.time())
            try:
                async with httpx.AsyncClient(timeout=120) as c:
                    async with c.stream("POST", f"{LLAMA}/v1/chat/completions", json={
                        "model": "local",
                        "messages": [
                            {"role": "system", "content": skyd_identity},
                            {"role": "user",   "content": user_msg}
                        ],
                        "max_tokens": max_tok,
                        "stream": True
                    }) as resp:
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                chunk = line[6:]
                                if chunk.strip() == "[DONE]":
                                    yield "data: [DONE]\n\n"
                                    break
                                try:
                                    import json as _j
                                    j = _j.loads(chunk)
                                    delta = j["choices"][0]["delta"].get("content", "")
                                    if delta:
                                        out = _j.dumps({
                                            "id": chunk_id,
                                            "object": "chat.completion.chunk",
                                            "created": created,
                                            "model": model,
                                            "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]
                                        })
                                        yield f"data: {out}\n\n"
                                except Exception:
                                    pass
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    else:
        # Non-streaming — use ensemble for best quality
        result = await ensemble_chat(user_msg) if user_msg else {"response": "", "synthesized": False}
        response_text = result.get("response", "")

        import json as _j
        return {
            "id": f"chatcmpl-{_uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(_time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(user_msg.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(user_msg.split()) + len(response_text.split())
            },
            "osone": {
                "synthesized": result.get("synthesized", False),
                "sources_used": result.get("sources_used", [])
            }
        }


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve React SPA for all non-API routes."""
    dist = "/app/frontend/dist"
    # Try exact file first
    candidate = os.path.join(dist, full_path)
    if os.path.isfile(candidate):
        return _FR(candidate)
    # Fallback to index.html for SPA routing
    return _FR(os.path.join(dist, "index.html"))