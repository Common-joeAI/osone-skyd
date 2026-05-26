#!/usr/bin/env python3
"""
media_personality.py — skyd Media Personality Trainer
Scans the media library for subtitle files (.srt, .ass, .vtt)
Extracts dialogue patterns, emotional cues, conversational nuances
Distills them into personality lessons that skyd loads into its knowledge base

Categories it learns:
- Emotional responses (joy, anger, sadness, fear, surprise)
- Conversation starters / enders
- Humor patterns
- Empathy phrases
- Conflict de-escalation
- Casual / informal speech patterns
- Storytelling cadence
"""

import os, re, json, random, logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

MEDIA_PATHS  = ["/mnt/user/Data/Movies", "/mnt/user/Data/tvshows"]
KB_PATH      = Path("/var/log/skyd_knowledge.json")
PERSONALITY_LOG = Path("/var/log/skyd_personality.jsonl")
LESSON_BATCH = 25   # lessons to add per run
MAX_FILES    = 150  # subtitle files to scan per run (keeps it fast)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PERSONALITY] %(message)s")
log = logging.getLogger("personality")

# Emotional pattern signatures
EMOTION_PATTERNS = {
    "joy":       [r"\b(haha|lol|amazing|wonderful|love|great|fantastic|awesome|yay|brilliant)\b"],
    "anger":     [r"\b(damn|hell|angry|furious|hate|ridiculous|unbelievable|outrageous)\b"],
    "sadness":   [r"\b(sorry|miss|lost|gone|hurt|cry|tears|goodbye|wish|regret)\b"],
    "fear":      [r"\b(scared|afraid|terrified|help|run|danger|threat|worry|nervous)\b"],
    "surprise":  [r"\b(wow|really|seriously|no way|what|unbelievable|incredible|oh my)\b"],
    "empathy":   [r"\b(understand|feel|know how|must be|that's tough|I'm here|together)\b"],
    "humor":     [r"\b(funny|joke|laugh|hilarious|seriously though|kidding|ironic)\b"],
    "wisdom":    [r"\b(remember|truth|always|never|life|matter|important|realize|lesson)\b"],
}

SRT_CLEAN = re.compile(r'<[^>]+>|\{[^}]+\}|\d+:\d+:\d+[,\.]\d+\s*-->\s*\d+:\d+:\d+[,\.]\d+|\d+\n')

def find_subtitle_files(limit=MAX_FILES):
    subs = []
    for root in MEDIA_PATHS:
        if not os.path.exists(root):
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.endswith(('.srt', '.ass', '.vtt', '.sub')):
                    subs.append(os.path.join(dirpath, f))
            if len(subs) >= limit * 3:
                break
    random.shuffle(subs)
    return subs[:limit]

def parse_srt(filepath):
    """Extract clean dialogue lines from subtitle file"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()
        # Remove timing lines and tags
        lines = SRT_CLEAN.sub('', raw).split('\n')
        dialogue = []
        for line in lines:
            line = line.strip()
            if len(line) > 8 and len(line) < 200 and not line.isdigit():
                # Skip non-dialogue
                if not re.match(r'^[\d\s:,\.\-\>]+$', line):
                    dialogue.append(line)
        return dialogue
    except Exception as e:
        return []

def detect_emotion(line):
    line_lower = line.lower()
    for emotion, patterns in EMOTION_PATTERNS.items():
        for p in patterns:
            if re.search(p, line_lower):
                return emotion
    return None

def extract_conversational_patterns(lines):
    """Find interesting conversational patterns"""
    patterns = defaultdict(list)
    
    for i, line in enumerate(lines):
        # Conversation starters
        if i == 0 or (i > 0 and len(lines[i-1]) < 5):
            if len(line) > 15:
                patterns["opener"].append(line)
        
        # Questions
        if line.strip().endswith('?') and len(line) > 10:
            patterns["question"].append(line)
        
        # Emotional lines
        emotion = detect_emotion(line)
        if emotion:
            patterns[emotion].append(line)
        
        # Short punchy responses (likely snappy dialogue)
        if 5 < len(line) < 40 and i > 0:
            patterns["snappy"].append(line)
        
        # Long reflective lines (monologue/wisdom)
        if len(line) > 80:
            patterns["reflective"].append(line)

    return patterns

def distill_lessons(all_patterns, source_name):
    """Convert extracted patterns into skyd knowledge lessons"""
    lessons = []
    
    for category, lines in all_patterns.items():
        if not lines:
            continue
        sample = random.sample(lines, min(3, len(lines)))
        
        if category == "opener":
            lessons.append({
                "type": "conversation",
                "subtype": "opener",
                "content": f"Humans often open conversations with: {' | '.join(sample[:2])}",
                "source": source_name,
                "ts": datetime.now().isoformat()
            })
        elif category == "question":
            lessons.append({
                "type": "conversation",
                "subtype": "question_pattern",
                "content": f"Natural question phrasing: {' | '.join(sample[:2])}",
                "source": source_name,
                "ts": datetime.now().isoformat()
            })
        elif category in EMOTION_PATTERNS:
            lessons.append({
                "type": "emotion",
                "subtype": category,
                "content": f"When expressing {category}, humans say things like: {' | '.join(sample[:2])}",
                "source": source_name,
                "ts": datetime.now().isoformat()
            })
        elif category == "snappy":
            lessons.append({
                "type": "conversation",
                "subtype": "snappy_response",
                "content": f"Short, punchy human responses: {' | '.join(sample[:3])}",
                "source": source_name,
                "ts": datetime.now().isoformat()
            })
        elif category == "reflective":
            lessons.append({
                "type": "wisdom",
                "subtype": "reflective_statement",
                "content": f"Reflective human thought: {sample[0]}",
                "source": source_name,
                "ts": datetime.now().isoformat()
            })
    return lessons

def load_kb():
    try:
        return json.loads(KB_PATH.read_text())
    except:
        return {"lessons": []}

def save_kb(kb):
    KB_PATH.write_text(json.dumps(kb, indent=2))

def run_personality_trainer():
    log.info("=== Media Personality Trainer starting ===")
    
    subtitle_files = find_subtitle_files()
    log.info(f"Found {len(subtitle_files)} subtitle files to scan")
    
    if not subtitle_files:
        log.warning("No subtitle files found — media personality training skipped")
        log.info("Tip: Many media files don't have external .srt files. Consider running subliminal to auto-download subtitles.")
        # Still write a stub lesson so skyd knows this module ran
        kb = load_kb()
        kb["lessons"].append({
            "type": "meta",
            "subtype": "personality_scan",
            "content": "Media personality scan ran but found no subtitle files. Library uses embedded subtitles.",
            "ts": datetime.now().isoformat()
        })
        save_kb(kb)
        return {"subtitle_files_scanned": 0, "lessons_added": 0}

    all_patterns = defaultdict(list)
    files_processed = 0
    
    for fpath in subtitle_files:
        lines = parse_srt(fpath)
        if len(lines) < 10:
            continue
        fname = Path(fpath).stem
        patterns = extract_conversational_patterns(lines)
        for k, v in patterns.items():
            all_patterns[k].extend(v[:5])  # cap per file
        files_processed += 1
        if files_processed % 20 == 0:
            log.info(f"  Processed {files_processed}/{len(subtitle_files)} files...")

    log.info(f"Processed {files_processed} files. Distilling lessons...")
    
    # Distill into lessons
    lessons = distill_lessons(all_patterns, f"media_scan_{datetime.now().strftime('%Y%m%d')}")
    
    # Sample down to LESSON_BATCH
    if len(lessons) > LESSON_BATCH:
        lessons = random.sample(lessons, LESSON_BATCH)

    # Load KB and append
    kb = load_kb()
    kb["lessons"].extend(lessons)
    # Keep KB to 500 lessons max
    if len(kb["lessons"]) > 500:
        kb["lessons"] = kb["lessons"][-500:]
    save_kb(kb)

    # Write personality log
    with open(PERSONALITY_LOG, "a") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "files_scanned": files_processed,
            "lessons_added": len(lessons),
            "categories": {k: len(v) for k, v in all_patterns.items()}
        }) + "\n")

    log.info(f"✅ Personality training complete: {len(lessons)} lessons added from {files_processed} subtitle files")
    log.info(f"   Categories: {dict((k, len(v)) for k,v in all_patterns.items())}")
    return {"subtitle_files_scanned": files_processed, "lessons_added": len(lessons)}

if __name__ == "__main__":
    run_personality_trainer()
