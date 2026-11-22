"""Step 0 of docs/V5-512.md, perceptual: a toy transform codec with MULE's frame layouts, to rank
block-switching policies (which frames get 8 blocks of 256, 4 blocks of 512, or the long block)
by Zimtohrli at equal rate, before any change to the format.

Real MULE short frames cost about the bits of long ones (side information included: 258 against
270 bits per frame at q -6 on the test items); what decides is quality, so the toy codes every
block the same way and lets Zimtohrli judge. The mid channel; each frame's layout from a policy;
the windows of b512_study (Vorbis slopes, the long neighbours ending in the frame's first / last
block's slope, orthonormal MDCT). Per block and band (EDGES grid scaled to the block): a uniform
quantizer of step sqrt(12 D), D = the frame's long-block mean line energy in the band minus off dB
(the same noise level for every layout: what changes is where the noise lands in time, and how
many coefficients rise above it); a band from 2.8 kHz up quantized to all zeros is noise-filled at
its block's energy (MULE's noise filling, unquantized). Rate: the coefficients' empirical entropy
per (block size, band) over the item.

Policies, from the production encoder's trace at q -6 (classes of b512_study: atk, hf, hf6):
    thf0      atk short (the production before the highs detector)
    prod      atk, hf short (the production)
    hf512     atk short, hf 4 x 512
    hf6_256   atk, hf, hf6 short (the highs detector at 6 dB)
    hf6_512   atk, hf short, hf6 4 x 512
    all512    atk, hf, hf6 4 x 512
    atk512    atk 4 x 512, hf short
    short512  atk, hf 4 x 512 (the production's short frames all in 512)
    mix       atk, hf mixed: blocks of 256 on the attack's unit and the one before it (the unit of
              128 samples whose energy above 2.8 kHz rises most over the 3 before it), 512 elsewhere
    mix6      mix, and hf6 mixed too
    tf        atk, hf short with CELT-like per-band TF: in each band the 8 blocks combined by an
              orthonormal Hadamard in groups of 2^k (k 0-3, the L1-minimal one), quantized and
              noise-filled per group
    tflo      tf below 2.8 kHz only (the highs kept at 256)
    tf3       atk, hf short, all 8 blocks combined below 2.8 kHz (k 3), the highs at 256
    tf6       tf, and hf6 too

    python eval/b512_toy.py [--set test] [--items a,b] [--offs 10,13,16] [--policies a,b] [--out csv]
                            (prints per-policy Zimtohrli at the production's rate; nothing on disk
                            but --out)
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
from b512_study import BAND, BASIS, EDGES, NBANDS, bandpass, block_window, classes, coefs, long_window  # noqa: E402

SHORT, B512 = "11111111", "2222"
POLICIES = {
    "thf0": {"atk": SHORT},
    "prod": {"atk": SHORT, "hf": SHORT},
    "hf512": {"atk": SHORT, "hf": B512},
    "hf6_256": {"atk": SHORT, "hf": SHORT, "hf6": SHORT},
    "hf6_512": {"atk": SHORT, "hf": SHORT, "hf6": B512},
    "all512": {"atk": B512, "hf": B512, "hf6": B512},
    "atk512": {"atk": B512, "hf": SHORT},
    "short512": {"atk": B512, "hf": B512},
    "mix": {"atk": "MIX", "hf": "MIX"},
    "mix6": {"atk": "MIX", "hf": "MIX", "hf6": "MIX"},
    "tf": {"atk": "T", "hf": "T"},
    "tflo": {"atk": "TL", "hf": "TL"},
    "tf3": {"atk": "T3", "hf": "T3"},
    "tf6": {"atk": "T", "hf": "T", "hf6": "T"},
}
NF_BAND = 12


def frame_blocks(c, lay, prev, nxt):
    """[(start, window)] of frame centred on c with layout lay, its neighbours' layouts prev / nxt
    (setting a long frame's slopes)."""
    if lay == "L":
        Ll = 128 * int(prev[-1]) if prev != "L" else 1024
        Lr = 128 * int(nxt[0]) if nxt != "L" else 1024
        return [(c - 1024, long_window(Ll, Lr))]
    hs = [int(ch) for ch in lay]
    out, u = [], 0
    for i, h in enumerate(hs):
        hl = hs[i - 1] if i else (int(prev[-1]) if prev != "L" else h)
        hr = hs[i + 1] if i + 1 < len(hs) else (int(nxt[0]) if nxt != "L" else h)
        out.append((c - 512 + 128 * u - 64 * h, block_window(h, 128 * min(h, hl), 128 * min(h, hr))))
        u += h
    return out


def segment(n):
    return "2" * (n // 2) + "1" * (n % 2)


def mix_tiling(e, t):
    """Blocks of 256 on frame t's attack unit and the one before, 512 elsewhere; e: energy above
    2.8 kHz per 128 samples (unit u of frame t = e[8 t - 4 + u])."""
    k0 = 8 * t - 4
    r = [e[k0 + u] / (e[k0 + u - 3:k0 + u].mean() + 1e-12) for u in range(8)]
    u = int(np.argmax(r))
    a = max(u - 1, 0)
    return segment(a) + "1" * (u + 1 - a) + segment(7 - u)


def entropy_bits(q):
    _, n = np.unique(q, return_counts=True)
    p = n / n.sum()
    return float(-(n * np.log2(p)).sum())


def geom(lay):
    """The block geometry of a layout ("T..." layouts are short frames with per-band TF)."""
    return SHORT if lay.startswith("T") else lay


def hadamard(n):
    H = np.ones((1, 1))
    while len(H) < n:
        H = np.block([[H, H], [H, -H]])
    return H / np.sqrt(n)


HAD = {k: hadamard(2 ** k) for k in range(4)}


def tf_levels(arr, bd, lay):
    """Per band, the TF level k (blocks combined by groups of 2^k) of a short frame's coefficients
    arr (8, 128): "T" the L1-minimal level in every band, "TL" below band NF_BAND only (level 0
    above), "T3" level 3 below NF_BAND, 0 above (CELT's tf_analysis criterion, without bias)."""
    ks = np.zeros(NBANDS, int)
    for b in range(NBANDS):
        if lay == "T3":
            ks[b] = 3 if b < NF_BAND else 0
            continue
        if lay == "TL" and b >= NF_BAND:
            continue
        sub = arr[:, bd == b]
        l1 = [np.abs(np.concatenate([HAD[k] @ sub[g:g + 2 ** k] for g in range(0, 8, 2 ** k)])).sum()
              for k in range(4)]
        ks[b] = int(np.argmin(l1))
    return ks


def code_band(sub, step, nf, rng):
    """Quantized and noise-filled (if nf and all zero) coefficients of one group, and its symbols."""
    q = np.round(sub / step)
    out = q * step
    if nf and not q.any():
        e = np.sum(sub ** 2)
        if e > 0:
            z = rng.standard_normal(sub.shape)
            out = z * np.sqrt(e / np.sum(z ** 2))
    return out, q.astype(np.int64).ravel()


def toy(x, layouts, D, rng):
    """(decoded, bits, TF levels used): layouts[t] for frames 0..T-1, D[t] the bands' noise
    levels."""
    T = len(layouts)
    y = np.zeros(len(x) + 4096)
    syms = {}
    levels = []
    for t in range(1, T - 1):
        c = 1024 * t
        lay = layouts[t]
        blocks = frame_blocks(c, geom(lay), geom(layouts[t - 1]), geom(layouts[t + 1]))
        Xs = [coefs(x, s, w) for s, w in blocks]
        if lay.startswith("T"):
            arr = np.stack(Xs)
            bd = BAND[256]
            ks = tf_levels(arr, bd, lay)
            levels.append(ks)
            out = np.zeros_like(arr)
            for b in range(NBANDS):
                m = bd == b
                k, n = ks[b], 2 ** ks[b]
                step = np.sqrt(12 * D[t][b])
                for g in range(0, 8, n):
                    Y, q = code_band(HAD[k] @ arr[g:g + n][:, m], step, b >= NF_BAND, rng)
                    out[g:g + n, m] = HAD[k].T @ Y
                    syms.setdefault((256, b, k), []).append(q)
            Xqs = list(out)
        else:
            Xqs = []
            for (s, w), X in zip(blocks, Xs):
                bd = BAND[len(w)]
                Xq = np.zeros_like(X)
                for b in range(NBANDS):
                    m = bd == b
                    Xq[m], q = code_band(X[m], np.sqrt(12 * D[t][b]), b >= NF_BAND, rng)
                    syms.setdefault((len(w), b, 0), []).append(q)
                Xqs.append(Xq)
        for (s, w), Xq in zip(blocks, Xqs):
            if s >= 0:
                y[s:s + len(w)] += (BASIS[len(w)] @ Xq) * w
    bits = sum(entropy_bits(np.concatenate(v)) for v in syms.values())
    return y[:len(x)], bits, (np.array(levels) if levels else np.zeros((0, NBANDS)))


def job(args):
    name, wav, offs, pols = args
    from metrics import zimtohrli
    x2, short = classes(wav)
    x = x2.mean(axis=1)
    T = len(x) // 1024
    cls = ["atk" if t in short["thf0"] else "hf" if t in short[""] else
           "hf6" if t in short["thf8d6"] else "long" for t in range(T)]
    El = []
    for t in range(T):
        X = coefs(x, 1024 * t - 1024, long_window(1024, 1024))
        El.append(np.array([np.mean(X[BAND[2048] == b] ** 2) for b in range(NBANDS)]) + 1e-14)
    hp = bandpass(x, 12, NBANDS)
    e = np.add.reduceat(hp ** 2, np.arange(0, len(hp), 128))
    a, b = 2048, T * 1024 - 2048                 # the frames every policy codes
    rows = []
    for pol in pols:
        rule = POLICIES[pol]
        layouts = [rule.get(k, "L") for k in cls]
        layouts = [mix_tiling(e, t) if lay == "MIX" else lay for t, lay in enumerate(layouts)]
        layouts[0] = layouts[-1] = "L"
        for off in offs:
            D = [el * 10 ** (-off / 10) for el in El]
            y, bits, lv = toy(x, layouts, D, np.random.default_rng(1))
            z = zimtohrli(x[a:b, None], y[a:b, None], 44100)["zimt"]
            rows.append(dict(item=name, policy=pol, off=off, kbps=bits / (len(x) / 44100) / 1000,
                             zimt=z, n512=sum(lay == B512 for lay in layouts),
                             nmix=sum(lay not in ("L", B512, SHORT) and not lay.startswith("T") for lay in layouts),
                             ntf=len(lv), tf_lo=lv[:, :NF_BAND].mean() if len(lv) else np.nan,
                             tf_hi=lv[:, NF_BAND:].mean() if len(lv) else np.nan,
                             n256=sum(lay == SHORT for lay in layouts)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default="test")
    ap.add_argument("--items")
    ap.add_argument("--offs", default="10,13,16")
    ap.add_argument("--policies", default=",".join(POLICIES), help="(prod always measured)")
    ap.add_argument("--out")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    offs = [float(v) for v in a.offs.split(",")]
    pols = ["prod"] + [p for p in a.policies.split(",") if p != "prod"]
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        d = pd.DataFrame([r for rows in ex.map(job, [(n, w, offs, pols) for n, w in items]) for r in rows])
    if a.out:
        d.to_csv(a.out, index=False)
    # each policy's Zimtohrli at the production's rate at the middle off, per item (log-linear)
    mid = offs[len(offs) // 2]
    out = []
    for it, g in d.groupby("item"):
        r = g[(g.policy == "prod") & (g.off == mid)].kbps.iloc[0]
        for pol, h in g.groupby("policy"):
            h = h.sort_values("kbps")
            out.append(dict(item=it, policy=pol, zimt=np.exp(np.interp(r, h.kbps, np.log(h.zimt)))))
    t = pd.DataFrame(out).pivot(index="item", columns="policy", values="zimt")
    rel = (t.div(t["prod"], axis=0) - 1) * 100
    print(f"Zimtohrli at the production's rate (off {mid:g}), % against prod: mean, median, items better / worse by 1 %")
    for pol in pols:
        v = rel[pol]
        print(f"  {pol:8s} {v.mean():+6.2f} {v.median():+6.2f}   {(v < -1).sum():2d} / {(v > 1).sum():2d}")
    print("\nper item (%):")
    print(rel.round(1).to_string())


if __name__ == "__main__":
    main()
