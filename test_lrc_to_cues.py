"""Run: python3 test_lrc_to_cues.py"""
import json
import pathlib
import subprocess
import sys
import tempfile


def run(lrc):
    with tempfile.TemporaryDirectory() as d:
        src, dst = pathlib.Path(d, "in.lrc"), pathlib.Path(d, "out.json")
        src.write_text(lrc, encoding="utf-8")
        script = pathlib.Path(__file__).parent / "bin" / "lrc_to_cues.py"
        subprocess.run([sys.executable, str(script), str(src), str(dst)], check=True)
        return [(c["start"], c["end"], c["text"]) for c in json.loads(dst.read_text(encoding="utf-8"))]


# credits before and after the song are dropped; the last sung line still ends where the credit starts
assert run("""[ti:Example]
[00:00.00]Song - Artist
[00:01.00] 作词 : Writer A
[00:02.00]曲：Composer B
[00:03.00] Mixed By : Engineer C
[00:05.00]first sung line
[00:09.00]last sung line
[00:30.00] 音频工程师 : Engineer D
""") == [(0.0, 1.0, "Song - Artist"), (5.0, 9.0, "first sung line"), (9.0, 30.0, "last sung line")]

# lines with a colon that are not credits are kept, including duet speaker labels
assert run("""[00:01.00]男 : 我还在等你
[00:05.00]女：我也在等你
[00:09.00]I said : stay
[00:13.00]他说：别走
""") == [(1.0, 5.0, "男 : 我还在等你"), (5.0, 9.0, "女：我也在等你"),
         (9.0, 13.0, "I said : stay"), (13.0, 17.0, "他说：别走")]
print("ok")
