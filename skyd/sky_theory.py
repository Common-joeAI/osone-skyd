#!/usr/bin/env python3
"""
sky_theory.py — Advanced Music Theory Engine for Sky Music
Zero data interpolation — every note derived from first principles.
"""
import random
from typing import List, Tuple, Dict, Optional

# ── Pitch / interval tables ───────────────────────────────────────────────────
NOTE_MAP   = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,
              "F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}
NOTE_NAMES = ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"]

SCALES: Dict[str, List[int]] = {
    "major":          [0,2,4,5,7,9,11],
    "minor":          [0,2,3,5,7,8,10],
    "dorian":         [0,2,3,5,7,9,10],
    "phrygian":       [0,1,3,5,7,8,10],
    "lydian":         [0,2,4,6,7,9,11],
    "mixolydian":     [0,2,4,5,7,9,10],
    "locrian":        [0,1,3,5,6,8,10],
    "pentatonic_min": [0,3,5,7,10],
    "pentatonic_maj": [0,2,4,7,9],
    "blues":          [0,3,5,6,7,10],
    "whole_tone":     [0,2,4,6,8,10],
    "harmonic_minor": [0,2,3,5,7,8,11],
    "melodic_minor":  [0,2,3,5,7,9,11],
}

# Chord intervals from root (semitones)
CHORD_TYPES: Dict[str, List[int]] = {
    "major":  [0,4,7],      "minor":  [0,3,7],
    "dim":    [0,3,6],      "aug":    [0,4,8],
    "sus2":   [0,2,7],      "sus4":   [0,5,7],
    "maj7":   [0,4,7,11],   "min7":   [0,3,7,10],
    "dom7":   [0,4,7,10],   "dim7":   [0,3,6,9],
    "hdim7":  [0,3,6,10],   "add9":   [0,4,7,14],
    "min9":   [0,3,7,10,14],"maj9":   [0,4,7,11,14],
}

# Roman numeral → degree index
ROMAN_DEG = {"i":0,"ii":1,"iii":2,"iv":3,"v":4,"vi":5,"vii":6,
             "I":0,"II":1,"III":2,"IV":3,"V":4,"VI":5,"VII":6}

# Diatonic chord qualities per mode (index = scale degree 0-6)
DIATONIC_QUALITIES: Dict[str, List[str]] = {
    "major":         ["major","minor","minor","major","major","minor","dim"],
    "minor":         ["minor","dim","major","minor","minor","major","major"],
    "dorian":        ["minor","minor","major","major","minor","dim","major"],
    "phrygian":      ["minor","major","major","minor","dim","major","minor"],
    "mixolydian":    ["major","minor","dim","major","minor","minor","major"],
    "harmonic_minor":["minor","dim","aug","minor","major","major","dim"],
}

# Progressions as scale-degree indices
PROGRESSIONS: Dict[str, List[int]] = {
    "I-IV-V-I":     [0,3,4,0],    "I-V-vi-IV":   [0,4,5,3],
    "ii-V-I":       [1,4,0],      "I-vi-IV-V":   [0,5,3,4],
    "i-VII-VI-VII": [0,6,5,6],    "i-iv-VII-III":[0,3,6,2],
    "I-iii-IV-V":   [0,2,3,4],    "vi-IV-I-V":   [5,3,0,4],
    "i-v-i-iv":     [0,4,0,3],    "I-II-IV-I":   [0,1,3,0],
}

def root_midi(key: str, octave: int = 4) -> int:
    return 12 * (octave + 1) + NOTE_MAP.get(key.split()[0], 0)

def scale_midi(key: str, scale_name: str, octave: int = 4) -> List[int]:
    root = root_midi(key, octave)
    return [root + i for i in SCALES.get(scale_name, SCALES["minor"])]

def chord_notes(root: int, chord_type: str = "minor") -> List[int]:
    return [root + i for i in CHORD_TYPES.get(chord_type, [0,3,7])]

def diatonic_chord(key: str, scale_name: str, degree: int,
                   octave: int = 4) -> Tuple[List[int], str]:
    """Return (midi_notes, quality) for a diatonic chord."""
    s = scale_midi(key, scale_name, octave)
    qualities = DIATONIC_QUALITIES.get(scale_name, DIATONIC_QUALITIES["minor"])
    q = qualities[degree % len(qualities)]
    root = s[degree % len(s)]
    return chord_notes(root, q), q

def build_progression(key: str, scale_name: str,
                      prog_name: Optional[str] = None,
                      custom_degrees: Optional[List[int]] = None,
                      octave: int = 4) -> List[Tuple[List[int], str, int]]:
    """Returns list of (notes, quality, root_midi) for a full progression."""
    if custom_degrees:
        degrees = custom_degrees
    elif prog_name and prog_name in PROGRESSIONS:
        degrees = PROGRESSIONS[prog_name]
    else:
        # Pick progression appropriate for scale
        if scale_name in ("minor","phrygian","harmonic_minor"):
            degrees = PROGRESSIONS["i-iv-VII-III"]
        elif scale_name in ("dorian","mixolydian"):
            degrees = PROGRESSIONS["i-v-i-iv"]
        else:
            degrees = PROGRESSIONS["I-IV-V-I"]

    chords = []
    for deg in degrees:
        notes, q = diatonic_chord(key, scale_name, deg, octave)
        s = scale_midi(key, scale_name, octave)
        chords.append((notes, q, s[deg % len(s)]))
    return chords

# ── Voice leading ────────────────────────────────────────────────────────────
def voice_lead(chord1_notes: List[int], chord2_notes: List[int]) -> List[int]:
    """Smooth voice leading: move each voice to nearest note in chord2."""
    result = []
    used = set()
    for n1 in chord1_notes:
        best = min(chord2_notes, key=lambda n2: abs(n2 - n1))
        # avoid doubling same exact midi note if possible
        if best in used and len(chord2_notes) > len(used):
            alts = sorted(chord2_notes, key=lambda n2: abs(n2 - n1))
            for alt in alts:
                if alt not in used:
                    best = alt
                    break
        result.append(best)
        used.add(best)
    return result

def check_parallel_fifths(chord1: List[int], chord2: List[int]) -> bool:
    """Return True if parallel fifths detected (voice leading fault)."""
    for i in range(len(chord1)):
        for j in range(i+1, len(chord1)):
            if (chord1[j] - chord1[i]) % 12 == 7:   # fifth in chord1
                if (chord2[j] - chord2[i]) % 12 == 7: # fifth in chord2
                    if chord1[i] != chord2[i]:          # voices moved
                        return True
    return False

# ── Secondary dominants ───────────────────────────────────────────────────────
def secondary_dominant(key: str, target_degree: int,
                       scale_name: str = "minor", octave: int = 4) -> List[int]:
    """V7 of the target degree — applied dominant."""
    s = scale_midi(key, scale_name, octave)
    target_root = s[target_degree % len(s)]
    v_root = (target_root - 5) % 128   # perfect 4th below = dominant
    return chord_notes(v_root, "dom7")

# ── Modal interchange ─────────────────────────────────────────────────────────
def borrowed_chord(key: str, source_scale: str, degree: int, octave: int = 4):
    """Borrow a chord from a parallel mode."""
    return diatonic_chord(key, source_scale, degree, octave)

# ── Cadences ──────────────────────────────────────────────────────────────────
def cadence_chords(key: str, scale_name: str,
                   ctype: str = "perfect", octave: int = 4):
    """Return list of (notes, quality) for the cadence type."""
    if ctype == "perfect":    degrees = [4, 0]
    elif ctype == "half":      degrees = [0, 4]
    elif ctype == "deceptive": degrees = [4, 5]
    elif ctype == "plagal":    degrees = [3, 0]
    else:                      degrees = [4, 0]
    return [diatonic_chord(key, scale_name, d, octave) for d in degrees]

# ── Circle of fifths navigation ───────────────────────────────────────────────
COF_MAJORS = ["C","G","D","A","E","B","F#","Db","Ab","Eb","Bb","F"]
COF_MINORS = ["A","E","B","F#","C#","G#","Eb","Bb","F","C","G","D"]

def modulation_path(from_key: str, to_key: str) -> List[str]:
    """Shortest path on circle of fifths between two keys."""
    keys = COF_MAJORS
    try:
        a = keys.index(from_key)
        b = keys.index(to_key)
    except ValueError:
        return [from_key, to_key]
    n = len(keys)
    cw = (b - a) % n
    ccw = (a - b) % n
    if cw <= ccw:
        path = [keys[(a+i)%n] for i in range(cw+1)]
    else:
        path = [keys[(a-i)%n] for i in range(ccw+1)]
    return path
