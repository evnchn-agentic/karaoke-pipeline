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
# "作曲 : X" / "词：X" / "Mixed By : X": a short label naming a credit role, then a colon
CREDIT = re.compile(
    r"\s*([作填原]?[词詞曲]|[词詞]曲|[编編]曲|(制作|製作|监制|監製)人?|"
    r"(混音|录音|錄音|音频|音頻|母带|母帶)(工程师|工程師|师|師)?|和[声聲]([编編]写|[编編]寫)?|"
    r"lyrics?( by)?|lyricist|composer|composed by|music( by)?|arranger|arranged by|"
    r"producers?|produced by|(mix|mixed|mixing|master|mastered|mastering)( by| engineer)?|"
    r"(recording )?engineer|written by)\s*[:：]\s*\S", re.I)


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
    for line in open(src, encoding="utf-8-sig"):
        stamps = TS.findall(line)
        if not stamps or META.match(line):
            continue
        text = TS.sub("", line).strip()
        # keep timing lines even if text is empty (they bound the previous line)
        for mm, ss in stamps:
            events.append((int(mm) * 60 + float(ss) + offset, text))
    events.sort(key=lambda e: e[0])

    # Some sources (e.g. NetEase) open and close a song with credit lines such as
    # "作词 : X" on placeholder timestamps; they are not sung. Blank them but keep
    # their timestamps as line boundaries.
    for i, (t, text) in enumerate(events):
        if CREDIT.match(text):
            print(f"skipped credit line: {text}", file=sys.stderr)
            events[i] = (t, "")

    # Bilingual LRCs stamp each translation with the time of the line it translates, and
    # credits often share the first lyric's time. Two cues at one time give the first a
    # zero-length span, so keep one line per time: the first non-empty one.
    merged = []
    for t, text in events:
        if merged and merged[-1][0] == t:
            if not merged[-1][1]:
                merged[-1] = (t, text)
            elif text:
                print(f"dropped same-time line: {text}", file=sys.stderr)
            continue
        merged.append((t, text))
    events = merged

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
