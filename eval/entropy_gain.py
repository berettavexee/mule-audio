"""What the entropy coding brings: the C encoder's coding operations on 20 dev excerpts (q -7,
the default rate) costed under four schemes, from fixed-length codes to MULE's adaptive
context models. rANS itself codes within 0.01 % of these costs (P3-BITSTREAM.md).
Usage: python eval/entropy_gain.py"""
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "eval")]
import numpy as np, soundfile as sf
import corpus
from mule import native, params as E

def static_bits(cdf, n, sym):
    """15 - log2(freq) under a fixed CDF (the coded range: MIN_FREQ 4 per symbol)"""
    span = 32768 - n * 4
    st = (cdf.astype(np.int64) * span >> 15) + np.arange(n + 1) * 4
    st[n] = 32768
    freq = st[1:] - st[:-1]
    return float(np.sum(15 - np.log2(freq[sym])))

init = E.load_init()
items = [n for n, _ in corpus.items("dev")][:20]
wavs = dict(corpus.items("dev"))
tot = {k: 0.0 for k in ("fixed", "static", "adaptive_noctx", "adaptive")}
raw = 0.0
dur = 0.0
for it in items:
    x, fs = sf.read(wavs[it], dtype="float64", always_2d=True)
    m, v, fstart = native.c_ops(x, E.Params(q_db=-7))
    dur += len(x) / fs
    keys = np.asarray(fstart)[np.arange(0, len(fstart) - 1, 40)]
    raw += float(-m[m < 0].sum())
    for name, n, nctx in E.STREAMS:
        sel = (m >= E.OFF[name]) & (m < E.OFF[name] + nctx)
        if not sel.any():
            continue
        ctx = (m[sel] - E.OFF[name]).astype(np.int64)
        sym = v[sel].astype(np.int64)
        before = np.concatenate([[0], np.cumsum(sel)])[keys]
        tot["fixed"] += len(sym) * np.ceil(np.log2(n))
        tab = init.get(name)
        tot["static"] += sum(static_bits(tab[c], n, sym[ctx == c]) for c in range(nctx)) if tab is not None else len(sym) * np.log2(n)
        tot["adaptive_noctx"] += native.stream_cost(n, 1, np.zeros_like(ctx), sym, before, None)
        tot["adaptive"] += native.stream_cost(n, nctx, ctx, sym, before, tab)
print(f"{len(items)} items, {dur:.0f} s, raw bits (signs, escapes' suffixes, group masks): {raw / dur / 1000:.1f} kb/s")
base = (tot["adaptive"] + raw) / dur / 1000
for k, lab in (("fixed", "fixed-length codes, no entropy coding"),
               ("static", "static trained CDFs per context, no adaptation"),
               ("adaptive_noctx", "adaptive, no contexts (one model per stream), uniform start"),
               ("adaptive", "MULE: adaptive, contexts, trained start")):
    r = (tot[k] + raw) / dur / 1000
    print(f"  {lab:62s} {r:6.1f} kb/s  ({100 * (r / base - 1):+.1f} % vs MULE)")
