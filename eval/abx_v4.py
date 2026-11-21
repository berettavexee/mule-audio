"""The ABX kit of format v4 at 128 kb/s (data/listen/v4/, git-ignored like all of data/): for
each item, the original, Apple's AAC in constrained VBR at 128 kb/s (qaac --cvbr 128) and MULE v4
(production) set to the same rate on that item (q by bisection, 0.01 dB), all aligned on the
original, 44.1 kHz / 16 bits, no gain. Writes <item>__orig.wav, <item>__v4.wav, <item>__aapl.wav
and rates.txt; the procedure is data/listen/v4/README.md (run_abx.sh, squishyball).

    python eval/abx_v4.py [items...]        (default: the six of the kit)

Writes only into data/listen/v4/ (the files of the kit, overwritten if they exist).
"""
import os
import sys
import tempfile

import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402
from tonal_lines import mule_q  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "data", "listen", "v4")
ITEMS = ["glockenspiel", "harpsichord", "castanets", "b_belenos", "b_lebanon_hanover",
         "b_toru_takemitsu_hiroshi_w"]


def main(items):
    os.makedirs(OUT, exist_ok=True)
    wavs = dict(corpus.items("all"))
    lines = []
    for it in items:
        w = wavs[it]
        with tempfile.TemporaryDirectory() as t:
            target = refcodecs.run("aaplc_128", w, t)[2]
        cfg = f"mule_{mule_q('mule_-7', w, target):g}"
        for lab, c in (("aapl", "aaplc_128"), ("v4", cfg)):
            r, y, fs, kb, _lag = refcodecs.run_aligned(c, w)
            sf.write(os.path.join(OUT, f"{it}__{lab}.wav"), y, fs, subtype="PCM_16")
            lines.append(f"{it}__{lab}.wav  {c}  {kb:.1f} kb/s")
            print(lines[-1])
        sf.write(os.path.join(OUT, f"{it}__orig.wav"), r, fs, subtype="PCM_16")
    with open(os.path.join(OUT, "rates.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:] or ITEMS)
