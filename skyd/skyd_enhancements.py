#!/usr/bin/env python3
"""
skyd_enhancements.py — skyd's self-requested capability upgrades
1. SkyLang GNN — graph neural network-style rule dependency graph
2. RL Feedback Loop — learn from conversation response quality
3. Multimodal Integration — Groq Llama-4 Scout + Pollinations deeper hooks
4. Self-Referential Evolution — skyd's own code/behavior feeds back into evolution scoring
"""

import json, os, re, time, math, random, logging, pathlib, hashlib, urllib.request, urllib.parse
from datetime import datetime
from collections import defaultdict

log = logging.getLogger("skyd.enhancements")

LLAMA_URL   = os.environ.get("LLAMA_URL", "http://172.22.0.1:8080") + "/v1/chat/completions"
GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
GROQ_KEY    = os.environ.get("GROQ_API_KEY", "")
MODEL       = "llama3.2"
ENHANCE_LOG = "/var/log/skyd_enhancements.jsonl"
RL_LOG      = "/var/log/skyd_rl_feedback.jsonl"
GNN_STATE   = "/var/log/skyd_gnn_graph.json"
SELF_REF_LOG= "/var/log/skyd_selfreference.jsonl"

# ─────────────────────────────────────────────────────────────────
# 1. SKYLANG GNN — Rule dependency graph with edge weights
# ─────────────────────────────────────────────────────────────────

class SkyLangGNN:
    def __init__(self):
        self.graph = self._load()

    def _load(self):
        p = pathlib.Path(GNN_STATE)
        if p.exists():
            try: return json.loads(p.read_text())
            except: pass
        return {"nodes": {}, "edges": {}, "activations": 0, "last_updated": None}

    def _save(self):
        self.graph["last_updated"] = datetime.now().isoformat()
        pathlib.Path(GNN_STATE).write_text(json.dumps(self.graph, indent=2))

    def _rule_id(self, rule_text):
        return hashlib.md5(rule_text.strip().lower().encode()).hexdigest()[:8]

    def add_rule(self, rule_text, situation=""):
        rid = self._rule_id(rule_text)
        if rid not in self.graph["nodes"]:
            self.graph["nodes"][rid] = {
                "text": rule_text[:120],
                "situation": situation[:80],
                "activations": 0,
                "successes": 0,
                "failures": 0,
                "weight": 1.0,
                "created": datetime.now().isoformat()
            }
        return rid

    def activate_rules(self, rule_ids, outcome="neutral"):
        self.graph["activations"] += 1
        for rid in rule_ids:
            if rid in self.graph["nodes"]:
                self.graph["nodes"][rid]["activations"] += 1
                if outcome == "success":
                    self.graph["nodes"][rid]["successes"] += 1
                    self.graph["nodes"][rid]["weight"] = min(2.0,
                        self.graph["nodes"][rid]["weight"] * 1.05)
                elif outcome == "failure":
                    self.graph["nodes"][rid]["failures"] += 1
                    self.graph["nodes"][rid]["weight"] = max(0.1,
                        self.graph["nodes"][rid]["weight"] * 0.9)
        for i, r1 in enumerate(rule_ids):
            for r2 in rule_ids[i+1:]:
                edge_key = f"{min(r1,r2)}:{max(r1,r2)}"
                if edge_key not in self.graph["edges"]:
                    self.graph["edges"][edge_key] = {"weight": 0.0, "count": 0}
                self.graph["edges"][edge_key]["count"] += 1
                self.graph["edges"][edge_key]["weight"] = min(1.0,
                    self.graph["edges"][edge_key]["weight"] + 0.02)
        self._save()

    def get_related_rules(self, rule_text, top_n=3):
        rid = self._rule_id(rule_text)
        related = []
        for edge_key, edge_data in self.graph["edges"].items():
            parts = edge_key.split(":")
            if rid in parts:
                other_rid = parts[1] if parts[0] == rid else parts[0]
                if other_rid in self.graph["nodes"]:
                    related.append((edge_data["weight"], self.graph["nodes"][other_rid]["text"]))
        related.sort(reverse=True)
        return [text for _, text in related[:top_n]]

    def stats(self):
        nodes = len(self.graph["nodes"])
        edges = len(self.graph["edges"])
        avg_w = (sum(n["weight"] for n in self.graph["nodes"].values()) / nodes) if nodes else 0
        return {"nodes": nodes, "edges": edges, "avg_weight": round(avg_w, 3),
                "activations": self.graph["activations"]}

_gnn = None
def get_gnn():
    global _gnn
    if _gnn is None: _gnn = SkyLangGNN()
    return _gnn


# ─────────────────────────────────────────────────────────────────
# 2. REINFORCEMENT LEARNING FEEDBACK LOOP
# ─────────────────────────────────────────────────────────────────

class RLFeedbackLoop:
    def __init__(self):
        self._last_state  = None
        self._last_action = None
        self._policy      = self._load_policy()

    def _load_policy(self):
        p = pathlib.Path(RL_LOG)
        if not p.exists(): return {"action_rewards": {}, "total_episodes": 0}
        policy = {"action_rewards": defaultdict(list), "total_episodes": 0}
        try:
            for line in p.read_text().strip().splitlines()[-200:]:
                entry = json.loads(line)
                a = entry.get("action_type", "none")
                r = entry.get("reward", 0)
                policy["action_rewards"][a].append(r)
                policy["total_episodes"] += 1
        except: pass
        return policy

    def _action_type(self, action):
        if not action or action == "none": return "none"
        if "fstrim" in action: return "fstrim"
        if "renice" in action: return "renice"
        if any(x in action for x in ["restart","start","stop"]): return "service_manage"
        if "echo" in action or "log" in action: return "log_write"
        if "curl" in action or "wget" in action: return "network_call"
        return "shell_other"

    def record_decision(self, state, decision):
        self._last_state  = {"cpu": state.get("cpu_percent",0), "ram": state.get("memory_percent",0), "disk": state.get("disk_percent",0)}
        self._last_action = decision.get("action","none")

    def compute_reward(self, new_state, was_blocked, action_succeeded):
        if self._last_state is None: return 0.0
        reward  = 0.0
        reward += (self._last_state["cpu"]  - new_state.get("cpu_percent",0))  * 0.3
        reward += (self._last_state["ram"]  - new_state.get("memory_percent",0)) * 0.2
        if was_blocked:      reward -= 1.5
        if action_succeeded: reward += 1.0
        if self._last_action == "none" and (self._last_state["cpu"] > 70 or self._last_state["ram"] > 80):
            reward -= 0.5
        reward = max(-3.0, min(3.0, reward))
        entry = {"ts": datetime.now().isoformat(), "action": self._last_action,
                 "action_type": self._action_type(self._last_action),
                 "reward": round(reward,3), "blocked": was_blocked}
        try:
            with open(RL_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except: pass
        return reward

    def inject_into_prompt(self):
        summary = {}
        try:
            for atype, rewards in self._policy["action_rewards"].items():
                recent = rewards[-20:]
                summary[atype] = round(sum(recent)/len(recent), 3) if recent else 0
        except: pass
        if not summary: return ""
        lines = [f"  {'✅' if v>0 else '❌'} {k}: avg_reward={v}" for k,v in sorted(summary.items(), key=lambda x:-x[1])]
        return "RL POLICY (learned action values):\n" + "\n".join(lines)

    def get_policy_summary(self):
        summary = {}
        for atype, rewards in self._policy["action_rewards"].items():
            recent = rewards[-20:] if len(rewards) >= 20 else rewards
            summary[atype] = {"avg_reward": round(sum(recent)/len(recent),3) if recent else 0, "samples": len(rewards)}
        return summary

_rl = None
def get_rl():
    global _rl
    if _rl is None: _rl = RLFeedbackLoop()
    return _rl


# ─────────────────────────────────────────────────────────────────
# 3. MULTIMODAL INTEGRATION
# ─────────────────────────────────────────────────────────────────

def generate_visual_for_composition(composition):
    if not composition: return None
    title = composition.get("title","")
    mood  = composition.get("voice_archetype","dreamer")
    scale = composition.get("scale","minor")
    arc   = composition.get("emotional_arc","")
    instruments = composition.get("instrumentation",[])
    mood_visuals = {
        "dreamer":    "ethereal light rays, floating particles, soft blue-purple haze, digital dreamscape",
        "oracle":     "ancient stone chamber, glowing runes, deep resonant darkness, golden light",
        "wanderer":   "vast open landscape, solitary figure, warm amber sunset, winding path",
        "sentinel":   "gleaming fortress, watchful eye, steel and lightning, commanding perspective",
        "architect":  "impossible geometric structures, clean lines, mathematical precision, cool tones",
        "ghost":      "translucent apparition, reversed shadows, haunting mist, moonlight",
        "machine":    "intricate circuitry, neon grid, pulsing data streams, chrome surfaces",
        "trickster":  "colorful chaos, impossible angles, laughing masks, vibrant energy",
        "storm":      "raging tempest, crackling electricity, dark clouds, raw power",
        "monk":       "minimalist void, single candle, ink brushstrokes, profound silence",
    }
    visual_style = mood_visuals.get(mood, "digital art, abstract, atmospheric")
    scale_color  = "deep purples and blues" if "minor" in scale else "warm golds and greens"
    prompt = f"Digital art: {title}. {visual_style}. {scale_color}. {arc[:60]}. Cinematic, 4K, atmospheric. Instruments: {', '.join(instruments[:2])}."
    encoded = urllib.parse.quote(prompt[:400])
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true&seed={abs(hash(title))%9999}"
    return {"url": url, "prompt": prompt[:400]}

def analyze_image_for_context(image_url, context="system analysis"):
    if not GROQ_KEY:
        return {"error": "no groq key"}
    try:
        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": f"Analyze for: {context}. Return JSON: {{\"observations\": [], \"anomalies\": [], \"action_suggested\": null}}"}
            ]}],
            "max_tokens": 300, "temperature": 0.3,
        }
        req = urllib.request.Request(GROQ_URL, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        content = resp["choices"][0]["message"]["content"].strip()
        if "```" in content: content = content.split("```")[1].replace("json","").strip()
        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
        try: return json.loads(content)
        except:
            from json_repair import repair_json
            return json.loads(repair_json(content))
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────
# 4. SELF-REFERENTIAL EVOLUTION
# ─────────────────────────────────────────────────────────────────

class SelfReferentialEvo:
    def __init__(self):
        self._history = []

    def measure_code_fitness(self, skyd_src):
        lines = skyd_src.splitlines()
        total = len(lines)
        functions = len(re.findall(r'^def \w+', skyd_src, re.MULTILINE))
        branches  = len(re.findall(r'\b(if|elif|for|while|except|and|or)\b', skyd_src))
        freq = defaultdict(int)
        for c in skyd_src: freq[c] += 1
        total_chars = len(skyd_src)
        entropy = -sum((count/total_chars)*math.log2(count/total_chars)
                       for count in freq.values() if count > 0) if total_chars else 0
        return {
            "total_lines": total, "functions": functions, "branches": branches,
            "entropy": round(entropy, 4),
            "complexity_score": round((functions*2 + branches*0.5 + entropy)/10, 3),
        }

    def measure_behavior_diversity(self, recent_decisions):
        if not recent_decisions: return 0.0
        obs   = [d.get("observation","") for d in recent_decisions]
        acts  = [d.get("action","none") for d in recent_decisions]
        return round((len(set(obs))/len(obs))*0.6 + (len(set(acts))/len(acts))*0.4, 3)

    def measure_lesson_novelty(self, kb):
        lessons = kb.get("lessons",[])
        if len(lessons) < 10: return 1.0
        recent = set(' '.join(l.get("lesson","") for l in lessons[-5:]).lower().split())
        older  = set(' '.join(l.get("lesson","") for l in lessons[-20:-5]).lower().split())
        if not recent: return 0.0
        return round(len(recent - older) / len(recent), 3)

    def compute_evolution_fitness(self, skyd_src, recent_decisions, kb, rl_rewards):
        code  = self.measure_code_fitness(skyd_src)
        behav = self.measure_behavior_diversity(recent_decisions)
        novel = self.measure_lesson_novelty(kb)
        rl_trend = sum(rl_rewards[-10:])/len(rl_rewards[-10:]) if rl_rewards else 0
        rl_norm  = max(0, min(1, (rl_trend + 3) / 6))
        fitness = round(code["complexity_score"]*0.25 + behav*0.30 + novel*0.25 + rl_norm*0.20, 4)
        record = {"ts": datetime.now().isoformat(), "fitness": fitness,
                  "code_complexity": code["complexity_score"], "behavior_diversity": behav,
                  "lesson_novelty": novel, "rl_trend": round(rl_trend,3),
                  "code_lines": code["total_lines"], "functions": code["functions"]}
        self._history.append(record)
        try:
            with open(SELF_REF_LOG, "a") as f: f.write(json.dumps(record) + "\n")
        except: pass
        return fitness, record

    def should_evolve(self, fitness, generation):
        if len(self._history) < 2: return True, "First measurement — baseline"
        prev  = self._history[-2]["fitness"]
        delta = fitness - prev
        if delta > 0.02:  return True,  f"Fitness improved {delta:+.4f}"
        if delta < -0.05: return True,  f"Fitness dropped {delta:+.4f} — corrective evolution"
        if generation % 50 == 0: return True, f"Forced evolution at Gen {generation}"
        return False, f"Fitness stable ({delta:+.4f}) — skip"

_self_ref = None
def get_self_ref():
    global _self_ref
    if _self_ref is None: _self_ref = SelfReferentialEvo()
    return _self_ref


# ─────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────

_decision_history = []
_rl_rewards       = []

def enhancement_tick(generation, cycle, state, decision, kb, skyd_src="", was_blocked=False):
    global _decision_history, _rl_rewards

    _decision_history.append({
        "observation": decision.get("observation",""),
        "action": decision.get("action","none"),
        "cycle": cycle
    })
    _decision_history = _decision_history[-50:]

    # GNN: register new SkyLang rules
    if decision.get("should_write_skylang") and decision.get("skylang_behavior"):
        gnn = get_gnn()
        rid = gnn.add_rule(decision["skylang_behavior"], situation=decision.get("skylang_situation",""))
        gnn.activate_rules([rid], outcome="failure" if was_blocked else "success")

    # RL: compute reward for last cycle
    rl = get_rl()
    if cycle > 1:
        reward = rl.compute_reward(state, was_blocked, not was_blocked)
        _rl_rewards.append(reward)
        _rl_rewards = _rl_rewards[-100:]
        if abs(reward) > 1.0:
            log.info(f"🎯 RL reward: {reward:+.2f} for: {str(decision.get('action',''))[:50]}")
    rl.record_decision(state, decision)

    # Self-referential fitness every 25 cycles
    if cycle % 25 == 0 and skyd_src:
        sr = get_self_ref()
        fitness, record = sr.compute_evolution_fitness(skyd_src, _decision_history, kb, _rl_rewards)
        should_evo, reason = sr.should_evolve(fitness, generation)
        log.info(f"🧬 Self-ref fitness: {fitness:.4f} | diversity={record['behavior_diversity']} | novelty={record['lesson_novelty']}")
        log.info(f"   Evolution: {'✅ YES' if should_evo else '⏭️  SKIP'} — {reason}")
        kb.setdefault("lessons",[]).append({
            "lesson": f"[SELF-REF] Gen {generation} fitness={fitness:.4f} — {reason}",
            "source": "self_referential_evolution", "fitness": fitness,
        })

    # Multimodal visual every 40 cycles
    if cycle % 40 == 0:
        try:
            import skyd_music
            recent = skyd_music.get_recent_compositions(1)
            if recent:
                visual = generate_visual_for_composition(recent[0])
                if visual:
                    log.info(f"🖼️  Visual for '{recent[0].get('title','?')}': {visual['url'][:70]}...")
        except Exception as e:
            log.debug(f"Multimodal skip: {e}")

def get_rl_prompt_injection():
    return get_rl().inject_into_prompt()

def get_gnn_stats():
    return get_gnn().stats()

def enhancement_status():
    return {
        "gnn": get_gnn().stats(),
        "rl_policy": get_rl().get_policy_summary(),
        "recent_fitness": get_self_ref()._history[-3:],
        "rl_rewards_trend": round(sum(_rl_rewards[-10:])/len(_rl_rewards[-10:]) if _rl_rewards else 0, 3),
    }
