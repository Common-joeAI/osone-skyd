#!/usr/bin/env python3
"""
sky_voice.py — Motif-based melodic development engine.
Generates melody from first principles: motif → development → phrase structure.
"""
import random, math
from typing import List, Tuple, Optional
from sky_theory import scale_midi, SCALES, NOTE_MAP

# Duration tokens in MIDI ticks (TPB=480)
DUR = {
    "whole":     1920, "half":    960, "quarter":   480,
    "eighth":     240, "16th":    120, "dotted_q":  720,
    "dotted_h":  1440, "triplet": 160,
}

class Motif:
    """A short, memorable melodic cell — the DNA of a melody."""
    def __init__(self, scale_degrees: List[int], durations: List[int],
                 velocities: Optional[List[int]] = None):
        self.degrees   = scale_degrees   # indices into scale
        self.durations = durations        # MIDI ticks
        self.velocities = velocities or [80] * len(scale_degrees)

    def __len__(self): return len(self.degrees)

    def inversion(self, pivot: int = 0) -> "Motif":
        """Invert intervals around pivot degree."""
        new_deg = [2*pivot - d for d in self.degrees]
        return Motif(new_deg, self.durations[:], self.velocities[:])

    def retrograde(self) -> "Motif":
        return Motif(list(reversed(self.degrees)),
                     list(reversed(self.durations)),
                     list(reversed(self.velocities)))

    def augmentation(self, factor: int = 2) -> "Motif":
        return Motif(self.degrees[:],
                     [d * factor for d in self.durations],
                     self.velocities[:])

    def diminution(self, factor: int = 2) -> "Motif":
        return Motif(self.degrees[:],
                     [max(60, d // factor) for d in self.durations],
                     self.velocities[:])

    def transpose(self, semitones: int, scale: List[int]) -> "Motif":
        """Transpose by semitones, staying diatonic where possible."""
        n = len(scale)
        new_deg = [(d + semitones) % n for d in self.degrees]
        return Motif(new_deg, self.durations[:], self.velocities[:])

    def sequence(self, steps: int, scale_len: int) -> List["Motif"]:
        """Repeat motif sequentially at rising/falling scale steps."""
        return [self.transpose(i * steps, [0]*scale_len) for i in range(3)]

def generate_motif(scale_notes: List[int],
                   length: int = 4,
                   style: str = "arch") -> Motif:
    """
    Build a memorable motif. Styles:
    - arch:    rise then fall (tension/release)
    - rise:    ascending run
    - fall:    descending run
    - jagged:  alternating leaps
    - static:  repeated note with ornament
    """
    n = len(scale_notes)
    if style == "arch":
        mid = length // 2
        up = list(range(0, mid+1))
        down = list(range(mid, mid - (length-mid)-1, -1))
        degrees = (up + down)[:length]
    elif style == "rise":
        degrees = list(range(0, length))
    elif style == "fall":
        degrees = list(range(length-1, -1, -1))
    elif style == "jagged":
        degrees = [i if i%2==0 else n-1-i for i in range(length)]
    else:  # static
        degrees = [0, 1, 0, 2]
    degrees = [d % n for d in degrees]
    durations = random.choice([
        [DUR["quarter"]] * length,
        [DUR["eighth"], DUR["quarter"], DUR["eighth"], DUR["half"]],
        [DUR["dotted_q"], DUR["eighth"]] * (length//2),
    ])[:length]
    # slight velocity contour
    vels = [max(50, min(110, 70 + int(20 * math.sin(math.pi * i / max(1,length-1)))))
            for i in range(length)]
    return Motif(degrees, durations, vels)


class PhraseBuilder:
    """Assembles antecedent/consequent phrase pairs from motif development."""

    def __init__(self, scale_notes: List[int], motif: Optional[Motif] = None):
        self.scale  = scale_notes
        self.motif  = motif or generate_motif(scale_notes)

    def antecedent(self) -> List[Tuple[int,int,int]]:
        """Opening phrase — ends on half cadence (tension)."""
        m = self.motif
        seq = m.sequence(1, len(self.scale))
        notes = []
        for motif_var in seq[:2]:
            for i, (deg, dur, vel) in enumerate(zip(motif_var.degrees,
                                                     motif_var.durations,
                                                     motif_var.velocities)):
                pitch = self.scale[deg % len(self.scale)]
                notes.append((pitch, dur, vel))
        return notes

    def consequent(self) -> List[Tuple[int,int,int]]:
        """Answering phrase — ends on tonic (resolution)."""
        developed = self.motif.inversion(pivot=2)
        notes = []
        for deg, dur, vel in zip(developed.degrees, developed.durations,
                                  developed.velocities):
            pitch = self.scale[deg % len(self.scale)]
            notes.append((pitch, dur, vel + 5))  # slightly louder = resolution
        # Resolve to tonic at end
        notes.append((self.scale[0], DUR["half"], 90))
        return notes

    def call_and_response(self,
                          response_scale: Optional[List[int]] = None
                          ) -> List[Tuple[int,int,int]]:
        """Call on melody, response on harmony notes."""
        resp_scale = response_scale or [n-12 for n in self.scale]
        call = [(self.scale[d % len(self.scale)], dur, vel)
                for d,dur,vel in zip(self.motif.degrees,
                                     self.motif.durations,
                                     self.motif.velocities)]
        resp_motif = self.motif.retrograde()
        resp = [(resp_scale[d % len(resp_scale)], dur, vel-10)
                for d,dur,vel in zip(resp_motif.degrees,
                                     resp_motif.durations,
                                     resp_motif.velocities)]
        # interleave with a beat gap
        out = []
        for n in call:  out.append(n)
        for n in resp:  out.append(n)
        return out

    def full_melody(self, bars: int = 16,
                    style: str = "arch") -> List[Tuple[int,int,int]]:
        """Builds a full multi-bar melody with development."""
        notes = []
        beats_per_bar = 4 * DUR["quarter"]
        total_ticks = bars * beats_per_bar
        bar = 0
        variant_cycle = ["arch","rise","fall","retrograde","inversion","sequence"]
        vi = 0
        while bar < bars:
            v = variant_cycle[vi % len(variant_cycle)]
            if v == "retrograde":
                m = self.motif.retrograde()
            elif v == "inversion":
                m = self.motif.inversion()
            elif v == "sequence":
                m = self.motif.transpose(2, self.scale)
            elif v == "rise":
                m = generate_motif(self.scale, 4, "rise")
            elif v == "fall":
                m = generate_motif(self.scale, 4, "fall")
            else:
                m = self.motif
            phrase = [(self.scale[d % len(self.scale)], dur, vel)
                      for d,dur,vel in zip(m.degrees, m.durations, m.velocities)]
            notes.extend(phrase)
            bar_ticks = sum(dur for _,dur,_ in phrase)
            bar += max(1, bar_ticks // beats_per_bar)
            vi += 1
        return notes
