"""PEAQ basic's internal variables (MOVs) for any codec configurations, item by item: which of
PEAQ's variables carry the ODG gap between two configurations (eval/mov_diag.py did it for Opus
against MULE; this one takes any list).

    python eval/mov_compare.py aac_128,aapl_q63[,...] [--set test] [--items a,b] [-j N]
                               [--per-item odg,kbps,...]
                               (prints only; encodes in temporary directories)

For each pair (first configuration against each other one): the mean of each MOV, the mean
difference over the items divided by its spread (a t-like score), and the correlation, over the
items, of each MOV's difference with the ODG difference.
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

MOVS = ["BandwidthRefB", "BandwidthTestB", "Total NMRB", "WinModDiff1B", "ADBB", "EHSB",
        "AvgModDiff1B", "AvgModDiff2B", "RmsNoiseLoudB", "MFPDB", "RelDistFramesB"]


def job(args):
    cfg, name, wav = args
    r, y, fs, kbps, _lag = refcodecs.run_aligned(cfg, wav)
    m = metrics.peaq_movs(r, y, fs)
    return dict(item=name, config=cfg, kbps=kbps, odg=m["odg"], **{k: m.get(k, np.nan) for k in MOVS})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--set", default="test")
    ap.add_argument("--items")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    ap.add_argument("--per-item", help="also print these columns item by item (e.g. odg,kbps,ADBB)")
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        rows = list(ex.map(job, [(c, n, w) for c in configs for n, w in items]))
    d = pd.DataFrame(rows)
    cols = ["kbps", "odg"] + MOVS
    print(f"{len(items)} items of '{a.set}'; PEAQ basic model")
    print("\nmeans")
    print(d.groupby("config", sort=False)[cols].mean().T.round(3).to_string())
    for col in (a.per_item.split(",") if a.per_item else []):
        print(f"\n{col}, item by item")
        print(d.pivot(index="item", columns="config", values=col)[configs].round(3).to_string())
    base = configs[0]
    b = d[d.config == base].set_index("item")
    for other in configs[1:]:
        o = d[d.config == other].set_index("item").loc[b.index]
        diff = o[cols] - b[cols]
        print(f"\n{other} minus {base}, over the items: mean difference, t-like score (mean / sd * sqrt(n)), "
              f"correlation with the ODG difference")
        n = len(diff)
        for c in cols:
            v = diff[c].astype(float)
            t = v.mean() / (v.std(ddof=1) + 1e-12) * np.sqrt(n)
            r = np.corrcoef(v, diff["odg"])[0, 1] if c != "odg" and v.std() > 0 else float("nan")
            print(f"   {c:16s} {v.mean():+9.3f}   t {t:+6.1f}   r {r:+.2f}")


if __name__ == "__main__":
    main()
