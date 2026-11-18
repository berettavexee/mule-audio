"""G3 listening kit (after axis 2): MULE (current encoder, format v2) against Opus at the same
rate, per item, on the items where PEAQ still sees the largest gap; and the noise-fill bias that
PEAQ and ViSQOL disagree on (E2-LOG.md). 16-bit WAV in data/listen/g3/, README, run_abx.sh.
For each item, MULE's quality setting is searched so that its rate matches Opus's on that item
(within 2 %). Usage: python eval/abx_kit_g3.py"""
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "py")]
import corpus                                    # noqa: E402
import refcodecs                                 # noqa: E402
from mule import native, params as E           # noqa: E402

OUT = os.path.join(ROOT, "data", "listen", "g3")
GAP = ["female_en", "b_joy_division", "b_wolfmother", "b_modest_mussorgsky", "b_body_count", "heilung"]
NOISE = ["triangles", "glockenspiel", "orchestra"]
OPUS = (128, 160)


def mule_at(x, kbps, **kw):
    """(decoded float, rate, q) with the rate within 2 % of kbps (bisection on the quality)"""
    dur = len(x) / 44100
    lo, hi = -30.0, 6.0
    for _ in range(18):
        q = (lo + hi) / 2
        data, nb = native.c_encode(x, E.Params(q_db=q, **kw))
        r = len(data) * 8 / dur / 1000
        if abs(r / kbps - 1) < 0.02:
            break
        lo, hi = (q, hi) if r > kbps else (lo, q)
    with tempfile.TemporaryDirectory() as d:
        f, w = os.path.join(d, "a.mule"), os.path.join(d, "a.wav")
        open(f, "wb").write(data)
        subprocess.run([os.path.join(ROOT, "build", "mule-dec"), f, w], check=True)
        y, _ = sf.read(w, always_2d=True)
    return y, r, q


def opus(wav, kbps):
    with tempfile.TemporaryDirectory() as w:
        dec, _, kb = refcodecs.run(f"opus_{kbps}", wav, w)
        y, fs = sf.read(dec, always_2d=True)
    if fs != 44100:
        import soxr
        y = soxr.resample(y, fs, 44100, quality="VHQ")
    return y, kb


def write(name, y, n):
    sf.write(os.path.join(OUT, name), np.clip(y[:n], -1, 1), 44100, subtype="PCM_16")


def main():
    os.makedirs(os.path.join(OUT, "results"), exist_ok=True)
    wavs = dict(corpus.items("all"))
    rates = []
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from mule_enc import quality_for
    qn = quality_for(128)                       # 128 kb/s as a library average (mule-enc)
    for it in NOISE:                            # the noise-fill bias: the same setting, both
        x, fs = sf.read(wavs[it], dtype="float64", always_2d=True)
        write(f"{it}__orig.wav", x, len(x))
        for tag, kw in (("mule128", {}), ("mule128nf", {"nf_bias": 2})):
            data, nb = native.c_encode(x, E.Params(q_db=qn, **kw))
            with tempfile.TemporaryDirectory() as d:
                f, w = os.path.join(d, "a.mule"), os.path.join(d, "a.wav")
                open(f, "wb").write(data)
                subprocess.run([os.path.join(ROOT, "build", "mule-dec"), f, w], check=True)
                y, _ = sf.read(w, always_2d=True)
            write(f"{it}__{tag}.wav", y, len(x))
            rates.append(f"{it:20s} {tag:10s} {len(data) * 8 / (len(x) / 44100) / 1000:6.1f} kb/s (q {qn:+.1f})")
            print(rates[-1], flush=True)
    for it in GAP:
        x, fs = sf.read(wavs[it], dtype="float64", always_2d=True)
        write(f"{it}__orig.wav", x, len(x))
        for k in OPUS:
            yo, ro = opus(wavs[it], k)
            # Opus's decoder output is aligned by refcodecs (pre-skip removed); same length
            write(f"{it}__opus{k}.wav", yo, len(x))
            ym, rm, q = mule_at(x, ro)
            write(f"{it}__mule{k}.wav", ym, len(x))
            rates.append(f"{it:20s} opus{k:<4d} {ro:6.1f} kb/s   mule{k:<4d} {rm:6.1f} kb/s (q {q:+.1f})")
            print(rates[-1], flush=True)
    open(os.path.join(OUT, "rates.txt"), "w").write("\n".join(rates) + "\n")


if __name__ == "__main__":
    main()
