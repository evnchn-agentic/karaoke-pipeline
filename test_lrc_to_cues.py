"""Run: python3 test_lrc_to_cues.py"""
import json
import pathlib
import subprocess
import sys
import tempfile


def run(lrc, encoding="utf-8"):
    with tempfile.TemporaryDirectory() as d:
        src, dst = pathlib.Path(d, "in.lrc"), pathlib.Path(d, "out.json")
        src.write_text(lrc, encoding=encoding)
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
[00:13.00]你说的台词：我永远爱你
[00:17.00]I'm mixed up: I don't know
""") == [(1.0, 5.0, "男 : 我还在等你"), (5.0, 9.0, "女：我也在等你"), (9.0, 13.0, "I said : stay"),
         (13.0, 17.0, "你说的台词：我永远爱你"), (17.0, 21.0, "I'm mixed up: I don't know")]
# a UTF-8 BOM (Windows Notepad) must not hide a credit line from the skip or leak into the first lyric
assert run("""[00:00.00]作词 : Writer A
[00:05.00]first sung line
[00:09.00]
""", encoding="utf-8-sig") == [(5.0, 9.0, "first sung line")]
assert run("[00:05.00]first sung line\n[00:09.00]\n", encoding="utf-8-sig") == [(5.0, 9.0, "first sung line")]
# a bilingual LRC stamps each translation with its line's time: one cue per time, the first (sung) line,
# spanning to the next distinct time instead of flashing for 0 s
assert run("""[00:05.00]first sung line
[00:05.00]第一句译文
[00:09.00]second sung line
[00:09.00]第二句译文
[00:13.00]
""") == [(5.0, 9.0, "first sung line"), (9.0, 13.0, "second sung line")]

# credits sharing a time with a lyric, before or after it, never cost the lyric its span
assert run("""[00:00.00]作词 : Writer A
[00:00.00]Song - Artist
[00:00.00]作曲 : Composer B
[00:05.00]first sung line
[00:09.00]
""") == [(0.0, 5.0, "Song - Artist"), (5.0, 9.0, "first sung line")]
print("ok")
