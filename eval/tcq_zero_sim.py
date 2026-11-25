"""A zero in both rulers of the TCQ (VVC's dependent quantization) against MULE's TCQ, on the
model of eval/tcq_sim.py (generalized Gaussian samples cut into MULE's long-frame bands, one
Viterbi over the frame), with a rate-distortion Viterbi, at equal first-order entropy.

Levels k in units of step / 2. The state's parity picks the ruler (even: Q0, odd: Q1), the
branch the index parity p, through MULE's trellis family (eval/tcq_sim.py: branch br from state
s leads to (2 s + br) mod N, p = br ^ parity(s & mask)):
  mule : Q0 = even k, p = (k / 2) mod 2; Q1 = odd k, p = ((k - 1) / 2) mod 2 (k mod 4: no zero,
         +1 and -1 in different subsets) -- core/enc_tcq.c
  vvc  : Q0 the same; Q1 = {0, +-1, +-3, +-5, ...}, index q (0 -> 0, k > 0 -> (k + 1) / 2,
         k < 0 -> (k - 1) / 2), p = q mod 2: zero in both rulers, sign-symmetric
         (Schwarz et al., IEEE TCSVT 31(10), 2021)
  bias : mule's quantizer, the encoder pushed toward one sign for the near-zero levels of the odd
         ruler (k = +1 rather than -1: the first pass charges -1 BIAS extra bits; the later passes
         keep what that leaves in the frequencies, five passes): a "cheated", predictable sign,
         coded at its frequency. A fixed preference is as good as any pattern the decoder could
         know (an XOR with a known pattern is a bijection); its price is the trellis branch,
         which the sign of +-1 chooses in the odd ruler (k mod 4)
The rate of an index is -log2 of its frequency given the ruler, estimated from the previous pass
(three passes); the coded entropy is that of the index given the ruler. Each method's curve is
the lower envelope over steps and lambdas; gains are MSE (dB) against MULE's TCQ with the same
number of states, at the same entropy.

  python eval/tcq_zero_sim.py [--frames 150] [--beta 1.1 0.7]     (prints only, writes nothing)
"""
import argparse

import numpy as np

from tcq_sim import MASK64, WIDTHS, source

KR = 40                                         # |k| range of the rate tables


def members(method, ruler, p, k):
    """Is level k (int array) in ruler `ruler` with index parity p?"""
    if ruler == 0:
        return (k % 2 == 0) & ((k // 2) % 2 == p)
    if method == "mule":
        return (k % 2 == 1) & (((k - 1) // 2) % 2 == p)
    q = index_q1(k)
    return ((k == 0) | (k % 2 == 1)) & (q % 2 == p)


def index_q1(k):
    return np.where(k > 0, (k + 1) // 2, np.where(k < 0, (k - 1) // 2, 0))


def best_in_set(x, method, ruler, p, rate, lam):
    """Per sample: the RD-best level of the set (ruler, p), and its cost."""
    base = np.round(x).astype(np.int64)
    best_c = np.full(x.shape, np.inf)
    best_k = np.zeros(x.shape, np.int64)
    for d in range(-5, 6):
        k = base + d
        ok = members(method, ruler, p, k)
        c = (x - k) ** 2 + lam * rate[ruler][np.clip(k, -KR, KR) + KR]
        c = np.where(ok, c, np.inf)
        pick = c < best_c
        best_c = np.where(pick, c, best_c)
        best_k = np.where(pick, k, best_k)
    return best_k, best_c


def viterbi(x, n, mask, method, rate, lam):
    s = np.arange(n)
    g = np.array([bin(v & mask).count("1") & 1 for v in s])
    p1, p2 = s >> 1, (s >> 1) + n // 2             # predecessors of state t; branch br = t & 1
    br = s & 1
    combo1 = 2 * (p1 & 1) + (br ^ g[p1])           # (ruler, parity) column of each branch
    combo2 = 2 * (p2 & 1) + (br ^ g[p2])
    B, L = x.shape
    cost = np.where(s[None] == 0, 0.0, np.inf) * np.ones((B, 1))
    back = np.zeros((B, L, n), bool)
    for i in range(L):
        xi = x[:, i]
        cc = np.stack([best_in_set(xi, method, r, p, rate, lam)[1] for r in (0, 1) for p in (0, 1)], 1)
        c1 = cost[:, p1] + cc[:, combo1]
        c2 = cost[:, p2] + cc[:, combo2]
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
        xi = x[:, i]
        for rr in (0, 1):
            for pp in (0, 1):
                sel = (r == rr) & (p == pp)
                if sel.any():
                    kk, _ = best_in_set(xi[sel], method, rr, pp, rate, lam)
                    k[sel, i] = kk
        ruler[:, i] = r
        st = pred
    return k, ruler


def rates_from(k, ruler):
    """-log2 frequency of each level given the ruler (smoothed), and the coded entropy."""
    tab, h = [], 0.0
    for r in (0, 1):
        v = np.clip(k[ruler == r], -KR, KR) + KR
        c = np.bincount(v, minlength=2 * KR + 1).astype(float)
        if c.sum():
            q = c[c > 0] / c.sum()
            h += c.sum() / k.size * -(q * np.log2(q)).sum()
        tab.append(-np.log2((c + 0.05) / (c.sum() + 0.05 * len(c))))
    return tab, h


BIAS = 2.0


def run(x, n, mask, method, step, lam):
    xs = x / (step / 2)
    rate = [np.zeros(2 * KR + 1), np.zeros(2 * KR + 1)]
    q = "mule" if method == "bias" else method
    passes = 3
    if method == "bias":
        rate[1][KR - 1] = BIAS                  # k = -1 in the odd ruler
        passes = 5
    for it in range(passes):
        k, ruler = viterbi(xs, n, mask, q, rate, lam if (it or method == "bias") else 0.0)
        rate, h = rates_from(k, ruler)
    odd1 = np.abs(k[ruler == 1]) == 1
    plus = np.mean(k[ruler == 1][odd1] > 0) if odd1.any() else np.nan
    return h, np.mean((x - k * step / 2) ** 2), plus


def envelope(points, hs):
    """log10 MSE of the lower envelope at entropies hs (points: (h, mse))."""
    pts = sorted(points)
    hull = []
    for h, m in pts:                            # lower convex hull in (h, log mse)
        lm = np.log10(m)
        while len(hull) >= 2 and ((hull[-1][1] - hull[-2][1]) * (h - hull[-2][0])
                                  >= (lm - hull[-2][1]) * (hull[-1][0] - hull[-2][0])):
            hull.pop()
        hull.append((h, lm))
    hh, ll = np.array(hull).T
    return np.where((hs >= hh.min()) & (hs <= hh.max()), np.interp(hs, hh, ll), np.nan)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--beta", type=float, nargs="+", default=[1.1, 0.7])
    ap.add_argument("--states", type=int, nargs="+", default=[8, 64])
    ap.add_argument("--methods", nargs="+", default=["vvc"], help="compared with mule: vvc, bias")
    a = ap.parse_args()
    hs = np.array([0.3, 0.5, 0.75, 1.0, 1.5, 2.0])
    steps = np.geomspace(0.6, 6.0, 9)
    lams = (0.0, 0.1, 0.25, 0.5)
    L = sum(WIDTHS) * 8
    for beta in a.beta:
        x = source(np.random.default_rng(1), beta, (a.frames, L))
        print(f"\nbeta {beta:g}: {a.frames} frames of {L} samples; MSE gain over mule (dB) "
              f"at entropy (bits/sample): " + " ".join(f"{h:g}" for h in hs), flush=True)
        for n in a.states:
            mask = {8: 0b110, 64: MASK64}[n]
            env, plus = {}, {}
            for method in ("mule", *a.methods):
                pts = []
                for st in steps:
                    for lam in lams:
                        h, m, pl = run(x, n, mask, method, st, lam)
                        pts.append((h, m))
                        plus.setdefault(method, []).append(pl)
                env[method] = envelope(pts, hs)
            for method in a.methods:
                gain = 10 * (env["mule"] - env[method])
                print(f"  {n:2d} states, {method:5s}: " + " ".join(f"{g:+6.3f}" for g in gain)
                      + f"   (share of +1 among the odd ruler's +-1: {np.nanmean(plus[method]):.2f})", flush=True)


if __name__ == "__main__":
    main()
