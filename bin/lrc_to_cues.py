#!/usr/bin/env python3
"""Parse a standard .lrc (web synced lyrics) into the {start,end,text} cue format
that cues_to_ass.py renders. Line-level timestamps become karaoke line spans; each
line's end is the next line's start. Metadata tags ([ar:],[ti:],...) are skipped.

Usage: lrc_to_cues.py in.lrc out.json
"""
import json
import re
import sys

TS = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
META = re.compile(r"^\[[a-zA-Z]+:")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="constant shift in seconds added to every timestamp "
                         "(fixes a source LRC that runs early/late; e.g. -0.3)")
    a = ap.parse_args()
    src, dst, offset = a.src, a.dst, a.offset
    events = []  # (time, text)
    for line in open(src, encoding="utf-8"):
        stamps = TS.findall(line)
        if not stamps or META.match(line):
            continue
        text = TS.sub("", line).strip()
        # keep timing lines even if text is empty (they bound the previous line)
        for mm, ss in stamps:
            events.append((int(mm) * 60 + float(ss) + offset, text))
    events.sort(key=lambda e: e[0])

    cues = []
    for i, (t, text) in enumerate(events):
        if not text:
            continue
        end = events[i + 1][0] if i + 1 < len(events) else t + 4.0
        if end <= t:
            end = t + 1.0
        cues.append({"start": round(t, 3), "end": round(end, 3), "text": text})

    json.dump(cues, open(dst, "w"), ensure_ascii=False, indent=1)
    print(f"{len(cues)} cues -> {dst}", file=sys.stderr)


if __name__ == "__main__":
    main()
