#!/usr/bin/env python3
"""Whisper vocals.json -> {start,end,text} cues (one per segment) for the scroll
renderer, so Whisper-fallback tracks share the same multi-line karaoke view.

Usage: whisper_to_cues.py vocals.json out.json
"""
import json
import sys

d = json.load(open(sys.argv[1]))
cues = []
for seg in d.get("segments", []):
    t = (seg.get("text") or "").strip()
    if t:
        cues.append({"start": float(seg["start"]), "end": float(seg["end"]), "text": t})
json.dump(cues, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
print(f"{len(cues)} cues -> {sys.argv[2]}", file=sys.stderr)
