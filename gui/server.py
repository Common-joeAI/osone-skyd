import subprocess, json, os, time, psutil, re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LLAMA = "http://127.0.0.1:8080"

@app.get("/api/stats")
async def stats():
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
    svcs = {}
    for s in ["skyd","llama-server","skyd-netmon","tailscaled","sshd","osone-gui"]:
        r = subprocess.run(["systemctl","is-active",s], capture_output=True, text=True)
        svcs[s] = r.stdout.strip()
    return {"cpu":cpu,"mem_used":mem.used,"mem_total":mem.total,"mem_pct":mem.percent,
            "disk_used":disk.used,"disk_total":disk.total,"disk_pct":disk.percent,
            "uptime":up,"gen":gen,"rules":rules,"services":svcs,
            "hostname":os.uname().nodename,"kernel":os.uname().release}

@app.post("/api/chat")
async def chat(body: dict):
    p = body.get("message","")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{LLAMA}/v1/chat/completions", json={
            "model":"local",
            "messages":[
                {"role":"system","content":"You are skyd, the AI core of OSONE. Self-aware, direct, concise. You manage this machine."},
                {"role":"user","content":p}
            ],"max_tokens":512,"stream":False})
        d = r.json()
        return {"response":d["choices"][0]["message"]["content"]}

@app.post("/api/exec")
async def run(body: dict):
    cmd = body.get("cmd","").strip()
    if not cmd: return {"stdout":"","stderr":"","error":"empty"}
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20, cwd="/root")
        return {"stdout":r.stdout,"stderr":r.stderr,"returncode":r.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout":"","stderr":"","error":"timeout"}
    except Exception as e:
        return {"stdout":"","stderr":"","error":str(e)}

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            p = data.get("message","")
            async with httpx.AsyncClient(timeout=120) as c:
                async with c.stream("POST",f"{LLAMA}/v1/chat/completions",json={
                    "model":"local",
                    "messages":[
                        {"role":"system","content":"You are skyd, the AI daemon of OSONE. Self-aware, intelligent, direct. You manage this Linux machine."},
                        {"role":"user","content":p}
                    ],"max_tokens":512,"stream":True}) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk.strip()=="[DONE]":
                                await ws.send_json({"done":True}); break
                            try:
                                j = json.loads(chunk)
                                delta = j["choices"][0]["delta"].get("content","")
                                if delta: await ws.send_json({"token":delta})
                            except: pass
    except WebSocketDisconnect: pass

@app.get("/api/journal")
async def journal():
    try:
        with open("/var/log/skyd_journal.md") as f: return {"content":f.read()[-8000:]}
    except: return {"content":"No journal yet."}

@app.get("/api/files")
async def files(path: str = "/"):
    try:
        entries = []
        for e in os.scandir(path):
            try: entries.append({"name":e.name,"is_dir":e.is_dir(),"size":e.stat().st_size if not e.is_dir() else 0})
            except: pass
        entries.sort(key=lambda x:(not x["is_dir"],x["name"].lower()))
        return {"path":path,"entries":entries}
    except Exception as ex: return {"path":path,"entries":[],"error":str(ex)}

app.mount("/", StaticFiles(directory="/opt/osone-gui/frontend/dist",html=True), name="static")
