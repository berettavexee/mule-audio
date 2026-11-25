"""A zero in both TCQ rulers (VVC's dependent quantization) on the real coefficients of `dev`: the
values the encoder quantizes (its trace: x256, in units of step / 2), re-quantized by MULE's TCQ
and by the VVC-style odd ruler of eval/tcq_zero_sim.py, same trellis (64 states), RD Viterbi.

Production --bitrate settings at --rate kb/s; one chain per frame, channel and group (as the
encoder: the state carried from band to band), every --every-th frame of every --step-th item of
dev. The rate of an index: -log2 of its frequency given the allocation class and the ruler
(the codec's contexts are richer: absolute bits are not the codec's, the difference is the
point), from the previous pass. Distortion: mean squared error in units of (step / 2)^2.
Each method's curve is the lower envelope over value scales (a step change) and lambdas; the
gain is read at the entropy of the codec's own levels (trace), both as MSE (dB) at equal
entropy and as bits at equal MSE.

  python eval/tcq_zero_dev.py [--rate 128] [--every 4] [--step 2]   (prints only, writes nothing)
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
from tcq_sim import MASK64  # noqa: E402
from tcq_zero_sim import KR, envelope, members  # noqa: E402

NAC = 16


def chains(rate, every, step):
    """The coefficients' values (step / 2 units), classes and codec levels, one row per chain
    (padded; mask w)."""
    import soundfile as sf
    from mule import native, params as mp
    F = native.TRACE_FIELDS["coef"]
    ci = {f: i for i, f in enumerate(F)}
    seqs = []
    secs = 0.0
    for name, wav in corpus.items("dev")[::step]:
        x, fs = sf.read(wav, dtype="float64", always_2d=True)
        secs += len(x) / fs
        _m, _v, _f, tr = native.c_trace(x, mp.for_bitrate(rate))
        c = tr[tr[:, 0] == 0]
        c = c[c[:, ci["frame"]] % every == 0]
        key = c[:, ci["frame"]] * 2 + c[:, ci["ch"]]
        cut = np.flatnonzero((np.diff(key) != 0) | (np.diff(c[:, ci["band"]]) < 0)) + 1
        for s in np.split(np.arange(len(c)), cut):
            if len(s):
                seqs.append((c[s, ci["x256"]] / 256.0, c[s, ci["ac"]], c[s, ci["level"]]))
        print(f"  {name}: {len(c)} coefficients", flush=True)
    L = max(len(s[0]) for s in seqs)
    B = len(seqs)
    X = np.zeros((B, L))
    AC = np.zeros((B, L), np.int64)
    LV = np.zeros((B, L), np.int64)
    W = np.zeros((B, L), bool)
    for i, (v, a, lv) in enumerate(seqs):
        X[i, :len(v)], AC[i, :len(v)], LV[i, :len(v)], W[i, :len(v)] = v, a, lv, True
    return X, AC, LV, W, secs * 1.0 / every


def viterbi(x, ac, w, n, mask, method, rate, lam):
    s = np.arange(n)
    g = np.array([bin(v & mask).count("1") & 1 for v in s])
    p1, p2 = s >> 1, (s >> 1) + n // 2
    br = s & 1
    combo1, combo2 = 2 * (p1 & 1) + (br ^ g[p1]), 2 * (p2 & 1) + (br ^ g[p2])
    B, L = x.shape
    cost = np.where(s[None] == 0, 0.0, np.inf) * np.ones((B, 1))
    back = np.zeros((B, L, n), bool)
    kbest = np.zeros((B, L, 4), np.int64)
    for i in range(L):
        xi, ai, wi = x[:, i], ac[:, i], w[:, i]
        base = np.round(xi).astype(np.int64)
        cc = np.full((B, 4), np.inf)
        for d in range(-5, 6):
            k = base + d
            kc = np.clip(k, -KR, KR) + KR
            dist = (xi - k) ** 2
            for r in (0, 1):
                rr = rate[ai, r, kc]
                for p in (0, 1):
                    j = 2 * r + p
                    c = np.where(members(method, r, p, k), dist + lam * rr, np.inf)
                    pick = c < cc[:, j]
                    cc[:, j] = np.where(pick, c, cc[:, j])
                    kbest[:, i, j] = np.where(pick, k, kbest[:, i, j])
        cc = np.where(wi[:, None], cc, 0.0)     # padding: free, any branch
        c1, c2 = cost[:, p1] + cc[:, combo1], cost[:, p2] + cc[:, combo2]
        pick = c2 < c1
        back[:, i] = pick
        cost = np.where(pick, c2, c1)
    st = np.argmin(cost, 1)
    k = np.zeros((B, L), np.int64)
    ruler = np.zeros((B, L), np.int64)
    rows = np.arange(B)
    for i in range(L - 1, -1, -1):
        pred = np.where(back[rows, i, st], (st >> 1) + n // 2, st >> 1)
        r, p = pred & 1, (st & 1) ^ g[pred]
        k[:, i] = kbest[rows, i, 2 * r + p]
        ruler[:, i] = r
        st = pred
    return k, ruler


def stats(k, ruler, ac, w):
    """Rate tables [class, ruler, level] and the entropy per coefficient (index | class, ruler)."""
    tab = np.zeros((NAC, 2, 2 * KR + 1))
    h = 0.0
    tot = w.sum()
    for a in range(NAC):
        for r in (0, 1):
            sel = w & (ac == a) & (ruler == r)
            c = np.bincount(np.clip(k[sel], -KR, KR) + KR, minlength=2 * KR + 1).astype(float)
            if c.sum():
                q = c[c > 0] / c.sum()
                h += c.sum() / tot * -(q * np.log2(q)).sum()
            tab[a, r] = -np.log2((c + 0.05) / (c.sum() + 0.05 * len(c)))
    return tab, h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=int, default=128)
    ap.add_argument("--every", type=int, default=4)
    ap.add_argument("--step", type=int, default=2)
    a = ap.parse_args()
    X, AC, LV, W, secs = chains(a.rate, a.every, a.step)
    ncoef = W.sum()
    print(f"{X.shape[0]} chains, {ncoef} coefficients ({ncoef / secs / 1000:.1f} k coefficients/s coded)")
    # the codec's own levels: ruler = level parity (MULE)
    _t, h_codec = stats(LV, LV & 1, AC, W)
    mse_codec = np.mean((X[W] - LV[W]) ** 2)
    print(f"codec's levels: {h_codec:.3f} bits/coefficient (index | class, ruler), MSE {mse_codec:.4f}")
    for lo, hi in ((0, 1), (1, 2), (2, 16)):
        sel = W & (AC >= lo) & (AC < hi)
        print(f"  class {lo}-{hi - 1}: {sel.sum() / ncoef:.1%} of the coefficients, "
              f"zeros {np.mean(LV[sel] == 0):.1%}, odd levels {np.mean(LV[sel] & 1):.1%}")
    pts = {}
    for method in ("mule", "vvc"):
        pts[method] = []
        for sc in (0.85, 1.0, 1.15):
            for lam in (0.25, 0.5, 1.0):
                rate = np.zeros((NAC, 2, 2 * KR + 1))
                for it in range(3):
                    k, ruler = viterbi(X * sc, AC, W, 64, MASK64, method, rate, lam if it else 0.0)
                    rate, h = stats(k, ruler, AC, W)
                m = np.mean((X[W] * sc - k[W]) ** 2) / sc ** 2      # back to the codec's units
                pts[method].append((h, m))
                print(f"  {method:4s} scale {sc:.2f} lambda {lam:.2f}: {h:.3f} bits, MSE {m:.4f}", flush=True)
    hs = np.array([h_codec * f for f in (0.8, 0.9, 1.0, 1.1, 1.2)])
    em, ev = envelope(pts["mule"], hs), envelope(pts["vvc"], hs)
    print("\nentropy (bits/coef): " + " ".join(f"{h:.3f}" for h in hs))
    print("vvc over mule, MSE (dB, + = better): " + " ".join(f"{10 * (m - v):+.3f}" for m, v in zip(em, ev)))
    # bits at equal MSE, at the codec's entropy
    hh = np.linspace(min(p[0] for p in pts["mule"] + pts["vvc"]), max(p[0] for p in pts["mule"] + pts["vvc"]), 400)
    em_f, ev_f = envelope(pts["mule"], hh), envelope(pts["vvc"], hh)
    target = np.interp(h_codec, hh, em_f)
    ok = ~np.isnan(ev_f)
    o = np.argsort(ev_f[ok])                    # log MSE ascending (np.interp needs it)
    h_v = np.interp(target, ev_f[ok][o], hh[ok][o])
    dh = h_codec - h_v
    print(f"at the codec's entropy {h_codec:.3f}: vvc saves {dh:+.3f} bits/coefficient "
          f"({100 * dh / h_codec:+.1f} % of the coefficients' index bits, about "
          f"{dh * ncoef / secs / 1000:.2f} kb/s)")


if __name__ == "__main__":
    main()
