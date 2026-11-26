"""Joint coding of coefficient pairs, estimated on the encoder's trace (no format change made).

Today each coefficient's index u (spec 5.3) is one symbol of the `coef` stream: 8 symbols (escape
at 7), 96 contexts (ac x the class of 2*tail1 + tail2, mixed with the inter-frame prediction pm).
The decoder's cost is in the models: a linear search in the CDF and an update of every entry
(eval/results/C-LOG.md). Here two consecutive coefficients of a band (scan order) share one
symbol when both indices are below T: u1*T + u2, or the escape T*T, after which both are coded
one by one as today. The quantized values do not change (same encoder, same trellis decisions:
only the rate and the decoder's work move), so each scheme's cost is recomputed with the real
adaptive models (resets at key packets), each with its own initial tables trained on `train`.

Schemes:
  base      the format's v5 coding, tables trained here (the reference of every difference)
  pT        pairs below T; escaped pairs and a band's odd last coefficient in the `coef` models
  pT+       the same, an escaped pair's coefficients in their own models; the second one, when
            the first is below T, coded as min(u, 7) - T (it is known to be >= T)
The pair's context: the tails before the pair, and the mean of the two pm (same class map, 96
contexts). Pair symbols are searched in their order of frequency on `train` (fixed by the format).

Decoder work, per frame: model symbols, search steps, CDF entries updated; an instruction
estimate with fixed costs per symbol (--o), per step (--s) and per entry (--u), from C-LOG's
measurements (about 8 instructions per entry updated; the rest assumed).

  python eval/pair_lab.py [--rate 128] [--step 1]   (prints only; writes nothing)
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "eval")]
import corpus  # noqa: E402
from ctx_lab import C, coef_resets, ctx_from  # noqa: E402   (the format's context rule)
from mule import native, params as mp  # noqa: E402

TS = (2, 3)
NCTX = 96
# each scheme's streams (the base is the format's own coding)
SCHEMES = {"": ("pair", "single"), "+": ("pair", "lone", "esc", "esc2")}


def streams(co, T):
    """The symbol streams of one item, in decoding order: {name: (ctx, sym, rows, nsym)}, rows:
    the trace rows each symbol is coded at (the first of a pair)."""
    u = co[:, C["mag"]].astype(np.int64)
    cs = co[:, C["ctx"]]                                    # the encoder's own contexts
    s8 = np.minimum(u, 7)

    def single(rows, shift=0):
        return cs[rows], s8[rows] - shift, rows, 8 - shift

    key = (co[:, C["frame"]].astype(np.int64) * 2 + co[:, C["ch"]]) * 64 + co[:, C["band"]]
    start = np.r_[True, key[1:] != key[:-1]]
    run = np.cumsum(start) - 1                              # band call index
    pos = np.arange(len(co)) - np.flatnonzero(start)[run]   # position in the band call
    i1 = np.flatnonzero((pos % 2 == 0) & (pos + 1 < np.bincount(run)[run]))   # pairs' first
    i2 = i1 + 1
    lone = np.ones(len(co), bool)
    lone[i1] = lone[i2] = False                             # odd last coefficients
    lo = np.flatnonzero(lone)
    pm1, pm2 = co[i1, C["pm"]].astype(np.int64), co[i2, C["pm"]].astype(np.int64)
    pmp = (np.minimum(pm1, 31) + np.minimum(pm2, 31) + 1) >> 1     # the pair's prediction
    small = (u[i1] < T) & (u[i2] < T)
    esc = i1[~small]
    known = u[esc] < T                                      # then the second is >= T
    return {"base": single(np.arange(len(co))),
            "pair": (ctx_from(co[i1], np.where(pm1 >= 0, pmp, -1)),
                     np.where(small, u[i1] * T + u[i2], T * T), i1, T * T + 1),
            # shared: escaped pairs' coefficients and lone ones in the coef models
            "single": single(np.sort(np.r_[esc, esc + 1, lo])),
            # split: escaped pairs in their own models, the second shifted when known >= T
            "lone": single(lo),
            "esc": single(np.sort(np.r_[esc, esc[~known] + 1])),
            "esc2": single(esc[known] + 1, T)}


def _trace(args):
    wav, rate = args
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    p = mp.for_bitrate(rate)
    _m, _v, fstart, tr = native.c_trace(x, p)
    co = tr[tr[:, 0] == 0]
    keys = fstart[np.arange(0, len(fstart) - 1, p.keyframe)]
    return x, fs, co, keys, len(fstart) - 1


def _counts(ctx, sym, ns):
    return np.bincount(ctx * ns + sym, minlength=NCTX * ns).reshape(NCTX, ns).astype(float)


def _train_job(args):
    _x, _fs, co, _k, _n = _trace(args)
    out = {}
    for T in TS:
        for name, (ctx, sym, _rows, ns) in streams(co, T).items():
            out[f"{T}:{name}"] = _counts(ctx, sym, ns)
    return out


def work(ns, sym):
    """(symbols, search steps, entries updated) of a stream (symbol s found in s + 1 steps)."""
    return np.array([len(sym), (sym + 1).sum(), len(sym) * (ns - 1)], float)


def _dev_job(args):
    wav, rate, init, ranks = args
    x, fs, co, keys, nframes = _trace((wav, rate))
    data, _ab = native.c_encode(x, mp.for_bitrate(rate))    # the file's size (container included)
    res = {"secs": len(x) / fs, "frames": nframes, "bytes": len(data)}
    for T in TS:
        st = streams(co, T)
        c, sp, rows, n = st["pair"]
        st["pair"] = (c, ranks[T][sp], rows, n)
        cost = {k: (native.stream_cost(ns, NCTX, ctx, sym, coef_resets(co[rows], keys),
                                       init[f"{T}:{k}"]), work(ns, sym))
                for k, (ctx, sym, rows, ns) in st.items()}
        res["base"] = cost["base"]
        for sfx, names in SCHEMES.items():
            res[f"p{T}{sfx}"] = tuple(sum(cost[k][i] for k in names) for i in (0, 1))
        res[f"p{T}:share"] = 1 - len(st["single"][1]) / max(len(co), 1)   # coefficients in pairs, small
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=int, default=128)
    ap.add_argument("--step", type=int, default=1, help="every step-th item of train and dev")
    ap.add_argument("--o", type=float, default=30.0, help="instructions per model symbol")
    ap.add_argument("--s", type=float, default=7.0, help="instructions per search step")
    ap.add_argument("--u", type=float, default=8.0, help="instructions per CDF entry updated")
    ap.add_argument("--frame", type=float, default=922000.0, help="decoder instructions per frame")
    a = ap.parse_args()
    train = [(w, a.rate) for _n, w in corpus.items("train")[::a.step]]
    dev = corpus.items("dev")[::a.step]
    with ProcessPoolExecutor() as ex:
        print(f"training on {len(train)} train items...", file=sys.stderr, flush=True)
        counts = {}
        for c in ex.map(_train_job, train):
            for k, v in c.items():
                counts[k] = counts.get(k, 0) + v
        init = {k: native.counts_to_cdf(v) for k, v in counts.items()}
        ranks = {}
        for T in TS:                            # pair symbols renumbered in frequency order
            order = np.argsort(-counts[f"{T}:pair"].sum(0), kind="stable")
            ranks[T] = np.argsort(order)
            init[f"{T}:pair"] = native.counts_to_cdf(counts[f"{T}:pair"][:, order])
        print(f"evaluating {len(dev)} dev items...", file=sys.stderr, flush=True)
        res = list(ex.map(_dev_job, [(w, a.rate, init, ranks) for _n, w in dev]))
    secs = sum(r["secs"] for r in res)
    frames = sum(r["frames"] for r in res)
    kbps = sum(r["bytes"] for r in res) * 8 / secs / 1000
    b0 = np.array([r["base"][0] for r in res])
    w0 = sum(r["base"][1] for r in res)

    def instr(w):
        return np.dot((a.o, a.s, a.u), w) / frames

    print(f"\n{len(res)} dev items, {secs:.0f} s, --bitrate {a.rate}: {kbps:.1f} kb/s; "
          f"coefficient symbols {b0.sum() / secs / 1000:.2f} kb/s")
    print(f"base per frame: {w0[0] / frames:.0f} symbols, {w0[1] / frames:.0f} search steps, "
          f"{w0[2] / frames:.0f} entries updated")
    ins0 = instr(w0)
    print(f"{'scheme':8s} {'kb/s':>7s} {'rate %':>7s} {'worse':>7s} {'symbols':>8s} {'steps':>7s} "
          f"{'updates':>8s} {'instr/frame':>12s} {'decoder %':>9s}")
    for k in ["base"] + [f"p{T}{sfx}" for T in TS for sfx in SCHEMES]:
        b = np.array([r[k][0] for r in res])
        w = sum(r[k][1] for r in res)
        ins = instr(w)
        d = (b.sum() - b0.sum()) / 8 / 1000 / secs
        print(f"{k:8s} {d:+7.3f} {100 * d / kbps:+7.2f} {int((b > b0 + 1e-6).sum()):>3d}/{len(b):<3d} "
              f"{w[0] / frames:8.0f} {w[1] / frames:7.0f} {w[2] / frames:8.0f} {ins - ins0:+12.0f} "
              f"{100 * (ins - ins0) / a.frame:+9.2f}")
    for T in TS:
        sh = np.mean([r[f"p{T}:share"] for r in res])
        print(f"T={T}: {sh:.1%} of the coefficients in small pairs")


if __name__ == "__main__":
    main()
