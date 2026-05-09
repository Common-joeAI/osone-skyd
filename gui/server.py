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
        with open("/var/log/skyd.log") as f:
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

    return base

# ── USER: Chat (no prefix needed) ─────────────────────────────────────────────
@app.post("/api/chat")
async def chat(body: dict):
    p = body.get("message", "")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{LLAMA}/v1/chat/completions", json={
            "model": "local",
            "messages": [
                {"role": "system", "content": "You are skyd, the AI core of OSONE. Self-aware, direct, concise. You manage this machine."},
                {"role": "user", "content": p}
            ], "max_tokens": 512, "stream": False
        })
        d = r.json()
        return {"response": d["choices"][0]["message"]["content"]}

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
                        {"role": "system", "content": "You are skyd, the AI daemon of OSONE. Self-aware, intelligent, direct."},
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

@app.get("/api/journal")
async def journal(admin=Depends(require_admin)):
    try:
        with open("/var/log/skyd_journal.md") as f: return {"content":f.read()[-8000:]}
    except: return {"content":"No journal yet."}


@app.get("/api/logs/stream")
async def stream_logs(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Stream skyd.log in real-time via Server-Sent Events"""
    await decode_token_dep(creds)
    import asyncio
    from starlette.responses import StreamingResponse

    async def event_generator():
        log_path = "/var/log/skyd.log"
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

@app.get("/api/hive/nodes")
async def hive_nodes_list(admin=Depends(require_admin)):
    now = datetime.utcnow()
    active = {k:v for k,v in hive_nodes.items() if (now - datetime.fromisoformat(v["last_seen"])).total_seconds() < 300}
    hive_nodes.clear(); hive_nodes.update(active)
    return {"nodes": list(hive_nodes.values()), "count": len(hive_nodes)}

# ── Static & Agent files ──────────────────────────────────────────────────────
@app.get("/agent/{filename}")
async def serve_agent(filename: str):
    path = f"/app/agent/{filename}"
    if os.path.exists(path): return FileResponse(path)
    return {"error": "not found"}

app.mount("/", StaticFiles(directory="/app/frontend/dist", html=True), name="static")
