#!/usr/bin/env python3
"""Render line-level cues (OCR'd hard-subs) into a karaoke .ass.

OCR gives line text + start/end but no per-word timing, so the \\kf fill-sweep is
distributed evenly across the characters of each line — which reads naturally for
sung Chinese. Input JSON: [{start, end, text}, ...].

Usage: cues_to_ass.py <cues.json> <out.ass> [--playres 1920x1080] [--fontsize 60]
"""
import argparse
import json
import sys


def ass_time(s: float) -> str:
    s = max(0.0, s)
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h:d}:{m:02d}:{sec:05.2f}"


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KAR,PingFang SC,{fs},&H0066FF66,&H00F5F5F5,&H00202020,&H90000000,-1,0,0,0,100,100,0,0,1,4,1.5,2,90,90,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def kfline(text: str, dur_cs: int) -> str:
    n = sum(1 for c in text if c != " ")
    if not n:
        return text
    base = dur_cs // n
    rem = dur_cs - base * n
    out = []
    k = 0
    for c in text:
        if c == " ":
            out.append(" ")
            continue
        d = base + (1 if k < rem else 0)
        out.append(f"{{\\kf{max(1, d)}}}{c}")
        k += 1
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cues_json")
    ap.add_argument("ass_out")
    ap.add_argument("--playres", default="1920x1080")
    ap.add_argument("--fontsize", type=int, default=60)
    args = ap.parse_args()
    w, h = (int(x) for x in args.playres.lower().split("x"))
    cues = json.load(open(args.cues_json))

    with open(args.ass_out, "w") as f:
        f.write(HEADER.format(w=w, h=h, fs=args.fontsize))
        for i, c in enumerate(cues):
            start, end = float(c["start"]), float(c["end"])
            nxt = float(cues[i + 1]["start"]) if i + 1 < len(cues) else None
            if nxt is not None:
                end = min(end, nxt)
            if end <= start:
                end = start + 0.4
            dur_cs = max(1, round((end - start) * 100))
            f.write(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},KAR,,0,0,0,,{kfline(c['text'], dur_cs)}\n")
    print(f"wrote {len(cues)} cues -> {args.ass_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
