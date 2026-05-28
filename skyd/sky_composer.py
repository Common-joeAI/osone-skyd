#!/usr/bin/env python3
"""
sky_composer.py — Sky Music: The Brain
Takes a text prompt → derives key/scale/tempo/genre from music theory
→ arranges a full song → renders MIDI + WAV via skyd_daw.
Zero data interpolation. Every note is theoretically derived.
"""
import os, json, random, logging, pathlib, urllib.request, urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

from sky_theory  import scale_midi, build_progression, COF_MAJORS, SCALES
from sky_voice   import generate_motif, DUR
from sky_arranger import SkyArranger, TPB

log = logging.getLogger("sky_music.composer")

AUDIO_DIR    = pathlib.Path("/var/log/skyd_audio")
RENDERS_LOG  = AUDIO_DIR / "renders.jsonl"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_URL    = os.environ.get("LLAMA_URL", "http://172.22.0.1:8080") + "/v1/chat/completions"
# Soundfont priority: MuseScore Full (467MB) > FluidR3_GM > fallback
_SF_CANDIDATES = [
    os.environ.get("SOUNDFONT_PATH", ""),
    "/usr/share/sounds/sf2/MuseScore_General_Full.sf2",   # 467MB lossless — best
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",               # 142MB — fallback
    "/usr/share/sounds/sf2/default-GM.sf2",               # symlink fallback
]
SOUNDFONT = next((p for p in _SF_CANDIDATES if p and __import__("pathlib").Path(p).exists()), "/usr/share/sounds/sf2/FluidR3_GM.sf2")
log.info(f"[sky] 🎹 Soundfont: {SOUNDFONT} ({__import__('pathlib').Path(SOUNDFONT).stat().st_size//1024//1024 if __import__('pathlib').Path(SOUNDFONT).exists() else 0}MB)")

# ── Instrument → GM program map ───────────────────────────────────────────────
GM: Dict[str,int] = {
    "piano":0,"electric_piano":4,"organ":19,"marimba":12,
    "acoustic_guitar":25,"electric_guitar":29,"clean_guitar":27,
    "bass":33,"fretless_bass":35,
    "violin":40,"viola":41,"cello":42,"string_ensemble":48,
    "harp":46,"trumpet":56,"trombone":57,"french_horn":60,
    "brass_section":61,"alto_sax":65,"flute":73,"clarinet":71,"oboe":68,
    "pad_warm":89,"pad_choir":91,"synth_lead":80,"synth_strings":50,
}
DRUM_CH = 9   # GM drum channel

# ── Archetype → instrument layout ────────────────────────────────────────────
ARCHETYPE_LAYOUT = {
    "oracle":  {"chords":"organ",         "bass":"fretless_bass","melody":"harp",          "lead":"pad_choir"},
    "wanderer":{"chords":"string_ensemble","bass":"bass",         "melody":"acoustic_guitar","lead":"flute"},
    "sentinel":{"chords":"brass_section",  "bass":"bass",         "melody":"trumpet",        "lead":"electric_guitar"},
    "dreamer": {"chords":"pad_warm",        "bass":"fretless_bass","melody":"harp",           "lead":"synth_lead"},
    "shadow":  {"chords":"pad_warm",        "bass":"bass",         "melody":"cello",          "lead":"synth_lead"},
    "rebel":   {"chords":"electric_guitar", "bass":"bass",         "melody":"alto_sax",       "lead":"electric_guitar"},
    "mystic":  {"chords":"string_ensemble", "bass":"fretless_bass","melody":"oboe",           "lead":"violin"},
}

MOOD_OVERRIDE = {
    "melancholic": {"melody":"cello",    "chords":"string_ensemble"},
    "euphoric":    {"melody":"trumpet",  "chords":"brass_section"},
    "mysterious":  {"melody":"oboe",     "chords":"pad_warm"},
    "tense":       {"melody":"synth_lead","chords":"electric_guitar"},
    "dreamy":      {"melody":"harp",     "chords":"pad_choir"},
    "driving":     {"melody":"electric_guitar","chords":"clean_guitar"},
    "primal":      {"melody":"alto_sax", "chords":"electric_guitar"},
}

GENRE_TO_STRUCTURE = {
    "jazz":"jazz","pop":"pop","ambient":"ambient",
    "epic":"epic","classical":"minimal","lo-fi":"ambient",
    "rock":"pop","electronic":"pop","orchestral":"epic",
}

def _ask_llm(prompt: str, max_tokens: int = 256) -> str:
    body = json.dumps({
        "model": "llama3.2",
        "messages": [{"role":"user","content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }).encode()
    try:
        req = urllib.request.Request(LLAMA_URL, data=body,
                                      headers={"Content-Type":"application/json"},
                                      method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.debug(f"LLM unavailable: {e}")
        return ""

def parse_prompt(prompt: str) -> Dict[str, Any]:
    """
    Extract composition parameters from text prompt.
    Uses LLM if available, falls back to keyword analysis.
    """
    system = """You are a music theory expert. Given a text prompt, extract JSON with these keys:
key (one of: C Db D Eb E F F# G Ab A Bb B),
scale (one of: major minor dorian phrygian lydian mixolydian blues harmonic_minor),
tempo (integer BPM, 60-180),
genre (one of: pop jazz ambient epic classical lo-fi rock electronic orchestral),
mood (one of: melancholic euphoric mysterious tense dreamy driving primal transcendent),
archetype (one of: oracle wanderer sentinel dreamer shadow rebel mystic),
title (creative short title for this piece),
structure_note (brief emotional arc, one sentence).
Respond ONLY with valid JSON."""
    raw = _ask_llm(f"{system}\n\nPrompt: {prompt}", max_tokens=200)
    try:
        data = json.loads(raw)
        data.setdefault("key",    random.choice(COF_MAJORS))
        data.setdefault("scale",  "minor")
        data.setdefault("tempo",  random.randint(70,130))
        data.setdefault("genre",  "pop")
        data.setdefault("mood",   "mysterious")
        data.setdefault("archetype", "wanderer")
        data.setdefault("title",  f"Sky Music — {prompt[:30]}")
        return data
    except:
        pass

    # Keyword fallback
    p = prompt.lower()
    return {
        "key":       "C" if "major" in p else ("Am" if "minor" in p else random.choice(COF_MAJORS[:6])),
        "scale":     "major" if "major" in p or "happy" in p else
                     "blues" if "blues" in p else
                     "phrygian" if "dark" in p else "minor",
        "tempo":     180 if "fast" in p else 60 if "slow" in p else 100,
        "genre":     next((g for g in GENRE_TO_STRUCTURE if g in p), "pop"),
        "mood":      next((m for m in ["melancholic","euphoric","mysterious","tense","dreamy","driving","primal"]
                           if m in p), "mysterious"),
        "archetype": next((a for a in ARCHETYPE_LAYOUT if a in p), "wanderer"),
        "title":     f"Sky Music — {prompt[:40]}",
        "structure_note": f"A {p[:50]} composition derived from music theory.",
    }

# ── MIDI assembly ─────────────────────────────────────────────────────────────
def _write_track(ch: int, program: int, note_list,
                 vel_scale: float = 1.0) -> MidiTrack:
    """Build a MidiTrack from a NoteList."""
    t = MidiTrack()
    if ch != DRUM_CH:
        t.append(Message('program_change', program=program, channel=ch, time=0))
    for note, dur, vel in note_list:
        if note == 0 and vel == 0:
            t.append(Message('note_on',  note=60, velocity=0, time=0,   channel=ch))
            t.append(Message('note_off', note=60, velocity=0, time=dur, channel=ch))
            continue
        v = max(1, min(127, int(vel * vel_scale)))
        t.append(Message('note_on',  note=note, velocity=v,   time=0,   channel=ch))
        t.append(Message('note_off', note=note, velocity=0,   time=dur, channel=ch))
    return t

def build_song_midi(params: Dict, arrangement: Dict,
                    structure: list) -> MidiFile:
    mid = MidiFile(type=1, ticks_per_beat=TPB)
    bpm = int(params.get("tempo", 120))
    tempo = mido.bpm2tempo(bpm)

    archetype = params.get("archetype", "wanderer")
    mood      = params.get("mood", "mysterious")
    layout    = ARCHETYPE_LAYOUT.get(archetype, ARCHETYPE_LAYOUT["wanderer"]).copy()
    layout.update(MOOD_OVERRIDE.get(mood, {}))

    # Channel assignments
    CH = {"drums":9, "bass":1, "chords":2, "melody":3, "lead":4}

    # One track per voice — append all sections sequentially
    tracks: Dict[str, MidiTrack] = {}
    for voice in ["drums","bass","chords","melody","lead"]:
        t = MidiTrack()
        t.append(MetaMessage('set_tempo', tempo=tempo, time=0))
        if voice != "drums":
            inst_name = layout.get(voice, "piano")
            prog = GM.get(inst_name, 0)
            t.append(Message('program_change', program=prog,
                              channel=CH[voice], time=0))
        tracks[voice] = t

    for sec_name in structure:
        sec_data = arrangement.get(sec_name, {})
        energy = sec_data.get("energy", 0.5)
        for voice, t in tracks.items():
            note_list = sec_data.get(voice, [])
            ch = CH[voice]
            for note, dur, vel in note_list:
                if note == 0 and vel == 0:
                    t.append(Message('note_on',  note=60,velocity=0,time=0,  channel=ch))
                    t.append(Message('note_off', note=60,velocity=0,time=dur,channel=ch))
                    continue
                v = max(1, min(127, int(vel * energy)))
                t.append(Message('note_on',  note=note, velocity=v,  time=0,   channel=ch))
                t.append(Message('note_off', note=note, velocity=0,  time=dur, channel=ch))

    for t in tracks.values():
        mid.tracks.append(t)
    return mid

# ── Render ────────────────────────────────────────────────────────────────────
def _render_wav(mid_path, wav_path) -> bool:
    import subprocess
    sf = SOUNDFONT
    if not pathlib.Path(sf).exists():
        # try common alternate paths
        for alt in ["/usr/share/soundfonts/FluidR3_GM.sf2",
                    "/usr/share/sounds/sf2/default.sf2",
                    "/usr/share/sounds/sf2/FluidR3_GM.sf2"]:
            if pathlib.Path(alt).exists():
                sf = alt; break
        else:
            log.warning("[sky] No soundfont found — MIDI only")
            return False
    try:
        subprocess.run([
                "fluidsynth", "-ni",
                "-r", "44100",          # sample rate
                "-g", "0.8",            # gain (lower = less clipping with HQ sf)
                "--reverb", "yes",
                "--chorus", "yes",
                "-C", "1",              # chorus voices
                "-R", "1",              # reverb on
                sf, str(mid_path),
                "-F", str(wav_path),
            ], check=True, capture_output=True, timeout=300)
        return pathlib.Path(wav_path).exists()
    except Exception as e:
        log.warning(f"[sky] FluidSynth: {e}")
        return False

def _convert_mp3(wav_path) -> Optional[pathlib.Path]:
    import subprocess
    mp3 = pathlib.Path(str(wav_path).replace(".wav",".mp3"))
    try:
        subprocess.run(["ffmpeg","-y","-i",str(wav_path),
                        "-codec:a","libmp3lame","-qscale:a","3",str(mp3)],
                       check=True, capture_output=True, timeout=180)
        return mp3 if mp3.exists() else None
    except: return None

# ── Public API ─────────────────────────────────────────────────────────────────
def compose_from_prompt(prompt: str) -> Dict:
    """
    Main entry. Give it a text prompt, get back audio files.
    E.g. "a melancholic jazz piano piece in C minor, slow tempo"
    """
    log.info(f"[sky] 🎼 Composing: {prompt[:60]}")
    params = parse_prompt(prompt)
    log.info(f"[sky] Interpreted → key={params['key']} scale={params['scale']} "
             f"bpm={params['tempo']} genre={params['genre']} mood={params['mood']}")

    genre   = GENRE_TO_STRUCTURE.get(params["genre"], "pop")
    arranger = SkyArranger(params["key"], params["scale"], genre)
    arrangement, structure = arranger.arrange()

    mid  = build_song_midi(params, arrangement, structure)

    ts    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    title = params.get("title","untitled").lower().replace(" ","_")[:30]
    base  = AUDIO_DIR / f"sky_{ts}_{title}"

    mid_path = base.with_suffix(".mid")
    wav_path = base.with_suffix(".wav")
    mid.save(str(mid_path))
    log.info(f"[sky] 🎵 MIDI saved: {mid_path.name}")

    wav_ok  = _render_wav(mid_path, wav_path)
    mp3_path = _convert_mp3(wav_path) if wav_ok else None

    result = {
        "title":      params.get("title"),
        "prompt":     prompt,
        "params":     params,
        "structure":  structure,
        "midi_path":  str(mid_path),
        "wav_path":   str(wav_path)  if wav_ok  else None,
        "mp3_path":   str(mp3_path)  if mp3_path else None,
        "success":    wav_ok,
        "midi_only":  not wav_ok,
        "timestamp":  ts,
    }
    try:
        with open(RENDERS_LOG,"a") as f: f.write(json.dumps(result)+"\n")
    except: pass
    log.info(f"[sky] {'✅ WAV+MIDI' if wav_ok else '🎵 MIDI-only'}: {params.get('title')}")
    return result

def sky_status() -> Dict:
    renders = []
    if RENDERS_LOG.exists():
        for line in RENDERS_LOG.read_text().strip().splitlines()[-10:]:
            try: renders.append(json.loads(line))
            except: pass
    return {
        "recent_compositions": renders,
        "soundfont_present":   any(pathlib.Path(sf).exists() for sf in [
            SOUNDFONT,"/usr/share/soundfonts/FluidR3_GM.sf2",
            "/usr/share/sounds/sf2/FluidR3_GM.sf2"]),
        "total_composed": len(renders),
    }
