#!/usr/bin/env python3
"""Language-agnostic repetition analysis: does this song reuse sections (chorus)?

Chroma self-similarity + a time-lag representation. Strong off-diagonal stripes /
dominant lags = repeated sections you can solve ONCE and warp onto the repeats
(no acoustic model, no language support needed). Renders a heatmap and prints the
dominant repetition lags in seconds.

Usage: ssm.py <audio> <out.png> [--sr 22050]
"""
import argparse
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import librosa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out_png")
    ap.add_argument("--sr", type=int, default=22050)
    args = ap.parse_args()

    y, sr = librosa.load(args.audio, sr=args.sr, mono=True)
    dur = len(y) / sr
    # Beat-synchronous chroma: robust, tempo-normalized, cheap.
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    csync = librosa.util.sync(chroma, beats, aggregate=np.median)
    beat_times = librosa.frames_to_time(beats, sr=sr)

    # Self-similarity (cosine) on beat-synced chroma.
    S = librosa.segment.recurrence_matrix(csync, mode="affinity", sym=True, width=3)

    # Time-lag: sum affinity along each diagonal -> dominant repetition lags.
    n = S.shape[0]
    lag_score = np.array([np.mean(np.diagonal(S, k)) for k in range(1, n)])
    # Convert top lags (in beats) to seconds via median beat period.
    if len(beat_times) > 1:
        beat_per = np.median(np.diff(beat_times))
    else:
        beat_per = dur / max(1, n)
    top = np.argsort(lag_score)[::-1][:6]
    print(f"duration {dur:.1f}s | tempo ~{float(tempo):.0f} BPM | {n} beats | beat~{beat_per:.2f}s")
    print("dominant repetition lags (beats -> seconds, higher score = stronger repeat):")
    for k in sorted(top):
        print(f"  lag {k+1:3d} beats  ~{(k+1)*beat_per:5.1f}s   score {lag_score[k]:.3f}")
    overall = float(np.mean(lag_score))
    peak = float(np.max(lag_score))
    print(f"repetition signal: peak-lag {peak:.3f} vs mean {overall:.3f}  "
          f"(ratio {peak/max(overall,1e-6):.1f}x -> "
          f"{'clear repeats' if peak/max(overall,1e-6) > 2.2 else 'weak/through-composed'})")

    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    librosa.display.specshow(S, x_axis="time", y_axis="time", sr=sr,
                             hop_length=512, ax=ax[0], cmap="magma")
    ax[0].set_title("chroma self-similarity (bright off-diagonal = repeat)")
    ax[1].plot([(k+1)*beat_per for k in range(len(lag_score))], lag_score, lw=1)
    ax[1].set(xlabel="lag (s)", ylabel="mean affinity", title="repetition by lag")
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out_png, dpi=110)
    print(f"heatmap -> {args.out_png}", file=sys.stderr)


if __name__ == "__main__":
    main()
