#!/usr/bin/env python3
"""Benchmark Whisper transcription against OCR'd hard-subs (ground truth).

Ground truth = OCR cues (text + timing). For each cue we gather the Whisper text whose
word/segment timing overlaps the cue window, then measure a Trad/Simp-normalized
character error rate (CER) per line and overall, plus the line-start timing offset.

Usage: bench.py <whisper_vocals.json> <ocr_cues.json> [--out report.json]
"""
import argparse
import json
import re
import sys

try:
    from opencc import OpenCC
    _t2s = OpenCC("t2s").convert
except Exception:  # pragma: no cover
    _t2s = lambda s: s

_CJK = re.compile(r"[㐀-鿿]")


def canon(s: str) -> str:
    """Trad->Simp, keep CJK + ascii-alnum only (drop punctuation/space)."""
    s = _t2s(s)
    return "".join(ch.lower() for ch in s if _CJK.match(ch) or ch.isalnum())


def lev(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    r = canon(ref)
    if not r:
        return 0.0 if not canon(hyp) else 1.0
    return lev(r, canon(hyp)) / len(r)


def whisper_words(seg_json):
    """Flatten whisper segments -> [(start, end, text)] at word granularity if present."""
    words = []
    for seg in seg_json.get("segments", []):
        if seg.get("words"):
            for w in seg["words"]:
                if w.get("word", "").strip():
                    words.append((float(w["start"]), float(w["end"]), w["word"]))
        else:
            words.append((float(seg["start"]), float(seg["end"]), seg.get("text", "")))
    return words


def whisper_text_in(window, words):
    s, e = window
    return "".join(t for (ws, we, t) in words if we > s and ws < e)


def whisper_start_in(window, words):
    s, e = window
    hits = [ws for (ws, we, t) in words if we > s and ws < e]
    return min(hits) if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("whisper_json")
    ap.add_argument("ocr_json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    wj = json.load(open(args.whisper_json))
    cues = json.load(open(args.ocr_json))
    words = whisper_words(wj)

    rows, offsets = [], []
    tot_ref = tot_err = 0
    for c in cues:
        win = (c["start"], c["end"])
        hyp = whisper_text_in(win, words)
        r = canon(c["text"])
        errs = lev(r, canon(hyp))
        tot_ref += len(r); tot_err += errs
        ws = whisper_start_in(win, words)
        off = None if ws is None else round(ws - c["start"], 2)
        if off is not None:
            offsets.append(off)
        rows.append({
            "start": c["start"], "ref_len": len(r),
            "cer": round(errs / len(r), 3) if r else None,
            "timing_offset_s": off,
        })

    # Overall doc-level CER on the full concatenation too (order-sensitive).
    gt_all = "".join(c["text"] for c in cues)
    wh_all = "".join(t for (_, _, t) in words)
    micro_cer = round(tot_err / tot_ref, 3) if tot_ref else None
    doc_cer = round(cer(gt_all, wh_all), 3)
    matched = [r for r in rows if r["cer"] is not None]
    covered = sum(1 for r in rows if r["timing_offset_s"] is not None)
    med_off = sorted(offsets)[len(offsets) // 2] if offsets else None
    mean_line_cer = round(sum(r["cer"] for r in matched) / len(matched), 3) if matched else None

    report = {
        "ocr_cues": len(cues),
        "whisper_words": len(words),
        "cue_coverage_by_whisper": f"{covered}/{len(cues)}",
        "micro_cer_char_weighted": micro_cer,
        "mean_line_cer": mean_line_cer,
        "doc_level_cer": doc_cer,
        "median_timing_offset_s": med_off,
        "rows": rows,
    }
    print(json.dumps({k: v for k, v in report.items() if k != "rows"},
                     ensure_ascii=False, indent=2))
    if args.out:
        json.dump(report, open(args.out, "w"), ensure_ascii=False, indent=1)
        print(f"\nfull per-line report -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
