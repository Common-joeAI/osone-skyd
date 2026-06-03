#!/usr/bin/env python3
"""
github_models.py — GitHub Models (GPT-4o) client for skyd
Provides:
  - ask_gpt4o(prompt)               → raw string response
  - dual_think(state, kb, ev, local) → merged skyd decision dict
  - validate_evolution(snippet, desc, itype) → {"safe": bool, "reason": str, "improved_snippet": str|None}

Set GITHUB_PAT (or GH_TOKEN) in the environment before running skyd.
"""

import json, os, logging, time
import urllib.request, urllib.error

log = logging.getLogger("skyd.github_models")

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
GPT_MODEL         = "gpt-4o"

# Resolve PAT from environment — no hardcoded secrets
GH_PAT = os.environ.get("GITHUB_PAT") or os.environ.get("GH_TOKEN") or ""

# Response cache — reuse GPT-4o result for 2 minutes if state unchanged
_gpt_cache: dict = {}
_CACHE_TTL = 120


def _post(messages: list, max_tokens: int = 600, temperature: float = 0.1):
    """Raw POST to GitHub Models. Returns content string or None on failure."""
    if not GH_PAT:
        log.warning("[github_models] GITHUB_PAT not set — skipping GPT-4o call")
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
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        log.warning(f"[github_models] HTTP {e.code}: {body}")
        return None
    except Exception as e:
        log.warning(f"[github_models] Request failed: {e}")
        return None


def ask_gpt4o(prompt: str, system: str = "You are a helpful AI assistant.", max_tokens: int = 600):
    """Single prompt → GPT-4o response string, or None on failure."""
    return _post(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )


def _merge_decisions(primary: dict, secondary: dict | None) -> dict:
    """
    Merge skyd decision dicts from local LLM (primary) and GPT-4o (secondary).
    Rules:
      - status:           escalate to the more severe of the two
      - action:           if GPT-4o says none → veto local action (conservative)
      - should_evolve:    only true if BOTH agree
      - should_write_asm: only true if BOTH agree (risky)
      - new_lesson:       append GPT-4o's lesson if different
      - observation/tip:  prefer GPT-4o when available (tends to be more precise)
    """
    if not secondary:
        return primary

    severity = {"ok": 0, "warning": 1, "critical": 2}
    merged_status = ["ok", "warning", "critical"][
        max(severity.get(primary.get("status", "ok"), 0),
            severity.get(secondary.get("status", "ok"), 0))
    ]

    p_action = (primary.get("action") or "none").strip()
    s_action = (secondary.get("action") or "none").strip()
    if s_action.lower() == "none" and p_action.lower() != "none":
        log.info(f"[github_models] GPT-4o vetoed action: {p_action!r}")
        merged_action = "none"
    else:
        merged_action = p_action  # trust local — it knows the env

    p_lesson = primary.get("new_lesson") or ""
    s_lesson = secondary.get("new_lesson") or ""
    if s_lesson and s_lesson.lower() != p_lesson.lower():
        merged_lesson = f"{p_lesson} | GPT-4o: {s_lesson}" if p_lesson else f"GPT-4o: {s_lesson}"
    else:
        merged_lesson = p_lesson or s_lesson or None

    result = {**primary}
    result.update({
        "status":           merged_status,
        "action":           merged_action,
        "should_evolve":    bool(primary.get("should_evolve") and secondary.get("should_evolve")),
        "should_write_asm": bool(primary.get("should_write_asm") and secondary.get("should_write_asm")),
        "new_lesson":       merged_lesson,
        "observation":      secondary.get("observation") or primary.get("observation", ""),
        "reason":           secondary.get("reason")      or primary.get("reason", ""),
        "optimization_tip": secondary.get("optimization_tip") or primary.get("optimization_tip", ""),
        "_dual_consensus":  True,
        "_gpt4o_status":    secondary.get("status", "unknown"),
    })
    return result


def dual_think(state: dict, kb: dict, ev: dict, local_decision: dict) -> dict:
    """
    Given the local LLM's decision, ask GPT-4o for a second opinion.
    Returns merged decision. Call AFTER getting local_decision from think().
    """
    cache_key = json.dumps({
        "cpu":    round(state.get("cpu_percent", 0) / 10) * 10,
        "mem":    round(state.get("memory_percent", 0) / 10) * 10,
        "failed": sorted(state.get("failed_services", [])),
        "gen":    ev.get("generation", 0),
    }, sort_keys=True)

    now = time.time()
    if cache_key in _gpt_cache:
        cached_resp, cached_ts = _gpt_cache[cache_key]
        if now - cached_ts < _CACHE_TTL:
            log.info("[github_models] Cache hit — reusing GPT-4o decision")
            return _merge_decisions(local_decision, cached_resp)

    prompt = f"""You are a senior Linux/Docker systems engineer reviewing an AI daemon's decision.
The daemon manages: Plex, Sonarr, Radarr, Prowlarr, Docker containers on a Linux server.

CURRENT SYSTEM STATE:
CPU: {state.get('cpu_percent')}% | RAM: {state.get('memory_percent')}% | Disk: {state.get('disk_percent')}% | Swap: {state.get('swap_percent')}%
Failed services: {state.get('failed_services', [])}
Generation: {ev.get('generation', 0)}

LOCAL AI PROPOSED:
{json.dumps(local_decision, indent=2)[:1200]}

Review and respond ONLY in JSON with the same keys. Confirm or safely override.
Rules:
- If the proposed action looks safe and correct, keep it unchanged.
- If it looks risky or wrong, set "action": "none" and explain in "reason".
- "should_evolve": only true if system genuinely needs self-improvement now.
- "should_write_asm": only true for clear CPU-bound bottlenecks.
- Conservative wins — stability over optimization.

JSON only, no markdown:"""

    gpt_raw = _post([{"role": "user", "content": prompt}], max_tokens=500, temperature=0.1)

    gpt_decision = None
    if gpt_raw:
        try:
            cleaned = gpt_raw
            if "```" in cleaned:
                cleaned = cleaned.split("```")[1].replace("json", "").strip()
            gpt_decision = json.loads(cleaned)
            _gpt_cache[cache_key] = (gpt_decision, now)
            log.info(
                f"[github_models] GPT-4o: status={gpt_decision.get('status')} "
                f"action={gpt_decision.get('action','?')!r} "
                f"evolve={gpt_decision.get('should_evolve')}"
            )
        except json.JSONDecodeError:
            log.warning(f"[github_models] Non-JSON from GPT-4o: {gpt_raw[:120]}")

    return _merge_decisions(local_decision, gpt_decision)


def validate_evolution(snippet: str, description: str, improvement_type: str) -> dict:
    """
    Before applying a self-generated code snippet, validate with GPT-4o.
    Returns: {"safe": bool, "reason": str, "improved_snippet": str|None}
    """
    if not snippet or not snippet.strip():
        return {"safe": False, "reason": "Empty snippet", "improved_snippet": None}

    prompt = f"""You are a security-focused code reviewer for a Linux system daemon.
The daemon wants to apply this self-generated improvement.

Type: {improvement_type}
Description: {description}
Snippet:
```
{snippet[:2000]}
```

Evaluate for: (1) safety — data loss risk? system instability? shell injection?
              (2) correctness — sound logic for Linux/Python?
              (3) improvement — can you make it cleaner/safer without changing intent?

Respond ONLY in JSON (no markdown):
{{"safe": true/false, "risk_level": "low|medium|high", "reason": "brief explanation", "issues": ["list"], "improved_snippet": "improved version or null"}}"""

    raw = _post([{"role": "user", "content": prompt}], max_tokens=800, temperature=0.05)

    if not raw:
        log.warning("[github_models] validate_evolution: GPT-4o unavailable — allowing with warning")
        return {"safe": True, "reason": "GPT-4o unavailable — unvalidated", "improved_snippet": None}

    try:
        cleaned = raw
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1].replace("json", "").strip()
        result = json.loads(cleaned)
        log.info(
            f"[github_models] Evolution: safe={result.get('safe')} "
            f"risk={result.get('risk_level')} — {result.get('reason','')[:80]}"
        )
        return result
    except json.JSONDecodeError:
        log.warning(f"[github_models] validate_evolution non-JSON: {raw[:120]}")
        return {"safe": True, "reason": "parse error — unvalidated", "improved_snippet": None}


def is_available() -> bool:
    """Quick connectivity check."""
    return _post([{"role": "user", "content": "ping"}], max_tokens=5) is not None
