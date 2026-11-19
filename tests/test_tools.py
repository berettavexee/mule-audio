"""The encoder's tools: ReplayGain (BS.1770-4), Ogg comment rewriting (big packets over several
pages, audio untouched), and mule-enc / mule-gain from the command line."""
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "tools")]
from mule import native, params as E, oggfile, replaygain  # noqa: E402

PY = sys.executable


def tone(seconds=3, fs=44100, ch=2, f=997, amp=0.5):
    """A sine of f Hz, amplitude amp, in ch channels."""
    t = np.arange(int(seconds * fs)) / fs
    return np.repeat((amp * np.sin(2 * np.pi * f * t))[:, None], ch, axis=1)


def test_bs1770_reference():
    """A 997 Hz sine at 0 dBFS in one channel: -3.01 LUFS; the 48 kHz K-weighting coefficients"""
    for fs in (44100, 48000):
        x = np.zeros((fs * 5, 2))
        x[:, 0] = tone(5, fs, 1, amp=1.0)[:, 0]
        m = replaygain.Meter(fs)
        m.add(x[:fs])                           # in parts, as a decoder delivers it
        m.add(x[fs:])
        assert abs(m.loudness() + 3.01) < 0.02
    (b1, a1), (b2, a2) = replaygain._k_filter(48000)
    assert np.allclose(b1, [1.53512485958697, -2.69169618940638, 1.19839281085285], atol=1e-9)
    assert np.allclose(a1[1:], [-1.69065929318241, 0.73248077421585], atol=1e-9)
    assert np.allclose(a2[1:], [-1.99004745483398, 0.99007225036621], atol=1e-9)


def test_gating_and_album():
    """Silence has no loudness (gain 0); a track 20 dB quieter is gated out of the album's"""
    fs = 44100
    m = replaygain.Meter(fs)
    m.add(np.zeros((fs * 3, 2)))
    assert m.loudness() == -np.inf and replaygain.gain(m.loudness()) == 0.0
    a, b = replaygain.Meter(fs), replaygain.Meter(fs)
    a.add(tone(4, amp=0.5))
    b.add(tone(4, amp=0.05))                    # 20 dB quieter: gated out of the album
    lufs, peak = replaygain.Meter.merge([a, b])
    assert abs(lufs - a.loudness()) < 0.1 and peak == a.peak


def test_comment_rewrite_keeps_audio():
    """A comment header rewritten over several pages: audio packets and MULEHead unchanged,
    the comments read back, every page's CRC right"""
    x = tone(2)
    data, _ = native.c_encode(x, E.Params(q_db=-9), [("TITLE", "t")])
    big = [("COMMENT", "x" * 200_000)]          # over 3 pages
    out = oggfile.replace_comments(data, oggfile.build_comments("v", big))
    a, b = oggfile.packets(data), oggfile.packets(out)
    assert [p for p, _ in a[2:]] == [p for p, _ in b[2:]] and a[0][0] == b[0][0]
    assert oggfile.parse_comments(b[1][0]) == ("v", big)
    for p in oggfile.pages(out):                # every CRC right
        h = bytearray(out[p["pos"]:p["end"]])
        c = int.from_bytes(h[22:26], "little")
        h[22:26] = b"\0\0\0\0"
        assert oggfile.crc(bytes(h)) == c


def test_encoder_big_comment_packet():
    """mule_encode's comment header over several pages (a cover of 300 KB used to overflow)"""
    data, _ = native.c_encode(tone(1), E.Params(q_db=-9), [("METADATA_BLOCK_PICTURE", "A" * 300_000)])
    pk = oggfile.packets(data)
    assert oggfile.parse_comments(pk[1][0])[1][0][1] == "A" * 300_000
    assert pk[2][1] > 1 and len(oggfile.pages(data)) > 6


def test_cli(tmp_path):
    """mule-enc from the command line: resampling, mono to stereo, tags; then mule-gain"""
    src = tmp_path / "in.wav"
    sf.write(src, tone(3, fs=48000, ch=1), 48000)
    out = tmp_path / "out.mule"
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "mule_enc.py"), "--bitrate", "128",
                        "--title", "T", "--artist", "A", "--artist", "B", "--comment", "foo=bar",
                        str(src), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = out.read_bytes()
    tags = dict(oggfile.parse_comments(oggfile.packets(data)[1][0])[1])
    assert tags["TITLE"] == "T" and tags["FOO"] == "bar" and "REPLAYGAIN_TRACK_GAIN" in tags
    arts = [v for k, v in oggfile.parse_comments(oggfile.packets(data)[1][0])[1] if k == "ARTIST"]
    assert arts == ["A", "B"]
    second = tmp_path / "b.mule"
    second.write_bytes(data)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "mule_gain.py"), "-a", "-q", str(out), str(second)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    tags = dict(oggfile.parse_comments(oggfile.packets(out.read_bytes())[1][0])[1])
    assert tags["REPLAYGAIN_ALBUM_GAIN"] == tags["REPLAYGAIN_TRACK_GAIN"]
