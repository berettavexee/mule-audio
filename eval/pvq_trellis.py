"""Trellis-coded PVQ against plain PVQ (a study for CELT / Opus, independent of MULE): does a trellis
over the bands buy the granular gain on the shape that TCQ buys on scalars?

Plain PVQ(N, K): the shapes are the integer vectors of N coordinates with K unit pulses (sum of
|y_i| = K), normalised; the index costs log2 V(N, K) bits (CELT codes it uniformly).

Trellis-coded PVQ: the union of the pyramids K and K+1 (normalised: their directions interleave on
the sphere, the "half step"), each cut in two by a parity rule, gives 4 subsets D0 = A0, D1 = A1
(pyramid K), D2 = B0, D3 = B1 (pyramid K+1). The trellis is MULE's TCQ trellis (core/mule.h,
n states): from state s, the branch bit br uses subset j = (s & 1) + 2 (br ^ parity(s & mask)) and
leads to (2 s + br) mod n; a state thus allows A_(s&1) and B_(s&1). The decoder follows the state;
the index within the allowed union A_p U B_p costs log2 |A_p U B_p| bits. The encoder runs a Viterbi
over a sequence of L vectors (the bands of a frame), each vector's best codeword in each subset
found by exhaustive search.

Parity rules (which half of a pyramid a vector belongs to):
    odd     the sum of the coordinates at odd positions, mod 2
    first   the first coordinate, mod 2
    mixed   odd, exclusive-or the sum of the coordinates at positions i with i mod 4 < 2, mod 2
    none    no split (A0 = A1 = A, B0 = B1 = B): the trellis constrains nothing, the encoder picks
            freely in the union of the two pyramids; a check, which should land near the plain
            PVQ curve (a bigger codebook, no trellis gain)

Prints, for each N, source and rule: per K, the plain PVQ (bits per vector, shape SNR) and the
trellis (bits, SNR, and its gain in dB over plain PVQ at the same rate, interpolated in rate).

    python eval/pvq_trellis.py [--n 4,8] [--kmax 8] [--states 4,8] [--seqs 400] [--len 20]
                               (prints only; nothing written)
"""
import argparse
import numpy as np


def pyramid(n, k):
    """All integer vectors of n coordinates with sum |y| = k, (V, n) int array."""
    out = []

    def rec(prefix, left, dims):
        if dims == 1:
            out.append(prefix + [left])
            if left:
                out.append(prefix + [-left])
            return
        for v in range(-left, left + 1):
            rec(prefix + [v], left - abs(v), dims - 1)
    rec([], k, n)
    return np.array(out, dtype=np.int64)


PAR = np.array([bin(v).count("1") & 1 for v in range(256)])  # parity of the bits of 0..255


def tcq_mask(n):
    return {64: 0x33, 32: 0x17, 16: 0xD, 8: 0x6, 4: 0x2}[n]


def split(Y, rule):
    """0/1 label of each codeword of a pyramid."""
    idx = np.arange(Y.shape[1])
    if rule == "odd":
        return Y[:, idx % 2 == 1].sum(axis=1) % 2     # (numpy: never negative for a positive divisor)
    if rule == "first":
        return Y[:, 0] % 2
    if rule == "mixed":
        return Y[:, idx % 2 == 1].sum(axis=1) % 2 ^ Y[:, (idx % 4) < 2].sum(axis=1) % 2
    raise ValueError(rule)


def source(kind, count, n, rng):
    x = rng.laplace(size=(count, n)) if kind == "laplace" else rng.standard_normal((count, n))
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def best_corr(X, C, chunk=1000):
    """For each row of X, the best correlation with the (normalised) codewords C (by blocks of rows:
    a pyramid of 10^5 codewords times 10^4 vectors would not fit at once)."""
    return np.concatenate([(X[i:i + chunk] @ C.T).max(axis=1) for i in range(0, len(X), chunk)])


def trellis_sim(dist, size, states, L):
    """Viterbi over sequences of L vectors: mean squared shape error and mean bits per vector.
    dist: (vectors, 4) the squared error of each vector's best codeword in the subsets D0..D3;
    size: the allowed union's size per state parity (bits: its log2)."""
    mask = tcq_mask(states)
    M = len(dist) // L
    tot_d = tot_b = 0.0
    for m in range(M):
        cost = np.full(states, np.inf)
        cost[0] = 0.0
        bits = np.zeros(states)
        for i in range(L):
            d = dist[m * L + i]
            nc = np.full(states, np.inf)
            nb = np.zeros(states)
            for s in range(states):
                if not np.isfinite(cost[s]):
                    continue
                for br in (0, 1):
                    j = (s & 1) + 2 * (br ^ PAR[s & mask])
                    t = (2 * s + br) % states
                    c = cost[s] + d[j]
                    if c < nc[t]:
                        nc[t] = c
                        nb[t] = bits[s] + np.log2(size[s & 1])
            cost, bits = nc, nb
        s = int(np.argmin(cost))
        tot_d += cost[s]
        tot_b += bits[s]
    return tot_d / (M * L), tot_b / (M * L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", default="4,8")
    ap.add_argument("--kmax", type=int, default=8)
    ap.add_argument("--states", default="4,8")
    ap.add_argument("--seqs", type=int, default=400)
    ap.add_argument("--len", type=int, default=20)
    ap.add_argument("--rules", default="none,odd,first,mixed")
    ap.add_argument("--sources", default="laplace,gauss")
    ap.add_argument("--maxcw", type=int, default=300000, help="largest pyramid searched exhaustively")
    a = ap.parse_args()
    rng = np.random.default_rng(1)
    for n in [int(v) for v in a.n.split(",")]:
        pyr = {}
        for k in range(1, a.kmax + 2):
            Y = pyramid(n, k)
            if len(Y) > a.maxcw:
                break
            pyr[k] = Y
        ks = sorted(pyr)
        for src in a.sources.split(","):
            X = source(src, a.seqs * a.len, n, rng)
            plain = []
            for k in ks:
                C = pyr[k] / np.linalg.norm(pyr[k], axis=1, keepdims=True)
                mse = np.mean(2 - 2 * best_corr(X, C))
                plain.append((np.log2(len(C)), -10 * np.log10(mse)))
            pr, ps = np.array(plain).T
            print(f"\n=== N = {n}, source {src}: plain PVQ (K: bits per vector, shape SNR dB)")
            print("   " + "  ".join(f"K{k}: {r:.2f} b {s:.2f} dB" for k, r, s in zip(ks, pr, ps)))
            states = [int(v) for v in a.states.split(",")]
            for rule in a.rules.split(","):
                lines = {st: [] for st in states}
                for k in ks[:-1]:
                    A, B = pyr[k], pyr[k + 1]
                    if rule == "none":
                        sub = [A, A, B, B]
                    else:
                        la, lb = split(A, rule), split(B, rule)
                        sub = [A[la == 0], A[la == 1], B[lb == 0], B[lb == 1]]
                    if min(len(S) for S in sub) == 0:
                        for st in states:
                            lines[st].append(f"K{k}: (empty subset)")
                        continue
                    sub = [S / np.linalg.norm(S, axis=1, keepdims=True) for S in sub]
                    dist = 2 - 2 * np.stack([best_corr(X, D) for D in sub], axis=1)   # once per rule and K
                    size = [len(sub[0]) + len(sub[2]), len(sub[1]) + len(sub[3])]
                    for st in states:
                        mse, bits = trellis_sim(dist, size, st, a.len)
                        snr = -10 * np.log10(mse)
                        ref = np.interp(bits, pr, ps) if pr[0] <= bits <= pr[-1] else np.nan
                        lines[st].append(f"K{k}/{k + 1}: {bits:.2f} b {snr:.2f} dB ({snr - ref:+.2f})")
                for st in states:
                    print(f"   trellis {st} states, rule {rule}: " + "  ".join(lines[st]))


if __name__ == "__main__":
    main()
