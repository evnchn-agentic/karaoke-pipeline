#!/usr/bin/env bash
# karaoke.sh — turn ONE legally-owned audio file into a karaoke lyrics video,
# in both original-mix and no-vocal (instrumental) formats, fully local.
#
#   [audio] --demucs--> vocals + no_vocals
#                       |            |
#                  whisper(word ts)  |
#                       |            |
#                    .ass \kf   ->  ffmpeg burn-in --> <name>.original.mp4
#                                                 \--> <name>.karaoke.mp4
#
# Usage: karaoke.sh <input-audio> [--lang en|yue|zh|auto] [--res 1280x720]
#                   [--device mps|cpu] [--model large-v3-turbo|medium|...]
# Requires: ffmpeg-full (libass), the sibling .venv (demucs), uvx (whisper).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Prefer Homebrew's ffmpeg-full (has libass); else fall back to ffmpeg/ffprobe on PATH.
# Override either by exporting FFMPEG=/path before running.
FFMPEG="${FFMPEG:-/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg}"; [ -x "$FFMPEG" ] || FFMPEG=ffmpeg
FFPROBE="${FFPROBE:-/opt/homebrew/opt/ffmpeg-full/bin/ffprobe}"; [ -x "$FFPROBE" ] || FFPROBE=ffprobe
PY="$ROOT/.venv/bin/python"

INPUT="${1:?usage: karaoke.sh <input-audio> [--lang ..] [--res ..] [--device ..] [--model ..]}"; shift || true
LANG_OPT="auto"; RES="1280x720"; DEVICE="mps"; MODEL="large-v3-turbo"
while [[ $# -gt 0 ]]; do case "$1" in
  --lang)   LANG_OPT="$2"; shift 2;;
  --res)    RES="$2";      shift 2;;
  --device) DEVICE="$2";   shift 2;;
  --model)  MODEL="$2";    shift 2;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done

[[ -f "$INPUT" ]] || { echo "no such file: $INPUT" >&2; exit 1; }
NICE="$(basename "$INPUT")"; NICE="${NICE%.*}"          # display name (may hold spaces/CJK)
EXT="${INPUT##*.}"
WORK="$ROOT/work/$(echo -n "$NICE" | shasum | cut -c1-8)"  # ascii-safe per-song dir
mkdir -p "$WORK"
cp -f "$INPUT" "$WORK/track.$EXT"                        # ascii internal name

echo "==> [1/4] separating stems (demucs, device=$DEVICE) ..."
"$PY" -m demucs --two-stems=vocals -d "$DEVICE" -o "$WORK/demucs" "$WORK/track.$EXT" \
  || { echo "   mps failed, retrying on cpu ..."; \
       "$PY" -m demucs --two-stems=vocals -d cpu -o "$WORK/demucs" "$WORK/track.$EXT"; }
STEM="$WORK/demucs/htdemucs/track"
VOCALS="$STEM/vocals.wav"; NOVOX="$STEM/no_vocals.wav"
[[ -f "$VOCALS" && -f "$NOVOX" ]] || { echo "demucs output missing" >&2; exit 1; }

echo "==> [2/4] transcribing vocals with word timestamps (whisper $MODEL) ..."
WHISPER_ARGS=(--model "$MODEL" --word_timestamps True --output_format json \
              --output_dir "$WORK" --device cpu --fp16 False)
[[ "$LANG_OPT" != "auto" ]] && WHISPER_ARGS+=(--language "$LANG_OPT")
# let whisper find the same ffmpeg (only prepend when it's an absolute path)
case "$FFMPEG" in /*) export PATH="$(dirname "$FFMPEG"):$PATH";; esac
uvx --from openai-whisper whisper "$VOCALS" "${WHISPER_ARGS[@]}"
JSON="$WORK/vocals.json"
[[ -f "$JSON" ]] || { echo "whisper json missing" >&2; exit 1; }

echo "==> [3/4] building karaoke .ass (\\kf fill-sweep) ..."
ASS="$WORK/track.ass"
"$PY" "$ROOT/bin/whisper_to_ass.py" "$JSON" "$ASS" --playres "$RES"

echo "==> [4/4] rendering videos (original + no-vocal) ..."
OUTDIR="$ROOT/out"; mkdir -p "$OUTDIR"
render () {  # render <audio-file> <out.mp4>
  "$FFMPEG" -y -f lavfi -i "color=c=0x0d1117:s=$RES:r=24" -i "$2" \
    -filter_complex "[0:v]ass=$ASS[v]" -map "[v]" -map 1:a \
    -shortest -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
    -c:a aac -b:a 192k "$3" -loglevel error -stats
}
ORIG_OUT="$OUTDIR/$NICE.original.mp4"
KARA_OUT="$OUTDIR/$NICE.karaoke.mp4"
render x "$WORK/track.$EXT" "$ORIG_OUT"
render x "$NOVOX"           "$KARA_OUT"
# also expose the raw no-vocal audio (karaoke instrumental) for reuse
cp -f "$NOVOX" "$OUTDIR/$NICE.no_vocal.wav"

echo
echo "DONE:"
echo "  original-mix video : $ORIG_OUT"
echo "  no-vocal video     : $KARA_OUT"
echo "  no-vocal audio     : $OUTDIR/$NICE.no_vocal.wav"
echo "  karaoke subtitles  : $ASS"
