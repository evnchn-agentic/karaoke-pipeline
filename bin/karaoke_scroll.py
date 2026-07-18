#!/usr/bin/env python3
"""Scrolling multi-line karaoke .ass from {start,end,text} cues.

The active line sits in the vertical centre; past lines stack above (dim), future
lines below (dim). At each line change the whole stack glides up exactly one slot
via ASS \\move (smooth, no row-jump). The active line carries a \\kf fill sweep
whose total duration is CAPPED to a singing pace — so when an instrumental
interlude makes a line's on-screen window long, the sweep completes at a natural
speed and then holds fully-sung, instead of dragging across the interlude.

Usage: karaoke_scroll.py cues.json out.ass [--res 1280x720] [--fontsize 44]
                        [--slots 2] [--per-char-cs 55]
"""
import argparse
import json
import statistics
import sys


def ass_time(s: float) -> str:
    s = max(0.0, s)
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h:d}:{m:02d}:{sec:05.2f}"


def kf_capped(text: str, window_s: float, per_char_cs: int, floor_cs: int) -> str:
    """Distribute a \\kf sweep across chars, total capped so interludes don't drag."""
    chars = [c for c in text if c != " "]
    n = len(chars)
    if n == 0:
        return text
    window_cs = int(round(window_s * 100))
    cap = max(floor_cs, n * per_char_cs)
    total = min(window_cs, cap) if window_cs > 0 else cap
    base, rem = divmod(total, n)
    out, k = [], 0
    for c in text:
        if c == " ":
            out.append(" "); continue
        d = base + (1 if k < rem else 0)
        out.append(f"{{\\kf{max(1, d)}}}{c}")
        k += 1
    return "".join(out)


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KARS,PingFang SC,{fs},&H0066FF66,&H00F5F5F5,&H00202020,&H90000000,-1,0,0,0,100,100,0,0,1,3.5,1.2,5,60,60,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def context_style(d):
    """Appearance of a context (non-active) line `d` slots from the active one.
    Dimmer + more transparent with distance — works for any --slots, not just 1/2.
    Returns (alpha, greyscale-colour) as ASS &H..& literals."""
    d = max(1, abs(d))
    alpha = min(0xD5, 0x35 + (d - 1) * 0x50)   # 1→0x35, 2→0x85, 3→0xD5(cap)
    g = max(0x70, 0xD0 - (d - 1) * 0x20)        # 1→D0, 2→B0, 3→90, floor 70
    return f"&H{alpha:02X}&", f"&H{g:02X}{g:02X}{g:02X}&"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cues_json")
    ap.add_argument("ass_out")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--fontsize", type=int, default=44)
    ap.add_argument("--slots", type=int, default=2, help="past/future lines shown each side")
    ap.add_argument("--per-char-cs", type=int, default=55)
    args = ap.parse_args()

    W, H = (int(x) for x in args.res.lower().split("x"))
    cx, cy = W // 2, int(H * 0.5)
    spacing = int(args.fontsize * 1.5)
    cues = json.load(open(args.cues_json))
    n = len(cues)
    if not n:
        open(args.ass_out, "w").write(HEADER.format(w=W, h=H, fs=args.fontsize))
        return

    starts = [float(c["start"]) for c in cues]
    # sing window = the real singing span (drives the \kf sweep + glide speed); clamped so
    # adjacent lines never overlap.
    sing_ends = []
    for i, c in enumerate(cues):
        e = float(c["end"])
        if i + 1 < n:
            e = min(e, starts[i + 1])
        sing_ends.append(e if e > starts[i] else starts[i] + 1.0)
    windows = [sing_ends[i] - starts[i] for i in range(n)]
    # display window = shown until the NEXT line begins, so a line holds fully-sung through
    # interludes instead of vanishing. The LAST line holds far past any plausible video end
    # (libass ignores events beyond EOF) — covers the outro regardless of stem-length padding,
    # with no need to know the song duration. No inter-segment / outro blank.
    disp_ends = [starts[i + 1] if i + 1 < n else sing_ends[-1] + 3600.0 for i in range(n)]
    med = statistics.median(windows) if windows else 2.0
    floor_cs = max(120, int(med * 70))  # min sweep length

    S = args.slots
    lines_out = []

    def ctx_body(off, text, extra=""):  # dim context (non-active) line at slot `off`
        alpha, col = context_style(off)
        text = text.replace("{", "").replace("}", "")
        return "{" + extra + f"\\1c{col}\\alpha{alpha}" + "}" + text

    # INTRO pre-roll: fill [0, first line] with the opening stack so the screen is never blank
    # before singing. The upcoming active line shows unsung (secondary colour, no sweep yet).
    if starts[0] > 0.3:
        for off in range(0, S + 1):
            L = off
            if L >= n:
                continue
            y = cy + off * spacing
            pos = f"\\an5\\pos({cx},{y})"
            if off == 0:
                text = cues[L]["text"].replace("{", "").replace("}", "")
                body = "{" + pos + "\\1c&HF5F5F5&\\alpha&H10&}" + text  # about-to-sing, unswept
            else:
                body = ctx_body(off, cues[L]["text"], pos)
            lines_out.append(
                f"Dialogue: 0,{ass_time(0.0)},{ass_time(starts[0])},KARS,,0,0,0,,{body}")

    for w in range(n):
        t0, t1 = starts[w], disp_ends[w]  # displayed until the NEXT line begins (holds over gaps)
        # scroll-in duration: quick glide at the start of the window (paced by real singing span)
        dur_ms = int(min(450, max(160, windows[w] * 1000 * 0.5)))
        for off in range(-S, S + 1):
            L = w + off
            if L < 0 or L >= n:
                continue
            y_curr = cy + off * spacing
            y_prev = cy + (off + 1) * spacing  # was one slot lower in the prior window
            # w==0 has no prior window (the intro pre-roll placed it statically) -> no glide
            mv = (f"\\an5\\pos({cx},{y_curr})" if w == 0
                  else f"\\an5\\move({cx},{y_prev},{cx},{y_curr},0,{dur_ms})")
            if off == 0:
                body = "{" + mv + "}" + kf_capped(cues[L]["text"], windows[w],
                                                  args.per_char_cs, floor_cs)
            else:
                body = ctx_body(off, cues[L]["text"], mv)
            lines_out.append(
                f"Dialogue: 0,{ass_time(t0)},{ass_time(t1)},KARS,,0,0,0,,{body}")

    with open(args.ass_out, "w") as f:
        f.write(HEADER.format(w=W, h=H, fs=args.fontsize))
        f.write("\n".join(lines_out) + "\n")
    print(f"{n} lines -> {len(lines_out)} scroll events -> {args.ass_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
