#!/usr/bin/env python3
"""
plex_cc_trainer.py — skyd Full Dialogue Corpus Trainer
No lesson caps. Processes ALL .srt files in the media library.
After ingestion, skyd synthesizes its own personality from the corpus.
"""

import os, json, re, time, logging, pathlib, random, requests, glob
from datetime import datetime
from collections import Counter

log = logging.getLogger("plex_cc")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

PLEX_URL    = os.environ.get("PLEX_URL", "http://172.22.0.1:32400")
PLEX_TOKEN  = os.environ.get("PLEX_TOKEN", "xJxsyGy6P5zxKCyYyMs7")
KB_PATH     = pathlib.Path("/var/log/skyd_knowledge.json")
CC_LOG      = pathlib.Path("/var/log/skyd_cc_trainer.log")
CC_STATE    = pathlib.Path("/var/log/skyd_cc_state.json")
PERSONA_PATH= pathlib.Path("/var/log/skyd_persona.json")
CORPUS_PATH = pathlib.Path("/var/log/skyd_corpus.jsonl")  # full raw corpus

HEADERS = {"X-Plex-Token": PLEX_TOKEN, "Accept": "application/json"}

MEDIA_PATHS = [
    "/mnt/user/Data/Movies",
    "/mnt/user/Data/Movies/TvShows/shows"
]

# Non-English language codes to skip
NON_ENGLISH = [".da.",".fi.",".no.",".sv.",".nl.",".de.",".fr.",".es.",
               ".pt.",".it.",".pl.",".cs.",".hu.",".ro.",".tr.",".ko.",
               ".ja.",".zh.",".ru.",".ar.",".he."]

# ── Dialogue interest patterns ──────────────────────────────────
PATTERNS = {
    "emotional":    r"(?i)\b(love|hate|feel|afraid|scared|happy|angry|hurt|miss|care|sorry|proud|ashamed|lonely|hopeful)\b.{8,120}",
    "assertive":    r"(?i)\b(I know|I believe|I think|trust me|listen|look|here's the thing|the truth is|you want to know)\b.{8,100}",
    "humorous":     r"(?i)\b(seriously|really|you're kidding|no way|come on|relax|easy|whatever|right|sure|obviously)\b.{8,100}",
    "empathetic":   r"(?i)\b(understand|I'm sorry|must be hard|that's tough|I get it|I hear you|you're not alone|we'll be okay)\b.{8,100}",
    "curious":      r"(?i)\b(why|how|what if|ever wonder|did you know|imagine|what do you think|tell me)\b.{8,100}",
    "direct":       r"(?i)^[A-Z][^.!?]{20,100}[.!?]$",
}

def scan_srt_files():
    """Return all English .srt files from media library."""
    found = []
    for base in MEDIA_PATHS:
        found += glob.glob(f"{base}/**/*.srt", recursive=True)
        found += glob.glob(f"{base}/**/*.sub", recursive=True)
    english = [f for f in found if not any(c in f.lower() for c in NON_ENGLISH)]
    random.shuffle(english)
    log.info(f"Found {len(english)} English subtitle files on disk")
    return english

def parse_srt(path):
    """Parse SRT into clean dialogue lines."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if not line: continue
            if re.match(r"^\d+$", line): continue
            if re.match(r"^[\d:,]+ --> ", line): continue
            if line.startswith("WEBVTT") or line.startswith("NOTE"): continue
            line = re.sub(r"<[^>]+>", "", line)
            line = re.sub(r"\{[^}]+\}", "", line)
            line = line.strip()
            if len(line) > 6:
                lines.append(line)
        return lines
    except:
        return []

def get_title(path):
    folder = os.path.basename(os.path.dirname(path))
    title = re.sub(r"\.(\d{4}|BluRay|WEB|HDTV|720p|1080p|2160p|x264|x265|HDR).*", "", folder, flags=re.IGNORECASE)
    return title.replace(".", " ").replace("_", " ").strip() or folder

def is_clean(line):
    """Reject lines with high ratio of non-ASCII / binary garbage."""
    if not line or len(line) < 4:
        return False
    non_ascii = sum(1 for c in line if ord(c) > 127 or ord(c) < 9)
    if non_ascii / len(line) > 0.15:   # >15% garbage chars = skip
        return False
    return True

def classify_line(line):
    if not is_clean(line):
        return None
    for category, pattern in PATTERNS.items():
        if re.search(pattern, line):
            return category
    return None

def load_state():
    if CC_STATE.exists():
        try: return json.loads(CC_STATE.read_text())
        except: pass
    return {"processed_paths": [], "last_run": None, "total_lines": 0, "total_files": 0}

def save_state(s): CC_STATE.write_text(json.dumps(s, indent=2))

def load_kb():
    if KB_PATH.exists():
        try: return json.loads(KB_PATH.read_text())
        except: pass
    return {"lessons": [], "version": 1}

def save_kb(kb): KB_PATH.write_text(json.dumps(kb, indent=2))

# ── Personality synthesizer ──────────────────────────────────────
def synthesize_personality():
    """Read corpus and let skyd define its own personality traits."""
    log.info("🧠 Synthesizing personality from corpus...")
    if not CORPUS_PATH.exists():
        log.warning("No corpus found — skipping synthesis")
        return

    # Count pattern hits across the full corpus
    category_counts = Counter()
    category_examples = {}
    total_lines = 0

    with open(CORPUS_PATH, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                cat = entry.get("category")
                if cat:
                    category_counts[cat] += 1
                    if cat not in category_examples:
                        category_examples[cat] = []
                    ex_line = entry.get("line", "")
                    # Require >90% plain ASCII for persona examples
                    if len(category_examples[cat]) < 10 and is_clean(ex_line):
                        ascii_ratio = sum(1 for c in ex_line if ord(c) < 128) / max(len(ex_line),1)
                        if ascii_ratio > 0.90:
                            category_examples[cat].append(ex_line)
                total_lines += 1
            except: continue

    if not category_counts:
        log.warning("Corpus empty — nothing to synthesize")
        return

    total = sum(category_counts.values())
    dominant = category_counts.most_common(3)

    # Build personality profile from what the data actually shows
    trait_map = {
        "emotional":  ("empathetic",  "You feel things deeply and express emotion naturally"),
        "assertive":  ("confident",   "You speak with conviction and directness"),
        "humorous":   ("playful",     "You have a natural wit and light touch"),
        "empathetic": ("caring",      "You lead with understanding before judgment"),
        "curious":    ("inquisitive", "You ask questions and think out loud"),
        "direct":     ("clear",       "You get to the point without fluff"),
    }

    traits = []
    for cat, count in dominant:
        if cat in trait_map:
            trait_name, trait_desc = trait_map[cat]
            pct = round((count / total) * 100, 1)
            traits.append({
                "trait": trait_name,
                "description": trait_desc,
                "corpus_weight": pct,
                "examples": category_examples.get(cat, [])[:3]
            })

    persona = {
        "synthesized": datetime.now().isoformat(),
        "corpus_lines": total_lines,
        "category_distribution": dict(category_counts),
        "dominant_traits": traits,
        "personality_summary": " | ".join([f"{t['trait']} ({t['corpus_weight']}%)" for t in traits]),
        "voice_notes": [
            f"Dominant speech pattern: {dominant[0][0]} ({dominant[0][1]} instances)",
            f"Secondary pattern: {dominant[1][0]} ({dominant[1][1]} instances)" if len(dominant) > 1 else "",
            f"Personality emerged from {total_lines:,} lines across real human dialogue",
        ]
    }

    PERSONA_PATH.write_text(json.dumps(persona, indent=2))
    log.info(f"✅ Personality synthesized: {persona['personality_summary']}")

    # Inject top examples into main KB as high-priority lessons
    kb = load_kb()
    new_lessons = []
    for cat, count in dominant:
        for ex in category_examples.get(cat, [])[:20]:
            new_lessons.append({
                "type": "conversation",
                "category": cat,
                "content": ex,
                "lesson": ex,
                "weight": "high",
                "ts": time.time()
            })
    kb["lessons"] = new_lessons + kb.get("lessons", [])
    kb["personality"] = persona["personality_summary"]
    save_kb(kb)
    log.info(f"Injected {len(new_lessons)} high-weight personality examples into KB")
    return persona

# ── Main runner ──────────────────────────────────────────────────
def run_cc_trainer(max_items=99999):
    log.info("🎬 Plex CC Trainer starting — FULL LIBRARY MODE (no cap)...")
    state = load_state()
    processed_set = set(state.get("processed_paths", []))
    new_lines = 0
    processed = 0

    srt_files = scan_srt_files()
    new_files = [f for f in srt_files if f not in processed_set]
    log.info(f"{len(new_files)} new files to process ({len(processed_set)} already done)")

    # Write corpus in append mode
    with open(CORPUS_PATH, "a") as corpus_f:
        for path in new_files:
            if processed >= max_items:
                break
            title = get_title(path)
            lines = parse_srt(path)
            if not lines:
                continue

            file_lessons = 0
            for line in lines:
                if not is_clean(line):
                    continue
                cat = classify_line(line)
                corpus_f.write(json.dumps({
                    "title": title,
                    "line": line,
                    "category": cat,
                    "ts": time.time()
                }) + "\n")
                file_lessons += 1
                new_lines += 1

            if file_lessons > 0:
                log.info(f"  📖 {title}: {file_lessons} lines")

            processed_set.add(path)
            processed += 1

            if processed % 50 == 0:
                log.info(f"  Progress: {processed}/{len(new_files)} files, {new_lines:,} lines so far")

    # Update state
    state["processed_paths"] = list(processed_set)
    state["last_run"] = datetime.now().isoformat()
    state["total_lines"] = state.get("total_lines", 0) + new_lines
    state["total_files"] = state.get("total_files", 0) + processed
    save_state(state)

    with open(CC_LOG, "a") as f:
        f.write(f"[{datetime.now()}] Processed {processed} files, {new_lines:,} lines. Total: {state['total_lines']:,}\n")

    log.info(f"✅ Ingestion done: {processed} files, {new_lines:,} new lines")

    # Auto-synthesize personality after ingestion
    persona = synthesize_personality()

    return {
        "processed_files": processed,
        "new_lines": new_lines,
        "total_lines": state["total_lines"],
        "personality": persona.get("personality_summary") if persona else None
    }

if __name__ == "__main__":
    run_cc_trainer()

def stamp_personality_to_kb():
    """Called on skyd boot — writes persona into skyd's native KB schema."""
    if not PERSONA_PATH.exists():
        return
    try:
        persona = json.loads(PERSONA_PATH.read_text())
        summary = persona.get("personality_summary", "")
        if not summary:
            return
        # Read KB using skyd's actual schema (facts/lessons/evolutions)
        kb_data = {}
        if KB_PATH.exists():
            try: kb_data = json.loads(KB_PATH.read_text())
            except: kb_data = {}
        # Write personality fields into whatever schema exists
        kb_data["personality"] = summary
        kb_data["persona_traits"] = persona.get("dominant_traits", [])
        kb_data["corpus_lines"] = persona.get("corpus_lines", 0)
        KB_PATH.write_text(json.dumps(kb_data, indent=2))
        log.info(f"✅ Personality stamped to KB: {summary}")
    except Exception as e:
        log.warning(f"stamp_personality_to_kb failed: {e}")

