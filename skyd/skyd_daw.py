#!/usr/bin/env python3
"""
skyd_daw.py — Digital Audio Workstation for skyd
Turns composition metadata into real multi-track MIDI + WAV/MP3 audio.
Designed by Grok, engineered for skyd's architecture.
"""

import os, json, subprocess, logging, random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import mido
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    MIDO_OK = True
except ImportError:
    MIDO_OK = False

log = logging.getLogger("skyd.daw")

AUDIO_DIR        = Path("/var/log/skyd_audio")
RENDERS_LOG      = AUDIO_DIR / "renders.jsonl"
MUSIC_STATE_FILE = Path("/var/log/skyd_music_identity.json")
SOUNDFONT_PATH   = os.environ.get("SOUNDFONT_PATH", "/usr/share/soundfonts/FluidR3_GM.sf2")

AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────
# GM INSTRUMENT BANK  (program 0-127, channel 9 = drums)
# ─────────────────────────────────────────────────────────────────
INSTRUMENTS: Dict[str, dict] = {
    "piano":            {"prog": 0,   "drum": False, "family": "keys",      "emoji": "🎹"},
    "electric_piano":   {"prog": 4,   "drum": False, "family": "keys",      "emoji": "🎹"},
    "harpsichord":      {"prog": 6,   "drum": False, "family": "keys",      "emoji": "🎹"},
    "organ":            {"prog": 19,  "drum": False, "family": "keys",      "emoji": "🎹"},
    "marimba":          {"prog": 12,  "drum": False, "family": "perc",      "emoji": "🪘"},
    "acoustic_guitar":  {"prog": 25,  "drum": False, "family": "guitar",    "emoji": "🎸"},
    "electric_guitar":  {"prog": 29,  "drum": False, "family": "guitar",    "emoji": "🎸"},
    "clean_guitar":     {"prog": 27,  "drum": False, "family": "guitar",    "emoji": "🎸"},
    "bass":             {"prog": 33,  "drum": False, "family": "bass",      "emoji": "🎸"},
    "fretless_bass":    {"prog": 35,  "drum": False, "family": "bass",      "emoji": "🎸"},
    "violin":           {"prog": 40,  "drum": False, "family": "strings",   "emoji": "🎻"},
    "viola":            {"prog": 41,  "drum": False, "family": "strings",   "emoji": "🎻"},
    "cello":            {"prog": 42,  "drum": False, "family": "strings",   "emoji": "🎻"},
    "string_ensemble":  {"prog": 48,  "drum": False, "family": "strings",   "emoji": "🎻"},
    "harp":             {"prog": 46,  "drum": False, "family": "strings",   "emoji": "🎵"},
    "trumpet":          {"prog": 56,  "drum": False, "family": "brass",     "emoji": "🎺"},
    "trombone":         {"prog": 57,  "drum": False, "family": "brass",     "emoji": "🎺"},
    "french_horn":      {"prog": 60,  "drum": False, "family": "brass",     "emoji": "🎺"},
    "brass_section":    {"prog": 61,  "drum": False, "family": "brass",     "emoji": "🎺"},
    "alto_sax":         {"prog": 65,  "drum": False, "family": "woodwind",  "emoji": "🎷"},
    "flute":            {"prog": 73,  "drum": False, "family": "woodwind",  "emoji": "🎵"},
    "clarinet":         {"prog": 71,  "drum": False, "family": "woodwind",  "emoji": "🎵"},
    "oboe":             {"prog": 68,  "drum": False, "family": "woodwind",  "emoji": "🎵"},
    "pad_warm":         {"prog": 89,  "drum": False, "family": "synth",     "emoji": "🌊"},
    "pad_choir":        {"prog": 91,  "drum": False, "family": "synth",     "emoji": "🌊"},
    "synth_lead":       {"prog": 80,  "drum": False, "family": "synth",     "emoji": "🔊"},
    "synth_strings":    {"prog": 50,  "drum": False, "family": "synth",     "emoji": "🔊"},
    "drum_kit":         {"prog": 0,   "drum": True,  "family": "drums",     "emoji": "🥁"},
    "brush_kit":        {"prog": 40,  "drum": True,  "family": "drums",     "emoji": "🥁"},
}

# MIDI drum notes (GM standard)
DRUM_KICK   = 36
DRUM_SNARE  = 38
DRUM_HIHAT  = 42
DRUM_OHAT   = 46
DRUM_CRASH  = 49
DRUM_CLAP   = 39

# ─────────────────────────────────────────────────────────────────
# ARCHETYPE + MOOD → INSTRUMENT SELECTION
# ─────────────────────────────────────────────────────────────────
ARCHETYPE_MAP = {
    "oracle":    {"melody":"harp",         "chords":"organ",         "lead":"pad_choir",    "bass":"fretless_bass", "drums":"brush_kit"},
    "wanderer":  {"melody":"acoustic_guitar","chords":"string_ensemble","lead":"flute",      "bass":"bass",          "drums":"brush_kit"},
    "sentinel":  {"melody":"trumpet",       "chords":"brass_section", "lead":"electric_guitar","bass":"bass",        "drums":"drum_kit"},
    "dreamer":   {"melody":"harp",          "chords":"pad_warm",      "lead":"synth_lead",   "bass":"fretless_bass", "drums":"brush_kit"},
    "shadow":    {"melody":"cello",         "chords":"pad_warm",      "lead":"synth_lead",   "bass":"bass",          "drums":"drum_kit"},
    "rebel":     {"melody":"electric_guitar","chords":"electric_guitar","lead":"alto_sax",   "bass":"bass",          "drums":"drum_kit"},
    "mystic":    {"melody":"oboe",          "chords":"string_ensemble","lead":"violin",       "bass":"fretless_bass", "drums":"brush_kit"},
    "herald":    {"melody":"french_horn",   "chords":"brass_section", "lead":"trumpet",      "bass":"bass",          "drums":"drum_kit"},
}

MOOD_OVERRIDES = {
    "melancholic":   {"melody": "cello",    "chords": "string_ensemble"},
    "euphoric":      {"melody": "trumpet",  "chords": "brass_section"},
    "mysterious":    {"melody": "oboe",     "chords": "pad_warm"},
    "tense":         {"melody": "synth_lead","chords": "electric_guitar"},
    "dreamy":        {"melody": "harp",     "chords": "pad_choir"},
    "driving":       {"melody": "electric_guitar", "chords": "clean_guitar"},
    "primal":        {"melody": "alto_sax", "chords": "electric_guitar"},
    "transcendent":  {"melody": "pad_choir","chords": "synth_strings"},
}

# Scale intervals (semitones from root)
SCALES = {
    "major":       [0,2,4,5,7,9,11],
    "minor":       [0,2,3,5,7,8,10],
    "dorian":      [0,2,3,5,7,9,10],
    "phrygian":    [0,1,3,5,7,8,10],
    "lydian":      [0,2,4,6,7,9,11],
    "mixolydian":  [0,2,4,5,7,9,10],
    "blues":       [0,3,5,6,7,10],
    "pentatonic_min": [0,3,5,7,10],
    "pentatonic_maj": [0,2,4,7,9],
    "whole_tone":  [0,2,4,6,8,10],
}

NOTE_MAP = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,
            "F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}

def get_scale_notes(key: str, scale_name: str, octave: int = 4) -> List[int]:
    root = NOTE_MAP.get(key.split(" ")[0], 0)
    intervals = SCALES.get(scale_name, SCALES["minor"])
    base = 12 * (octave + 1) + root
    return [base + i for i in intervals]

def choose_instruments(composition: dict) -> dict:
    archetype = composition.get("voice_archetype", "wanderer")
    mood      = composition.get("mood", "mysterious")
    base = ARCHETYPE_MAP.get(archetype, ARCHETYPE_MAP["wanderer"]).copy()
    overrides = MOOD_OVERRIDES.get(mood, {})
    base.update(overrides)
    # Always ensure drums
    if "drums" not in base:
        base["drums"] = "drum_kit"
    return base

# ─────────────────────────────────────────────────────────────────
# MIDI TRACK BUILDERS
# ─────────────────────────────────────────────────────────────────
TPB = 480  # ticks per beat

def _note(track, note, vel, dur, ch, gap=0):
    """Helper: note_on then note_off with timing."""
    track.append(Message('note_on',  note=note, velocity=vel, time=gap,  channel=ch))
    track.append(Message('note_off', note=note, velocity=0,   time=dur,  channel=ch))

def build_drum_track(bars: int, tempo: int, feel: str = "straight") -> MidiTrack:
    t = MidiTrack()
    t.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo), time=0))
    t.append(Message('program_change', program=0, channel=9, time=0))
    beat = TPB
    half = TPB // 2
    for bar in range(bars):
        if feel == "swing":
            # swing: kick on 1, snare on 2&4, shuffle hats
            _note(t, DRUM_KICK,  100, beat//3, 9)
            _note(t, DRUM_HIHAT, 70,  beat//3, 9)
            _note(t, DRUM_SNARE, 90,  beat//3, 9)
            _note(t, DRUM_HIHAT, 60,  beat//3, 9)
            _note(t, DRUM_KICK,  80,  beat//3, 9)
            _note(t, DRUM_HIHAT, 70,  beat//3, 9)
            _note(t, DRUM_SNARE, 95,  beat//3, 9)
            _note(t, DRUM_HIHAT, 65,  beat//3, 9)
        elif feel == "half_time":
            _note(t, DRUM_KICK,  100, beat, 9)
            _note(t, DRUM_HIHAT, 70,  beat, 9)
            _note(t, DRUM_SNARE, 85,  beat*2, 9)
            _note(t, DRUM_HIHAT, 70,  beat, 9)
        else:  # straight 4/4
            _note(t, DRUM_KICK,  100, half, 9)
            _note(t, DRUM_HIHAT, 75,  half, 9)
            _note(t, DRUM_SNARE, 90,  half, 9)
            _note(t, DRUM_HIHAT, 70,  half, 9)
            _note(t, DRUM_KICK,  85,  half, 9)
            _note(t, DRUM_HIHAT, 75,  half, 9)
            _note(t, DRUM_SNARE, 95,  half, 9)
            _note(t, DRUM_HIHAT, 72,  half, 9)
    return t

def build_bass_track(scale_notes: List[int], progression: List[int],
                     bars: int, inst: str, ch: int = 1) -> MidiTrack:
    t = MidiTrack()
    prog_num = INSTRUMENTS[inst]["prog"]
    t.append(Message('program_change', program=prog_num, channel=ch, time=0))
    bass_notes = [n - 12 for n in scale_notes]  # one octave down
    bars_per_chord = max(1, bars // max(len(progression), 1))
    for deg in (progression * (bars // max(len(progression), 1) + 1))[:bars]:
        root = bass_notes[deg % len(bass_notes)]
        # Walking bass: root + fifth
        fifth = bass_notes[(deg + 2) % len(bass_notes)]
        _note(t, max(24, min(96, root)), 95, TPB, ch)
        _note(t, max(24, min(96, root)), 85, TPB, ch)
        _note(t, max(24, min(96, fifth)), 80, TPB, ch)
        _note(t, max(24, min(96, root)), 90, TPB, ch)
    return t

def build_chord_track(scale_notes: List[int], progression: List[int],
                      bars: int, inst: str, ch: int = 2) -> MidiTrack:
    t = MidiTrack()
    prog_num = INSTRUMENTS[inst]["prog"]
    t.append(Message('program_change', program=prog_num, channel=ch, time=0))
    # Basic triads from scale
    for deg in (progression * (bars // max(len(progression), 1) + 1))[:bars]:
        root  = scale_notes[deg % len(scale_notes)]
        third = scale_notes[(deg + 2) % len(scale_notes)]
        fifth = scale_notes[(deg + 4) % len(scale_notes)]
        # Strum: slight offsets for realism
        for note, vel, gap in [(root,70,0),(third,65,20),(fifth,68,20)]:
            t.append(Message('note_on',  note=min(127,note), velocity=vel, time=gap, channel=ch))
        for note in [root, third, fifth]:
            t.append(Message('note_off', note=min(127,note), velocity=0, time=TPB*2//3, channel=ch))
        # rest
        t.append(Message('note_on', note=root, velocity=0, time=TPB*4//3, channel=ch))
        t.append(Message('note_off', note=root, velocity=0, time=0, channel=ch))
    return t

def build_melody_track(scale_notes: List[int], bars: int,
                       inst: str, motif: Optional[List[int]], ch: int = 3) -> MidiTrack:
    t = MidiTrack()
    prog_num = INSTRUMENTS[inst]["prog"]
    t.append(Message('program_change', program=prog_num, channel=ch, time=0))
    melody_notes = [n + 12 for n in scale_notes]  # one octave up
    # Use motif if provided, else generate melodic phrase
    if motif and len(motif) >= 2:
        pattern = [melody_notes[i % len(melody_notes)] for i in motif]
    else:
        pattern = melody_notes
    durations = [TPB//2, TPB//2, TPB, TPB//4, TPB//4, TPB//2, TPB*2, TPB]
    pos = 0
    for bar in range(bars):
        for beat in range(4):
            note = pattern[(bar * 4 + beat) % len(pattern)]
            dur  = durations[(bar * 4 + beat) % len(durations)]
            vel  = random.randint(72, 92)
            _note(t, min(127, max(0, note)), vel, dur, ch)
    return t

def build_lead_track(scale_notes: List[int], bars: int,
                     inst: str, ch: int = 4) -> MidiTrack:
    """Sparse lead / counter-melody."""
    t = MidiTrack()
    prog_num = INSTRUMENTS[inst]["prog"]
    t.append(Message('program_change', program=prog_num, channel=ch, time=0))
    lead_notes = [n + 24 for n in scale_notes]  # two octaves up
    silence = TPB * 2
    for bar in range(bars):
        if bar % 2 == 0:  # play every other bar
            note = lead_notes[(bar * 3) % len(lead_notes)]
            _note(t, min(127, max(0, note)), 80, TPB * 2, ch)
        else:
            t.append(Message('note_on', note=60, velocity=0, time=TPB*4, channel=ch))
            t.append(Message('note_off', note=60, velocity=0, time=0, channel=ch))
    return t

# ─────────────────────────────────────────────────────────────────
# ASSEMBLE FULL MIDI
# ─────────────────────────────────────────────────────────────────
def build_midi(composition: dict, instruments: dict, bars: int = 16) -> MidiFile:
    mid = MidiFile(type=1, ticks_per_beat=TPB)

    bpm        = int(composition.get("tempo_bpm", composition.get("tempo", 120)))
    key        = composition.get("key", "C")
    scale_name = composition.get("scale", "minor")
    prog_raw   = composition.get("progression", [0, 5, 7, 0])
    motif      = composition.get("signature_motif", None)
    mood       = composition.get("mood", "mysterious")

    # Parse progression — could be list of ints or string
    if isinstance(prog_raw, str):
        try:
            prog_raw = [int(x.strip()) for x in prog_raw.split(",")]
        except:
            prog_raw = [0, 5, 7, 0]

    # Detect feel from mood/tempo
    feel = "swing" if mood in ("primal", "introspective") else \
           "half_time" if mood in ("melancholic", "dreamy") else "straight"

    scale_notes = get_scale_notes(key, scale_name, octave=4)

    mid.tracks.append(build_drum_track(bars, bpm, feel))
    mid.tracks.append(build_bass_track(scale_notes, prog_raw, bars, instruments["bass"], ch=1))
    mid.tracks.append(build_chord_track(scale_notes, prog_raw, bars, instruments["chords"], ch=2))
    mid.tracks.append(build_melody_track(scale_notes, bars, instruments["melody"], motif, ch=3))
    mid.tracks.append(build_lead_track(scale_notes, bars, instruments["lead"], ch=4))

    return mid

# ─────────────────────────────────────────────────────────────────
# RENDERING
# ─────────────────────────────────────────────────────────────────
def render_to_wav(mid_path: Path, wav_path: Path) -> bool:
    if not Path(SOUNDFONT_PATH).exists():
        log.warning(f"[daw] Soundfont not found: {SOUNDFONT_PATH}")
        return False
    cmd = ["fluidsynth", "-ni", SOUNDFONT_PATH, str(mid_path),
           "-F", str(wav_path), "-r", "44100", "-g", "1.0"]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return wav_path.exists()
    except Exception as e:
        log.warning(f"[daw] FluidSynth render failed: {e}")
        return False

def convert_to_mp3(wav_path: Path) -> Optional[Path]:
    mp3_path = wav_path.with_suffix(".mp3")
    try:
        subprocess.run(["ffmpeg", "-y", "-i", str(wav_path),
                        "-codec:a", "libmp3lame", "-qscale:a", "4",
                        str(mp3_path)],
                       check=True, capture_output=True, timeout=120)
        return mp3_path if mp3_path.exists() else None
    except Exception as e:
        log.debug(f"[daw] MP3 conversion skipped: {e}")
        return None

# ─────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────
def render_composition(composition: dict, bars: int = 16) -> dict:
    """
    Main entry — takes a compose() dict, returns paths to audio files.
    """
    if not MIDO_OK:
        log.error("[daw] mido not installed — cannot render")
        return {"success": False, "error": "mido not installed"}

    instruments = choose_instruments(composition)
    ts    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    title = composition.get("title", "untitled").lower().replace(" ", "_")[:30]
    base  = AUDIO_DIR / f"skyd_{ts}_{title}"

    mid_path = base.with_suffix(".mid")
    wav_path = base.with_suffix(".wav")

    # Build + save MIDI
    try:
        mid = build_midi(composition, instruments, bars=bars)
        mid.save(str(mid_path))
        log.info(f"[daw] MIDI written: {mid_path.name}")
    except Exception as e:
        log.error(f"[daw] MIDI build failed: {e}")
        return {"success": False, "error": str(e)}

    # Render WAV
    wav_ok  = render_to_wav(mid_path, wav_path)
    mp3_path = convert_to_mp3(wav_path) if wav_ok else None

    inst_names = {role: f"{INSTRUMENTS.get(inst,{}).get('emoji','🎵')} {inst}"
                  for role, inst in instruments.items()}

    result = {
        "title":       composition.get("title", "untitled"),
        "midi_path":   str(mid_path),
        "wav_path":    str(wav_path)  if wav_ok  else None,
        "mp3_path":    str(mp3_path)  if mp3_path else None,
        "instruments": inst_names,
        "key":         composition.get("key"),
        "scale":       composition.get("scale"),
        "bpm":         composition.get("tempo_bpm", composition.get("tempo")),
        "mood":        composition.get("mood"),
        "archetype":   composition.get("voice_archetype"),
        "success":     wav_ok,
        "timestamp":   ts,
    }

    # Append to render log
    try:
        with open(RENDERS_LOG, "a") as f:
            f.write(json.dumps(result) + "\n")
    except: pass

    log.info(f"[daw] {'✅' if wav_ok else '🎵 MIDI-only'} Rendered: {composition.get('title')} | "
             f"{', '.join(f'{r}:{i}' for r,i in instruments.items())}")
    return result

def daw_status() -> dict:
    """Return render history for the GUI."""
    renders = []
    if RENDERS_LOG.exists():
        for line in RENDERS_LOG.read_text().strip().splitlines()[-10:]:
            try: renders.append(json.loads(line))
            except: pass
    return {"recent_renders": renders, "audio_dir": str(AUDIO_DIR),
            "soundfont_present": Path(SOUNDFONT_PATH).exists(),
            "total_renders": len(renders)}

def list_instruments() -> dict:
    """Return all available instruments grouped by family."""
    grouped = {}
    for name, info in INSTRUMENTS.items():
        fam = info["family"]
        grouped.setdefault(fam, []).append(f"{info['emoji']} {name}")
    return grouped

# Hook for skyd_music.py music_tick()
def music_tick_hook(composition: dict) -> dict:
    return render_composition(composition)
