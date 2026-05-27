#!/usr/bin/env python3
"""
sky_arranger.py — Song Structure & Arrangement Engine
Builds multi-section songs: intro→verse→chorus→bridge→outro
Each section has its own energy, density, dynamics, and instrument weight.
"""
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from sky_theory import (build_progression, voice_lead, cadence_chords,
                         scale_midi, secondary_dominant, borrowed_chord)
from sky_voice import PhraseBuilder, generate_motif, DUR

TPB = 480  # ticks per beat

@dataclass
class Section:
    name:        str
    bars:        int
    energy:      float    # 0.0 – 1.0
    density:     float    # instrument density
    velocity_base: int    # MIDI velocity anchor
    velocity_var:  int    # ± variation
    use_lead:    bool     = True
    use_melody:  bool     = True
    use_chords:  bool     = True
    use_bass:    bool     = True
    use_drums:   bool     = True
    drum_intensity: float = 0.7   # 0=sparse, 1=full
    notes:       str      = ""    # e.g. "tension", "release", "climax"

# Standard song structures ────────────────────────────────────────────────────
SONG_STRUCTURES: Dict[str, List[str]] = {
    "pop":      ["intro","verse","chorus","verse","chorus","bridge","chorus","outro"],
    "jazz":     ["intro","verse","verse","chorus","bridge","verse","outro"],
    "ambient":  ["intro","verse","verse","bridge","outro"],
    "epic":     ["intro","verse","chorus","verse","chorus","bridge","chorus","chorus","outro"],
    "minimal":  ["intro","verse","chorus","outro"],
}

DEFAULT_SECTIONS: Dict[str, Section] = {
    "intro":  Section("intro",  4,  0.25, 0.40, 55, 8,  use_lead=False,  use_melody=False, drum_intensity=0.3),
    "verse":  Section("verse",  16, 0.50, 0.60, 70, 10, use_lead=True,   use_melody=True,  drum_intensity=0.6),
    "chorus": Section("chorus", 8,  0.90, 0.85, 90, 8,  use_lead=True,   use_melody=True,  drum_intensity=1.0, notes="climax"),
    "bridge": Section("bridge", 8,  0.65, 0.65, 75, 12, use_lead=True,   use_melody=False, drum_intensity=0.7, notes="tension"),
    "outro":  Section("outro",  4,  0.15, 0.30, 50, 6,  use_lead=False,  use_melody=False, drum_intensity=0.2, notes="release"),
}

# ── Note-list types ──────────────────────────────────────────────────────────
# All builders return List[Tuple[midi_note, duration_ticks, velocity]]
NoteList = List[Tuple[int,int,int]]

def _clamp_vel(v: int) -> int: return max(1, min(127, v))
def _clamp_note(n: int) -> int: return max(0, min(127, n))


class SkyArranger:
    def __init__(self, key: str, scale_name: str, genre: str = "pop"):
        self.key        = key
        self.scale_name = scale_name
        self.genre      = genre
        self.scale_notes = scale_midi(key, scale_name, octave=4)
        self.sections   = {k: v for k, v in DEFAULT_SECTIONS.items()}
        # Motif created once, used across all sections for coherence
        self.motif = generate_motif(self.scale_notes, 4,
                                     random.choice(["arch","rise","jagged"]))
        self.phrase_builder = PhraseBuilder(self.scale_notes, self.motif)

    def get_structure(self) -> List[str]:
        return SONG_STRUCTURES.get(self.genre, SONG_STRUCTURES["pop"])

    # ── Chord track ──────────────────────────────────────────────────────────
    def build_chords(self, section: Section, progression) -> NoteList:
        notes = []
        bars_done = 0
        prog_len  = len(progression)
        while bars_done < section.bars:
            chord_notes_raw, quality, root = progression[bars_done % prog_len]
            # Humanize: stagger strum slightly
            vel_base = _clamp_vel(section.velocity_base - 10
                                  + random.randint(-section.velocity_var, section.velocity_var))
            for i, note in enumerate(chord_notes_raw):
                stagger = i * 20 if section.energy > 0.6 else 0
                dur = TPB * 4 - stagger
                vel = _clamp_vel(vel_base - i*3)
                notes.append((_clamp_note(note), dur, vel))
            bars_done += 1
        return notes

    # ── Bass track ───────────────────────────────────────────────────────────
    def build_bass(self, section: Section, progression) -> NoteList:
        notes = []
        prog_len = len(progression)
        for bar in range(section.bars):
            chord_notes_raw, quality, root = progression[bar % prog_len]
            bass_root = _clamp_note(root - 12)
            fifth     = _clamp_note(chord_notes_raw[2] - 12 if len(chord_notes_raw) >= 3 else root-7)
            vel = _clamp_vel(section.velocity_base + 5
                              + random.randint(-section.velocity_var, section.velocity_var))
            if section.energy >= 0.8:  # walking bass in high-energy sections
                notes += [(bass_root, TPB, vel), (bass_root+2, TPB, vel-5),
                           (fifth,     TPB, vel-3), (bass_root+4, TPB, vel-5)]
            elif section.energy >= 0.5:
                notes += [(bass_root, TPB*2, vel), (fifth, TPB*2, vel-5)]
            else:
                notes += [(bass_root, TPB*4, vel)]
        return notes

    # ── Melody track ─────────────────────────────────────────────────────────
    def build_melody(self, section: Section) -> NoteList:
        if not section.use_melody:
            return []
        if section.notes == "climax":
            # Chorus: augmented + louder variant
            base = self.phrase_builder.full_melody(section.bars, "rise")
            return [(_clamp_note(n+12), d, _clamp_vel(v+15)) for n,d,v in base]
        elif section.notes == "tension":
            return self.phrase_builder.call_and_response()
        else:
            return self.phrase_builder.full_melody(section.bars)

    # ── Lead track ───────────────────────────────────────────────────────────
    def build_lead(self, section: Section) -> NoteList:
        if not section.use_lead:
            return []
        inv = self.motif.inversion()
        lead_scale = [n+24 for n in self.scale_notes]
        notes = []
        for bar in range(section.bars):
            if bar % 2 == 0:  # sparse — every other bar
                m = inv if bar % 4 == 0 else self.motif
                for deg, dur, vel in zip(m.degrees, m.durations, m.velocities):
                    pitch = _clamp_note(lead_scale[deg % len(lead_scale)])
                    notes.append((pitch, dur,
                                  _clamp_vel(vel + int(section.energy * 15))))
            else:
                notes.append((0, TPB*4, 0))  # rest
        return notes

    # ── Drum patterns ────────────────────────────────────────────────────────
    KICK=36; SNARE=38; HH=42; OH=46; CRASH=49; CLAP=39; RIDE=51

    def build_drums(self, section: Section) -> NoteList:
        if not section.use_drums:
            return []
        i = section.drum_intensity
        notes = []
        for bar in range(section.bars):
            if i >= 0.9:   # full kit — chorus
                notes += [
                    (self.KICK,  TPB//2, 105), (self.HH, TPB//2, 70),
                    (self.SNARE, TPB//2, 95),  (self.HH, TPB//2, 65),
                    (self.KICK,  TPB//4, 100), (self.KICK, TPB//4, 90),
                    (self.HH,    TPB//2, 68),
                    (self.SNARE, TPB//2, 98),  (self.HH, TPB//2, 72),
                ]
            elif i >= 0.6:  # verse — standard 4/4
                notes += [
                    (self.KICK,  TPB//2, 100), (self.HH, TPB//2, 65),
                    (self.SNARE, TPB//2, 90),  (self.HH, TPB//2, 62),
                    (self.KICK,  TPB//2, 95),  (self.HH, TPB//2, 65),
                    (self.SNARE, TPB//2, 92),  (self.HH, TPB//2, 60),
                ]
            elif i >= 0.3:  # sparse — intro/bridge
                notes += [
                    (self.KICK, TPB,   90), (self.RIDE, TPB, 55),
                    (self.SNARE,TPB*2, 80), (self.RIDE, TPB, 52),
                ]
            else:           # outro — just ride
                notes += [(self.RIDE, TPB, 45)] * 4
        return notes

    # ── Full arrangement ─────────────────────────────────────────────────────
    def arrange(self, progression_name: Optional[str] = None) -> Dict[str, Dict[str, NoteList]]:
        """
        Returns: { section_name: {drums, bass, chords, melody, lead} }
        in song order.
        """
        structure   = self.get_structure()
        arrangement = {}
        progression = build_progression(self.key, self.scale_name,
                                         prog_name=progression_name)
        # Add a cadence at the end for harmonic closure
        cad = cadence_chords(self.key, self.scale_name, "perfect")

        for section_name in structure:
            sec = self.sections.get(section_name, DEFAULT_SECTIONS["verse"])
            # Enrich progression for chorus: add secondary dominant
            if section_name == "chorus":
                sec_dom = secondary_dominant(self.key, 0, self.scale_name)
                chorus_prog = progression + [(sec_dom, "dom7", sec_dom[0])]
            elif section_name == "bridge":
                # Borrow a chord from parallel major for colour
                borrow, bq = borrowed_chord(self.key, "major", 3)
                cad_chord_notes, cad_q = cad[1]
                cad_root = cad_chord_notes[0] if cad_chord_notes else 60
                chorus_prog = progression[:-1] + [(borrow, bq, borrow[0])] + [(cad_chord_notes, cad_q, cad_root)]
            else:
                chorus_prog = progression

            arrangement[section_name] = {
                "drums":  self.build_drums(sec),
                "bass":   self.build_bass(sec, chorus_prog),
                "chords": self.build_chords(sec, chorus_prog),
                "melody": self.build_melody(sec),
                "lead":   self.build_lead(sec),
                "bars":   sec.bars,
                "energy": sec.energy,
            }

        return arrangement, structure
