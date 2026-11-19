"""Low-rate listening kit (64 kb/s): for each item, Opus at --bitrate 64 and MULE and Vorbis at
the same real rate on that item (each one's quality setting searched, within 3 %), with the
original; 16-bit WAV in data/listen/g64/, rates.txt (README and run_abx.sh are written by hand).
Usage: python eval/abx_kit_g64.py"""
import os
import sys
import tempfile

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # eval/ (this script: eval/archive/)
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "py")]
import corpus                                    # noqa: E402
import refcodecs                                 # noqa: E402
from abx_kit_g3 import mule_at, opus, write      # noqa: E402

OUT = os.path.join(ROOT, "data", "listen", "g64")
ITEMS = ["female_en", "castanets", "harpsichord", "orchestra", "abba", "b_joy_division", "glockenspiel"]


def vorbis_at(wav, kbps):
    """(decoded, rate, q): oggenc's quality searched so that the rate is within 3 % of kbps"""
    lo, hi, best = -1.0, 6.0, None
    for _ in range(20):                         # its rate moves by steps: the closest one kept
        q = round((lo + hi) / 2, 4)
        with tempfile.TemporaryDirectory() as w:
            dec, _, r = refcodecs.run(f"vorbis_q{q:g}", wav, w)
            y, fs = sf.read(dec, always_2d=True)
        if best is None or abs(r / kbps - 1) < abs(best[1] / kbps - 1):
            best = (y, r, q)
        if abs(r / kbps - 1) < 0.03:
            break
        lo, hi = (lo, q) if r > kbps else (q, hi)
    return best


def main():
    import abx_kit_g3
    abx_kit_g3.OUT = OUT                         # its write() puts the files here
    os.makedirs(os.path.join(OUT, "results"), exist_ok=True)
    wavs = dict(corpus.items("all"))
    rates = []
    for it in ITEMS:
        x, fs = sf.read(wavs[it], dtype="float64", always_2d=True)
        write(f"{it}__orig.wav", x, len(x))
        yo, ro = opus(wavs[it], 64)
        write(f"{it}__opus64.wav", yo, len(x))
        ym, rm, qm = mule_at(x, ro)
        write(f"{it}__mule64.wav", ym, len(x))
        yv, rv, qv = vorbis_at(wavs[it], ro)
        write(f"{it}__vorbis64.wav", np.asarray(yv), len(x))
        rates.append(f"{it:16s} opus64 {ro:5.1f} kb/s   mule64 {rm:5.1f} kb/s (q {qm:+.1f})   "
                     f"vorbis64 {rv:5.1f} kb/s (q {qv:.2f})")
        print(rates[-1], flush=True)
    open(os.path.join(OUT, "rates.txt"), "w").write("\n".join(rates) + "\n")


if __name__ == "__main__":
    main()
