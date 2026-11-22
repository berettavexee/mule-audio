"""How the noise of noise-filled bands is shaped in frequency, and how it behaves around attacks
and where the noise stops or falls from one frame to the next (branch v5, docs/TODO.md: the
vertex-centred noise shape against v4's slope). For each long frame and each band from 2.8 kHz
(band 12) up that the encoder noise-filled (the production's trace, first coded channel), on the
mid channel's spectrum (2048-point STFT, hop 1024: frame k is the long MULE frame k + 1):

    level   decoded band power over the original's (dB)
    tilt    the band's upper half over its lower half (dB), decoded minus original
    step    at an edge between two noise-filled bands, the power step across it (3 lines each
            side, dB), decoded minus original: the joins the noise shape gets wrong

Each cell is classed by its frame's context: attack (a short frame just before or after),
drop / rise (the original band's power falls / rises more than --jump dB from the frame before),
silenced (the band was noise-filled in the frame before and is silent or coded now: the step at
its edge then is the noise's end), steady otherwise.

    python eval/noise_shape_diag.py mule_-7[,other_-7] --items a,b [--set all] [--jump 10]
                                    (prints; encodes in temporary directories)

The first configuration's trace classes every configuration's cells: compare configurations that
share the encoder's decisions (written for the decoder-side noise-shape probes of branch v5, since
removed; N-LOG.md).
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
import refcodecs  # noqa: E402
from tonal_lines import EDGES, spec_db  # noqa: E402

NB = len(EDGES) - 1
START = 12


def trace(cfg, wav):
    """(set of short frames, {(frame, band): a}, {(frame, band): q}) of the first coded channel."""
    import soundfile as sf
    from mule import native, params as E
    x, _ = sf.read(wav, dtype="float64", always_2d=True)
    _m, _v, _fs, tr = native.c_trace(x, E.Params(**refcodecs.get(cfg).params.__dict__))
    band = pd.DataFrame(tr[tr[:, 0] == 2], columns=native.TRACE_FIELDS["band"])
    band = band[band.ch == 0]
    short = set(band.frame[band.type == 1])
    lg = band[band.type == 0]
    return short, dict(zip(zip(lg.frame, lg.band), lg.a)), dict(zip(zip(lg.frame, lg.band), lg.q))


def db(p):
    return 10 * np.log10(p + 1e-20)


def job(args):
    name, wav, configs, jump = args
    short, alloc, qv = trace(configs[0], wav)
    qmin = min(qv.values())                     # silent bands carry the lowest level

    def noise(t, b):
        return alloc.get((t, b), -1) == 0 and qv.get((t, b), qmin) > qmin
    rows = []
    for cfg in configs:
        r, y, fs, _kb, _lag = refcodecs.run_aligned(cfg, wav)
        P0, Pd = 10 ** (spec_db(r, fs) / 10), 10 ** (spec_db(y, fs) / 10)
        n = min(P0.shape[1], Pd.shape[1])
        for k in range(1, n):
            t = k + 1
            if t in short or (t, START) not in alloc:
                continue
            ctx0 = "attack" if (t - 1 in short or t + 1 in short) else None
            for b in range(START, NB):
                if not noise(t, b):
                    continue
                lo, hi = 8 * EDGES[b], 8 * EDGES[b + 1]
                mid = (lo + hi) // 2
                p0, pd_ = P0[lo:hi, k].sum(), Pd[lo:hi, k].sum()
                prev = P0[lo:hi, k - 1].sum()
                jmp = db(p0) - db(prev)
                ctx = ctx0 or ("drop" if jmp < -jump else "rise" if jmp > jump else "steady")
                tilt0 = db(P0[mid:hi, k].sum()) - db(P0[lo:mid, k].sum())
                tiltd = db(Pd[mid:hi, k].sum()) - db(Pd[lo:mid, k].sum())
                row = dict(item=name, config=cfg, frame=t, band=b, ctx=ctx, level=db(pd_) - db(p0),
                           tilt=tiltd - tilt0, step=np.nan, silenced=False)
                if b + 1 < NB:
                    e = hi
                    s0 = db(P0[e - 3:e, k].sum()) - db(P0[e:e + 3, k].sum())
                    sd = db(Pd[e - 3:e, k].sum()) - db(Pd[e:e + 3, k].sum())
                    if noise(t, b + 1):
                        row["step"] = sd - s0
                    row["silenced"] = noise(t - 1, b + 1) and not noise(t, b + 1)
                rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--items", required=True)
    ap.add_argument("--set", default="all")
    ap.add_argument("--jump", type=float, default=10.0)
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        d = pd.DataFrame([r for rows in ex.map(job, [(n, w, configs, a.jump) for n, w in items]) for r in rows])
    d["alevel"], d["atilt"], d["astep"] = d.level.abs(), d.tilt.abs(), d.step.abs()

    def show(g, title):
        t = g.groupby(["ctx", "config"], sort=False).agg(
            cells=("level", "size"), level=("level", "median"), alevel=("alevel", "median"),
            tilt=("tilt", "median"), atilt=("atilt", "median"), astep=("astep", "median"),
            astep90=("astep", lambda s: s.quantile(0.9)))
        print(f"\n{title}  (medians, dB; a- = absolute error; astep90 = 90th percentile)")
        print(t.round(2).to_string())
    show(d, "all items")
    for it, g in d.groupby("item", sort=False):
        show(g, it)
    s = d[d.silenced]
    if len(s):
        print("\nedges where the next band's noise stopped since the frame before (step to a coded/silent band)")
        print(s.groupby("config").agg(cells=("tilt", "size"), atilt=("atilt", "median"),
                                      tilt=("tilt", "median")).round(2).to_string())


if __name__ == "__main__":
    main()
