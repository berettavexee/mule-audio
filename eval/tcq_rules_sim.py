"""TCQ with more than two rulers, on eval/tcq_sim.py's model (samples of shape --beta, default
0.7, cut into MULE's long-frame bands, MSE at equal first-order entropy against a uniform scalar quantizer).

K rulers: the fine grid has a step of D/K (levels k in units of D/K), cut into 2K subsets
(k mod 2K); ruler r is the union of the subsets r and r + K, step D, offset r·D/K. The state s
imposes ruler s mod K; branch br leads to (2s + br) mod N and uses the subset
r + K·(br ^ parity(s & mask)). K = 2 is MULE's TCQ (tcq_sim.py, same numbers). The mask of each
(K, N) is the best of an exhaustive search (MSE at a fixed step, as in tcq_sim.py --masks).

The index coded given the ruler is (k - r) / K: the entropy is that of k given k mod K. Rulers
other than r = 0 have no zero level: their sign is always coded, which the entropy counts.

    python eval/tcq_rules_sim.py [--frames 400]      (prints only, writes nothing)
"""
import argparse

import numpy as np

from tcq_sim import WIDTHS, entropy, gain_db, source


def viterbi(x, K, n, mask, start=None):
    """MSE Viterbi over x [B, L] (units of D/K) from state 0 (or start[B]): the levels k."""
    s = np.arange(n)
    g = np.array([bin(v & mask).count("1") & 1 for v in s])
    sub = np.stack([(s % K) + K * (0 ^ g), (s % K) + K * (1 ^ g)], 1)
    B, L = x.shape
    p1, p2 = s >> 1, (s >> 1) + n // 2
    br = s & 1
    j1, j2 = sub[p1, br], sub[p2, br]
    back = np.zeros((B, L, n), bool)
    st0 = np.zeros(B, int) if start is None else start
    cost = np.where(s[None] == st0[:, None], 0.0, np.inf)
    m = 2 * K
    for i in range(L):
        xi = x[:, i:i + 1]
        k1 = np.round((xi - j1) / m) * m + j1
        k2 = np.round((xi - j2) / m) * m + j2
        c1 = cost[:, p1] + (xi - k1) ** 2
        c2 = cost[:, p2] + (xi - k2) ** 2
        pick = c2 < c1
        back[:, i] = pick
        cost = np.where(pick, c2, c1)
    k = np.zeros((B, L))
    st = np.argmin(cost, axis=1)
    rows = np.arange(B)
    for i in range(L - 1, -1, -1):
        pred = np.where(back[rows, i, st], (st >> 1) + n // 2, st >> 1)
        j = sub[pred, st & 1]
        k[:, i] = np.round((x[:, i] - j) / m) * m + j
        st = pred
    return k


def quantize(x, K, n, mask, edges, chain):
    if chain:
        return viterbi(x, K, n, mask)
    out = np.zeros_like(x)
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        out[:, a:b] = viterbi(x[:, a:b], K, n, mask)
    return out


def entropy_given_ruler(k, K):
    k = k.astype(np.int64).ravel()
    r = k % K
    h = 0.0
    for v in range(K):
        sel = k[r == v]
        if len(sel):
            _, c = np.unique(sel, return_counts=True)
            q = c / c.sum()
            h += len(sel) / len(k) * -(q * np.log2(q)).sum()
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=400)
    ap.add_argument("--beta", type=float, default=0.7, help="source shape (1: Laplacian, as in B-LOG.md)")
    a = ap.parse_args()
    rng = np.random.default_rng(1)                      # the same samples as tcq_sim.py
    edges = np.concatenate([[0], np.cumsum(np.array(WIDTHS) * 8)])
    L = int(edges[-1])
    x = source(rng, a.beta, (a.frames, L))
    steps = np.geomspace(0.5, 3.0, 9)
    rates = (1.0, 1.25, 1.5, 2.0)

    def curve(quant, K):
        out = []
        for d in steps:
            k, h = quant(x / (d / K))
            out.append((h, np.mean((x - k * d / K) ** 2)))
        return np.array(out)

    ref = curve(lambda v: (np.round(v / 2) * 2, entropy(np.round(v / 2))), 2)
    print(f"{a.frames} frames of {L} samples (generalized Gaussian, beta {a.beta:g}) in MULE's {len(WIDTHS)} long-frame bands; "
          f"MSE gain over a uniform scalar quantizer at equal entropy (dB)")
    print(f"{'quantizer':34s} " + " ".join(f"{r:>6.2f}b" for r in rates) + "   mask")
    sub_x = x[: max(a.frames // 8, 20)]
    for K in (2, 4):
        for n, chain in ((8, False), (8, True), (16, True), (32, True), (64, True)):
            if n < K:
                continue
            best = min(range(1, n), key=lambda m: np.mean((sub_x - viterbi(sub_x * K, K, n, m) / K) ** 2))
            c = curve(lambda v: (lambda k: (k, entropy_given_ruler(k, K)))(quantize(v, K, n, best, edges, chain)), K)
            lab = f"{K} rulers, {n} states, {'chain' if chain else 'restart'}"
            print(f"{lab:34s} " + " ".join(f"{g:+7.3f}" for g in gain_db(c, ref, rates)) + f"   {bin(best)}")


if __name__ == "__main__":
    main()
