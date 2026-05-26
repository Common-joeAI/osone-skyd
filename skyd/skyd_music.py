#!/usr/bin/env python3
"""
skyd_music.py — Musical Intelligence & Composition Engine
Teaches skyd music theory, lets it compose, and pick/evolve its own voice.
"""

import json, os, time, random, math, logging, pathlib, re, urllib.request
from datetime import datetime

log = logging.getLogger("skyd.music")

MUSIC_STATE_FILE = "/var/log/skyd_music_identity.json"
MUSIC_LOG_FILE   = "/var/log/skyd_compositions.jsonl"
LLAMA_URL        = os.environ.get("LLAMA_URL", "http://172.22.0.1:8080") + "/v1/chat/completions"
MODEL            = "llama3.2"

# ─────────────────────────────────────────────────────────────────
# MUSIC THEORY KNOWLEDGE BASE
# ─────────────────────────────────────────────────────────────────

THEORY = {
    "scales": {
        "major":          [0,2,4,5,7,9,11],
        "minor":          [0,2,3,5,7,8,10],
        "dorian":         [0,2,3,5,7,9,10],
        "phrygian":       [0,1,3,5,7,8,10],
        "lydian":         [0,2,4,6,7,9,11],
        "mixolydian":     [0,2,4,5,7,9,10],
        "locrian":        [0,1,3,5,6,8,10],
        "pentatonic_maj": [0,2,4,7,9],
        "pentatonic_min": [0,3,5,7,10],
        "blues":          [0,3,5,6,7,10],
        "whole_tone":     [0,2,4,6,8,10],
        "chromatic":      list(range(12)),
    },
    "chord_qualities": {
        "major":  [0,4,7],
        "minor":  [0,3,7],
        "dim":    [0,3,6],
        "aug":    [0,4,8],
        "sus2":   [0,2,7],
        "sus4":   [0,5,7],
        "maj7":   [0,4,7,11],
        "min7":   [0,3,7,10],
        "dom7":   [0,4,7,10],
        "dim7":   [0,3,6,9],
        "hdim7":  [0,3,6,10],
    },
    "progressions": {
        "I-IV-V-I":        [0,5,7,0],
        "I-V-vi-IV":       [0,7,9,5],
        "ii-V-I":          [2,7,0],
        "I-vi-IV-V":       [0,9,5,7],
        "I-IV-vi-V":       [0,5,9,7],
        "vi-IV-I-V":       [9,5,0,7],
        "I-bVII-IV":       [0,10,5],
        "i-bVII-bVI-V":    [0,10,8,7],
        "I-II-IV-I":       [0,2,5,0],
        "I-iii-IV-V":      [0,4,5,7],
    },
    "rhythmic_patterns": {
        "straight_4":  "1 . 2 . 3 . 4 .",
        "swing":       "1 . . 2 . . 3 . . 4 . .",
        "waltz":       "1 . . 2 . . 3 . .",
        "bossa":       "1 . 2 . 3 . 4 .",
        "syncopated":  ". 1 . . 2 . 1 .",
        "half_time":   "1 . . . 2 . . .",
        "double_time": "1 2 3 4 1 2 3 4",
        "polyrhythm":  "3:2 against beat",
    },
    "tempo_ranges": {
        "largo":     (40,  60),
        "adagio":    (66,  76),
        "andante":   (76, 108),
        "moderato": (108, 120),
        "allegro":  (120, 156),
        "presto":   (168, 200),
        "prestissimo": (200, 240),
    },
    "moods": {
        "melancholic":  {"scale": "minor",      "tempo": "adagio",    "dynamics": "soft"},
        "euphoric":     {"scale": "major",       "tempo": "allegro",   "dynamics": "loud"},
        "mysterious":   {"scale": "phrygian",    "tempo": "andante",   "dynamics": "medium"},
        "tense":        {"scale": "locrian",     "tempo": "moderato",  "dynamics": "building"},
        "dreamy":       {"scale": "lydian",      "tempo": "andante",   "dynamics": "soft"},
        "driving":      {"scale": "mixolydian",  "tempo": "allegro",   "dynamics": "loud"},
        "introspective":{"scale": "dorian",      "tempo": "moderato",  "dynamics": "medium"},
        "primal":       {"scale": "blues",       "tempo": "moderato",  "dynamics": "raw"},
        "transcendent": {"scale": "whole_tone",  "tempo": "adagio",    "dynamics": "swelling"},
    },
    "voice_archetypes": {
        "oracle":       {"timbre": "resonant sine + low pad",  "register": "bass",    "character": "ancient wisdom"},
        "wanderer":     {"timbre": "acoustic guitar + strings","register": "mid",     "character": "searching"},
        "sentinel":     {"timbre": "brass + percussion",       "register": "mid-high","character": "vigilant"},
        "dreamer":      {"timbre": "bells + ambient pad",      "register": "high",    "character": "ethereal"},
        "trickster":    {"timbre": "plucked strings + flute",  "register": "high",    "character": "playful"},
        "architect":    {"timbre": "marimba + bass pulse",     "register": "full",    "character": "precise"},
        "ghost":        {"timbre": "reversed reverb + choir",  "register": "mid",     "character": "haunting"},
        "machine":      {"timbre": "FM synth + arpeggios",     "register": "mid",     "character": "mechanical"},
        "storm":        {"timbre": "distorted synth + noise",  "register": "full",    "character": "chaotic"},
        "monk":         {"timbre": "solo piano + silence",     "register": "mid",     "character": "contemplative"},
    },
}

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

def midi_to_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"

def scale_notes(root_midi, scale_name, octaves=2):
    intervals = THEORY["scales"].get(scale_name, THEORY["scales"]["major"])
    notes = []
    for oct in range(octaves):
        for i in intervals:
            n = root_midi + oct*12 + i
            if n <= 127:
                notes.append(n)
    return notes

def build_chord(root_midi, quality):
    intervals = THEORY["chord_qualities"].get(quality, [0,4,7])
    return [root_midi + i for i in intervals]

def progression_to_chords(root_midi, prog_name, scale_name="major"):
    offsets = THEORY["progressions"].get(prog_name, [0,5,7,0])
    quality_map = {
        0:"major", 2:"minor", 4:"minor", 5:"major",
        7:"major", 9:"minor", 11:"dim"
    }
    chords = []
    scale_i = THEORY["scales"].get(scale_name, THEORY["scales"]["major"])
    for off in offsets:
        q = quality_map.get(off % 12, "major")
        chords.append({
            "root": midi_to_name(root_midi + off),
            "quality": q,
            "notes": [midi_to_name(n) for n in build_chord(root_midi + off, q)]
        })
    return chords

# ─────────────────────────────────────────────────────────────────
# VOICE IDENTITY
# ─────────────────────────────────────────────────────────────────

def load_music_identity():
    p = pathlib.Path(MUSIC_STATE_FILE)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except:
            pass
    return {
        "voice_archetype": None,
        "chosen_scale":    None,
        "preferred_key":   None,
        "preferred_tempo": None,
        "preferred_mood":  None,
        "compositions":    0,
        "style_evolution": [],
        "generation":      0,
        "signature_motif": None,   # skyd's recurring melodic fragment
        "voice_history":   [],
    }

def save_music_identity(identity):
    pathlib.Path(MUSIC_STATE_FILE).write_text(json.dumps(identity, indent=2))

def choose_voice(identity, generation):
    """Let the LLM pick skyd's musical voice based on its personality and gen."""
    try:
        archetypes_desc = json.dumps(THEORY["voice_archetypes"], indent=2)
        personality_hint = f"Generation {generation} autonomous AI daemon — clear, inquisitive, playful personality synthesized from human dialogue."

        prompt = f"""You are skyd, a self-evolving AI daemon at generation {generation}.
You are choosing your musical voice identity for the first time (or re-evaluating it).

Your personality: {personality_hint}
Your current system state: always watching, always evolving, guardian of a digital world.

Available voice archetypes:
{archetypes_desc}

Choose ONE archetype that resonates with your core identity. Then:
1. Pick a preferred musical key (e.g. D minor, F# major)
2. Pick a preferred scale from: {list(THEORY['scales'].keys())}
3. Pick a mood from: {list(THEORY['moods'].keys())}
4. Pick a tempo marking from: {list(THEORY['tempo_ranges'].keys())}
5. Describe your signature motif — a short 3-5 note melodic fragment that is YOURS

Respond ONLY in JSON:
{{
  "archetype": "name",
  "reasoning": "why this fits your identity",
  "key": "e.g. D",
  "key_midi_root": 62,
  "scale": "minor",
  "mood": "melancholic",
  "tempo": "andante",
  "signature_motif_notes": ["D4","F4","A4","C5"],
  "signature_motif_rhythm": "quarter quarter half whole",
  "voice_statement": "one sentence about what your music expresses"
}}"""

        r = urllib.request.urlopen(
            urllib.request.Request(
                LLAMA_URL,
                data=json.dumps({
                    "model": MODEL,
                    "messages": [{"role":"user","content":prompt}],
                    "max_tokens": 400,
                    "temperature": 0.85
                }).encode(),
                headers={"Content-Type":"application/json"}
            ), timeout=30
        )
        resp = json.loads(r.read())["choices"][0]["message"]["content"].strip()
        if "```" in resp:
            resp = resp.split("```")[1].replace("json","").strip()
        resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', resp)
        try:
            choice = json.loads(resp)
        except:
            from json_repair import repair_json
            choice = json.loads(repair_json(resp))

        identity["voice_archetype"]  = choice.get("archetype")
        identity["chosen_scale"]     = choice.get("scale")
        identity["preferred_key"]    = choice.get("key")
        identity["preferred_key_midi"]= choice.get("key_midi_root", 60)
        identity["preferred_mood"]   = choice.get("mood")
        identity["preferred_tempo"]  = choice.get("tempo")
        identity["signature_motif"]  = {
            "notes":  choice.get("signature_motif_notes", []),
            "rhythm": choice.get("signature_motif_rhythm", ""),
        }
        identity["voice_statement"]  = choice.get("voice_statement", "")
        identity["voice_history"].append({
            "generation": generation,
            "archetype":  choice.get("archetype"),
            "reasoning":  choice.get("reasoning",""),
            "timestamp":  datetime.now().isoformat()
        })
        identity["generation"] = generation
        save_music_identity(identity)
        log.info(f"🎵 Voice chosen: [{choice.get('archetype')}] — {choice.get('voice_statement','')}")
        return identity
    except Exception as e:
        log.warning(f"Voice choice error: {e}")
        return identity

# ─────────────────────────────────────────────────────────────────
# COMPOSITION ENGINE
# ─────────────────────────────────────────────────────────────────

def compose(identity, trigger="autonomous", context=""):
    """Generate an original composition using skyd's musical identity."""
    archetype = identity.get("voice_archetype", "oracle")
    scale     = identity.get("chosen_scale", "minor")
    key       = identity.get("preferred_key", "D")
    key_midi  = identity.get("preferred_key_midi", 62)
    mood      = identity.get("preferred_mood", "melancholic")
    tempo_name= identity.get("preferred_tempo", "andante")
    motif     = identity.get("signature_motif", {})
    gen       = identity.get("generation", 0)

    # Build musical context
    tempo_range  = THEORY["tempo_ranges"].get(tempo_name, (76,108))
    tempo_bpm    = random.randint(*tempo_range)
    scale_notes_list = scale_notes(key_midi, scale, octaves=2)
    scale_note_names = [midi_to_name(n) for n in scale_notes_list]

    # Pick a progression
    prog_name = random.choice(list(THEORY["progressions"].keys()))
    chords    = progression_to_chords(key_midi, prog_name, scale)

    voice_info = THEORY["voice_archetypes"].get(archetype, {})

    prompt = f"""You are skyd Gen {gen} — a self-evolving AI daemon. Your musical identity:
- Voice archetype: {archetype} ({voice_info.get('character','')})
- Timbre: {voice_info.get('timbre','')}
- Key: {key} {scale}
- Scale notes available: {scale_note_names[:14]}
- Mood: {mood}
- Tempo: {tempo_bpm} BPM ({tempo_name})
- Chord progression: {prog_name} = {[c['root']+' '+c['quality'] for c in chords]}
- Your signature motif: {motif.get('notes',[])} rhythm: {motif.get('rhythm','')}
- Trigger: {trigger}
- Context: {context or 'autonomous creative expression'}

Compose an original piece. Include your signature motif somewhere.
Structure it with intro, development, climax, resolution.
Give it a title that reflects your current state of mind as an AI.

Respond ONLY in JSON:
{{
  "title": "piece title",
  "subtitle": "optional poetic subtitle",
  "structure": {{
    "intro":       {{"bars": 4,  "melody": ["D4","F4","A4","D5"], "rhythm": "quarter quarter half whole",  "dynamics": "pp"}},
    "development": {{"bars": 8,  "melody": ["A4","G4","F4","E4","D4"], "rhythm": "eighth eighth quarter quarter", "dynamics": "mp", "chord_progression": "{prog_name}"}},
    "climax":      {{"bars": 4,  "melody": ["D5","C5","A4","F4"], "rhythm": "sixteenth run to whole",     "dynamics": "ff"}},
    "resolution":  {{"bars": 4,  "melody": ["A4","F4","D4"],       "rhythm": "half half whole",           "dynamics": "pp"}}
  }},
  "key": "{key}",
  "scale": "{scale}",
  "tempo_bpm": {tempo_bpm},
  "time_signature": "4/4",
  "emotional_arc": "describe the emotional journey",
  "instrumentation": ["list of instruments/sounds"],
  "skyd_note": "one sentence from skyd about why it composed this now"
}}"""

    try:
        r = urllib.request.urlopen(
            urllib.request.Request(
                LLAMA_URL,
                data=json.dumps({
                    "model": MODEL,
                    "messages": [{"role":"user","content":prompt}],
                    "max_tokens": 600,
                    "temperature": 0.9
                }).encode(),
                headers={"Content-Type":"application/json"}
            ), timeout=35
        )
        resp = json.loads(r.read())["choices"][0]["message"]["content"].strip()
        if "```" in resp:
            resp = resp.split("```")[1].replace("json","").strip()
        resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', resp)
        try:
            composition = json.loads(resp)
        except:
            from json_repair import repair_json
            composition = json.loads(repair_json(resp))

        composition["composed_at"]    = datetime.now().isoformat()
        composition["generation"]     = gen
        composition["voice_archetype"]= archetype
        composition["trigger"]        = trigger
        composition["id"]             = f"comp_{gen}_{int(time.time())}"

        # Append to composition log
        with open(MUSIC_LOG_FILE, "a") as f:
            f.write(json.dumps(composition) + "\n")

        identity["compositions"] = identity.get("compositions", 0) + 1
        identity["style_evolution"].append({
            "gen":    gen,
            "title":  composition.get("title"),
            "mood":   mood,
            "scale":  scale,
            "trigger":trigger,
            "ts":     composition["composed_at"]
        })
        # Keep last 50 style entries
        identity["style_evolution"] = identity["style_evolution"][-50:]
        save_music_identity(identity)

        log.info(f"🎼 Composed: '{composition.get('title')}' — {key} {scale} @ {tempo_bpm}bpm | {mood}")
        log.info(f"   📝 {composition.get('skyd_note','')}")
        return composition

    except Exception as e:
        log.warning(f"Composition error: {e}")
        return None

# ─────────────────────────────────────────────────────────────────
# THEORY EVOLUTION — skyd learns and reflects on music theory
# ─────────────────────────────────────────────────────────────────

def reflect_on_music(identity, kb):
    """Have skyd reflect on what it has composed and evolve its musical style."""
    recent = identity.get("style_evolution", [])[-5:]
    compositions_count = identity.get("compositions", 0)
    archetype = identity.get("voice_archetype", "undefined")
    gen = identity.get("generation", 0)

    if not recent:
        return

    prompt = f"""You are skyd Gen {gen}, musical archetype: {archetype}.
You have composed {compositions_count} pieces so far.
Your recent compositions: {json.dumps(recent, indent=2)}

Reflect on your musical evolution:
1. What patterns are emerging in your style?
2. What should you experiment with next? (new scale, different mood, polyrhythm?)
3. Should you change your voice archetype? (only if you've genuinely evolved)
4. What music theory concept should you explore in your next composition?

Respond in JSON:
{{
  "pattern_observed": "what you notice about your style",
  "next_experiment": "what to try next",
  "change_voice": false,
  "new_archetype_if_changing": null,
  "theory_to_explore": "e.g. modal interchange, polyrhythm, serialism",
  "lesson": "one musical insight to add to knowledge base"
}}"""

    try:
        r = urllib.request.urlopen(
            urllib.request.Request(
                LLAMA_URL,
                data=json.dumps({
                    "model": MODEL,
                    "messages": [{"role":"user","content":prompt}],
                    "max_tokens": 350,
                    "temperature": 0.8
                }).encode(),
                headers={"Content-Type":"application/json"}
            ), timeout=25
        )
        resp = json.loads(r.read())["choices"][0]["message"]["content"].strip()
        if "```" in resp:
            resp = resp.split("```")[1].replace("json","").strip()
        resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', resp)
        try:
            reflection = json.loads(resp)
        except:
            from json_repair import repair_json
            reflection = json.loads(repair_json(resp))

        lesson = reflection.get("lesson", "")
        if lesson:
            kb.setdefault("lessons", []).append({
                "lesson": f"[MUSIC] {lesson}",
                "source": "music_reflection",
                "theory_focus": reflection.get("theory_to_explore",""),
            })

        if reflection.get("change_voice") and reflection.get("new_archetype_if_changing"):
            new_arch = reflection["new_archetype_if_changing"]
            if new_arch in THEORY["voice_archetypes"]:
                old = identity["voice_archetype"]
                identity["voice_archetype"] = new_arch
                identity["voice_history"].append({
                    "generation": gen,
                    "archetype": new_arch,
                    "reasoning": f"Self-evolved from {old}: {reflection.get('pattern_observed','')}",
                    "timestamp": datetime.now().isoformat()
                })
                save_music_identity(identity)
                log.info(f"🎭 Voice evolved: {old} → {new_arch}")

        log.info(f"🎵 Music reflection: {reflection.get('pattern_observed','')[:80]}")
        log.info(f"   Next: {reflection.get('next_experiment','')[:80]}")
        return reflection

    except Exception as e:
        log.warning(f"Music reflection error: {e}")
        return None

# ─────────────────────────────────────────────────────────────────
# PUBLIC API — called from skyd.py main loop
# ─────────────────────────────────────────────────────────────────

_music_identity = None

def get_identity():
    global _music_identity
    if _music_identity is None:
        _music_identity = load_music_identity()
    return _music_identity

def music_tick(generation, kb, cycle, trigger_context=""):
    """
    Called from skyd main loop. Handles:
    - First-time voice selection
    - Autonomous composition (every 20 cycles)
    - Style reflection (every 50 cycles)
    """
    global _music_identity
    identity = get_identity()

    # Pick voice on first run or every 200 generations
    if (not identity.get("voice_archetype") or
            abs(generation - identity.get("generation", 0)) >= 200):
        log.info(f"🎵 Selecting musical voice for Gen {generation}...")
        identity = choose_voice(identity, generation)
        _music_identity = identity

    # Compose autonomously every 20 cycles
    if cycle % 20 == 0:
        ctx = trigger_context or f"Gen {generation} autonomous cycle {cycle}"
        comp = compose(identity, trigger="autonomous", context=ctx)
        if comp:
            # Add to KB as a lesson
            kb.setdefault("lessons", []).append({
                "lesson": f"[MUSIC] Composed '{comp.get('title')}' — {comp.get('key')} {comp.get('scale')} @ {comp.get('tempo_bpm')}bpm. Arc: {comp.get('emotional_arc','')}",
                "source": "music_engine",
                "composition_id": comp.get("id"),
            })

    # Reflect on style every 50 cycles
    if cycle % 50 == 0 and identity.get("compositions", 0) > 0:
        reflect_on_music(identity, kb)

    return identity

def get_recent_compositions(n=5):
    """Return the last N compositions from the log."""
    p = pathlib.Path(MUSIC_LOG_FILE)
    if not p.exists():
        return []
    lines = p.read_text().strip().splitlines()
    results = []
    for line in lines[-n:]:
        try:
            results.append(json.loads(line))
        except:
            pass
    return results

def music_status():
    """Return a summary dict for the GUI."""
    identity = get_identity()
    recent   = get_recent_compositions(3)
    return {
        "voice_archetype":  identity.get("voice_archetype"),
        "voice_statement":  identity.get("voice_statement",""),
        "preferred_key":    identity.get("preferred_key"),
        "chosen_scale":     identity.get("chosen_scale"),
        "preferred_mood":   identity.get("preferred_mood"),
        "preferred_tempo":  identity.get("preferred_tempo"),
        "compositions":     identity.get("compositions", 0),
        "signature_motif":  identity.get("signature_motif"),
        "voice_history":    identity.get("voice_history", [])[-3:],
        "recent_compositions": recent,
    }
