"""Points 16 and 17 (docs/V3-IDEAS.md) on a simple model, before touching the codec: the
granular gain of MULE's TCQ, at equal entropy, on samples cut into MULE's long-frame bands.

Source: a generalized Gaussian of unit variance, shape --beta (default 0.7, the measured shape of
the allocation classes 3 to 5, which hold half the coefficients: eval/results/S-LOG.md; the
classes 1 to 2 are Laplacian, beta 1.1). --beta 1 draws the original Laplacian samples, the ones
behind the numbers of eval/results/B-LOG.md and of blog post 2.

Trellis family (MULE's 8-state trellis is the case N = 8, mask 0b110): from state s, branch bit
br leads to (2 s + br) mod N and uses the subset j = (s & 1) + 2 (br ^ parity(s & mask)) of the
levels k (units of step / 2, subset k mod 4). Even states hold the even levels (zero
included), odd states the odd ones.

Compared, each at equal first-order entropy (the index given the state's parity, sign
included) against a uniform scalar quantizer:
  restart : the trellis restarts at state 0 in every band (format v2)
  chain   : one Viterbi over the whole frame, the state carried from band to band (point 16)
  N = 16, 32 : more states (point 17), chained, the best mask of each size

  python eval/tcq_sim.py [--frames 400]
"""
import argparse

import numpy as np

MASK64 = 0b110011                                 # set from the --masks search
WIDTHS = [1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 6, 6, 8, 12, 18, 22, 16]   # x 8 lines


def source(rng, beta, shape):
    """Unit-variance generalized Gaussian samples of shape beta (beta 1: rng.laplace, as before)."""
    if beta == 1:
        return rng.laplace(scale=1 / np.sqrt(2), size=shape)
    from scipy.special import gamma
    from scipy.stats import gennorm
    return gennorm.rvs(beta, scale=np.sqrt(gamma(1 / beta) / gamma(3 / beta)), size=shape, random_state=rng)


def trellis(n, mask):
    s = np.arange(n)
    g = np.array([bin(v & mask).count("1") & 1 for v in s])
    nxt = np.stack([(2 * s) % n, (2 * s + 1) % n], 1)
    sub = np.stack([(s & 1) + 2 * (0 ^ g), (s & 1) + 2 * (1 ^ g)], 1)
    return nxt, sub


def viterbi(x, n, mask, start=None, end_state=False):
    """MSE Viterbi over x [B, L] (units of step / 2) from state 0 (or start[B]), any end state:
    the levels k [B, L] (and the end states)."""
    _, sub = trellis(n, mask)
    B, L = x.shape
    t = np.arange(n)
    p1, p2 = t >> 1, (t >> 1) + n // 2          # the two predecessors of state t
    br = t & 1
    j1, j2 = sub[p1, br], sub[p2, br]
    back = np.zeros((B, L, n), bool)
    st0 = np.zeros(B, int) if start is None else start
    cost = np.where(t[None] == st0[:, None], 0.0, np.inf)
    for i in range(L):
        xi = x[:, i:i + 1]
        k1 = np.round((xi - j1) / 4) * 4 + j1
        k2 = np.round((xi - j2) / 4) * 4 + j2
        c1 = cost[:, p1] + (xi - k1) ** 2
        c2 = cost[:, p2] + (xi - k2) ** 2
        pick = c2 < c1
        back[:, i] = pick
        cost = np.where(pick, c2, c1)
    k = np.zeros((B, L))
    s = np.argmin(cost, axis=1)
    send = s.copy()
    rows = np.arange(B)
    for i in range(L - 1, -1, -1):
        pred = np.where(back[rows, i, s], (s >> 1) + n // 2, s >> 1)
        j = sub[pred, s & 1]
        k[:, i] = np.round((x[:, i] - j) / 4) * 4 + j
        s = pred
    return (k, send) if end_state else k


def viterbi_bands(x, n, mask, edges, chain):
    """Chain: one Viterbi over the frame; "greedy": one per band, each from the previous band's
    best end state; restart: one per band, each from state 0."""
    if chain == "greedy":
        out = np.zeros_like(x)
        st = np.zeros(len(x), int)
        for a, b in zip(edges[:-1], edges[1:], strict=True):
            out[:, a:b], st = viterbi(x[:, a:b], n, mask, st, True)
        return out
    if chain:
        return viterbi(x, n, mask)
    out = np.zeros_like(x)
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        out[:, a:b] = viterbi(x[:, a:b], n, mask)
    return out


def entropy_tcq(k):
    """First-order entropy per sample of the index given the parity (the union is known)."""
    k = k.astype(np.int64).ravel()
    par = k & 1
    h = 0.0
    for p in (0, 1):
        v = k[par == p]
        if not len(v):
            continue
        _, c = np.unique(v, return_counts=True)
        q = c / c.sum()
        h += len(v) / len(k) * -(q * np.log2(q)).sum()
    return h


def entropy(k):
    _, c = np.unique(k.astype(np.int64).ravel(), return_counts=True)
    q = c / c.sum()
    return -(q * np.log2(q)).sum()


def curve(x, quant, steps):
    """(entropy, MSE) for each step."""
    out = []
    for d in steps:
        k = quant(x / (d / 2))
        out.append((k[1], np.mean((x - k[0] * d / 2) ** 2)))
    return np.array(out)


def gain_db(c, ref, rates):
    """MSE gain (dB) of curve c over ref at the given entropies."""
    def mse_at(cv, r):
        o = np.argsort(cv[:, 0])
        return np.interp(r, cv[o, 0], np.log10(cv[o, 1]))
    return [10 * (mse_at(ref, r) - mse_at(c, r)) for r in rates]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=400)
    ap.add_argument("--beta", type=float, default=0.7, help="source shape (1: Laplacian)")
    ap.add_argument("--masks", action="store_true", help="search the masks of 16 and 32 states")
    a = ap.parse_args()
    rng = np.random.default_rng(1)
    edges = np.concatenate([[0], np.cumsum(np.array(WIDTHS) * 8)])
    L = int(edges[-1])
    x = source(rng, a.beta, (a.frames, L))
    steps = np.geomspace(0.5, 3.0, 9)
    rates = (1.0, 1.25, 1.5, 2.0)

    def scalar(v):
        k = np.round(v / 2) * 2
        return k, entropy(k / 2)

    ref = curve(x, scalar, steps)

    def tcq(n, mask, chain):
        def q(v):
            k = viterbi_bands(v, n, mask, edges, chain)
            return k, entropy_tcq(k)
        return q

    masks = {8: [0b110]}
    if a.masks:
        for n in (16, 32, 64):
            res = []
            sub_x = x[: max(a.frames // 8, 20)]
            for m in range(1, n):
                k = viterbi(sub_x * 2, n, m)
                res.append((np.mean((sub_x - k / 2) ** 2), m))
            res.sort()
            masks[n] = [res[0][1]]
            print(f"{n} states: best masks {[bin(m) for _, m in res[:3]]} (MSE at step 1 {res[0][0]:.4f}; "
                  f"8 states 0b110: {np.mean((sub_x - viterbi(sub_x * 2, 8, 0b110) / 2) ** 2):.4f})")
    else:
        masks[16], masks[32], masks[64] = [0b1101], [0b10111], [MASK64]   # the --masks search's best
    print(f"{a.frames} frames of {L} samples (generalized Gaussian, beta {a.beta:g}) in MULE's {len(WIDTHS)} long-frame bands; "
          f"MSE gain over a uniform scalar quantizer at equal entropy (dB)")
    print(f"{'quantizer':32s} " + " ".join(f"{r:>6.2f}b" for r in rates))
    for lab, n, chain in (("8 states, restart (v2)", 8, False), ("8 states, chain (16)", 8, True),
                          ("8 states, greedy chain", 8, "greedy"), ("32 states, greedy chain", 32, "greedy"),
                          ("16 states, restart", 16, False), ("16 states, chain", 16, True),
                          ("32 states, restart", 32, False), ("32 states, chain", 32, True),
                          ("64 states, chain", 64, True)):
        c = curve(x, tcq(n, masks[n][0], chain), steps)
        print(f"{lab:32s} " + " ".join(f"{g:+7.3f}" for g in gain_db(c, ref, rates)))


if __name__ == "__main__":
    main()
