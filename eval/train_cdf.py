"""Trains the initial CDFs from the C encoder's coding operations (production statistics) on the
training corpus (data/train, disjoint from dev/test), and measures the rate on dev against the
installed tables. Usage: python eval/train_cdf.py [--install]
--install writes py/mule/init_cdf.npz (then: tools/gen_init_cdf.py with the new TABLE_ID, make)."""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus                                    # noqa: E402
from mule import native, params as E            # noqa: E402

QS = (-6.0, -9.0, -12.0, -15.0)


def ops(wav, q):
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    m, v, fstart = native.c_ops(x, E.Params(q_db=q))
    return m, v, fstart, len(x) / fs


def counts_job(args):
    m, v, _, _ = ops(*args)
    out = {}
    for name, n, nctx in E.STREAMS:
        sel = (m >= E.OFF[name]) & (m < E.OFF[name] + nctx)
        k = np.zeros((nctx, n), np.int64)
        np.add.at(k, (m[sel] - E.OFF[name], v[sel].astype(np.int64)), 1)
        out[name] = k
    return out


def cost(m, v, fstart, init, keyframe=40):
    keys = np.asarray(fstart)[np.arange(0, len(fstart) - 1, keyframe)]
    bits = float(-m[m < 0].sum())
    for name, n, nctx in E.STREAMS:
        sel = (m >= E.OFF[name]) & (m < E.OFF[name] + nctx)
        if sel.any():
            before = np.concatenate([[0], np.cumsum(sel)])[keys]
            bits += native.stream_cost(n, nctx, m[sel] - E.OFF[name], v[sel].astype(np.int64),
                                       before, init.get(name) if init else None)
    return bits


def cost_job(args):
    wav, q, tabs = args
    m, v, fstart, dur = ops(wav, q)
    return [cost(m, v, fstart, t) for t in tabs], dur


def main():
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(counts_job, [(w, q) for _, w in corpus.items("train") for q in QS]))
    acc = {k: sum(r[k] for r in res) for k in res[0]}
    new = {k: native.counts_to_cdf(c) for k, c in acc.items()}
    old = E.load_init("default")
    print("dev rate (kb/s): installed tables / new tables (trained on data/train)")
    for q in (-9.0, -12.0):
        with ProcessPoolExecutor() as ex:
            out = list(ex.map(cost_job, [(w, q, (old, new)) for _, w in corpus.items("dev")]))
        dur = sum(d for _, d in out)
        a = sum(c[0] for c, _ in out) / dur / 1000
        b = sum(c[1] for c, _ in out) / dur / 1000
        print(f"  q {q:+.0f}: {a:7.2f} / {b:7.2f}  ({100 * (b / a - 1):+.2f} %)")
    if "--install" in sys.argv:
        np.savez_compressed(E.INIT_DEFAULT, **new)
        print("->", E.INIT_DEFAULT)


if __name__ == "__main__":
    main()
