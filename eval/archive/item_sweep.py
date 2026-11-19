"""One item, encoder parameter sets: (kb/s, ODG, ODG advanced) per quality, and ODG interpolated at
a common rate. Usage: python eval/item_sweep.py ITEM RATE 'k=v,k=v' ['k=v' ...] (MULE_BUILD for the
library and mule-dec). Parallel over (set, q)."""
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # eval/ (this script: eval/archive/)
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "py")]
import corpus                                    # noqa: E402
import metrics                                   # noqa: E402
from mule import native, params as E            # noqa: E402

QS = (-6.0, -9.0, -12.0, -15.0)


def parse(spec):
    out = {}
    for kv in filter(None, spec.split(",")):
        k, v = kv.split("=")
        d = getattr(E.Params(), k)
        out[k] = None if v == "none" else (v if isinstance(d, str) else (float(v) if d is None else type(d)(float(v))))
    return out


def job(args):
    wav, spec, q = args
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    with tempfile.TemporaryDirectory() as d:
        enc, dec = os.path.join(d, "a.mule"), os.path.join(d, "a.wav")
        data, nb = native.c_encode(x, E.Params(q_db=q, **parse(spec)))
        open(enc, "wb").write(data)
        subprocess.run([os.path.join(ROOT, os.environ.get("MULE_BUILD", "build"), "mule-dec"), enc, dec],
                       check=True)
        r = metrics.evaluate(wav, dec)
    return spec, q, nb * 8 / (len(x) / fs) / 1000, r["odg"], r["odg_adv"]


def main():
    item, rate, specs = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
    wav = dict(corpus.items("all"))[item]
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(job, [(wav, s, q) for s in specs for q in QS]))
    for s in specs:
        rows = sorted([r for r in res if r[0] == s], key=lambda r: r[2])
        k = np.array([r[2] for r in rows])
        o = np.interp(rate, k, [r[3] for r in rows])
        a = np.interp(rate, k, [r[4] for r in rows])
        pts = " ".join(f"{r[2]:.0f}:{r[3]:+.2f}" for r in rows)
        print(f"{s or 'base':28s} @{rate:.0f}: odg {o:+.3f} adv {a:+.3f}   ({pts})", flush=True)


if __name__ == "__main__":
    main()
