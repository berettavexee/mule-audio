"""PEAQ basic ODG passage by passage: each item cut into windows of a few seconds (after
alignment), scored for each configuration, to see where in an item the grade is lost.

    python eval/segment_odg.py mule_-7,opus_128 --items a,b [--win 3] [--set test] [-j N]
                               (prints; encodes in temporary directories)

PEAQ needs a short settling time and averages over the window: a window's ODG is a local
estimate, comparable between configurations on the same window, not with a whole item's.
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import metrics  # noqa: E402
import refcodecs  # noqa: E402


def job(args):
    cfg, name, wav, win = args
    r, y, fs, _kbps, _lag = refcodecs.run_aligned(cfg, wav)
    n = int(win * fs)
    rows = []
    for k in range(len(r) // n):
        s = slice(k * n, (k + 1) * n)
        m = metrics.peaq_movs(r[s], y[s], fs)
        lvl = 10 * np.log10(np.mean(r[s] ** 2) + 1e-20)
        rows.append(dict(item=name, config=cfg, seg=k, t0=k * win, level_db=lvl, odg=m["odg"],
                         nmr=m["Total NMRB"], adb=m["ADBB"], bw=m["BandwidthTestB"]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--set", default="test")
    ap.add_argument("--items", required=True)
    ap.add_argument("--win", type=float, default=3.0)
    ap.add_argument("--dump")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        d = pd.DataFrame([r for rows in ex.map(job, [(c, n, w, a.win) for c in configs for n, w in items])
                          for r in rows])
    if a.dump:
        d.to_csv(a.dump, index=False)
    base = configs[0]
    for name, _ in items:
        t = d[d.item == name].pivot(index="seg", columns="config", values="odg")[configs]
        lv = d[(d.item == name) & (d.config == base)].set_index("seg")
        t.insert(0, "t0 (s)", lv.t0)
        t.insert(1, "level dB", lv.level_db.round(1))
        for c in configs[1:]:
            t[f"{base} - {c}"] = t[base] - t[c]
        print(f"\n{name}: ODG per {a.win:g} s window")
        print(t.round(3).to_string())


if __name__ == "__main__":
    main()
