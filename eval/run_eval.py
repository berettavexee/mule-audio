"""Encodes the corpus with each codec configuration, decodes, measures, writes a CSV and a summary.

Usage:
  python eval/run_eval.py                         # default reference set
  python eval/run_eval.py vorbis_q4 opus_128      # chosen configurations
  python eval/run_eval.py --items castanets,abba  # subset of the corpus
Results: eval/results/<tag>.csv (one row per item x configuration) and a summary on stdout.
"""
import argparse
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refcodecs                                 # noqa: E402
import corpus                                    # noqa: E402
import metrics                                   # noqa: E402

DEFAULT = ["vorbis_q3", "vorbis_q4", "vorbis_q5", "vorbis_q6",
           "opus_96", "opus_128", "opus_160", "opus_192"]
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def job(args):
    cfg, name, wav = args
    with tempfile.TemporaryDirectory() as work:
        dec, _enc, kbps = refcodecs.run(cfg, wav, work)
        res = metrics.evaluate(wav, dec)
    return {"config": cfg, "item": name, "kbps": kbps, **res}


def summary(df):
    cols = [c for c in ["kbps", "nmr_db", "nmr_max_db", "adf", "snr_db", "visqol", "odg", "odg_adv", "mms2f", "zimt"]
            if c in df]
    g = df.groupby("config", sort=False)[cols].mean()
    worst = df.loc[df.groupby("config", sort=False)["nmr_db"].idxmax(), ["config", "item", "nmr_db"]]
    g["worst_item"] = worst.set_index("config")["item"]
    g["worst_nmr_db"] = worst.set_index("config")["nmr_db"]
    return g


def at_rates(df, rates=(128, 160), metric="nmr_db"):
    """Metric of each codec family (config prefix) interpolated at equal mean rates, from its
    configurations' (mean kb/s, mean metric) curve: the fair comparison between codecs."""
    g = df.groupby("config", sort=False)[["kbps", metric]].mean()
    g["family"] = [c.split("_")[0] for c in g.index]
    out = {}
    for fam, sub in g.groupby("family", sort=False):
        sub = sub.sort_values("kbps")
        out[fam] = {f"{metric}@{r}": (np.interp(r, sub["kbps"], sub[metric])
                                      if sub["kbps"].min() <= r <= sub["kbps"].max() else np.nan)
                    for r in rates}
    return pd.DataFrame(out).T


def write_params(configs, path):
    """The encoder settings each MULE configuration resolved to, in full: a variant only sets its
    own fields and inherits the production defaults of the day, which change (eval/refcodecs.py)."""
    import dataclasses
    import json
    mule = {c: dataclasses.asdict(refcodecs.get(c).params) for c in configs if c.startswith("mule")}
    if mule:
        with open(path, "w") as f:
            json.dump(mule, f, indent=1, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="*", default=DEFAULT)
    ap.add_argument("--items", help="comma-separated subset of the corpus")
    ap.add_argument("--set", default="p0", help="corpus subset: p0 (default), dev, test, all")
    ap.add_argument("--tag", default="refs")
    ap.add_argument("-j", type=int, default=os.cpu_count())
    a = ap.parse_args()
    corpus.build(verbose=False)
    items = corpus.items(a.set, a.items)
    jobs = [(c, n, w) for c in a.configs for n, w in items]
    with ProcessPoolExecutor(a.j) as ex:
        rows = list(ex.map(job, jobs))
    df = pd.DataFrame(rows)
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, f"{a.tag}.csv")
    df.to_csv(out, index=False, float_format="%.6g")
    write_params(a.configs, os.path.join(RESULTS, f"{a.tag}.params.json"))
    with pd.option_context("display.width", 200, "display.precision", 2):
        print(summary(df))
        print()
        print(at_rates(df))
    print(f"\n{len(df)} rows -> {out}")
    bad = df[np.abs(df["delay"]) > 0]
    if len(bad):
        print(f"note: {len(bad)} decodes needed a delay correction "
              f"({sorted(set(bad['delay']))} samples)")


if __name__ == "__main__":
    main()
