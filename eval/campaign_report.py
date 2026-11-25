"""The statistics of eval/campaign.py: each codec at equal mean rate, paired comparisons.

Rate matching: for a codec and a target rate R, the two settings whose mean rates over the corpus
bracket R, mixed with the weight that gives R exactly; every item's metrics (and rate) mixed with
that same weight. Each codec is thus taken at the setting a user would pick for R kb/s on average,
item rates varying as VBR does.

Paired comparisons (A against B, same items): the mean difference oriented so that > 0 means A is
better, a 95 % confidence interval by a bootstrap over artists (the clusters: tracks of an artist
are not independent), the Wilcoxon signed-rank test (Holm-corrected over all the comparisons of the
report), and the share of items where A is better.
"""
import csv
import itertools
import json
import os

import numpy as np

METRICS = [  # (column, label, +1 if higher is better, scale shown)
    ("zimt", "Zimtohrli distance x 10^4", -1, 1e4),
    ("odg", "PEAQ basic ODG", +1, 1),
    ("odg_adv", "PEAQ advanced ODG", +1, 1),
    ("nmr_db", "NMR (dB)", -1, 1),
]
NAMES = {"mule": "MULE v5", "opus": "Opus (libopus 1.6.1)", "aac": "Apple AAC (TVBR)",
         "mule_ath20": "MULE v5, ATH -20 dB", "mule_athrg": "MULE v5, ATH by ReplayGain",
         "mule_athl": "MULE v5, relative ATH"}
BOOT = 10000


def load(path):
    rows = list(csv.DictReader(open(path)))
    out = {}
    for r in rows:
        d = out.setdefault(r["config"], {})
        d[r["item"]] = {k: float(v) for k, v in r.items() if k not in ("config", "item") and v != ""}
    return out


def matched(res, configs, rate, items):
    """{item: {metric: value, "kbps": rate}} of a codec at mean rate `rate`, the settings used and
    the weight; None if its settings do not bracket the rate"""
    pts = sorted((np.mean([res[c][i]["kbps"] for i in items]), c) for c in configs)
    for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
        if r0 <= rate <= r1:
            w = (rate - r0) / (r1 - r0)
            vals = {}
            for i in items:
                a, b = res[c0][i], res[c1][i]
                vals[i] = {k: (1 - w) * a[k] + w * b[k] for k in a if k in b}
            return vals, (c0, c1, w)
    return None, None


def boot_ci(diff, clusters, rng):
    """95 % interval of the mean of diff, resampling the clusters"""
    groups = {}
    for d, c in zip(diff, clusters):
        groups.setdefault(c, []).append(d)
    keys = list(groups)
    sums = np.array([np.sum(groups[k]) for k in keys])
    cnts = np.array([len(groups[k]) for k in keys])
    idx = rng.integers(0, len(keys), size=(BOOT, len(keys)))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return np.percentile(means, [2.5, 97.5])


def holm(ps):
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def main(results, tracks, configs, rates, tag="", exclude=None):
    """exclude: {item: reason}, items left out of the report (still encoded by run)."""
    from scipy.stats import wilcoxon
    res = load(results)
    meta = json.load(open(tracks))
    artist = {t["item"]: t["artist"] for t in meta["tracks"]}
    allc = [c for fam in configs.values() for c in fam]
    exclude = exclude or {}
    items = sorted(i for i in artist if i not in exclude and all(c in res and i in res[c] for c in allc))
    rng = np.random.default_rng(2026)
    L = [f"# MULE v5, Opus and Apple AAC on {len(items)} tracks", "",
         f"{len(items)} excerpts of {meta['excerpt_s']:.0f} s (the middle of each track), "
         f"{len(set(artist[i] for i in items))} artists, drawn at random (seed {meta['seed']}). "
         "Each codec at the setting whose mean rate over these excerpts is the target "
         "(interpolated between its two nearest settings), audio payload only."
         + "".join(f" Left out: {i} ({why})." for i, why in sorted(exclude.items())), ""]
    table, comps = {}, []
    for rate in rates:
        per = {}
        for fam, cfgs in configs.items():
            vals, how = matched(res, cfgs, rate, items)
            if vals:
                per[fam] = (vals, how)
        table[rate] = per
    # means
    L += ["## Means at equal rate", "",
          "| kb/s | codec | settings (weight) | " + " | ".join(m[1] for m in METRICS) + " |",
          "|---|---|---|" + "---|" * len(METRICS)]
    for rate, per in table.items():
        for fam, (vals, (c0, c1, w)) in per.items():
            cells = []
            for col, _lab, _s, k in METRICS:
                v = k * np.array([vals[i][col] for i in items if col in vals[i]])
                cells.append(f"{v.mean():.3f}" if len(v) else "-")
            L.append(f"| {rate} | {NAMES.get(fam, fam)} | {c0} / {c1} ({w:.2f}) | " + " | ".join(cells) + " |")
    L.append("")
    # paired comparisons
    for rate, per in table.items():
        for fa, fb in itertools.combinations(per, 2):
            va, vb = per[fa][0], per[fb][0]
            for col, lab, sgn, k in METRICS:
                its = [i for i in items if col in va[i] and col in vb[i]]
                if len(its) < 10:
                    continue
                d = sgn * k * (np.array([va[i][col] for i in its]) - np.array([vb[i][col] for i in its]))
                lo, hi = boot_ci(d, [artist[i] for i in its], rng)
                p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
                comps.append(dict(rate=rate, a=fa, b=fb, metric=lab, n=len(its), mean=d.mean(),
                                  lo=lo, hi=hi, p=p, win=np.mean(d > 0), tie=np.mean(d == 0)))
    if comps:
        for c, pa in zip(comps, holm(np.array([c["p"] for c in comps]))):
            c["p_holm"] = pa
    L += ["## Paired comparisons", "",
          "A minus B, oriented so that a positive difference means A is better; 95 % interval by a "
          "bootstrap over artists; Wilcoxon signed-rank p, Holm-corrected over the "
          f"{len(comps)} comparisons; share of tracks where A is better.", "",
          "| kb/s | A vs B | metric | mean difference [95 % CI] | p (Holm) | A better on |",
          "|---|---|---|---|---|---|"]
    for c in comps:
        sig = "**" if c["p_holm"] < 0.05 and (c["lo"] > 0 or c["hi"] < 0) else ""
        L.append(f"| {c['rate']} | {NAMES.get(c['a'], c['a'])} vs {NAMES.get(c['b'], c['b'])} | {c['metric']} | "
                 f"{sig}{c['mean']:+.4f} [{c['lo']:+.4f}, {c['hi']:+.4f}]{sig} | {c['p_holm']:.2g} | "
                 f"{100 * c['win']:.0f} % |")
    L += ["", "Bold: significant at 5 % after correction, interval excluding zero. These are "
          "objective measures, not listening tests: they say where the codecs differ on average by "
          "these models of hearing, not that a listener hears it.", ""]
    out = os.path.join(os.path.dirname(results), f"report{tag}.md")
    with open(out, "w") as f:
        f.write("\n".join(L))
    # the interpolated per-item values, for figures
    with open(os.path.join(os.path.dirname(results), f"matched{tag}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rate", "codec", "item", "artist", "kbps"] + [m[0] for m in METRICS])
        for rate, per in table.items():
            for fam, (vals, _how) in per.items():
                for i in items:
                    w.writerow([rate, fam, i, artist[i], round(vals[i]["kbps"], 2)]
                               + [f"{vals[i].get(m[0], np.nan):.6g}" for m in METRICS])
    print("\n".join(L))
    print(f"(written to {out})")
