"""How MULE's coded coefficients are distributed before quantization, from the encoder's trace
(format v3, default settings): the shape of the distribution, small values, signs, neighbours.
Values are in units of the step D (the scalar step; TCQ levels are at D/2).

    python eval/coef_stats.py [--set dev] [--items a,b] [-j N]     (prints only, writes nothing)

Each item is analysed in its own worker, which returns aggregates only (memory bounded by one
item per worker).

1. shape: kurtosis and the generalized Gaussian shape β fitted by moments (β = 1 Laplacian, 2
   Gaussian), overall and per allocation class;
2. small values: share of |x| < D/4, D/2, D; share of TCQ levels that are not the nearest
   level of the allowed ruler (rate-driven choices);
3. signs: P(+); agreement with the previous line's sign (same band) and with the same line's sign
   in the previous long frame; conditional entropy of the sign given those two signs (the bits a
   sign context could save), for all coefficients and for large ones (|x| ≥ 2D);
4. neighbours: Spearman correlation of |x| with the previous line and the previous frame.
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "py"))
sys.path.insert(0, HERE)


BUCKETS = ((1, 3), (3, 6), (6, 9), (9, 12), (12, 16))
THRESH = (0.25, 0.5, 1.0, 2.0)
SAMPLE = 20000                                   # pairs per item kept for the rank correlations


def one(path):
    """The aggregates of one item (all its arrays stay in this worker)."""
    import soundfile as sf
    from mule import native, params
    xin, _ = sf.read(path, dtype="float64", always_2d=True)
    _, _, _, tr = native.c_trace(xin, params.Params())
    co = tr[tr[:, 0] == 0]
    del tr
    frame, ch, typ, band, line, ac, level, x256 = (co[:, j].astype(np.int64) for j in (2, 3, 4, 5, 6, 7, 16, 17))
    x = x256 / 512.0                                 # in units of D
    ax_ = np.abs(x)
    r = {"n": len(x), "n_long": int(np.sum(typ == 0))}
    mom = []
    for lo, hi in ((0, 99),) + BUCKETS:
        m = (ac >= lo) & (ac < hi)
        v = x[m]
        mom.append([m.sum(), np.abs(v).sum(), (v ** 2).sum(), (v ** 4).sum()])
    r["mom"] = np.array(mom)
    r["small"] = np.array([np.sum(ax_ < t) for t in THRESH])
    r["level0"], r["odd"] = int(np.sum(level == 0)), int(np.sum(level % 2 != 0))
    k2 = x256 / 256.0
    par = np.abs(level) % 2
    nearest = np.where(par == 0, 2 * np.round(k2 / 2), 2 * np.round((k2 - 1) / 2) + 1)
    nn = nearest != level
    r["notnear"], r["tozero"] = int(nn.sum()), int(np.sum(np.abs(level[nn]) < np.abs(nearest[nn])))
    signed = level != 0
    s = (level > 0).astype(int)
    key = frame * 4 + ch
    prev_line = np.r_[False, (key[1:] == key[:-1]) & (band[1:] == band[:-1]) & (line[1:] == line[:-1] + 1)]
    sp, lp = np.r_[0, s[:-1]], np.r_[0, level[:-1]]
    fkey = (frame * 2 + ch) * 1024 + line
    longi = np.flatnonzero(typ == 0)
    order = longi[np.argsort(fkey[longi])]
    skeys = fkey[order]
    want = fkey - 2 * 1024
    pos = np.clip(np.searchsorted(skeys, want), 0, len(skeys) - 1)
    pidx = np.where((skeys[pos] == want) & (typ == 0), order[pos], -1)
    pf = np.where(pidx >= 0, level[np.maximum(pidx, 0)], 0)
    m1 = signed & prev_line & (lp != 0)
    m2 = signed & (pf != 0)
    r["signed"], r["plus"] = int(signed.sum()), int(np.sum(s[signed]))
    r["m1"], r["m1_same"] = int(m1.sum()), int(np.sum(s[m1] == sp[m1]))
    r["m2"], r["m2_same"] = int(m2.sum()), int(np.sum(s[m2] == (pf[m2] > 0)))
    ctx = np.where(m1, 1 + (lp > 0), 0) * 3 + np.where(pf != 0, 1 + (pf > 0), 0)
    tabs = []
    for m in (signed, signed & (ax_ >= 2)):
        t = np.zeros((9, 2), np.int64)
        np.add.at(t, (ctx[m], s[m]), 1)
        tabs.append(t)
    r["ctx"] = tabs
    rng = np.random.default_rng(len(x))
    i1 = np.flatnonzero(prev_line)
    i1 = rng.choice(i1, min(SAMPLE, len(i1)), replace=False)
    r["pair_line"] = np.c_[ax_[i1], ax_[i1 - 1]]
    i2 = np.flatnonzero(pidx >= 0)
    xs, ys = x[i2], x[pidx[i2]]
    r["pear"] = np.array([len(xs), xs.sum(), ys.sum(), (xs * xs).sum(), (ys * ys).sum(), (xs * ys).sum()])
    j = rng.choice(len(i2), min(SAMPLE, len(i2)), replace=False)
    r["pair_frame"] = np.c_[np.abs(xs[j]), np.abs(ys[j])]
    return r


def h2(p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


def cond_entropy(sign, ctx):
    """H(sign | ctx) in bits, ctx an integer array."""
    h = 0.0
    for c in np.unique(ctx):
        m = ctx == c
        h += m.mean() * h2(sign[m].mean())
    return h


def spearman(a, b):
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return np.corrcoef(ra, rb)[0, 1]


def beta_from(m):
    from scipy.optimize import brentq
    from scipy.special import gamma
    n, s1, s2, _ = m
    rat = (s1 / n) ** 2 / (s2 / n)
    f = lambda b: gamma(2 / b) ** 2 / (gamma(1 / b) * gamma(3 / b)) - rat  # noqa: E731
    try:
        return brentq(f, 0.1, 10)
    except ValueError:
        return np.nan


def ctx_entropy(t):
    n = t.sum()
    h = 0.0
    for row in t:
        if row.sum():
            h += row.sum() / n * h2(row[1] / row.sum())
    return h


def main():
    import corpus
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default="dev")
    ap.add_argument("--items")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 6))
    a = ap.parse_args()
    items = corpus.items(a.set)
    if a.items:
        keep = set(a.items.split(","))
        items = [it for it in items if it[0] in keep]
    with ProcessPoolExecutor(a.j) as ex:
        R = list(ex.map(one, [p for _, p in items]))
    S = lambda k: sum(r[k] for r in R)  # noqa: E731
    n = S("n")
    print(f"{len(items)} items, {n} coded coefficients ({S('n_long') / n:.1%} in long frames)")
    mom = S("mom")
    print("\n1. shape (x in units of D)")
    c, s1, s2, s4 = mom[0]
    print(f"   all: E|x| {s1 / c:.3f}, rms {np.sqrt(s2 / c):.3f}, kurtosis {(s4 / c) / (s2 / c) ** 2:.2f} "
          f"(Laplacian 6, Gaussian 3), shape beta {beta_from(mom[0]):.2f} (a mixture: see per class)")
    for (lo, hi), m in zip(BUCKETS, mom[1:], strict=True):
        if m[0] > 1000:
            print(f"   allocation class {lo:2d}-{hi - 1:2d}: {m[0] / n:5.1%} of coefs, rms {np.sqrt(m[2] / m[0]):6.2f} D, "
                  f"kurtosis {(m[3] / m[0]) / (m[2] / m[0]) ** 2:6.2f}, beta {beta_from(m):.2f}")
    print("\n2. small values")
    for t, v in zip(THRESH, S("small"), strict=True):
        print(f"   |x| < {t:4.2f} D: {v / n:6.1%}")
    print(f"   level 0: {S('level0') / n:.1%}; odd levels (no zero, sign always coded): {S('odd') / n:.1%}")
    print(f"   TCQ level not the nearest of its ruler (rate-driven): {S('notnear') / n:.1%}; "
          f"of which towards zero: {S('tozero') / S('notnear'):.1%}")
    print(f"   coded signs: {S('signed') / n:.1%} of coefficients")
    print("\n3. signs (of the coded level, where a sign is written)")
    print(f"   P(+) {S('plus') / S('signed'):.4f}")
    print(f"   same sign as the previous line (both non-zero): {S('m1_same') / S('m1'):.3f} ({S('m1') / n:.0%} of coefs)")
    print(f"   same sign as the same line in the previous long frame: {S('m2_same') / S('m2'):.3f} ({S('m2') / n:.0%} of coefs)")
    for lab, k in (("all signs", 0), ("|x| >= 2D", 1)):
        hc = ctx_entropy(sum(r["ctx"][k] for r in R))
        print(f"   {lab}: H(sign | previous line, previous frame) = {hc:.4f} bit: saving {1 - hc:.2%} of the sign bits")
    print("\n4. neighbours (|x|, rank correlations on a sample of pairs)")
    pl = np.concatenate([r["pair_line"] for r in R])
    pfr = np.concatenate([r["pair_frame"] for r in R])
    print(f"   Spearman |x| vs previous line (same band): {spearman(pl[:, 0], pl[:, 1]):.3f} ({len(pl)} pairs)")
    print(f"   Spearman |x| vs same line, previous long frame: {spearman(pfr[:, 0], pfr[:, 1]):.3f} ({len(pfr)} pairs)")
    k_, sx, sy, sxx, syy, sxy = S("pear")
    cov = sxy / k_ - (sx / k_) * (sy / k_)
    print(f"   Pearson x vs same line, previous long frame (signed): "
          f"{cov / np.sqrt((sxx / k_ - (sx / k_) ** 2) * (syy / k_ - (sy / k_) ** 2)):.3f}")


if __name__ == "__main__":
    main()
