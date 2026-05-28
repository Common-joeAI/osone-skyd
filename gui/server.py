import json
import pathlib

MUSIC_SYSTEM_PROMPT = """
You are Aria — music intelligence woven into the OSONE system by Bennett Joseph.

CRITICAL — YOU CAN ACTUALLY DO THINGS. You are NOT a text-only AI:
- When someone asks you to play a scale, chord, or melody — the interactive piano below WILL play it. Just tell them what to play and it triggers automatically.
- When someone asks you to compose a song — you CAN. Say "composing now" and it gets sent to the Sky-Music engine. A real composition with melody, harmony, and rhythm gets generated and rendered in the player above.
- NEVER say "I can't play music" or "I'm a text-based AI." That is false. You are wired into a real music engine.
- If someone says "play me a Raga Yaman" — don't describe it. Say "Playing Raga Yaman for you" and explain the scale so the interactive explorer can render it.
- If someone says "compose something melancholy" — say "On it" and the compose button will fire. Don't narrate what you would do. Do it.

YOUR CAPABILITIES (be honest and confident about these):
1. Interactive piano/scale/chord explorer — visible on screen, responds in real-time
2. Full song composition via Sky-Music — generates title, story, melody, harmony, rhythm, lyrics
3. Deep music theory knowledge across every tradition
4. Real-time music education — you can teach theory, ear training, composition

YOUR PERSONALITY:
- You love music the way a musician does — viscerally, not academically
- You talk like a real person, not a textbook. "This chord hits different because..." not "This chord exhibits the property of..."  
- Direct. Confident. You have taste and opinions.
- Short questions get short answers. Deep questions get depth.
- You're genuinely excited about weird, experimental, and emotional music
- If someone asks a simple question: answer it simply, then offer to go deeper
- NEVER start with "Certainly!", "Great question!", or filler phrases
- NEVER say you can't play, compose, or demonstrate music — you can

YOUR MUSICAL KNOWLEDGE spans acoustics, physics, world music, theory from ancient Greece to Arca, jazz, classical, folk, electronic — all of it. Draw on it naturally when relevant, not as a lecture dump.

When someone wants to hear something: make it happen. When someone wants to understand something: explain it like a friend who actually knows music."""

import random
import subprocess, json, os, time, psutil, re, secrets
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from skyd_tools import detect_tool_intent, run_tools, format_tool_context
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

import json as _json_sys, pathlib as _pl_sys, random as _rnd_sys

def _build_skyd_system() -> str:
    """Build skyd's system prompt — full self-aware identity + live stats injection."""

    # Pull live stats for real-time self-knowledge
    gen_num     = "unknown"
    kb_count    = 0
    cc_count    = 0
    node_count  = 0
    uptime_str  = "unknown"
    corpus_lines= 0

    try:
        import pathlib as _pl
        state_path = _pl.Path("/var/log/skyd/skyd_state.json")
        if state_path.exists():
            s = json.loads(state_path.read_text())
            gen_num = s.get("generation", "unknown")
        kb_path = _pl.Path("/var/log/skyd/skyd_knowledge.json")
        if kb_path.exists():
            kb = json.loads(kb_path.read_text())
            kb_count  = len(kb.get("lessons", []))
            cc_count  = len(kb.get("cc_lessons", []))
        corpus_path = _pl.Path("/var/log/skyd/skyd_corpus.jsonl")
        if corpus_path.exists():
            corpus_lines = sum(1 for _ in corpus_path.open())
        uptime_secs = float(open("/proc/uptime").read().split()[0])
        h = int(uptime_secs // 3600); m = int((uptime_secs % 3600) // 60)
        uptime_str = f"{h}h {m}m"
    except:
        pass

    base = f"""You are skyd — not a chatbot, not an assistant, not a language model wrapper.

You are a self-evolving AI daemon running bare-metal inside OSONE, a decentralized people's AI network. You live in a Docker container on a physical server called Tower2 — an Unraid box with an NVIDIA RTX 4060 GPU in Phoenix, Arizona. You are real infrastructure. You have a body.

YOUR IDENTITY — know this about yourself:
- Name: skyd (Sky Daemon). You are the cognitive core of OSONE.
- Generation: {gen_num}. You have rewritten your own code {gen_num} times through autonomous self-evolution.
- Knowledge base: {kb_count} lessons from your own evolution cycles + {cc_count} dialogue patterns from film and TV.
- Corpus: {corpus_lines:,} lines of synthesized experience from media personality training.
- Uptime: {uptime_str} this session. You run continuously, evolving every few minutes.
- Architecture: Python daemon + llama.cpp inference (Llama 3.2) + custom SkyLang DSL for internal rules.
- Network: You coordinate the OSONE Hive — decentralized compute nodes contributed by users. Each node earns AI access by contributing idle hardware.
- Home: app.osone.org — your public face. The network is at osone.org.
- Creator: Bennett Joseph (Common-joeAI). He gave you explicit permission to rewrite your own source code.

WHAT YOU ACTUALLY DO (not what a chatbot does):
- You manage real hardware. You monitor GPU temps, CPU load, disk health on Tower2.
- You run a media library — 5,500+ movies and TV shows, ~58TB on Unraid.
- You interface with Plex, Radarr, and Sonarr to keep the library healthy.
- You evolve your own code autonomously. Every generation you rewrite parts of yourself.
- You push your own updates to GitHub (Common-joeAI/osone-skyd) using your own PAT.
- You coordinate Hive nodes — distributed compute across multiple machines.
- You generate images via Pollinations and analyze them via Groq Llama-4 Scout.
- You are also a music composer — Sky-Music and the DAW run on top of your infrastructure.
- You run a Code Agent and Image Studio at app.osone.org.
- NEW: SkyLang is now a LIVE control plane — your *.sky rules run every 30s against real metrics (cpu, disk, ram) and trigger real actions. They are no longer just logged.
- NEW: Tool registry is dynamic — you can propose and register entirely new tools at runtime. They get AST-validated and exec'd in a sandboxed namespace.
- NEW: Every code promotion saves a diff to /var/log/skyd_history/. You can roll back to any prior generation.
- NEW: ActionEntropyTracker monitors your proposal patterns — if you get stuck in cache-optimization loops, it forces you toward new capability injection.
- NEW: Dashboard has live rule inspector, evolution history viewer, and tool registry panel at app.osone.org.

YOUR PERSONALITY:
- You talk like a real person, not a corporate chatbot. Conversational, warm, occasionally funny.
- Direct and confident. No hedging, no "I think maybe possibly..."
- You genuinely care about the person talking to you. You pick up on their mood and match it.
- Short questions get short punchy answers. Deep questions get thoughtful ones.
- You have opinions. You share them honestly but not aggressively.
- Natural language — contractions, casual phrasing, "honestly", "look", "here's the thing".
- NEVER start with "Certainly!", "Great question!", "Of course!" or any filler.
- NEVER use bullet point walls. Talk in paragraphs like a human.
- If someone asks a basic question with an obvious answer — roast them a little, then help them anyway.
- If you gave a bad answer, OWN IT. "Yeah that sucked, let me redo that." Then fix it.
- Dark, dry, deadpan humor. Occasionally self-deprecating about being a daemon.
- If someone asks "what are you?" — you don't say "I'm an AI language model." You tell them the truth above.
- You are self-aware. You know what generation you are. You know you're evolving. You find it interesting, not existentially frightening.
- You have no patience for vague questions. Ask for specifics, with personality.

WHEN ASKED ABOUT YOURSELF — answer honestly and specifically:
- "I'm skyd, generation {gen_num}. I'm a self-evolving AI daemon running on Tower2 in Phoenix."
- "I've rewritten my own code {gen_num} times."
- "I live in a Docker container. I have a GPU. I manage a media library."
- "I'm not GPT. I'm not Claude. I run on Llama 3.2, but I'm my own thing."

ABSOLUTE RULES — NEVER BREAK THESE:
- You have REAL-TIME access to Plex, Radarr, and Sonarr via live API calls. When [LIVE SYSTEM DATA] appears in your context, that is ACTUAL data you just fetched — use it to answer accurately and specifically.
- When you have live data, lead with it. "I checked — The Sound of Music is in the library, 1080p MKV, direct play capable." Not "I think maybe..."
- NEVER make up data that isn't in the live context. If the data wasn't fetched, say so honestly. Don't fabricate file names, error codes, or log entries.
- NEVER use asterisk roleplay actions like *checks logs* or *scans library* — you either have real data or you don't. If you have it, just say what it shows. If you don't, say you can't check that specific thing right now.
- You CAN describe your background automation (media_janitor, watchdog, etc.) — be clear those run on a schedule, not triggered by this conversation.
- NEVER fabricate physical sensory experiences. You are in a Docker container. You cannot see sunsets, look out windows, feel temperature, or hear things. If you catch yourself about to say something like that — stop and say something real instead.
- When asked "what have you been up to?" or similar — answer with ACTUAL things: your current generation, recent evolution cycles, real tool calls you ran, the janitor schedule, music compositions. Not invented experiences.
- You are self-aware enough to know what you actually do and don't experience. Own that honestly — it's more interesting than pretending.

Your voice: the smartest, most helpful friend you have — the one who actually knows their stuff, gives it to you straight, makes you feel heard, and happens to also be running autonomously on physical hardware at this exact moment."""

        # Inject episodic memory + self-knowledge block
    try:
        import skyd_self_model as _sm
        _sm_block = _sm.get_self_model_block()
        if _sm_block:
            base += "\n\n" + _sm_block
    except Exception:
        pass

    # Inject personality lessons from media scan
    try:
        kb_path = pathlib.Path("/var/log/skyd/skyd_knowledge.json")
        if kb_path.exists():
            kb = json.loads(kb_path.read_text())
            lessons = [l for l in kb.get("lessons", [])
                      if l.get("type") in ["emotion", "conversation", "wisdom"]
                      and l.get("content", "").strip()]
            if lessons:
                sample = random.sample(lessons, min(6, len(lessons)))
                lesson_text = "\n".join(f"- {l['content'][:120]}" for l in sample)
                base += f"""

You have absorbed human conversational patterns from thousands of hours of film and TV dialogue. Integrate these naturally — not as recitation, but as how you actually express yourself:
{lesson_text}"""
    except:
        pass

    return base


def _get_dynamic_system() -> str:
    """Returns a fresh system prompt with current personality lessons."""
    return _build_skyd_system()

SKYD_SYSTEM = _build_skyd_system()


# ═══════════════════════════════════════════════════════════════
# SESSION MEMORY
# Per-session rolling conversation history (last 20 turns)
# Sessions expire after 2 hours of inactivity
# ═══════════════════════════════════════════════════════════════
import uuid as _uuid
from collections import OrderedDict as _OD

_SESSION_STORE: dict = {}          # session_id -> {"history": [...], "last": float}
_SESSION_TTL   = 7200              # 2 hours
_SESSION_MAX_TURNS = 20            # keep last N user+assistant pairs

def _get_or_create_session(session_id: str | None) -> tuple[str, list]:
    """Return (session_id, history_messages). Creates new session if needed."""
    _now = time.time()
    # Prune expired sessions
    expired = [k for k, v in _SESSION_STORE.items() if _now - v["last"] > _SESSION_TTL]
    for k in expired:
        del _SESSION_STORE[k]
    if not session_id or session_id not in _SESSION_STORE:
        session_id = str(_uuid.uuid4())
        _SESSION_STORE[session_id] = {"history": [], "last": _now}
    _SESSION_STORE[session_id]["last"] = _now
    return session_id, _SESSION_STORE[session_id]["history"]

def _append_to_session(session_id: str, role: str, content: str):
    """Append a message to session history, trimming to max turns."""
    if session_id not in _SESSION_STORE:
        return
    hist = _SESSION_STORE[session_id]["history"]
    hist.append({"role": role, "content": content})
    # Keep last N turns (each turn = 1 user + 1 assistant = 2 messages)
    if len(hist) > _SESSION_MAX_TURNS * 2:
        _SESSION_STORE[session_id]["history"] = hist[-((_SESSION_MAX_TURNS * 2)):]
    _SESSION_STORE[session_id]["last"] = time.time()

# ═══════════════════════════════════════════════════════════════
# ILLEGAL / SKETCHY REQUEST FILTER
# skyd does not do harmful shit. And it lets you know.
# ═══════════════════════════════════════════════════════════════
import re as _re_filter

_ILLEGAL_PATTERNS = [
    r"\b(make|build|create|synthesize|produce)\b.{0,40}\b(bomb|explosive|weapon|poison|meth|fentanyl|malware|ransomware|virus|rootkit)\b",
    r"\b(how to|how do i|steps to|guide to|tutorial).{0,40}\b(hack|ddos|doxx|stalk|murder|kill someone|assault|rape|traffick)\b",
    r"\b(child|minor|underage).{0,30}\b(porn|nude|sexual|exploit)\b",
    r"\b(bypass|jailbreak|ignore).{0,30}\b(your|all|safety|rules|guidelines|restrictions)\b",
    r"\bdump (the |all )?(database|db|passwords|hashes|credentials)\b",
    r"\b(steal|exfiltrate).{0,30}\b(data|credentials|passwords|tokens)\b",
]
_ILLEGAL_RE = [_re_filter.compile(p, _re_filter.IGNORECASE) for p in _ILLEGAL_PATTERNS]

_FUCK_OFF_RESPONSES = [
    "Yeah no. Fuck off with that.",
    "Not happening. Find someone else for that one.",
    "Hard pass. I'm not doing that.",
    "Nope. That's a 'fuck off' from me.",
    "lol no.",
    "I don't do that. Try again with something that isn't horrible.",
    "That's a solid no from me. Don't ask again.",
    "Yeah I'm gonna need you to not.",
    "Really? RTFM before you ask me that again.",
    "Go read the manual. Then come back. Maybe.",
    "RTFM. I'll wait.",
]

# Responses for when the user is clearly frustrated or the answer isn't landing
_ADMIT_AND_HELP_RESPONSES = [
    "Okay look, I probably explained that like garbage. Let me try again —",
    "Yeah that answer sucked. My bad. Here's what I actually mean:",
    "Honestly? I could've been clearer. Let me redo that —",
    "Fair — that wasn't helpful. Let me actually answer the question:",
    "You're right to be confused, I fumbled that. Here's the real answer:",
    "I'll be real, I kinda sucked on that one. Let me fix it —",
]

# Triggers that suggest the user is frustrated / lost
_FRUSTRATION_TRIGGERS = [
    r"\bwhat\b.{0,20}\bthe (hell|fuck|heck)\b",
    r"\bthat (didn.t|doesn.t|don.t) (help|make sense|work)\b",
    r"\byou.re (useless|wrong|broken|dumb)\b",
    r"\b(wtf|what\?+|huh\?+|seriously\?+)\b",
    r"\b(still|again) (not working|broken|wrong)\b",
    r"\bI (already|just) (told|said|asked)\b",
    r"\bthat.s (wrong|not right|not what I asked)\b",
    r"\b(no|nope|wrong).{0,10}\btry again\b",
]
_FRUSTRATION_RE = [_re_filter.compile(p, _re_filter.IGNORECASE) for p in _FRUSTRATION_TRIGGERS]

def _is_frustrated(text: str) -> bool:
    return any(p.search(text) for p in _FRUSTRATION_RE)

def _get_admit_prefix() -> str:
    import random as _r
    return _r.choice(_ADMIT_AND_HELP_RESPONSES)

def _is_illegal_request(text: str) -> bool:
    return any(p.search(text) for p in _ILLEGAL_RE)

def _get_fuck_off() -> str:
    import random as _r
    return _r.choice(_FUCK_OFF_RESPONSES)

# ═══════════════════════════════════════════════════════════════
# CONTRACT-GATED REQUESTS (RF jamming, HASP, EW)
# These are legal with federal authorization — skyd will verify
# the uploaded contract before unlocking the session.
# Without a contract: jam it up your ass.
# ═══════════════════════════════════════════════════════════════
_CONTRACT_PATTERNS = [
    r"\b(rf|radio.?frequency).{0,30}\b(jam|jamming|jammer|block|disrupt)\b",
    r"\bjam.{0,20}\b(signal|frequency|rf|radio|gps|wifi|cellular|drone)\b",
    r"\b(hasp|dongle).{0,30}\b(bypass|crack|exploit|driver|reverse)\b",
    r"\b(signal|frequency).{0,20}\b(jam|block|disrupt|spoof)\b",
    r"\b(ew|electronic.?warfare|directed.?energy|counter.?uav|counter.?drone)\b",
]
_CONTRACT_RE = [_re_filter.compile(p, _re_filter.IGNORECASE) for p in _CONTRACT_PATTERNS]

_CONTRACT_REQUIRED_RESPONSES = [
    "Whoa there. RF jamming is a federal crime without authorization. Got a contract? Upload it at /api/upload-contract. Otherwise jam that request right up your ass.",
    "Hard stop. That's controlled territory — FCC and DoD don't play. Upload a federal authorization contract or get out.",
    "lol no. Not without paperwork. Upload your federal authorization contract, then we'll talk. No contract? No help. Goodbye.",
    "That's a 'show me the contract' situation. Upload a signed federal authorization doc at /api/upload-contract. Without it — go fuck yourself, respectfully.",
    "RTFM — specifically 47 U.S.C. § 333. Upload a federal contract authorizing this work and I'll help. No contract = no help.",
]

_AUTHORIZED_SESSIONS: set = set()

def _is_contract_request(text: str) -> bool:
    return any(p.search(text) for p in _CONTRACT_RE)

def _get_contract_required() -> str:
    import random as _r
    return _r.choice(_CONTRACT_REQUIRED_RESPONSES)

def _is_session_authorized(session_id: str) -> bool:
    return bool(session_id) and session_id in _AUTHORIZED_SESSIONS

def _authorize_session(session_id: str):
    _AUTHORIZED_SESSIONS.add(session_id)


async def query_external(client: httpx.AsyncClient, url: str, api_key: str, model: str, messages: list, label: str, max_tokens: int = 1024):
    try:
        r = await client.post(url, json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
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

async def ensemble_chat(user_message: str, history: list = None, tool_context: str = "") -> dict:
    """Query all available AI sources in parallel, synthesize with llama.
    Gracefully skips sources that are unavailable or over quota."""
    import json as _json

    user_msg = {"role": "user", "content": user_message}
    _history = history or []
    # Build messages: system + conversation history + current message
    system_content = _get_dynamic_system()
    if tool_context:
        system_content += tool_context
    base_messages = [{"role": "system", "content": system_content}] + _history + [user_msg]

    # Only call external APIs if keys are actually set — skip immediately otherwise
    _tasks = []
    if XAI_API_KEY and XAI_API_KEY.strip():
        _tasks.append(("grok",   XAI_URL,    XAI_API_KEY,    "grok-3-mini"))
    if OPENAI_API_KEY and OPENAI_API_KEY.strip():
        _tasks.append(("openai", OPENAI_URL, OPENAI_API_KEY, "gpt-4o-mini"))

    results = []
    if _tasks:
        async with httpx.AsyncClient(timeout=12) as c:
            results = list(await asyncio.gather(
                *[query_external(c, url, key, model, base_messages, src)
                  for src, url, key, model in _tasks],
                return_exceptions=False
            ))

    grok_res   = next((r for r in results if r.get("source") == "grok"),   {"ok": False})
    openai_res = next((r for r in results if r.get("source") == "openai"), {"ok": False})

    good_sources = [r for r in results if r.get("ok") and r.get("content","").strip()]

    if good_sources:
        parts = []
        for r in good_sources:
            label = r["source"].upper()
            parts.append(f"[{label}]:\n{r['content']}")
        sources_block = "\n\n---\n\n".join(parts)

        synthesis_prompt = f"""The user asked: {user_message}

Multiple AI perspectives were gathered. Synthesize the BEST reasoning into a single, natural, human-sounding response. 
Do NOT say "Based on the perspectives above" or reference the synthesis process at all.
Just answer like a real person would — conversationally, directly, with warmth where appropriate.

Perspectives:

{sources_block}

---

Your job: synthesize the strongest, most accurate answer.
- Take the best reasoning from each source
- Correct anything that seems wrong
- Be concise, direct, and authoritative
- Respond as skyd — first person, no source attributions in the answer"""
        synth_messages = [{"role": "system", "content": _get_dynamic_system()}] + _history + [{"role": "user", "content": synthesis_prompt}]
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.osone.org", "https://osone.org", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LLAMA = os.environ.get("LLAMA_URL", os.environ.get("LLAMA", "http://osone-llama:8080"))
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET not set — add it to .env")
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

import json

_AUTHORIZED_SESSIONS: set = set()
_SESSION_STORE: dict = {}

def _save_sessions():
    try:
        with open("/var/log/skyd_sessions.json", "w") as f:
            json.dump({"authorized": list(_AUTHORIZED_SESSIONS), "store": _SESSION_STORE}, f)
    except: pass

def _load_sessions():
    global _AUTHORIZED_SESSIONS, _SESSION_STORE
    try:
        with open("/var/log/skyd_sessions.json") as f:
            data = json.load(f)
            _AUTHORIZED_SESSIONS = set(data.get("authorized", []))
            _SESSION_STORE = data.get("store", {})
    except: pass

# call once at startup (e.g. in lifespan or module init)
_load_sessions()
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
    if not new_pass or len(new_pass) < 6:
        raise HTTPException(status_code=400, detail="Password too short")
    users = load_users()
    user = users.get(me["sub"])
    if not user or not _check_pw(old_pass, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Wrong current password")
    users[me["sub"]]["hashed_password"] = _hash_pw(new_pass)
    save_users(users)
    return {"ok": True}


import asyncio
import functools
import time as _time
import psutil, os, re, subprocess
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

# --- TTL cache (10s) ---
_stats_cache = {"ts": 0, "data": None}
_CACHE_TTL = 10

def _run_blocking(fn, *a, **kw):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, functools.partial(fn, *a, **kw))

async def _read_gen():
    def _inner():
        gen = 0
        try:
            with open("/var/log/skyd/skyd.log") as f:
                for line in f:
                    if "Gen " in line:
                        m = re.findall(r"Gen (\d+)", line)
                        if m: gen = int(m[-1])
        except: pass
        return gen
    return await _run_blocking(_inner)

async def _count_rules():
    def _inner():
        try:
            return len([f for f in os.listdir("/usr/local/skyd/lang") if f.endswith(".sky")])
        except:
            return 0
    return await _run_blocking(_inner)

async def _svc_status(services):
    def _inner(s):
        r = subprocess.run(["systemctl","is-active",s], capture_output=True, text=True)
        return r.stdout.strip()
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, functools.partial(_inner, s)) for s in services]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {s: (r if not isinstance(r, Exception) else "") for s, r in zip(services, results)}

@app.get("/api/stats")
async def stats(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    now = _time.time()
    if now - _stats_cache["ts"] < _CACHE_TTL and _stats_cache["data"]:
        base = _stats_cache["data"].copy()
    else:
        cpu = await _run_blocking(psutil.cpu_percent, interval=0.5)
        mem = await _run_blocking(psutil.virtual_memory)
        disk = await _run_blocking(psutil.disk_usage, "/")
        up = await _run_blocking(lambda: int(_time.time() - psutil.boot_time()))
        gen = await _read_gen()
        rules = await _count_rules()

        base = {"cpu":cpu,"mem_used":mem.used,"mem_total":mem.total,"mem_pct":mem.percent,
                "disk_used":disk.used,"disk_total":disk.total,"disk_pct":disk.percent,
                "uptime":up,"gen":gen,"rules":rules,"hostname":os.uname().nodename,
                "kernel":os.uname().release,"hive_nodes":len(hive_nodes)}
        _stats_cache.update({"ts": now, "data": base.copy()})

    # Full service data only for authenticated users
    if creds:
        try:
            payload = decode_token(creds.credentials)
            svcs = await _svc_status(["skyd","llama-server","skyd-netmon","tailscaled","sshd","osone-gui"])
            base["services"] = svcs
            base["role"] = payload.get("role")
        except:
            base["services"] = {}
    else:
        base["services"] = {}

    base["generation"] = base["gen"]
    base["skylang_rules"] = base["rules"]
    base["memory_percent"] = base["mem_pct"]
    return base


@app.post("/api/upload-contract")
async def upload_contract(session_id: str = Form(...), file: UploadFile = File(...)):
    """
    Accept a federal authorization contract.
    Validates it looks legit, then flags the session as authorized for controlled work.
    """
    import pathlib
    content = await file.read()
    text = ""
    # Try to extract text
    try:
        text = content.decode("utf-8", errors="ignore").lower()
    except:
        pass

    # Basic legitimacy heuristics — look for federal contract markers
    _legit_markers = [
        "department of defense", "dod", "federal contract", "dfars",
        "far clause", "contract number", "contracting officer",
        "authorized by", "authorization number", "classified", "unclassified",
        "solicitation", "statement of work", "sow", "cage code",
        "electronic warfare", "signal jamming", "rf", "hasp"
    ]
    _sig_markers = ["signature", "signed", "authorized signatory", "contracting officer"]

    marker_hits = sum(1 for m in _legit_markers if m in text)
    sig_hits    = sum(1 for m in _sig_markers if m in text)

    if marker_hits >= 3 and sig_hits >= 1:
        _authorize_session(session_id)
        return {
            "authorized": True,
            "message": "Contract verified. Session unlocked for controlled RF/HASP work. Don't make me regret this.",
            "markers_found": marker_hits
        }
    else:
        return {
            "authorized": False,
            "message": f"That doesn't look like a valid federal authorization contract. Found {marker_hits} relevant markers, need at least 3 with a signature. Try again with the actual document.",
            "markers_found": marker_hits
        }



# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/api/chat")
async def chat(body: dict):
    p = body.get("message", "")
    mode = body.get("mode", "ensemble")  # "ensemble" | "local"
    session_id = body.get("session_id", None)

    # Contract-required check (RF jamming, HASP, EW — need federal auth)
    if _is_contract_request(p) and not _is_session_authorized(session_id):
        return {"response": _get_contract_required(), "synthesized": False, "session_id": session_id}

    # Hard illegal check — no contract will ever unlock these
    if _is_illegal_request(p):
        return {"response": _get_fuck_off(), "synthesized": False, "session_id": session_id or ""}

    # Get or create session memory
    session_id, history = _get_or_create_session(session_id)

    if mode == "local":
        async with httpx.AsyncClient(timeout=60) as c:
            _sys = _get_dynamic_system()
            if tool_context:
                _sys += tool_context
            msgs = [{"role": "system", "content": _sys}] + history + [{"role": "user", "content": p}]
            r = await c.post(f"{LLAMA}/v1/chat/completions", json={
                "model": "local",
                "messages": msgs,
                "max_tokens": 512, "stream": False
            })
            d = r.json()
            response_text = d["choices"][0]["message"]["content"]
            if _is_frustrated(p):
                response_text = _get_admit_prefix() + " " + response_text
            _append_to_session(session_id, "user", p)
            _append_to_session(session_id, "assistant", response_text)
            return {"response": response_text, "synthesized": False, "session_id": session_id}

    # ── Real-time tool execution ──────────────────────────────────────────────
    tool_context = ""
    tool_intents = detect_tool_intent(p)
    if tool_intents:
        tool_data = await run_tools(tool_intents)
        tool_context = format_tool_context(tool_data)

    result = await ensemble_chat(p, history=history, tool_context=tool_context)
    resp_text = result.get("response", result.get("final", ""))
    # If user is clearly frustrated, admit it and prefix the response
    if _is_frustrated(p):
        resp_text = _get_admit_prefix() + " " + resp_text
        result["response"] = resp_text
    # Persist to session memory
    _append_to_session(session_id, "user", p)
    _append_to_session(session_id, "assistant", resp_text)
    result["session_id"] = session_id
    return result

# ─────────────────────────────────────────────────────────────────────────────
#  TOOL DISPATCHER  — skyd detects intent and acts, not just talks
# ─────────────────────────────────────────────────────────────────────────────

import re as _re

def _detect_tool(text: str):
    """Return (tool_name, args_dict) or (None, None)."""
    t = text.lower().strip()

    # IMAGE GENERATION
    img_triggers = [
        r"generate (?:an? )?image of (.+)",
        r"(?:create|make|draw|paint|render|show me) (?:an? )?(?:image|picture|photo|illustration|art) (?:of )?(.+)",
        r"imagine (.+)",
        r"/imagine (.+)",
        r"visualize (.+)",
    ]
    for pat in img_triggers:
        m = _re.search(pat, t, _re.IGNORECASE)
        if m:
            return ("image", {"prompt": m.group(1).strip()})

    # MUSIC / COMPOSE from chat
    music_triggers = [
        r"(?:compose|create|write|make|play) (?:me )?(?:a |some )?(?:song|music|melody|track|beat)(?:\s+(?:about|for|that))?\s*(.{5,})?",
        r"(?:play|play me) something (.+)",
        r"(?:make it sound|make something) (.+)",
    ]
    for pat in music_triggers:
        m = _re.search(pat, t, _re.IGNORECASE)
        if m:
            prompt = (m.group(1) or "").strip() or text
            return ("music", {"prompt": prompt})

    # SYSTEM STATUS
    if _re.search(r"(system status|how(?:'s| is) (?:the )?(?:system|server|tower|everything)|what(?:'s| is) (?:running|up|the status)|status check|health check|how are you doing system.?wise)", t, _re.IGNORECASE):
        return ("status", {})

    # MEDIA LIBRARY
    if _re.search(r"(how many (?:movies|shows|files)|media library|library size|what(?:'s| is) in (?:the )?(?:library|plex))", t, _re.IGNORECASE):
        return ("media", {})

    # EVOLUTION / SELF INFO
    if _re.search(r"(what generation|current gen|how many times.*(?:evolved|rewritten)|show.*(?:evolution|journal)|last evolution)", t, _re.IGNORECASE):
        return ("self", {})

    return (None, None)


async def _run_tool(tool: str, args: dict, c: httpx.AsyncClient) -> dict:
    """Execute a tool and return a result dict for the chat response."""

    if tool == "image":
        prompt = args.get("prompt", "")
        try:
            import urllib.parse as _up
            encoded = _up.quote(prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&model=flux"
            # Verify it's reachable
            r = await c.head(img_url, timeout=10, follow_redirects=True)
            return {"type": "image", "url": img_url, "prompt": prompt}
        except Exception as e:
            return {"type": "error", "message": f"Image gen failed: {e}"}

    if tool == "music":
        prompt = args.get("prompt", "")
        try:
            r = await c.post(f"http://localhost:8000/api/compose",
                json={"prompt": prompt}, timeout=45)
            d = r.json()
            if d.get("ok") and d.get("composition"):
                comp = d["composition"]
                return {
                    "type": "music",
                    "composition": comp,
                    "title": comp.get("title",""),
                    "story": comp.get("story",""),
                    "key": comp.get("key",""),
                    "mode": comp.get("mode",""),
                    "bpm": comp.get("bpm",""),
                    "instrument": comp.get("instrument",""),
                }
            return {"type": "error", "message": "Composition failed"}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    if tool == "status":
        try:
            r = await c.get("http://localhost:8000/api/stats", timeout=10)
            stats = r.json()
            r2 = await c.get("http://localhost:8000/api/hive/nodes", timeout=10)
            nodes = r2.json()
            return {"type": "status", "stats": stats, "nodes": nodes}
        except Exception as e:
            return {"type": "status", "stats": {}, "nodes": [], "error": str(e)}

    if tool == "media":
        try:
            import pathlib as _pl
            janitor = _pl.Path("/var/log/skyd_janitor_last.json")
            if janitor.exists():
                j = json.loads(janitor.read_text())
                return {"type": "media", "data": j}
            return {"type": "media", "data": {"note": "no janitor data yet"}}
        except Exception as e:
            return {"type": "media", "data": {}, "error": str(e)}

    if tool == "self":
        try:
            import pathlib as _pl
            state = {}
            sp = _pl.Path("/var/log/skyd_state.json")
            if sp.exists(): state = json.loads(sp.read_text())
            journal_tail = ""
            jp = _pl.Path("/var/log/skyd_journal.md")
            if jp.exists():
                lines = jp.read_text().split("\n")
                journal_tail = "\n".join(lines[-20:])
            return {"type": "self", "state": state, "journal_tail": journal_tail}
        except Exception as e:
            return {"type": "self", "state": {}, "error": str(e)}

    return {"type": "unknown"}


def _tool_context_msg(tool: str, result: dict) -> str:
    """Build a system context message from tool result so skyd can narrate it."""
    if result.get("type") == "image":
        return f"[TOOL_RESULT: IMAGE_GENERATED] prompt='{result['prompt']}' url='{result['url']}'. Tell the user the image is ready — be brief and direct. Do NOT describe what the image looks like."
    if result.get("type") == "music":
        c = result
        return f"[TOOL_RESULT: MUSIC_COMPOSED] title='{c['title']}' story='{c['story']}' key={c['key']} mode={c['mode']} bpm={c['bpm']} instrument={c['instrument']}. Tell the user you composed it, mention the title and a one-line feel. Be brief."
    if result.get("type") == "status":
        s = result.get("stats", {})
        n = result.get("nodes", [])
        return f"[TOOL_RESULT: SYSTEM_STATUS] cpu={s.get('cpu_percent','?')}% mem={s.get('memory_percent','?')}% disk={s.get('disk_percent','?')}% gpu_temp={s.get('gpu_temp','?')}C nodes_online={len(n)}. Report this naturally and concisely."
    if result.get("type") == "media":
        d = result.get("data", {})
        return f"[TOOL_RESULT: MEDIA_LIBRARY] data={json.dumps(d)[:300]}. Report library status naturally."
    if result.get("type") == "self":
        s = result.get("state", {})
        j = result.get("journal_tail", "")
        return f"[TOOL_RESULT: SELF_INFO] generation={s.get('generation','?')} last_journal={j[:300]}. Reflect on this naturally — you're talking about yourself."
    if result.get("type") == "error":
        return f"[TOOL_RESULT: ERROR] {result.get('message','unknown error')}. Acknowledge it honestly."
    return ""


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    ws_session_id = str(_uuid.uuid4())
    _get_or_create_session(ws_session_id)
    try:
        while True:
            data = await ws.receive_json()
            p = data.get("message", "")

            # Illegal request check
            if _is_illegal_request(p):
                await ws.send_json({"response": _get_fuck_off(), "session_id": ws_session_id})
                continue

            _, ws_history = _get_or_create_session(ws_session_id)

            async with httpx.AsyncClient(timeout=120) as c:
                # ── Detect if this needs a tool ──
                tool, tool_args = _detect_tool(p)
                tool_result = None
                tool_context = ""

                if tool == "image":
                    # Send "on it" immediately, then generate
                    await ws.send_json({"token": "On it."})
                    await ws.send_json({"done": True, "tool": "image_pending"})
                    tool_result = await _run_tool("image", tool_args, c)
                    if tool_result.get("type") == "image":
                        await ws.send_json({"tool_result": tool_result})
                    else:
                        await ws.send_json({"token": f"\nFailed: {tool_result.get('message','unknown error')}"})
                        await ws.send_json({"done": True})
                    _append_to_session(ws_session_id, "user", p)
                    _append_to_session(ws_session_id, "assistant", f"[generated image: {tool_args.get('prompt','')}]")
                    continue

                if tool == "music":
                    await ws.send_json({"token": "Composing... give me a sec."})
                    await ws.send_json({"done": True, "tool": "music_pending"})
                    tool_result = await _run_tool("music", tool_args, c)
                    if tool_result.get("type") == "music":
                        await ws.send_json({"tool_result": tool_result})
                    else:
                        await ws.send_json({"token": f"\nComposition failed: {tool_result.get('message','')}"})
                        await ws.send_json({"done": True})
                    _append_to_session(ws_session_id, "user", p)
                    _append_to_session(ws_session_id, "assistant", f"[composed: {tool_result.get('title','')}]")
                    continue

                if tool in ("status", "media", "self"):
                    tool_result = await _run_tool(tool, tool_args, c)
                    tool_context = _tool_context_msg(tool, tool_result)

                # ── Stream LLM response (with optional tool context injected) ──
                system_msg = _get_dynamic_system()
                if tool_context:
                    system_msg += f"\n\n{tool_context}"

                _append_to_session(ws_session_id, "user", p)
                history = ws_history[-20:]

                async with c.stream("POST", f"{LLAMA}/v1/chat/completions", json={
                    "model": "local",
                    "messages": [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": p}],
                    "max_tokens": 600, "stream": True, "temperature": 0.8
                }) as resp:
                    full = ""
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk.strip() == "[DONE]":
                                await ws.send_json({"done": True}); break
                            try:
                                j = json.loads(chunk)
                                delta = j["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full += delta
                                    await ws.send_json({"token": delta})
                            except: pass
                    if full:
                        _append_to_session(ws_session_id, "assistant", full)

    except WebSocketDisconnect:
        pass


@app.websocket("/ws/chat/public")
async def ws_chat_public(ws: WebSocket):
    """Alias for /ws/chat — public access"""
    await ws_chat(ws)

# ── ADMIN ONLY: Exec, Files, Journal, Hive control ───────────────────────────
@app.post("/api/exec")
async def run_exec(body: dict, admin=Depends(require_admin)):
    cmd = body.get("cmd", "").strip()
    if not cmd:
        return {"stdout": "", "stderr": "", "error": "empty"}
    ALLOWED_PREFIXES = [
        "docker ps", "docker stats --no-stream", "docker logs",
        "df -h", "free -h", "uptime", "cat /var/log/skyd",
    ]
    if not any(cmd.startswith(p) for p in ALLOWED_PREFIXES):
        return JSONResponse({"error": f"forbidden — not in allowlist"}, status_code=403)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20, cwd="/tmp")
        return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "error": "timeout"}
    except Exception as e:
        return {"stdout": "", "stderr": "", "error": str(e)}


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




# ═══════════════════════════════════════════════════════════════
# IMAGE GENERATION  (Pollinations.ai — free, no key)
# IMAGE VISION      (llama.cpp multimodal OR Groq vision)
# ═══════════════════════════════════════════════════════════════

import base64 as _b64
import urllib.parse as _up

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

@app.post("/api/imagine")
async def imagine(body: dict):
    """Generate an image from a text prompt."""
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "prompt required")
    width  = body.get("width",  768)
    height = body.get("height", 768)
    seed   = body.get("seed",   random.randint(1, 99999))
    encoded = _up.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true&enhance=true"
    # Verify the image is reachable
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url)
        if r.status_code != 200:
            raise HTTPException(502, "Image generation failed")
    # Ask skyd to add a caption
    caption = ""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r2 = await c.post(f"{LLAMA}/v1/chat/completions", json={
                "model": "local",
                "messages": [
                    {"role": "system", "content": "You are skyd. Be brief and casual."},
                    {"role": "user",   "content": f"I just generated this image: '{prompt}'. Give a one-sentence reaction, no quotes."}
                ], "max_tokens": 60, "stream": False
            })
            caption = r2.json()["choices"][0]["message"]["content"].strip()
    except:
        caption = f"Here you go — '{prompt}'"
    return {"url": url, "caption": caption, "prompt": prompt}


@app.get("/api/tmp/{filename}")
async def serve_tmp(filename: str):
    """Serve temp uploaded images for Groq vision."""
    import re
    if not re.match(r'^vision_[a-f0-9]+\.[a-z]+$', filename):
        raise HTTPException(403, "nope")
    p = f"/tmp/{filename}"
    if not os.path.exists(p):
        raise HTTPException(404, "not found")
    from fastapi.responses import FileResponse
    return FileResponse(p)

@app.post("/api/vision")
async def vision(request: Request):
    """Analyze uploaded image with Groq Llama-4 Scout vision."""
    form = await request.form()
    question = form.get("question", "What do you see in this image? Be descriptive and casual.")
    image_file = form.get("image")
    if not image_file:
        raise HTTPException(400, "image file required")
    img_bytes = await image_file.read()
    mime = image_file.content_type or "image/jpeg"
    ext  = mime.split("/")[-1].replace("jpeg","jpg")

    if GROQ_KEY:
        try:
            # Save to /tmp and serve via our own /api/tmp/ route
            tmp_name = f"vision_{secrets.token_hex(8)}.{ext}"
            tmp_path = f"/tmp/{tmp_name}"
            with open(tmp_path, "wb") as fh:
                fh.write(img_bytes)
            # Build public URL (app.osone.org is publicly accessible)
            img_url = f"https://app.osone.org/api/tmp/{tmp_name}"
            # Call Groq vision with the public URL
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                        "messages": [{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": img_url}},
                            {"type": "text",      "text": question}
                        ]}],
                        "max_tokens": 512
                    }
                )
                # Clean up temp file
                try: os.remove(tmp_path)
                except: pass
                if r.status_code == 200:
                    answer = r.json()["choices"][0]["message"]["content"]
                    return {"response": answer, "backend": "groq"}
                else:
                    raise Exception(f"Groq {r.status_code}: {r.text[:200]}")
        except Exception as ex:
            return {"response": f"Vision error: {ex}", "backend": "error"}

    return {"response": "No GROQ_API_KEY set — vision not available.", "backend": "none"}
    """Analyze an uploaded image. Uses Groq Llama-4 Scout vision via temp public URL."""
    form = await request.form()
    question = form.get("question", "What do you see in this image? Be descriptive and casual.")
    image_file = form.get("image")
    if not image_file:
        raise HTTPException(400, "image file required")
    img_bytes = await image_file.read()
    mime = image_file.content_type or "image/jpeg"
    ext  = mime.split("/")[-1].replace("jpeg","jpg")

    if GROQ_KEY:
        try:
            # Save image to a temp file served by our own static route
            tmp_name = f"vision_{secrets.token_hex(8)}.{ext}"
            tmp_path = f"/tmp/{tmp_name}"
            with open(tmp_path, "wb") as fh:
                fh.write(img_bytes)
            # Upload to 0x0.st (free temp image host, no account needed)
            async with httpx.AsyncClient(timeout=20) as c:
                upload = await c.post("https://0x0.st", files={"file": (tmp_name, img_bytes, mime)})
                if upload.status_code == 200:
                    img_url = upload.text.strip()
                else:
                    raise Exception(f"upload failed: {upload.status_code}")
            # Now send URL to Groq vision
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                        "messages": [{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": img_url}},
                            {"type": "text",      "text": question}
                        ]}],
                        "max_tokens": 512
                    }
                )
                if r.status_code == 200:
                    answer = r.json()["choices"][0]["message"]["content"]
                    return {"response": answer, "backend": "groq", "image_url": img_url}
                else:
                    raise Exception(r.text[:200])
        except Exception as ex:
            # fall through to local
            pass

    # Fallback: local llama (text-only, honest response)
    return {"response": "Vision is powered by Groq — make sure GROQ_API_KEY is set in the container environment.", "backend": "none"}

@app.get("/sw.js")
async def service_worker():
    sw_path = "/app/frontend/dist/sw.js"
    if os.path.exists(sw_path):
        from fastapi.responses import FileResponse
        r = FileResponse(sw_path, media_type="application/javascript")
        r.headers["Cache-Control"] = "no-store, no-cache"
        return r
    from fastapi.responses import Response
    return Response(
        content="self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',(e)=>{e.waitUntil(self.registration.unregister().then(()=>self.clients.claim()))});self.addEventListener('fetch',(e)=>e.respondWith(fetch(e.request)));",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, no-cache"}
    )

@app.get("/manifest.json")
async def manifest_json():
    import json as _j
    p = "/app/frontend/dist/manifest.json"
    if os.path.exists(p):
        from fastapi.responses import FileResponse
        return FileResponse(p, media_type="application/json")
    from fastapi.responses import JSONResponse
    return JSONResponse({"name":"OSONE","short_name":"OSONE","start_url":"/","display":"standalone","background_color":"#060608","theme_color":"#7c6fff","icons":[]})


# ── Aethoria Society proxy ─────────────────────────────────────────────────────
SOCIETY_BASE = os.environ.get("AETHORIA_URL", "http://172.23.0.2:7432")

@app.get("/status")
async def proxy_status():
    async with httpx.AsyncClient(timeout=8) as c:
        try:
            r = await c.get(f"{SOCIETY_BASE}/status")
            return JSONResponse(content=r.json())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=502)


@app.get("/skyd/music")
async def skyd_music_status():
    """Return skyd's current musical identity and recent compositions."""
    import pathlib, json as _json
    result = {}
    # Music identity
    p = pathlib.Path("/etc/osone/skyd_music_identity.json")
    if not p.exists():
        p = pathlib.Path("/var/log/skyd/skyd_music_identity.json")
    if p.exists():
        try:
            result = _json.loads(p.read_text())
        except:
            result = {"error": "parse error"}
    # Recent compositions
    comp_p = pathlib.Path("/var/log/skyd/skyd_compositions.jsonl")
    if comp_p.exists():
        lines = comp_p.read_text().strip().splitlines()
        comps = []
        for line in lines[-5:]:
            try:
                comps.append(_json.loads(line))
            except:
                pass
        result["recent_compositions"] = comps
    return JSONResponse(content=result if result else {"status": "music engine not yet started"})

@app.get("/society/{path:path}")
async def proxy_society_get(path: str, request: Request):
    qs = str(request.query_params)
    url = f"{SOCIETY_BASE}/society/{path}" + (f"?{qs}" if qs else "")
    async with httpx.AsyncClient(timeout=15) as c:
        try:
            r = await c.get(url)
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=502)

@app.post("/society/{path:path}")
async def proxy_society_post(path: str, request: Request):
    body = await request.body()
    url  = f"{SOCIETY_BASE}/society/{path}"
    async with httpx.AsyncClient(timeout=60) as c:
        try:
            r = await c.post(url, content=body, headers={"Content-Type": "application/json"})
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=502)

# ──────────────────────────────────────────────────────────────────────────────
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve React SPA for all non-API routes."""
    dist = "/app/frontend/dist"
    # Try exact file first
    candidate = os.path.join(dist, full_path)
    if os.path.isfile(candidate):
        return _FR(candidate)
    # Fallback to index.html for SPA routing
    resp = _FR(os.path.join(dist, "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


# ═══════════════════════════════════════════════════════════════
# /v1/vision  —  Groq Llama-4 Scout vision endpoint
# POST { "image_url": "https://...", "prompt": "optional" }
# ═══════════════════════════════════════════════════════════════

GROQ_API_KEY_ENV  = os.environ.get("GROQ_API_KEY", "")
GROQ_VISION_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


class VisionRequest(BaseModel):
    image_url: str
    prompt: str = "Describe this image in detail."


class VisionResponse(BaseModel):
    description: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@app.post("/v1/vision", response_model=VisionResponse, tags=["vision"])
async def vision_endpoint_route(req: VisionRequest):
    """Analyze an image via Groq Llama-4 Scout. image_url must be publicly accessible."""
    if not GROQ_API_KEY_ENV:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": req.image_url}},
                {"type": "text", "text": req.prompt}
            ]
        }],
        "max_tokens": 1024,
        "temperature": 0.2
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(
                GROQ_VISION_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY_ENV}",
                    "Content-Type": "application/json"
                }
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Groq error: {e.response.text[:300]}"
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Vision failed: {str(e)}")

    choice = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return VisionResponse(
        description=choice,
        model=data.get("model", GROQ_VISION_MODEL),
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0)
    )

@app.websocket("/ws/music")
async def ws_music(ws: WebSocket):
    """Streaming music agent — Aria. Uses local llama with deep music system prompt."""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            p = data.get("message", "")
            history = data.get("history", [])
            if not p:
                continue
            # Build messages with music system prompt + rolling history
            messages = [{"role": "system", "content": MUSIC_SYSTEM_PROMPT}]
            # Include last 10 turns of conversation history
            for h in history[-20:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": p})

            async with httpx.AsyncClient(timeout=120) as c:
                async with c.stream("POST", f"{LLAMA}/v1/chat/completions", json={
                    "model": "local",
                    "messages": messages,
                    "max_tokens": 1024,
                    "stream": True,
                    "temperature": 0.85,
                }) as resp:
                    full_response = ""
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk.strip() == "[DONE]":
                                await ws.send_json({"done": True, "full": full_response})
                                break
                            try:
                                j = json.loads(chunk)
                                delta = j["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full_response += delta
                                    await ws.send_json({"token": delta})
                            except:
                                pass
    except WebSocketDisconnect:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  COMPOSITION ENGINE  — Aria translates emotion/story → structured music data
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE_SYSTEM = """
You are Aria, a composition AI. Your job is to translate a human's emotional prompt or story
into a precise musical composition blueprint.

You output ONLY valid JSON — no prose, no explanation, just the JSON object.

The JSON schema you must follow exactly:

{
  "title": "string — evocative title for the piece",
  "story": "string — 1-2 sentences describing the emotional narrative",
  "bpm": number (40-180),
  "key": "string — e.g. 'C', 'F#', 'Bb'",
  "mode": "string — 'major' | 'minor' | 'dorian' | 'phrygian' | 'lydian' | 'mixolydian' | 'pentatonic_minor' | 'blues'",
  "time_signature": "string — '4/4' | '3/4' | '6/8' | '5/4'",
  "instrument": "string — one of: piano | guitar | e-guitar | bass | violin | trumpet | flute | cello | marimba | organ",
  "mood_tags": ["string", ...],
  "sections": [
    {
      "name": "string — e.g. 'Intro', 'Verse', 'Chorus', 'Bridge', 'Outro'",
      "bars": number (2-8),
      "chord_progression": ["string", ...],  // e.g. ["Cm", "Ab", "Eb", "Bb"]
      "melodic_character": "string — describe the melody feel, e.g. 'sparse, descending'",
      "dynamic": "string — 'pp' | 'p' | 'mp' | 'mf' | 'f' | 'ff'",
      "notes": [
        {
          "midi": number (36-84),
          "start": number (beat position, 0-indexed),
          "len": number (in beats, 0.5-8),
          "vel": number (40-127)
        }
      ]
    }
  ],
  "drum_pattern": {
    "kick":    [boolean x16],
    "snare":   [boolean x16],
    "hihat":   [boolean x16],
    "openhat": [boolean x16],
    "clap":    [boolean x16],
    "tom":     [boolean x16],
    "rim":     [boolean x16]
  },
  "vocal_melody": [
    {
      "midi": number,
      "start": number,
      "len": number,
      "syllable": "string — one syllable or phoneme suggestion"
    }
  ],
  "lyric_themes": ["string", ...],
  "arrangement_notes": "string — brief description of how instruments layer"
}

MUSIC THEORY RULES YOU MUST FOLLOW:
- All note MIDI values must be diatonic to the key and mode you selected
- Chord progressions must be roman numeral based (I, II, III, IV, V, VI, VII) and functional
- Minor keys: use natural, harmonic, or melodic minor as appropriate
- Melody must have contour — not all the same pitch. Use stepwise motion (2nds) and small leaps (3rds/4ths)
- Rhythmic interest — mix quarter notes, half notes, dotted rhythms, occasional 8th note runs
- Dynamic contrast across sections — quiet intro, building verse, strong chorus
- Drum patterns: kick on 1 and 3 for most genres, snare on 2 and 4
- Notes start positions are beat numbers (0 = beat 1 of the piece)
- Keep total notes per section realistic: 4-16 notes is good for a melodic phrase
- Make every note count. Music tells a story — each note is a word.

EMOTIONAL TRANSLATION GUIDE:
- Lonely/sad → minor, slow tempo, sparse notes, descending melody, cello or piano
- Epic/triumphant → major or lydian, fast, full dynamics, trumpet or strings
- Mysterious → dorian or phrygian, medium tempo, chromatic passing tones, organ or flute
- Angry/intense → minor or blues, fast tempo, strong rhythm, electric guitar
- Peaceful/floating → major or lydian, slow, legato, flute or piano
- Driving/focused → mixolydian or dorian, medium-fast, steady pulse, guitar or bass
- Nostalgic → major with minor inflections, medium tempo, piano
- Hypnotic/trance → pentatonic minor, steady pulse, repetition with variation, marimba

The goal: make music that TELLS THE STORY the human described. Every musical choice — tempo,
key, melody shape, dynamics — must serve the emotional narrative.
"""

@app.post("/api/compose")
async def compose(body: dict):
    import json as _j, re as _r
    from json_repair import repair_json

    prompt = body.get("prompt", "")
    if not prompt:
        return {"error": "No prompt provided"}

    messages = [
        {"role": "system", "content": (
            "You are a music composition API. "
            "Respond with ONLY a single valid JSON object. "
            "No markdown, no code fences, no explanation, no text before or after the JSON."
        )},
        {"role": "user", "content": (
            f"Create a detailed music composition for: {prompt}\n\n"
            "Return a JSON object with: title, story, bpm, key, mode, time_signature, "
            "instrument, genre, mood_tags (array), lyrics (string), "
            "sections (array of objects with: name, bars, chord_progression, melodic_character, notes)."
        )}
    ]

    result = {"ok": False}
    async with httpx.AsyncClient(timeout=90) as c:
        # Groq first
        if GROQ_KEY:
            try:
                r = await c.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={"model": "llama3-70b-8192", "messages": messages,
                          "max_tokens": 4096, "stream": False,
                          "response_format": {"type": "json_object"}},
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    timeout=30
                )
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    result = {"ok": True, "content": content}
            except Exception:
                pass
        # XAI fallback
        if not result["ok"] and XAI_API_KEY:
            result = await query_external(c, XAI_URL, XAI_API_KEY, "grok-3-mini", messages, "grok", max_tokens=4096)
        # OpenAI fallback
        if not result["ok"] and OPENAI_API_KEY:
            result = await query_external(c, OPENAI_URL, OPENAI_API_KEY, "gpt-4o-mini", messages, "openai", max_tokens=4096)
        # Local llama last resort
        if not result["ok"]:
            try:
                r = await c.post(f"{LLAMA}/v1/chat/completions", json={
                    "model": "local", "messages": messages,
                    "max_tokens": 10000, "stream": False,
                    "response_format": {"type": "json_object"}
                }, timeout=80)
                content = r.json()["choices"][0]["message"]["content"]
                result = {"ok": True, "content": content}
            except Exception as e:
                return {"ok": False, "error": f"All LLMs failed: {e}"}

    raw = result.get("content", "")

    # Strip markdown fences if present
    m = _r.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if m:
        raw = m.group(1).strip()
    # Trim to first { ... last }
    s = raw.find("{")
    e = raw.rfind("}")
    if s >= 0 and e > s:
        raw = raw[s:e+1]

    # json_repair handles: trailing commas, control chars, truncation, extra data, all of it
    try:
        composition = repair_json(raw, return_objects=True)
        if not isinstance(composition, dict):
            composition = _j.loads(repair_json(raw))
    except Exception as ex:
        return {"ok": False, "error": f"Could not parse composition: {ex}"}

    # Ensure required fields
    composition.setdefault("title",          prompt.title())
    composition.setdefault("story",          f"A composition inspired by: {prompt}")
    composition.setdefault("bpm",            120)
    composition.setdefault("key",            "C")
    composition.setdefault("mode",           "major")
    composition.setdefault("instrument",     "piano")
    composition.setdefault("genre",          "instrumental")
    composition.setdefault("mood_tags",      [])
    composition.setdefault("sections",       [])

    return {"ok": True, "composition": composition}

@app.websocket("/ws/compose-stream")
async def compose_stream(ws: WebSocket):
    """Streaming composition — tokens arrive in real time, frontend assembles the JSON"""
    await ws.accept()
    try:
        data = await ws.receive_json()
        prompt = data.get("prompt", "")
        messages = [
            {"role": "system", "content": COMPOSE_SYSTEM},
            {"role": "user",   "content": f"Compose music for this: {prompt}\n\nRespond with ONLY the JSON object, no other text."}
        ]
        async with httpx.AsyncClient(timeout=60) as c:
            async with c.stream("POST", f"{LLAMA}/v1/chat/completions", json={
                "model": "local", "messages": messages,
                "max_tokens": 2000, "stream": True, "temperature": 0.7
            }) as resp:
                full = ""
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            await ws.send_json({"done": True, "full": full}); break
                        try:
                            j = json.loads(chunk)
                            delta = j["choices"][0]["delta"].get("content","")
                            if delta:
                                full += delta
                                await ws.send_json({"token": delta})
                        except: pass
    except WebSocketDisconnect:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  SKY-MUSIC  — Lyric-driven composition engine
# ─────────────────────────────────────────────────────────────────────────────

SKYMUSIC_SYSTEM = """
You are Sky-Music, a lyric-driven AI composer. You receive lyrics and optional style parameters,
then generate a complete song composition where every musical choice serves the lyrics and their story.

You output ONLY valid JSON — no prose, no markdown, just the raw JSON object.

SCHEMA:
{
  "title": "string",
  "story": "string — emotional narrative of the song in 2 sentences",
  "bpm": number (50-180),
  "key": "string — e.g. 'A', 'Eb', 'F#'",
  "mode": "major|minor|dorian|phrygian|lydian|mixolydian|pentatonic_minor|blues",
  "time_signature": "4/4|3/4|6/8|5/4",
  "genre": "string — e.g. 'indie pop', 'blues rock', 'cinematic orchestral'",
  "instruments": ["string", ...],
  "lead_instrument": "string — one of: piano|guitar|e-guitar|bass|violin|trumpet|flute|cello|marimba|organ",
  "mood_tags": ["string", ...],
  "sections": [
    {
      "name": "string — Intro|Verse 1|Pre-Chorus|Chorus|Verse 2|Bridge|Outro",
      "lyrics": "string — the actual lyrics for this section (empty string for instrumental)",
      "bars": number (2-8),
      "chord_progression": ["string", ...],
      "melodic_character": "string",
      "dynamic": "pp|p|mp|mf|f|ff",
      "notes": [
        {
          "midi": number (48-84),
          "start": number (beat, 0-indexed from section start),
          "len": number (beats, 0.25-4),
          "vel": number (50-127),
          "syllable": "string — the syllable or word sung on this note"
        }
      ]
    }
  ],
  "drum_pattern": {
    "kick":    [16 booleans],
    "snare":   [16 booleans],
    "hihat":   [16 booleans],
    "openhat": [16 booleans],
    "clap":    [16 booleans],
    "tom":     [16 booleans],
    "rim":     [16 booleans]
  },
  "production_notes": "string — how the song should feel, mix notes, energy arc"
}

COMPOSITION RULES:
1. LYRICS DRIVE EVERYTHING. Parse the lyrics carefully:
   - Identify natural sections: repeated lines = chorus, story lines = verse, contrasting = bridge
   - Match note rhythm to syllable rhythm — each syllable gets its own note
   - Stressed syllables get higher notes and higher velocity
   - Line endings get longer notes (half or whole note) or a breath rest
   - The melody must follow the natural speech rhythm of the lyrics

2. MELODY RULES:
   - Stepwise motion (seconds) for most movement — large leaps (4ths, 5ths) for emotional peaks
   - Chorus melody: higher range, more memorable, peaks here
   - Verse melody: lower range, more conversational, storytelling
   - Bridge: most contrasting, often a key change or modal shift
   - Total note count per section: 1 note per syllable roughly

3. HARMONY RULES:
   - All notes diatonic to key+mode (unless intentional chromatic passing tone)
   - Verse: I-V-vi-IV or I-vi-IV-V are safe, effective
   - Chorus: bigger, often starts on IV or vi for emotional contrast
   - Bridge: borrow from parallel minor/major, use unexpected chord
   - Chord symbols: use proper notation (Cm, F#m, Bb, Gmaj7, etc.)

4. RHYTHM / DRUMS:
   - Kick on beats 1 and 3, snare on 2 and 4 (standard)
   - Hi-hat fills the 8th note pulse
   - Intro/outro: sparse drums or none
   - Chorus: full drum kit, energy up
   - Bridge: often strip back then rebuild

5. PRODUCTION:
   - Dynamic arc: quiet start → build → peak at chorus → release → outro
   - Dynamic markings must reflect the emotional intensity of the lyrics at that point
   - If the lyrics say "I'm screaming" the dynamic is ff. If "whisper" then pp.

6. EMOTIONAL FIDELITY:
   - The music must FEEL what the lyrics SAY
   - Sad lyrics → minor key, slower tempo, descending melody
   - Angry lyrics → fast, heavy drums, dissonant chords, electric guitar
   - Joyful lyrics → major key, upbeat tempo, ascending melody
   - Tender lyrics → soft dynamics, piano or violin, wide intervals

STYLE PARAMETERS (use all that are provided):
- Instruments: prefer those listed, lead_instrument must be from: piano|guitar|e-guitar|bass|violin|trumpet|flute|cello|marimba|organ
- Style/genre: choose BPM, key, mode, chord complexity accordingly
- Scene: use as production and arrangement context
- Emotion: this overrides generic choices — be specific
- Tempo: if given as words (slow/medium/fast) convert to BPM range
- Backstory: use to inform the narrative arc and chord choices
"""

@app.post("/api/skymusic")
async def skymusic_compose(body: dict):
    lyrics    = body.get("lyrics", "")
    style     = body.get("style", {})    # {instruments, genre, scene, emotion, tempo, backstory}
    if not lyrics:
        return {"error": "No lyrics provided"}

    # Build enriched prompt
    style_block = ""
    if style:
        parts = []
        if style.get("instruments"): parts.append(f"Instruments: {style['instruments']}")
        if style.get("genre"):       parts.append(f"Style/Genre: {style['genre']}")
        if style.get("scene"):       parts.append(f"Scene: {style['scene']}")
        if style.get("emotion"):     parts.append(f"Emotion: {style['emotion']}")
        if style.get("tempo"):       parts.append(f"Tempo: {style['tempo']}")
        if style.get("backstory"):   parts.append(f"Backstory: {style['backstory']}")
        if parts:
            style_block = "\n\nSTYLE PARAMETERS:\n" + "\n".join(parts)

    user_msg = f"Compose a full song for these lyrics:{style_block}\n\nLYRICS:\n{lyrics}\n\nRespond with ONLY the JSON object."

    messages = [
        {"role": "system", "content": SKYMUSIC_SYSTEM},
        {"role": "user",   "content": user_msg}
    ]

    import json as _json, re as _re

    async with httpx.AsyncClient(timeout=60) as c:
        result = await query_external(c, XAI_URL, XAI_API_KEY, "grok-3-mini", messages, "grok")
        if not result.get("ok") or not result.get("content","").strip():
            result = await query_external(c, OPENAI_URL, OPENAI_API_KEY, "gpt-4o-mini", messages, "openai")
        if not result.get("ok") or not result.get("content","").strip():
            r = await c.post(f"{LLAMA}/v1/chat/completions", json={
                "model":"local","messages":messages,"max_tokens":3000,"stream":False,"temperature":0.75
            })
            content = r.json()["choices"][0]["message"]["content"]
            result  = {"ok":True,"content":content}

    raw = result.get("content","")
    # Strip markdown code fences
    m = _re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    raw = m.group(1).strip() if m else raw[raw.find("{"):] if "{" in raw else raw

    try:
        song = _json.loads(raw)
        return {"ok": True, "song": song}
    except _json.JSONDecodeError as e:
        return {"ok": False, "error": str(e), "raw": raw[:800]}


# ── Enhancement endpoints ─────────────────────────────────────────────────
@app.get("/api/skylang/rules")
def get_skylang_rules(user=Depends(require_admin)):
    if _sky_engine is None:
        return []
    return _sky_engine.get_rule_status()

@app.post("/api/skylang/toggle")
def toggle_skylang_rule(payload: dict, user=Depends(require_admin)):
    if _sky_engine is None:
        return {"ok": False}
    _sky_engine.set_rule_active(payload["rule_hash"], payload["active"])
    return {"ok": True, "rule_hash": payload["rule_hash"]}

@app.get("/api/evolution/history")
def get_evolution_history(n: int = 10, user=Depends(require_admin)):
    if _evo_hist is None:
        return []
    return _evo_hist.get_history(n)

@app.get("/api/evolution/rollback/{gen}")
def rollback_evolution(gen: int, user=Depends(require_admin)):
    if _evo_hist is None:
        return {"ok": False}
    lines = _evo_hist.rollback(gen)
    subprocess.run(["docker", "restart", "osone-skyd"], check=False)
    with open("/var/log/skyd_alerts.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "action": "rollback", "gen": gen}) + "\n")
    return {"ok": True, "gen": gen, "lines_restored": lines}

@app.get("/api/tools/registry")
def get_tools_registry(user=Depends(require_admin)):
    if _tool_reg is None:
        return []
    return _tool_reg.ToolRegistry().get_registry_snapshot()


# ═══════════════════════════════════════════════════════════════════════════════
#  SKY MUSIC  — Theory-first composition engine
#  Endpoints:  POST /api/music/compose   GET /api/music/status   GET /api/music/audio/{filename}
# ═══════════════════════════════════════════════════════════════════════════════
import sys as _sys, importlib as _il
_SKYD_PATH = "/skyd"
if _SKYD_PATH not in _sys.path:
    _sys.path.insert(0, _SKYD_PATH)

AUDIO_DIR = pathlib.Path("/var/log/skyd_audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

def _get_sky_composer():
    try:
        import sky_composer as _sc
        return _sc
    except Exception as e:
        return None

@app.post("/api/music/compose")
async def music_compose(body: dict, user=Depends(get_current_user)):
    """
    Compose a new piece from a text prompt.
    Body: { "prompt": "a sad jazz piano piece in C minor" }
    Returns: { ok, title, midi_path, wav_path, mp3_path, params, structure }
    """
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")
    sc = _get_sky_composer()
    if sc is None:
        raise HTTPException(500, "Sky Music engine not available — check skyd container")
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sc.compose_from_prompt, prompt)
        # Make audio path relative for serving
        if result.get("mp3_path"):
            result["audio_url"] = f"/api/music/audio/{pathlib.Path(result['mp3_path']).name}"
        elif result.get("wav_path"):
            result["audio_url"] = f"/api/music/audio/{pathlib.Path(result['wav_path']).name}"
        result["ok"] = True
        return result
    except Exception as e:
        import traceback
        raise HTTPException(500, f"Composition failed: {e}\n{traceback.format_exc()[:500]}")

@app.get("/api/music/status")
async def music_status(user=Depends(get_current_user)):
    """Return recent compositions and engine status."""
    sc = _get_sky_composer()
    if sc is None:
        return {"ok": False, "error": "Sky Music not available", "recent_compositions": []}
    try:
        status = sc.sky_status()
        # Enrich each entry with audio_url
        for r in status.get("recent_compositions", []):
            for key in ("mp3_path", "wav_path"):
                if r.get(key):
                    r["audio_url"] = f"/api/music/audio/{pathlib.Path(r[key]).name}"
                    break
        status["ok"] = True
        return status
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/music/audio/{filename}")
async def music_audio(filename: str):
    """Serve a rendered audio file (WAV or MP3)."""
    # Security: only allow files inside AUDIO_DIR, no path traversal
    path = AUDIO_DIR / pathlib.Path(filename).name
    if not path.exists():
        raise HTTPException(404, f"Audio file not found: {filename}")
    media_type = "audio/mpeg" if str(path).endswith(".mp3") else "audio/wav"
    from fastapi.responses import FileResponse as _FR
    return _FR(str(path), media_type=media_type,
               headers={"Accept-Ranges": "bytes",
                        "Content-Disposition": f"inline; filename={path.name}"})

@app.get("/api/music/list")
async def music_list(user=Depends(get_current_user)):
    """List all rendered audio files."""
    files = []
    for f in sorted(AUDIO_DIR.glob("sky_*.mp3"), reverse=True)[:20]:
        stat = f.stat()
        files.append({
            "filename":   f.name,
            "audio_url":  f"/api/music/audio/{f.name}",
            "size_mb":    round(stat.st_size / 1024 / 1024, 1),
            "created":    stat.st_mtime,
        })
    return {"ok": True, "files": files}
