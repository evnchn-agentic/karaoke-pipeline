"""Run: python3 test_lrc_to_cues.py"""
import json
import pathlib
import subprocess
import sys
import tempfile

LRC = """[ti:Example]
[00:00.00] 作词 : Writer A
[00:01.00] 作曲 : Composer B/Composer C
[00:02.00] Mixed By : Engineer D
[00:05.00]first sung line
[00:08.00]他说：别走
[00:11.00]I said: stay
[00:14.00]label : mid-song lines stay
[00:17.00]last sung line
[00:21.00]
[00:30.00] 音频工程师 : Engineer E
[00:31.00] 混音工程师 : Engineer F
"""


def run(lrc):
    with tempfile.TemporaryDirectory() as d:
        src, dst = pathlib.Path(d, "in.lrc"), pathlib.Path(d, "out.json")
        src.write_text(lrc, encoding="utf-8")
        script = pathlib.Path(__file__).parent / "bin" / "lrc_to_cues.py"
        subprocess.run([sys.executable, str(script), str(src), str(dst)], check=True)
        return json.loads(dst.read_text(encoding="utf-8"))


cues = run(LRC)
assert [c["text"] for c in cues] == [
    "first sung line", "他说：别走", "I said: stay", "label : mid-song lines stay", "last sung line",
], cues
assert cues[0]["start"] == 5.0 and cues[-1]["end"] == 21.0, cues

# no credit lines: output unchanged
plain = run("[00:01.00]a\n[00:02.00]他说：别走\n[00:03.00]b\n")
assert [(c["start"], c["end"], c["text"]) for c in plain] == [
    (1.0, 2.0, "a"), (2.0, 3.0, "他说：别走"), (3.0, 7.0, "b")], plain
print("ok")
