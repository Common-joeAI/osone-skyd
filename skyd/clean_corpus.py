#!/usr/bin/env python3
"""Re-filter corpus to remove non-ASCII garbage lines."""
import json, pathlib, os

src = pathlib.Path("/var/log/skyd_corpus.jsonl")
tmp = pathlib.Path("/var/log/skyd_corpus_clean.jsonl")

kept = 0; dropped = 0
with open(src) as fin, open(tmp, "w") as fout:
    for raw in fin:
        try:
            entry = json.loads(raw)
            line = entry.get("line", "")
            if not line: continue
            ascii_ratio = sum(1 for c in line if ord(c) < 128) / max(len(line), 1)
            if ascii_ratio > 0.90:
                fout.write(raw); kept += 1
            else:
                dropped += 1
        except: continue

os.rename(tmp, src)
print(f"Corpus cleaned: kept {kept:,}, dropped {dropped:,} garbage lines")
