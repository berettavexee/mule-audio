"""Step 0 of docs/V5-512.md, without a format: would blocks of 512 points (alone, or mixed with
blocks of 256 in one frame) serve the frames that switch to short blocks better than 8 blocks of
256, or than the long block?

For each long frame t (centred on sample 1024 t of the input, the mid channel), each layout of its
1024 hop is measured: the long block (L), or a tiling of its 8 units of 128 samples by blocks of
256 points (1 unit, "1") and of 512 points (2 units, "2"), 34 tilings from "11111111" (MULE's
short frame, MULE_SHORT_OFF 448) to "2222". Each block's slopes are the shorter of its and its
neighbour's (128 samples next to a block of 256, 256 between blocks of 512), the neighbour long
blocks t-1 and t+1 end in the slope of the frame's first / last block (Vorbis power-complementary
slopes, orthonormal MDCT). Per layout:

    R      the perceptual-entropy cost of frame t (bits): sum over its 1024 coefficients of
           max(0, 0.5 log2(|X|^2 / D)), D per band (EDGES) = the long block's mean line energy
           minus --off dB, the same for every layout (the classic block-switching criterion: a
           tonal frame costs less in a long block, an attack less in short ones); also split
           into 4 regions (R0: bands 0-11, below 2.8 kHz; R1-R3: the err regions)
    err    the noise-filling envelope error: the expected power envelope of noise filled with
           each block's energy (sum over blocks of w^2 E / M) against the original's, band-passed
           to 2.8-5.9, 5.9-10.3 and 10.3-22 kHz, over 8 bins of 128 samples (2.9 ms) of the hop,
           energy-weighted mean |dB|, the three regions weighted by energy (err1-err3 apart)
    pre    the noise in excess of the original in the worst bin (dB, the original floored at
           30 dB under the hop's loudest bin): the pre-echo of noise filling
    nb     the number of blocks (side information: one set of band energies each, before
           grouping)

Frames are classed from the encoder's trace at q -6 (first coded channel; the detector as it was
then, CLASS_DETECTORS): atk (short
for the 3 kHz detector alone, thf0), hf (short only because of the highs detector, tr_hf), hf6
(long in the production, short with the highs detector at 6 dB, thf8d6), long (the others).

    python eval/b512_study.py [--set test] [--items a,b] [--off 13] [--out csv]
                              (prints a summary; writes --out if given; encodes nothing to disk)
"""
import argparse
import functools
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402
from tonal_lines import EDGES  # noqa: E402

GROUPS = [(12, 16), (16, 19), (19, 23)]        # bands (EDGES): 2.8-5.9, 5.9-10.3, 10.3-22 kHz
REGIONS = [(0, 12)] + GROUPS
NBANDS = len(EDGES) - 1


def tilings(n=8):
    if n == 0:
        return [""]
    out = ["1" + t for t in tilings(n - 1)]
    return out + (["2" + t for t in tilings(n - 2)] if n >= 2 else [])


TILINGS = tilings()                             # 34
LAYOUTS = ["L"] + TILINGS


def slope(L):
    i = np.arange(L)
    return np.sin(np.pi / 2 * np.sin(np.pi * (i + 0.5) / (2 * L)) ** 2)


def basis(N):
    M = N // 2
    n, k = np.arange(N)[:, None], np.arange(M)[None, :]
    return np.sqrt(2 / M) * np.cos(np.pi / M * (n + 0.5 + M / 2) * (k + 0.5))     # (N, M)


BASIS = {N: basis(N) for N in (2048, 512, 256)}


def band_of(M):
    return np.searchsorted(np.array(EDGES) * (M // 128), np.arange(M), side="right") - 1


BAND = {N: band_of(N // 2) for N in (2048, 512, 256)}


@functools.lru_cache(maxsize=None)
def block_window(h, Ll, Lr):
    """Window of a block of h units (256 h points) whose hop is its middle 128 h samples, slopes of
    Ll / Lr samples centred on its hop's edges."""
    N, q = 256 * h, 64 * h
    w = np.zeros(N)
    w[q - Ll // 2:q + Ll // 2] = slope(Ll)
    w[q + Ll // 2:N - q - Lr // 2] = 1
    w[N - q - Lr // 2:N - q + Lr // 2] = slope(Lr)[::-1]
    return w


def long_window(Ll, Lr):
    """A long block's window (2048) whose left / right slope is Ll / Lr samples (1024: long)."""
    return block_window(8, Ll, Lr)


def coefs(x, start, w):
    seg = np.zeros(len(w))
    lo, hi = max(start, 0), min(start + len(w), len(x))
    if hi > lo:
        seg[lo - start:hi - start] = x[lo:hi]
    return (seg * w) @ BASIS[len(w)]


def bandpass(x, b0, b1):
    X = np.fft.rfft(x)
    f = np.arange(len(X)) / len(x) * 2048        # in long lines (1024 = Nyquist)
    keep = (f >= 8 * EDGES[b0]) & (f < 8 * EDGES[b1])
    return np.fft.irfft(X * keep, len(x))


# the transient detector as it was when this study ran (22/11/2026, before the v5 detector): the
# production of then (highs pass at 8.5 dB), without the highs pass, with it at 6 dB
CLASS_DETECTORS = {"": {"tr_hf_db": 8.5}, "thf0": {"tr_hf": 0}, "thf8d6": {"tr_hf_db": 6.0}}


def classes(wav):
    import soundfile as sf
    from mule import native, params as E
    x, _ = sf.read(wav, dtype="float64", always_2d=True)
    short = {}
    for v, kw in CLASS_DETECTORS.items():
        p = E.Params(q_db=-6.0, tr_decay_db=3.0, tr_hf_ton=0.0, **kw)
        tr = native.c_trace(x, p)[3]
        b = pd.DataFrame(tr[tr[:, 0] == 2], columns=native.TRACE_FIELDS["band"])
        b = b[b.ch == b.ch.min()]
        short[v] = set(b.frame[b.type == 1])
    return x, short


class Frame:
    """Frame t's blocks, measured once each (a block is shared by many tilings)."""

    def __init__(self, x, t, D):
        self.x, self.c, self.D = x, 1024 * t, D
        self.memo = {}

    def block(self, start, w):
        key = (start, id(w))                    # the windows are cached (block_window)
        if key in self.memo:
            return self.memo[key]
        X = coefs(self.x, start, w)
        N, M = len(w), len(w) // 2
        bd = BAND[N]
        R = np.zeros(len(REGIONS))
        r = np.maximum(0, 0.5 * np.log2(X ** 2 / self.D[bd] + 1e-30))
        for i, (b0, b1) in enumerate(REGIONS):
            R[i] = r[(bd >= b0) & (bd < b1)].sum()
        env = np.zeros((len(GROUPS), 8))
        a, e = max(start, self.c - 512), min(start + N, self.c + 512)
        if e > a:
            w2 = np.zeros(1024)
            w2[a - (self.c - 512):e - (self.c - 512)] = w[a - start:e - start] ** 2
            w2 = w2.reshape(8, 128).mean(axis=1)
            for gi, (b0, b1) in enumerate(GROUPS):
                env[gi] = w2 * np.sum(X[(bd >= b0) & (bd < b1)] ** 2) / M
        self.memo[key] = (R, env)
        return R, env


def layout_blocks(c, lay):
    """[(start, window, own)] of a layout: the frame's blocks (own) and the neighbours'."""
    if lay == "L":
        return [(c - 1024, long_window(1024, 1024), True), (c - 2048, long_window(1024, 1024), False),
                (c, long_window(1024, 1024), False)]
    hs = [int(ch) for ch in lay]
    out, u = [], 0
    for i, h in enumerate(hs):
        hl = hs[i - 1] if i else h
        hr = hs[i + 1] if i + 1 < len(hs) else h
        w = block_window(h, 128 * min(h, hl), 128 * min(h, hr))
        out.append((c - 512 + 128 * u - 64 * h, w, True))
        u += h
    out += [(c - 2048, long_window(1024, 128 * hs[0]), False), (c, long_window(128 * hs[-1], 1024), False)]
    return out


def job(args):
    name, wav, off = args
    x2, short = classes(wav)
    x = x2.mean(axis=1)
    T = len(x) // 1024
    xg = [bandpass(x, *g) for g in GROUPS]
    rows = []
    for t in range(2, T - 2):
        cls = ("atk" if t in short["thf0"] else "hf" if t in short[""] else
               "hf6" if t in short["thf8d6"] else "long")
        c = 1024 * t
        Xl = coefs(x, c - 1024, long_window(1024, 1024))
        El = np.array([np.mean(Xl[BAND[2048] == b] ** 2) for b in range(NBANDS)])
        if El.sum() < 1e-12:
            continue
        fr = Frame(x, t, El * 10 ** (-off / 10) + 1e-14)
        Po = [np.array([np.mean(g[c - 512 + 128 * j:c - 384 + 128 * j] ** 2) for j in range(8)]) for g in xg]
        ptot = sum(p.sum() for p in Po)
        row = dict(item=name, frame=t, cls=cls)
        for lay in LAYOUTS:
            R = np.zeros(len(REGIONS))
            env = np.zeros((len(GROUPS), 8))
            for s, w, own in layout_blocks(c, lay):
                r, e = fr.block(s, w)
                if own:
                    R += r
                env += e
            err = wsum = 0.0
            pre = -99.0
            for gi in range(len(GROUPS)):
                po = np.maximum(Po[gi], Po[gi].max() * 1e-3) + 1e-20
                d = 10 * np.log10((env[gi] + 1e-20) / po)
                eg = np.sum(Po[gi] * np.abs(d))
                row[f"err{gi + 1}_{lay}"] = eg / (Po[gi].sum() + 1e-20)
                err += eg
                wsum += Po[gi].sum()
                if Po[gi].sum() > 1e-3 * ptot:
                    pre = max(pre, d.max())
            row[f"R_{lay}"], row[f"err_{lay}"], row[f"pre_{lay}"] = R.sum(), err / (wsum + 1e-20), pre
            for i in range(len(REGIONS)):
                row[f"R{i}_{lay}"] = R[i]
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default="test")
    ap.add_argument("--items")
    ap.add_argument("--off", type=float, default=13.0)
    ap.add_argument("--out")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        d = pd.DataFrame([r for rows in ex.map(job, [(n, w, a.off) for n, w in items]) for r in rows])
    if a.out:
        d.to_csv(a.out, index=False)
    g = d.groupby("cls")
    print(f"frames per class: {g.size().to_dict()}")
    cols = [f"{m}_{lay}" for m in ("R", "err", "pre") for lay in ("L", "2222", "11111111")]
    print("medians, the uniform layouts: R (bits / frame), err (dB), pre (dB)")
    print(g[cols].median().round(2).to_string())


if __name__ == "__main__":
    main()
