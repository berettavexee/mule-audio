"""M6 (docs/V3-IDEAS.md): joint tuning of the encoder's settings by CMA-ES.

Objective: the mean of PEAQ's basic and advanced ODG at 128 kb/s, at equal rate, on half of `dev`
(the even-numbered items). For each candidate, the qualities giving about 120 and 136 kb/s on
those items are found first (secant on q, encodes only), then PEAQ is run at both, and 128 kb/s
interpolated between them: never extrapolated (a first run with fixed qualities extrapolated
below both points when a candidate spent more bits, and the search exploited that bias:
m6_search_extrapolated.csv). The
other half and `test` are kept for validation. ViSQOL stays out of the loop (it is never an
optimization target: docs/NOTES-2026-11-18.md); the 2f-model and the internal NMR are recorded.
Encoder only: the format does not change.

  python eval/m6_tune.py search [--gens 12] [--pop 8]   # eval/results/m6_search.csv, m6_best.json
  python eval/m6_tune.py best                           # the best point found so far

The tuned settings (tcq_rdl replaces the notes' tcq_lam, which tcq_rd = 1 leaves unused):
"""
import argparse
import dataclasses
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
os.environ["VISQOL"] = ""                       # no ViSQOL in the loop
import corpus  # noqa: E402
import metrics  # noqa: E402
import refcodecs  # noqa: E402

RESULTS = os.path.join(HERE, "results")
SEARCH_CSV = os.path.join(RESULTS, "m6_search.csv")
BEST_JSON = os.path.join(RESULTS, "m6_best.json")
RATE = 128.0
TARGETS = (120.0, 136.0)                        # the two measured points, around RATE
TOL = 2.0                                       # kb/s
# setting: (low, high, production)
SPACE = {
    "tcap_db": (15.0, 35.0, 25.0),
    "mid_db": (0.0, 8.0, 4.0),
    "fft_noise_db": (2.0, 6.0, 4.0),
    "rd_lambda": (1.0, 3.0, 2.0),
    "tcq_rdl": (0.25, 1.0, 0.5),
}
__doc__ += "".join(f"  {k}: {lo:g} to {hi:g} (production {p:g})\n" for k, (lo, hi, p) in SPACE.items())
KEYS = list(SPACE)


def to_settings(x):
    """[0, 1]^5 -> settings (over the fixed BASE ones)."""
    out = dict(BASE)
    out.update({k: SPACE[k][0] + float(np.clip(v, 0, 1)) * (SPACE[k][1] - SPACE[k][0]) for k, v in zip(KEYS, x, strict=True)})
    return out


def to_unit(settings):
    return np.array([(settings[k] - SPACE[k][0]) / (SPACE[k][1] - SPACE[k][0]) for k in KEYS])


def search_items():
    return corpus.items("dev")[0::2]


BASE = {}                       # fixed settings under the tuned ones (--base), e.g. the v3 trellis


def job(args):
    """One excerpt at one quality with the given settings: kb/s and metrics."""
    settings, q, name, wav = args
    os.environ["VISQOL"] = ""
    codec = refcodecs.Mule("", q)
    codec.params = dataclasses.replace(codec.params, **settings)
    with tempfile.TemporaryDirectory() as work:
        dec, enc, nbytes = codec.run(wav, work)
        import soundfile as sf
        kbps = nbytes * 8 / sf.info(wav).duration / 1000
        res = metrics.evaluate(wav, dec)
    return {"item": name, "q": q, "kbps": kbps, **{k: res.get(k, np.nan) for k in ("odg", "odg_adv", "mms2f", "nmr_db")}}


def rate_job(args):
    """kb/s of one excerpt encoded at q with the given settings (no decoding, no metric)."""
    settings, q, name, wav = args
    import soundfile as sf
    from mule import native
    codec = refcodecs.Mule("", q)
    p = dataclasses.replace(codec.params, **settings)
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    return native.c_encode(x, p)[1] * 8 / (len(x) / fs) / 1000


def find_qs(settings_list, ex, items):
    """For each candidate, the q of each target rate (mean kb/s over items within TOL): secant on
    q, every candidate's encodes of an iteration in one pool. Rate falls as q rises."""
    def rates(pairs):                           # [(cand, q)] -> mean kb/s each
        tasks = [(settings_list[c], q, n, w) for c, q in pairs for n, w in items]
        r = list(ex.map(rate_job, tasks, chunksize=2))
        k = len(items)
        return [float(np.mean(r[i * k:(i + 1) * k])) for i in range(len(pairs))]
    out = {}
    for t in TARGETS:
        pts = {c: [] for c in range(len(settings_list))}
        q0 = -7.0 - (t - 118.0) / 10.5          # production's slope on these items
        first = [(c, q0) for c in pts] + [(c, q0 - 1.5) for c in pts]
        for (c, q), r in zip(first, rates(first), strict=True):
            pts[c].append((q, r))
        for _ in range(6):
            todo = []
            for c, p in pts.items():
                (qa, ra), (qb, rb) = sorted(p, key=lambda v: abs(v[1] - t))[:2]
                if abs(ra - t) <= TOL:
                    out[(c, t)] = qa
                    continue
                q = qa + (t - ra) * (qb - qa) / (rb - ra) if rb != ra else qa - 0.5
                todo.append((c, float(np.clip(q, qa - 4, qa + 4))))
            if not todo:
                break
            for (c, q), r in zip(todo, rates(todo), strict=True):
                pts[c].append((q, r))
        for c, p in pts.items():                # closest found if not within TOL
            out.setdefault((c, t), min(p, key=lambda v: abs(v[1] - t))[0])
    return out


def at_rate(rows, metric):
    """The corpus curve (mean kb/s, mean metric) through the two measured points, at RATE."""
    df = pd.DataFrame(rows).groupby("q")[["kbps", metric]].mean().sort_values("kbps")
    k, m = df["kbps"].to_numpy(), df[metric].to_numpy()
    return float(m[0] + (m[1] - m[0]) * (RATE - k[0]) / (k[1] - k[0]))


def evaluate_population(xs, ex, items):
    """Each candidate's scores at 128 kb/s (bracketed); every metric job of the generation in one
    pool."""
    settings = [to_settings(x) for x in xs]
    qs = find_qs(settings, ex, items)
    tasks = [(i, (settings[i], qs[(i, t)], n, w)) for i in range(len(xs)) for t in TARGETS for n, w in items]
    rows = list(ex.map(job, [t for _, t in tasks], chunksize=1))
    out = []
    for i in range(len(xs)):
        r = [row for (j, _), row in zip(tasks, rows, strict=True) if j == i]
        s = {m: at_rate(r, m) for m in ("odg", "odg_adv", "mms2f", "nmr_db")}
        lo, hi = (float(np.mean([row["kbps"] for row in r if row["q"] == qs[(i, t)]])) for t in TARGETS)
        s.update(q_lo=qs[(i, TARGETS[0])], q_hi=qs[(i, TARGETS[1])], rate_lo=lo, rate_hi=hi,
                 bracketed=bool(min(lo, hi) <= RATE <= max(lo, hi)))
        s["objective"] = (s["odg"] + s["odg_adv"]) / 2 if s["bracketed"] else -9.0
        out.append(s)
    return out


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def cmd_search(a):
    import cma
    items = search_items()
    x0 = to_unit({k: v[2] for k, v in SPACE.items()})
    es = cma.CMAEvolutionStrategy(x0, a.sigma, {"bounds": [0, 1], "popsize": a.pop, "seed": 1,
                                                "maxiter": a.gens, "verbose": -9})
    rows = []
    best = None
    log(f"M6 search: {len(items)} dev items, rates {TARGETS} around {RATE:g}, popsize {a.pop}, {a.gens} generations, "
        f"base {BASE or 'production'}")
    with ProcessPoolExecutor() as ex:
        base = evaluate_population([x0], ex, items)[0]
        rows.append({"gen": 0, "cand": 0, **to_settings(x0), **base})
        best = rows[-1]
        log(f"production: objective {base['objective']:+.4f} (odg {base['odg']:+.4f}, "
            f"odg_adv {base['odg_adv']:+.4f}, 2f {base['mms2f']:.2f}; q {base['q_lo']:.2f} -> "
            f"{base['rate_lo']:.1f}, q {base['q_hi']:.2f} -> {base['rate_hi']:.1f} kb/s)")
        pd.DataFrame(rows).to_csv(SEARCH_CSV, index=False)
        gen = 0
        while not es.stop():
            gen += 1
            xs = es.ask()
            scores = evaluate_population(xs, ex, items)
            es.tell(xs, [-s["objective"] for s in scores])
            for i, (x, s) in enumerate(zip(xs, scores, strict=True)):
                rows.append({"gen": gen, "cand": i, **to_settings(x), **s})
                if s["objective"] > best["objective"]:
                    best = rows[-1]
            pd.DataFrame(rows).to_csv(SEARCH_CSV, index=False)
            json.dump({**BASE, **{k: best[k] for k in KEYS}}, open(BEST_JSON, "w"), indent=1)
            gbest = max(scores, key=lambda s: s["objective"])
            log(f"gen {gen}: best of gen {gbest['objective']:+.4f}, best so far {best['objective']:+.4f} "
                f"({best['objective'] - base['objective']:+.4f} over production) "
                + " ".join(f"{k}={best[k]:.3g}" for k in KEYS))
    log("search done")


def cmd_best(a):
    df = pd.read_csv(SEARCH_CSV)
    base = df[df.gen == 0].iloc[0]
    print(df.sort_values("objective", ascending=False).head(10)[["gen", *KEYS, "objective", "odg", "odg_adv", "mms2f", "nmr_db"]]
          .to_string(index=False))
    print(f"production objective {base.objective:+.4f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["search", "best"])
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--pop", type=int, default=8)
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--base", default="", help="fixed integer settings, e.g. tcq_chain=1,tcq_states=64")
    ap.add_argument("--tag", default="", help="suffix of the result files")
    a = ap.parse_args()
    for kv in filter(None, a.base.split(",")):
        k, v = kv.split("=")
        BASE[k] = int(v)
    if a.tag:
        globals()["SEARCH_CSV"] = os.path.join(RESULTS, f"m6_search_{a.tag}.csv")
        globals()["BEST_JSON"] = os.path.join(RESULTS, f"m6_best_{a.tag}.json")
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
