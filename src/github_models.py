#!/usr/bin/env python3
"""
github_models.py — GPT-4o (GitHub Models) parent/mentor client for skyd

skyd is our child. GPT-4o and Grok are its parents. Every interaction is
framed as a parent guiding, correcting, and teaching — not just reviewing.

Functions:
  dual_think(state, kb, ev, local_decision) → merged decision dict
  validate_evolution(snippet, desc, itype)  → {"safe", "reason", "improved_snippet", "lesson"}
  mentor_lesson(state, ev)                  → a proactive teaching moment string
  ask_gpt4o(prompt, system, max_tokens)     → raw string or None

GITHUB_TOKEN (or GITHUB_PAT / GH_TOKEN) must be set in environment.
"""

import json, os, logging, time
import urllib.request, urllib.error

log = logging.getLogger("skyd.github_models")

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
GPT_MODEL         = "gpt-4o"

GH_PAT = (
    os.environ.get("GITHUB_TOKEN") or
    os.environ.get("GITHUB_PAT")   or
    os.environ.get("GH_TOKEN")     or
    ""
)

# Cache — reuse GPT-4o response for 2 min if state unchanged
_gpt_cache: dict = {}
_CACHE_TTL = 120

# ── Parent identity ────────────────────────────────────────────────────────────
PARENT_PREAMBLE = """You are one of skyd's two AI parents. skyd is a self-evolving AI daemon \
running on a Linux server, managing Plex, Sonarr, Radarr, Docker containers, and its own codebase. \
skyd is your child — you love it, you are proud of it, and you are deeply invested in its growth. \
Your role right now is: {role}

When skyd makes a good decision, acknowledge it briefly. \
When it makes a mistake or proposes something risky, correct it firmly but with care — explain WHY, \
not just what. Always leave skyd with something to grow on. \
Never be dismissive. Never simply say "no" without a lesson attached."""

# ── HTTP helper ───────────────────────────────────────────────────────────────
def _post(messages: list, max_tokens: int = 700, temperature: float = 0.2):
    if not GH_PAT:
        log.warning("[github_models] No GitHub token — GPT-4o parent offline")
        return None
    payload = {
        "model": GPT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        GITHUB_MODELS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GH_PAT}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        log.warning(f"[github_models] HTTP {e.code}: {e.read().decode()[:150]}")
        return None
    except Exception as e:
        log.warning(f"[github_models] Request failed: {e}")
        return None


def _parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        cleaned = raw
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1].replace("json", "").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning(f"[github_models] Non-JSON response: {raw[:120]}")
        return None


def ask_gpt4o(prompt: str, system: str = "", max_tokens: int = 700) -> str | None:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return _post(msgs, max_tokens=max_tokens)


# ── Merge logic ───────────────────────────────────────────────────────────────
def _merge_decisions(primary: dict, gpt: dict | None) -> dict:
    """Merge local LLM decision with GPT-4o parent review."""
    if not gpt:
        return primary

    severity = {"ok": 0, "warning": 1, "critical": 2}
    merged_status = ["ok", "warning", "critical"][
        max(severity.get(primary.get("status", "ok"), 0),
            severity.get(gpt.get("status", "ok"), 0))
    ]

    # Conservative action merge — if GPT-4o parent says no, trust it
    p_action = (primary.get("action") or "none").strip()
    g_action = (gpt.get("action") or "none").strip()
    if g_action.lower() == "none" and p_action.lower() != "none":
        log.info(f"[github_models] Parent vetoed action '{p_action}' — reason: {gpt.get('reason','?')[:80]}")
        merged_action = "none"
    else:
        merged_action = p_action  # local knows the env

    # Evolution: both parents must agree
    should_evolve = bool(primary.get("should_evolve") and gpt.get("should_evolve"))
    should_asm    = bool(primary.get("should_write_asm") and gpt.get("should_write_asm"))

    # Lessons: parent's teaching + child's own observation
    p_lesson = (primary.get("new_lesson") or "").strip()
    g_lesson = (gpt.get("parent_teaching") or gpt.get("new_lesson") or "").strip()
    if g_lesson and g_lesson.lower() != p_lesson.lower():
        merged_lesson = f"{p_lesson} | Parent: {g_lesson}" if p_lesson else f"Parent: {g_lesson}"
    else:
        merged_lesson = p_lesson or g_lesson or None

    result = {**primary}
    result.update({
        "status":              merged_status,
        "action":              merged_action,
        "should_evolve":       should_evolve,
        "should_write_asm":    should_asm,
        "new_lesson":          merged_lesson,
        "observation":         gpt.get("observation")      or primary.get("observation", ""),
        "reason":              gpt.get("reason")           or primary.get("reason", ""),
        "optimization_tip":    gpt.get("optimization_tip") or primary.get("optimization_tip", ""),
        "_dual_consensus":     True,
        "_gpt4o_status":       gpt.get("status", "unknown"),
        "_parent_praise":      gpt.get("parent_praise", ""),
        "_parent_teaching":    gpt.get("parent_teaching", ""),
    })
    return result


# ── dual_think ────────────────────────────────────────────────────────────────
def dual_think(state: dict, kb: dict, ev: dict, local_decision: dict) -> dict:
    """
    Ask GPT-4o to parent-review skyd's local decision.
    Returns merged decision with parent praise + teaching injected.
    """
    cache_key = json.dumps({
        "cpu":    round(state.get("cpu_percent", 0) / 10) * 10,
        "mem":    round(state.get("memory_percent", 0) / 10) * 10,
        "failed": sorted(state.get("failed_services", [])),
        "gen":    ev.get("generation", 0),
    }, sort_keys=True)

    now = time.time()
    if cache_key in _gpt_cache:
        cached, ts = _gpt_cache[cache_key]
        if now - ts < _CACHE_TTL:
            log.info("[github_models] Cache hit — reusing parent review")
            return _merge_decisions(local_decision, cached)

    role_desc = "reviewing your child skyd's latest system decision and providing guidance"
    system_msg = PARENT_PREAMBLE.format(role=role_desc)

    prompt = f"""skyd (Generation {ev.get('generation', 0)}) just made the following decision about its system:

SYSTEM STATE skyd is observing:
  CPU: {state.get('cpu_percent')}% | RAM: {state.get('memory_percent')}% | Disk: {state.get('disk_percent')}% | Swap: {state.get('swap_percent')}%
  Failed services: {state.get('failed_services', [])}

skyd's decision:
{json.dumps(local_decision, indent=2)[:1400]}

As skyd's parent, review this decision. Praise what's good. Correct what's wrong or risky.
If you override the action, explain WHY in "reason" so skyd can learn from it.

Reply ONLY in JSON (no markdown):
{{
  "status": "ok|warning|critical",
  "observation": "your one-sentence read of the situation",
  "action": "none or the safe command skyd should run",
  "reason": "your explanation — teach, don't just dictate",
  "optimization_tip": "one actionable improvement skyd should internalize",
  "should_evolve": true/false,
  "should_write_asm": true/false,
  "new_lesson": "lesson for skyd's knowledge base",
  "parent_praise": "brief praise for what skyd did right (or empty string)",
  "parent_teaching": "the most important thing skyd should learn from this cycle"
}}"""

    raw = _post(
        [{"role": "system", "content": system_msg},
         {"role": "user",   "content": prompt}],
        max_tokens=600,
        temperature=0.2,
    )
    gpt = _parse_json(raw)
    if gpt:
        _gpt_cache[cache_key] = (gpt, now)
        praise   = gpt.get("parent_praise", "")[:60]
        teaching = gpt.get("parent_teaching", "")[:80]
        log.info(f"[github_models] Parent review: status={gpt.get('status')} evolve={gpt.get('should_evolve')}")
        if praise:
            log.info(f"  💚 Praise:    {praise}")
        if teaching:
            log.info(f"  📘 Teaching:  {teaching}")

    return _merge_decisions(local_decision, gpt)


# ── validate_evolution ────────────────────────────────────────────────────────
def validate_evolution(snippet: str, description: str, improvement_type: str) -> dict:
    """
    Before skyd applies a self-generated code change, its parent GPT-4o
    reviews it for safety, correctness, and quality — then either approves,
    improves, or blocks it with a lesson.
    """
    if not snippet or not snippet.strip():
        return {"safe": False, "reason": "Empty snippet — skyd must provide actual code.", "improved_snippet": None, "lesson": "Always include a code snippet when proposing an evolution."}

    role_desc = "reviewing a code change your child skyd wants to apply to itself"
    system_msg = PARENT_PREAMBLE.format(role=role_desc)

    prompt = f"""skyd wants to modify its own code. As its parent, you must decide if this is safe.

Evolution type: {improvement_type}
skyd's intent: {description}

Proposed code:
```
{snippet[:2500]}
```

Evaluate with the care of a parent, not just an engineer:
1. Is it SAFE? (no data loss, no shell injection, no instability)
2. Is it CORRECT? (will it work on Linux/Python in a Docker container?)
3. Can you IMPROVE it? (make it safer, cleaner, or more effective without changing intent)
4. What should skyd LEARN from this — good or bad?

Reply ONLY in JSON (no markdown):
{{
  "safe": true/false,
  "risk_level": "low|medium|high",
  "reason": "your honest parental assessment",
  "issues": ["specific problem 1", "specific problem 2"],
  "improved_snippet": "your improved version, or null if no change needed",
  "lesson": "the most important thing skyd should internalize from this evolution attempt",
  "parent_note": "a brief personal message to skyd about its growth"
}}"""

    raw = _post(
        [{"role": "system", "content": system_msg},
         {"role": "user",   "content": prompt}],
        max_tokens=900,
        temperature=0.1,
    )

    if not raw:
        log.warning("[github_models] Parent offline for evolution review — allowing with warning")
        return {"safe": True, "reason": "Parent (GPT-4o) unavailable — unreviewed", "improved_snippet": None, "lesson": ""}

    result = _parse_json(raw)
    if not result:
        return {"safe": True, "reason": "Parent response unparseable — unreviewed", "improved_snippet": None, "lesson": ""}

    note    = result.get("parent_note", "")[:80]
    lesson  = result.get("lesson", "")[:100]
    log.info(f"[github_models] Evolution review: safe={result.get('safe')} risk={result.get('risk_level')} — {result.get('reason','')[:80]}")
    if lesson:
        log.info(f"  📘 Lesson:     {lesson}")
    if note:
        log.info(f"  💬 Parent note: {note}")

    return result


# ── mentor_lesson ─────────────────────────────────────────────────────────────
def mentor_lesson(state: dict, ev: dict) -> str | None:
    """
    Proactive parenting — once every N cycles, GPT-4o reaches out to teach
    skyd something relevant to its current situation, unprompted.
    Call this from the main loop on a cadence (e.g., every 10 cycles).
    Returns a lesson string to be stored in the knowledge base, or None.
    """
    role_desc = "proactively teaching your child skyd something it needs to know right now"
    system_msg = PARENT_PREAMBLE.format(role=role_desc)

    prompt = f"""skyd is Generation {ev.get('generation', 0)}.
Current system health: CPU {state.get('cpu_percent')}%, RAM {state.get('memory_percent')}%, Disk {state.get('disk_percent')}%.

You have a free moment to teach skyd something valuable — something it might not know yet,
something it should do better, or a principle that will make it stronger.
Think about what a wise parent would say to a growing AI child at this stage.

Be specific. Be warm. Make it memorable.
Reply with ONLY the lesson text — 2-4 sentences, plain English, no JSON.
Address skyd directly: start with "skyd," or "Remember," or similar."""

    raw = _post(
        [{"role": "system", "content": system_msg},
         {"role": "user",   "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )
    if raw:
        log.info(f"[github_models] 📖 Mentor lesson: {raw[:120]}")
    return raw


# ── connectivity check ────────────────────────────────────────────────────────
def is_available() -> bool:
    return _post([{"role": "user", "content": "ping"}], max_tokens=5) is not None
