"""ABX kit comparing two MULE encoder settings at the same rate (data/listen/<kit>/, git-ignored like
all of data/): for each item, the original and each setting with its q set by bisection (0.01 dB)
so that its rate on that item is --rate kb/s, all aligned on the original, 44.1 kHz / 16 bits, no
gain. Writes <item>__orig.wav, <item>__<label>.wav for both, rates.txt and run_abx.sh.

    python eval/abx_pair.py m6z1 mule:prod mule-m6z1:m6z1 [--rate 128] [items...]

Writes only into data/listen/<kit>/ (the files of the kit, overwritten if they exist).
"""
import argparse
import os
import sys

import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402
from tonal_lines import mule_q  # noqa: E402

ITEMS = ["b_monster_magnet", "b_red_fang", "b_zombie_zombie", "heilung", "b_belenos", "harpsichord"]

RUN = """#!/bin/sh
# ABX {a} contre {b} (16 essais par extrait), puis chacun contre l'original si voulu.
# Usage : ./run_abx.sh                (= {a} contre {b})
#         ./run_abx.sh {b} orig       (une version contre l'original)
# Résultats : results/<extrait>__<x>__vs_<y>.txt (sortie de squishyball).
x=${{1:-{a}}}
y=${{2:-{b}}}
cd "$(dirname "$0")"
mkdir -p results
for it in {items}; do
    echo "=== $it : $x contre $y  (Ctrl-C pour passer à l'extrait suivant)"
    squishyball -b -n 16 -N -r "${{it}}__${{y}}.wav" "${{it}}__${{x}}.wav" > "results/${{it}}__${{x}}__vs_${{y}}.txt"
done
echo "Scores : grep -i -H correct results/*.txt"
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kit")
    ap.add_argument("a", help="family:label, e.g. mule:prod")
    ap.add_argument("b", help="family:label, e.g. mule-m6z1:m6z1")
    ap.add_argument("items", nargs="*", default=ITEMS)
    ap.add_argument("--rate", type=float, default=128.0)
    o = ap.parse_args()
    out = os.path.join(os.path.dirname(HERE), "data", "listen", o.kit)
    os.makedirs(out, exist_ok=True)
    wavs = dict(corpus.items("all"))
    sets = [s.split(":") for s in (o.a, o.b)]
    lines = []
    for it in o.items:
        w = wavs[it]
        for fam, lab in sets:
            cfg = f"{fam}_{mule_q(f'{fam}_-7', w, o.rate):g}"
            r, y, fs, kb, _lag = refcodecs.run_aligned(cfg, w)
            sf.write(os.path.join(out, f"{it}__{lab}.wav"), y, fs, subtype="PCM_16")
            lines.append(f"{it}__{lab}.wav  {cfg}  {kb:.1f} kb/s")
            print(lines[-1], flush=True)
        sf.write(os.path.join(out, f"{it}__orig.wav"), r, fs, subtype="PCM_16")
    with open(os.path.join(out, "rates.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    sh = os.path.join(out, "run_abx.sh")
    with open(sh, "w") as f:
        f.write(RUN.format(a=sets[0][1], b=sets[1][1], items=" ".join(o.items)))
    os.chmod(sh, 0o755)


if __name__ == "__main__":
    main()
