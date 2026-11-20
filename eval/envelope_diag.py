"""Where the temporal envelope of the highs is lost (eval/results/N-LOG.md, branch v4, step 0): for each long frame
and each MULE band from 2.8 kHz up, the envelope over 8 sub-blocks of 2.9 ms (the frame's
central 1024 samples), original against decoded: the shape error (rms of the dB difference once
its mean is removed) and the flattening (decoded envelope's spread over the original's). Each
(frame, band) cell is classed by what MULE's encoder decided (the production's trace, first
coded channel): noise-filled (allocation 0), coded with fewer than half its coefficients at
level 0, or coded with at least half at 0. Other codecs are measured on the same cells.

    python eval/envelope_diag.py mule_-7,opus_128[,...] --items a,b [--set test] [-j N]
                                 (prints; encodes in temporary directories)

Cells kept: long frames, the original's envelope varying (spread at least 1.5 dB) and the band
within 50 dB of the frame's strongest band from 2.8 kHz up. The first configuration must be a
MULE one: its quality gives the trace's.
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.signal import stft

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402

EDGES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 100, 116]
B0 = 12                                         # first band studied (2.8 kHz)
CLASSES = ["noise-filled", "coded, zeros < 50 %", "coded, zeros >= 50 %"]


def envelopes(x, fs):
    """Sub-block band powers (both channels summed): (sub-blocks, bands B0..21), in dB. STFT of
    256 samples, hop 128: one bin = 172.3 Hz = one unit of EDGES."""
    _f, _t, Z = stft(x.T, fs, window="hann", nperseg=256, noverlap=128, boundary=None, padded=False)
    P = (np.abs(Z) ** 2).sum(axis=0)            # (bins, sub-blocks)
    E = np.array([P[EDGES[b]:EDGES[b + 1]].sum(axis=0) for b in range(B0, len(EDGES) - 1)]).T
    return 10 * np.log10(E + 1e-20)


def classes(wav, q):
    """{(frame, band): class} from the production encoder's trace, first coded channel."""
    import soundfile as sf
    from mule import native, params as E
    x, _ = sf.read(wav, dtype="float64", always_2d=True)
    _m, _v, _fs, tr = native.c_trace(x, E.Params(q_db=q))
    band = pd.DataFrame(tr[tr[:, 0] == 2], columns=native.TRACE_FIELDS["band"])
    band = band[(band.ch == 0) & (band.type == 0) & (band.band >= B0)]
    coef = pd.DataFrame(tr[tr[:, 0] == 0], columns=native.TRACE_FIELDS["coef"])
    coef = coef[(coef.ch == 0) & (coef.type == 0) & (coef.band >= B0)]
    zeros = coef.level.eq(0).groupby([coef.frame, coef.band]).mean()
    out = {}
    for fr, b, a in zip(band.frame, band.band, band.a):
        out[(fr, b)] = 0 if a == 0 else (1 if zeros.get((fr, b), 0) < 0.5 else 2)
    return out


def job(args):
    name, wav, configs = args
    q = float(configs[0].rsplit("_", 1)[1])
    cls = classes(wav, q)
    rows = []
    for cfg in configs:
        r, y, fs, _kbps, _lag = refcodecs.run_aligned(cfg, wav)
        er, ed = envelopes(r, fs), envelopes(y, fs)
        n = min(len(er), len(ed))
        er, ed = er[:n], ed[:n]
        for t in range(1, n // 8):
            j = slice(8 * t - 4, 8 * t + 4)     # frame t's central 1024 samples
            if j.stop > n:
                break
            top = er[j].mean(axis=0).max()
            for k in range(er.shape[1]):
                b = B0 + k
                c = cls.get((t, b))
                sr = er[j, k].std()
                if c is None or sr < 1.5 or er[j, k].mean() < top - 50:
                    continue
                d = ed[j, k] - er[j, k]
                rows.append(dict(item=name, config=cfg, frame=t, band=b, cls=CLASSES[c],
                                 shape_db=float(np.sqrt(np.mean((d - d.mean()) ** 2))),
                                 flat=float(ed[j, k].std() / sr)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--items", required=True)
    ap.add_argument("--set", default="test")
    ap.add_argument("--dump")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        d = pd.DataFrame([r for rows in ex.map(job, [(n, w, configs) for n, w in items]) for r in rows])
    if a.dump:
        d.to_csv(a.dump, index=False)
    print(f"{len(items)} items; cells: long frames, bands {B0}-21 (from 2.8 kHz), varying envelopes")
    for title, sel in [("all items", d)] + [(n, d[d.item == n]) for n, _ in items]:
        print(f"\n{title}")
        share = sel[sel.config == configs[0]].cls.value_counts(normalize=True)
        t = sel.groupby(["cls", "config"]).agg(shape=("shape_db", "mean"), flat=("flat", "median")).unstack()
        print(f"   {'class':22s} {'cells':>6s}  " + "  ".join(f"{c[:12]:>12s}" for c in configs)
              + "   (shape error dB | flattening, median)")
        for c in CLASSES:
            if c not in t.index:
                continue
            print(f"   {c:22s} {share.get(c, 0) * 100:5.1f}%  "
                  + "  ".join(f"{t.loc[c, ('shape', k)]:5.2f} | {t.loc[c, ('flat', k)]:4.2f}" for k in configs))


if __name__ == "__main__":
    main()
