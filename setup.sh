#!/usr/bin/env bash
# One-shot setup: create the .venv the pipeline expects and install deps.
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "Install uv first:  curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements.txt
echo
echo "✓ .venv ready."
echo "  Also required — ffmpeg with libass:   brew install ffmpeg-full"
echo "  Whisper runs via uvx (openai-whisper) on first use; no extra install needed."
echo "  Try:   bin/karaoke.sh <your-audio> --lang en"
