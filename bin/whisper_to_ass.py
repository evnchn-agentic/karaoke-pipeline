#!/usr/bin/env python3
"""Convert an openai-whisper word-timestamp JSON into a karaoke .ass subtitle.

Each whisper segment becomes one centered karaoke line. Every word gets a
`{\\kf<cs>}` fill-sweep tag so libass wipes the highlight left-to-right in sync
with the singing; inter-word gaps get their own sweep token so the fill "waits"
through pauses instead of racing ahead.

ASS colours are &HAABBGGRR. Sung text fills to PrimaryColour; not-yet-sung text
sits in SecondaryColour.

Usage: whisper_to_ass.py in.json out.ass [--playres 1280x720] [--fontsize 54]
"""
import argparse
import json
import sys


def cs(seconds: float) -> int:
    """Seconds -> centiseconds, clamped non-negative (ASS \\k unit)."""
    return max(0, round(seconds * 100))


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KAR,Arial,{fs},&H0066FF66,&H00E8E8E8,&H00202020,&H90000000,-1,0,0,0,100,100,0,0,1,3.5,1,5,80,80,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_line(seg, next_start):
    words = [w for w in seg.get("words", []) if w.get("word", "").strip()]
    if not words:
        return None
    start = float(words[0]["start"])
    last_end = float(words[-1]["end"])
    # Let the line linger briefly, but never bleed into the next line.
    end = last_end + 0.6
    if next_start is not None:
        end = min(end, float(next_start))
    if end <= start:
        end = start + 0.4

    tokens = []
    for i, w in enumerate(words):
        w_start = float(w["start"])
        w_end = float(w["end"])
        text = w["word"].strip()
        dur = cs(w_end - w_start)
        if dur <= 0:
            dur = 1
        tokens.append(f"{{\\kf{dur}}}{text}")
        # Gap sweep on the joining space, so the wipe pauses through silence.
        if i + 1 < len(words):
            gap = cs(float(words[i + 1]["start"]) - w_end)
            if gap > 0:
                tokens.append(f"{{\\kf{gap}}} ")
            else:
                tokens.append(" ")
    return start, end, "".join(tokens)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_in")
    ap.add_argument("ass_out")
    ap.add_argument("--playres", default="1280x720")
    ap.add_argument("--fontsize", type=int, default=54)
    args = ap.parse_args()

    w, h = (int(x) for x in args.playres.lower().split("x"))
    with open(args.json_in) as f:
        data = json.load(f)

    segs = [s for s in data.get("segments", []) if s.get("words")]
    lines = []
    for idx, seg in enumerate(segs):
        next_start = segs[idx + 1]["words"][0]["start"] if idx + 1 < len(segs) else None
        built = build_line(seg, next_start)
        if built:
            lines.append(built)

    with open(args.ass_out, "w") as f:
        f.write(HEADER.format(w=w, h=h, fs=args.fontsize))
        for start, end, text in lines:
            f.write(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},KAR,,0,0,0,,{text}\n")

    print(f"wrote {len(lines)} karaoke lines -> {args.ass_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
