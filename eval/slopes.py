"""How far MULE's psychoacoustic model is from Zimtohrli's: marginal slopes per frequency region.

If the model spent the bits as Zimtohrli would, a kb/s moved into any region would buy the same
drop of Zimtohrli's distance: the slopes dZ/dR of the seven regions of eval/zimt_diag.py would be
equal. Their spread is the mismatch, and moving bits from the low-slope regions to the high-slope
ones at constant rate is the gain to expect (second order: each region's curvature from the
three points).

  measure  for each rate, on the even half of dev: the --bitrate settings with the rate leveler
           off (fixed q: clean local derivatives; the Opus table kept at the rate), then each
           region's masks raised and lowered by DB dB (band_db), and q -/+ 1.5 dB (the uniform
           direction). eval/results/slopes_<rate>.csv, the summary in slopes_summary.json
  check    the predicted reallocation (offsets in dB per region) against the base, on the odd
           half of dev, both at two q around the rate and interpolated to the base's mean rate:
           every judge. eval/results/slopes_check_<rate>.csv

Encoder only (band_db, default 0: production unchanged). VISQOL= (no ViSQOL).
"""
import argparse
import dataclasses
import json
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
os.environ["VISQOL"] = ""
import corpus  # noqa: E402
import metrics  # noqa: E402
import refcodecs  # noqa: E402
from mule import params as mp  # noqa: E402

RESULTS = os.path.join(HERE, "results")
NB = 22                         # MULE_NB coded bands (core/mule.h)
# Zimtohrli's regions (eval/zimt_diag.py REGIONS) as MULE bands (edges x 172.3 Hz)
REGIONS = [("0-250", 0, 2), ("250-1k", 2, 6), ("1k-2.8k", 6, 12), ("2.8k-6k", 12, 16),
           ("6k-10k", 16, 19), ("10k-13k", 19, 20), ("13k-20k", 20, 22)]
DB = 3.0
DQ = 1.5
METRICS = ("zimt", "odg", "odg_adv", "nmr_db")


def base(rate, **kw):
    p = mp.for_bitrate(rate)
    return dataclasses.replace(p, rc_k=0.0, opa_kbps=float(rate), **kw)


def offsets(region_db):
    """{region index: dB} -> band_db tuple"""
    out = [0.0] * NB
    for r, d in region_db.items():
        for b in range(REGIONS[r][1], REGIONS[r][2]):
            out[b] = float(d)
    return tuple(out)


def job(args):
    tag, p, name, wav = args
    os.environ["VISQOL"] = ""
    codec = refcodecs.Mule("", p.q_db)
    codec.params = p
    import soundfile as sf
    with tempfile.TemporaryDirectory() as work:
        dec, enc, nbytes = codec.run(wav, work)
        kbps = nbytes * 8 / sf.info(wav).duration / 1000
        res = metrics.evaluate(wav, dec)
    return {"tag": tag, "item": name, "q": p.q_db, "kbps": kbps, **{k: res.get(k, np.nan) for k in METRICS}}


def configs(rate):
    p0 = base(rate)
    out = [("base", p0), ("q-", dataclasses.replace(p0, q_db=p0.q_db - DQ)),
           ("q+", dataclasses.replace(p0, q_db=p0.q_db + DQ))]
    for r, (name, _, _) in enumerate(REGIONS):
        for s, d in (("-", -DB), ("+", DB)):
            out.append((f"{name}{s}", dataclasses.replace(p0, band_db=offsets({r: d}))))
    return out


def fit(df):
    """Per direction: rate slope dR/dx, Zimtohrli slope dZ/dR (x 1e4 per kb/s, negative: more
    bits help) and curvature d2Z/dR2, from the three corpus-mean points (minus, base, plus)."""
    m = df.groupby("tag")[["kbps", *METRICS]].mean()
    out = []
    dirs = [("uniform", "q-", "q+", DQ)] + [(n, f"{n}-", f"{n}+", DB) for n, _, _ in REGIONS]
    for name, lo, hi, step in dirs:
        R = np.array([m.loc[lo, "kbps"], m.loc["base", "kbps"], m.loc[hi, "kbps"]])
        Z = np.array([m.loc[lo, "zimt"], m.loc["base", "zimt"], m.loc[hi, "zimt"]]) * 1e4
        c2, c1, _ = np.polyfit(R - R[1], Z, 2)
        row = {"dir": name, "dR_per_db": (R[2] - R[0]) / (2 * step), "dR": R[2] - R[0],
               "slope": c1, "curv": 2 * c2}
        for k in ("odg", "odg_adv", "nmr_db"):
            row[f"slope_{k}"] = (m.loc[hi, k] - m.loc[lo, k]) / (R[2] - R[0])
        out.append(row)
    return pd.DataFrame(out)


def realloc(f):
    """Bits moved between regions at constant rate (Delta b sums to 0) minimizing the quadratic
    model; the predicted gain, and each region's offset in dB (from its dR/ddB)."""
    reg = f[f["dir"] != "uniform"].reset_index(drop=True)
    s = reg["slope"].to_numpy()                 # dZ/dR, < 0
    c = np.maximum(reg["curv"].to_numpy(), 1e-4)
    lam = np.sum(s / c) / np.sum(1 / c)
    db = -(s - lam) / c                         # kb/s to add per region
    gain = float(np.sum((s - lam) ** 2 / (2 * c)))
    off = np.clip(db / reg["dR_per_db"].to_numpy(), -6, 6)    # dR_per_db < 0: dB raises masks
    return {"lambda": float(lam), "dkbps": dict(zip(reg["dir"], db.round(3).tolist())),
            "offset_db": dict(zip(reg["dir"], off.round(2).tolist())), "gain_zimt_e4": gain}


def cmd_measure(a):
    items = corpus.items("dev")[0::2]
    summary = {}
    path = os.path.join(RESULTS, "slopes_summary.json")
    if os.path.exists(path):
        summary = json.load(open(path))
    with ProcessPoolExecutor(a.jobs) as ex:
        for rate in a.rates:
            csv = os.path.join(RESULTS, f"slopes_{rate}.csv")
            if os.path.exists(csv) and not a.force:
                df = pd.read_csv(csv)
            else:
                tasks = [(t, p, n, w) for t, p in configs(rate) for n, w in items]
                df = pd.DataFrame(list(ex.map(job, tasks, chunksize=1)))
                df.to_csv(csv, index=False)
            f = fit(df)
            r = realloc(f)
            summary[str(rate)] = {"fit": f.round(5).to_dict("records"), **r}
            print(f"== {rate} kb/s ({len(items)} items)\n{f.round(4).to_string(index=False)}")
            print(json.dumps(r, indent=1))
            json.dump(summary, open(path, "w"), indent=1)


def cmd_check(a):
    items = corpus.items("dev")[1::2]
    summary = json.load(open(os.path.join(RESULTS, "slopes_summary.json")))
    with ProcessPoolExecutor(a.jobs) as ex:
        for rate in a.rates:
            off = summary[str(rate)]["offset_db"]
            band = offsets({i: off[n] for i, (n, _, _) in enumerate(REGIONS)})
            p0 = base(rate)
            tasks = []
            for tag, p in (("base", p0), ("realloc", dataclasses.replace(p0, band_db=band))):
                for dq in (-0.75, 0.75):
                    tasks += [(tag, dataclasses.replace(p, q_db=p0.q_db + dq), n, w) for n, w in items]
            df = pd.DataFrame(list(ex.map(job, tasks, chunksize=1)))
            df.to_csv(os.path.join(RESULTS, f"slopes_check_{rate}.csv"), index=False)
            m = df.groupby(["tag", "q"])[["kbps", *METRICS]].mean()
            target = float(m.loc["base", "kbps"].mean())
            print(f"== {rate} kb/s, check on {len(items)} odd dev items, at {target:.1f} kb/s")
            for tag in ("base", "realloc"):
                t = m.loc[tag].sort_values("kbps")
                w = (target - t["kbps"].iloc[0]) / (t["kbps"].iloc[1] - t["kbps"].iloc[0])
                v = t.iloc[0] + w * (t.iloc[1] - t.iloc[0])
                print(f"  {tag:8s} zimt {v['zimt'] * 1e4:.3f}  odg {v['odg']:.3f}  odg_adv {v['odg_adv']:.3f}"
                      f"  nmr {v['nmr_db']:.2f}  (w {w:.2f})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("measure", "check"))
    ap.add_argument("--rates", type=int, nargs="+", default=[96, 128, 160])
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    {"measure": cmd_measure, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
