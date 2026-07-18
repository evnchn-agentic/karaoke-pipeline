#!/usr/bin/env python3
"""Extract burned-in (hard) subtitles from a video into timed cues via Apple Vision OCR.

Samples the subtitle band at N fps, OCRs each frame (ocrmac -> VNRecognizeTextRequest),
then collapses runs of similar text into cues. Per-cue text is the majority vote across
its frames, which denoises OCR jitter. Output: JSON list of {start, end, text}.

Usage: ocr_hardsubs.py <video> <out.json> [--fps 4] [--y0 0.84 --bh 0.13]
                       [--langs zh-Hant,en] [--min-dur 0.3] [--sim 0.72]
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from difflib import SequenceMatcher

from ocrmac import ocrmac

FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def norm(s: str) -> str:
    return "".join(s.split())


def ocr_frame(png: str, langs) -> str:
    """Return the subtitle-band text: Vision detections joined top->bottom, left->right."""
    res = ocrmac.OCR(png, language_preference=langs, recognition_level="accurate").recognize()
    # res: list of (text, confidence, bbox[x,y,w,h]); y is bottom-origin normalized.
    good = [(t, box) for (t, conf, box) in res if conf and conf > 0.3 and t.strip()]
    if not good:
        return ""
    # Reading order: higher y first (top), then left->right.
    good.sort(key=lambda tb: (-round(tb[1][1], 2), tb[1][0]))
    return " ".join(t.strip() for t, _ in good)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_json")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--y0", type=float, default=0.84, help="band top as fraction of height")
    ap.add_argument("--bh", type=float, default=0.13, help="band height as fraction")
    ap.add_argument("--langs", default="zh-Hant,en-US")
    ap.add_argument("--min-dur", type=float, default=0.3)
    ap.add_argument("--sim", type=float, default=0.72, help="similarity to merge into one cue")
    args = ap.parse_args()
    langs = args.langs.split(",")

    with tempfile.TemporaryDirectory() as td:
        crop = f"crop=iw:ih*{args.bh}:0:ih*{args.y0}"
        vf = f"fps={args.fps},{crop}"
        subprocess.run(
            [FFMPEG, "-y", "-i", args.video, "-vf", vf, "-q:v", "2",
             os.path.join(td, "f_%05d.png"), "-loglevel", "error"],
            check=True,
        )
        frames = sorted(glob.glob(os.path.join(td, "f_*.png")))
        print(f"OCR over {len(frames)} frames @ {args.fps}fps ...", file=sys.stderr)

        texts = []  # (time, text)
        for i, png in enumerate(frames):
            t = i / args.fps
            txt = ocr_frame(png, langs)
            texts.append((t, txt))
            if i % 50 == 0:
                print(f"  {i}/{len(frames)}", file=sys.stderr)

    # Collapse consecutive similar/equal text into cues; blank breaks a cue.
    cues = []
    cur = None  # {start, last_t, members:[str]}
    dt = 1.0 / args.fps
    for t, txt in texts:
        n = norm(txt)
        if not n:
            if cur:
                cues.append(cur); cur = None
            continue
        if cur and SequenceMatcher(None, norm(cur["members"][-1]), n).ratio() >= args.sim:
            cur["members"].append(txt); cur["last_t"] = t
        else:
            if cur:
                cues.append(cur)
            cur = {"start": t, "last_t": t, "members": [txt]}
    if cur:
        cues.append(cur)

    out = []
    for c in cues:
        end = c["last_t"] + dt
        if end - c["start"] < args.min_dur:
            continue
        text = Counter(c["members"]).most_common(1)[0][0]  # majority vote
        out.append({"start": round(c["start"], 3), "end": round(end, 3), "text": text})

    with open(args.out_json, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(out)} cues -> {args.out_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
