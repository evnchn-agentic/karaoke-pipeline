"""Run: python3 test_whisper_to_ass.py"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "bin"))
from whisper_to_ass import build_line


def shown(words):
    """The text a viewer sees: the line with every {...} karaoke tag removed."""
    seg = {"words": [{"word": w, "start": s, "end": s + 0.3} for w, s in words]}
    return re.sub(r"\{[^}]*\}", "", build_line(seg, None)[2])


# Whisper marks a word boundary with a leading space on the token; CJK characters and
# the pieces of a split English word carry none, so no space may be inserted there
assert shown([(" Code", 0.0), (" Monkey,", 0.4), (" get", 0.8)]) == "Code Monkey, get"
assert shown([(" 淋", 0.0), ("出", 0.4), ("眼", 0.8), ("泪", 1.2)]) == "淋出眼泪"
assert shown([(" 回", 0.0), ("头", 0.4), (" 再", 1.0), ("看", 1.4)]) == "回头 再看"
assert shown([(" Tas", 0.0), ("ks", 0.4), (" 爱", 0.8), ("你", 1.2)]) == "Tasks 爱你"

# a pause before an unspaced token still gets its own sweep, so the fill waits through it
line = build_line({"words": [{"word": " 淋", "start": 0.0, "end": 0.3},
                             {"word": "出", "start": 1.3, "end": 1.6}]}, None)[2]
assert line == r"{\kf30}淋{\kf100}{\kf30}出", line
print("ok")
