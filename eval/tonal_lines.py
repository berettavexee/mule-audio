"""What each codec does with the original's stable tonal lines (eval/results/N-LOG.md, the author's
remark: Apple's AAC keeps tonal notes better). Lines: local maxima of the original's spectrum
(2048-point STFT, hop 1024, the mid channel) at least --prom dB above the median of the +-1 kHz
around them, within 70 dB of the frame's strongest, from --fmin up, present in a neighbouring
frame too (a partial, not a click). Each line in the decoded file:

    drowned     no longer stands --keep dB above its decoded surroundings (lost in noise, or zeroed)
    attenuated  stands out, more than 3 dB under the original's level
    boosted     stands out, more than 3 dB over
    kept        stands out, within 3 dB

skirt: the power the decoding adds or removes around the line (2 to 6 bins each side, the
line's own bins left out), in dB over the original's: noise spread around a partial (roughness).

For a MULE configuration, where the line went (the encoder's trace, first coded channel, the
long frame centred on the STFT frame): short frame, zero-bit band (noise filling), coefficient
at level 0, or coded.

    python eval/tonal_lines.py mule_-9,mule-sl6v4_-9,opus_128,aapl_q63 --items a,b [--set test]
                               [--match aapl_q63] [--fmin 1] [--prom 12] [--keep 6] [-j N]
                               [--dump lines.csv]

--match REF: each MULE configuration's q is set per item to REF's rate on that item (bisection,
0.01 dB), REF then listed as given. Prints; encodes in temporary directories.
"""
import argparse
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, median_filter
from scipy.signal import stft

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402

NFFT, HOP = 2048, 1024                          # one bin = one long MDCT line (21.5 Hz)
EDGES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 100, 116, 128]
BAND_OF = np.searchsorted(np.array(EDGES) * 8, np.arange(1024), side="right") - 1
REGIONS = [(1000, 4000, "1-4 kHz"), (4000, 10000, "4-10 kHz"), (10000, 20000, "10-20 kHz")]
CLASSES = ["kept", "attenuated", "boosted", "drowned"]
CAUSES = ["short frame", "zero-bit band", "level 0", "coded"]


def spec_db(x, fs):
    """Power spectrogram of the mid channel, dB: (bins, frames); frame k centred on sample
    1024 (k + 1), the long MULE frame k + 1 of an aligned decoding."""
    _f, _t, Z = stft(x.mean(axis=1), fs, window="hann", nperseg=NFFT, noverlap=NFFT - HOP,
                     boundary=None, padded=False)
    return 10 * np.log10(np.abs(Z) ** 2 + 1e-20)


def background(S):
    return median_filter(S, size=(93, 1), mode="nearest")       # +-1 kHz, per frame


def lines(S, fs, fmin, prom):
    """Boolean (bins, frames): the original's stable tonal lines."""
    f = np.arange(S.shape[0]) * fs / NFFT
    peak = (S == maximum_filter1d(S, 5, axis=0)) & (S - background(S) >= prom)
    peak &= S >= S.max(axis=0, keepdims=True) - 70
    peak &= ((f >= fmin) & (f < 20000))[:, None]
    near = maximum_filter1d(peak.astype(np.uint8), 3, axis=0).astype(bool)   # +-1 bin
    stable = np.zeros_like(peak)
    stable[:, 1:] |= near[:, :-1]
    stable[:, :-1] |= near[:, 1:]
    return peak & stable


def mule_q(cfg, wav, target):
    """q (0.01 dB) of MULE configuration cfg whose rate on wav is nearest target (kb/s)."""
    import soundfile as sf
    from mule import native, params as E
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    fam = cfg.rsplit("_", 1)[0]
    base = refcodecs.get(f"{fam}_-9").params.__dict__

    def kb(q):
        return native.c_encode(x, E.Params(**{**base, "q_db": q}))[1] * 8 / (len(x) / fs) / 1000
    lo, hi = -24.0, 4.0                         # rate falls as q rises
    while hi - lo > 0.01:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if kb(mid) > target else (lo, mid)
    return round((lo + hi) / 2, 2)


def causes(cfg, wav):
    """{(frame, line): cause index} from the MULE configuration's trace (first coded channel)."""
    import soundfile as sf
    from mule import native, params as E
    import refcodecs as rc
    x, _ = sf.read(wav, dtype="float64", always_2d=True)
    m = rc.get(cfg)
    _m, _v, _fs, tr = native.c_trace(x, E.Params(**m.params.__dict__))
    band = pd.DataFrame(tr[tr[:, 0] == 2], columns=native.TRACE_FIELDS["band"])
    band = band[band.ch == 0]
    coef = pd.DataFrame(tr[tr[:, 0] == 0], columns=native.TRACE_FIELDS["coef"])
    coef = coef[(coef.ch == 0) & (coef.type == 0)]
    short = set(band.frame[band.type == 1])
    a = {(fr, b): v for fr, b, v in zip(band.frame[band.type == 0], band.band[band.type == 0], band.a[band.type == 0])}
    lev = {(fr, ln): v for fr, ln, v in zip(coef.frame, coef.line, coef.level)}
    return short, a, lev


def job(args):
    name, wav, configs, match, fmin, prom, keep = args
    rows, used = [], []
    ref_rate = None
    if match:
        with tempfile.TemporaryDirectory() as w:
            ref_rate = refcodecs.run(match, wav, w)[2]
    S0 = None
    for cfg in configs:
        run_cfg = cfg
        if match and cfg.startswith("mule"):
            run_cfg = f"{cfg.rsplit('_', 1)[0]}_{mule_q(cfg, wav, ref_rate):g}"
        r, y, fs, kbps, _lag = refcodecs.run_aligned(run_cfg, wav)
        if S0 is None:
            S0 = spec_db(r, fs)
            L = lines(S0, fs, fmin, prom)
            B0 = background(S0)
        Sd = spec_db(y, fs)
        n = min(S0.shape[1], Sd.shape[1])
        Sd = Sd[:, :n]
        Bd = background(Sd)
        Dmax = maximum_filter1d(Sd, 3, axis=0)                  # the line may move a bin
        mc = causes(run_cfg, wav) if cfg.startswith("mule") else None
        P0, Pd = 10 ** (S0[:, :n] / 10), 10 ** (Sd / 10)
        ring = np.zeros(13)
        ring[[0, 1, 2, 3, 4, 8, 9, 10, 11, 12]] = 1        # offsets -6..-2 and 2..6
        from scipy.ndimage import convolve1d
        R0 = convolve1d(P0, ring, axis=0, mode="nearest")
        Rd = convolve1d(Pd, ring, axis=0, mode="nearest")
        bins, frames = np.nonzero(L[:, :n])
        for i, k in zip(bins, frames):
            err = Dmax[i, k] - S0[i, k]
            standing = Dmax[i, k] - Bd[i, k] >= keep
            c = 3 if not standing else (1 if err < -3 else (2 if err > 3 else 0))
            row = dict(item=name, config=cfg, run=run_cfg, kbps=kbps, frame=int(k), bin=int(i),
                       hz=i * fs / NFFT, prom=float(S0[i, k] - B0[i, k]), err=float(err), cls=CLASSES[c],
                       skirt=float(10 * np.log10((Rd[i, k] + 1e-30) / (R0[i, k] + 1e-30))))
            if mc is not None:
                short, a, lev = mc
                t = int(k) + 1
                if t in short:
                    row["cause"] = CAUSES[0]
                elif a.get((t, int(BAND_OF[i])), 0) == 0:
                    row["cause"] = CAUSES[1]
                elif max(abs(lev.get((t, j), 0)) for j in (i - 1, i, i + 1)) == 0:
                    row["cause"] = CAUSES[2]
                else:
                    row["cause"] = CAUSES[3]
            rows.append(row)
        used.append((cfg, run_cfg, kbps))
    return rows, (name, used)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--items", required=True)
    ap.add_argument("--set", default="test")
    ap.add_argument("--match")
    ap.add_argument("--fmin", type=float, default=1.0, help="kHz")
    ap.add_argument("--prom", type=float, default=12.0)
    ap.add_argument("--keep", type=float, default=6.0)
    ap.add_argument("--dump")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set, a.items)
    with ProcessPoolExecutor(a.j) as ex:
        out = list(ex.map(job, [(n, w, configs, a.match, a.fmin * 1000, a.prom, a.keep) for n, w in items]))
    d = pd.DataFrame([r for rows, _ in out for r in rows])
    if a.dump:
        d.to_csv(a.dump, index=False)
    for name, used in (u for _, u in out):
        print(f"{name:32s} " + "  ".join(f"{run} {kb:.1f}" for _c, run, kb in used))
    print(f"\n{len(d[d.config == configs[0]])} lines (stable, {a.prom:g} dB over their +-1 kHz)")

    def table(sel, title):
        t = sel.groupby("config").cls.value_counts(normalize=True).unstack().reindex(columns=CLASSES).fillna(0) * 100
        e = sel.groupby("config").err.median()
        kept = sel[sel.cls == "kept"]
        sk = kept.groupby("config").skirt.median()
        sk90 = kept.groupby("config").skirt.quantile(0.9)
        print(f"\n{title}\n   {'':26s}" + "".join(f"{c:>12s}" for c in CLASSES)
              + "   median dB   skirt of kept lines: median, p90 dB")
        for c in configs:
            if c in t.index:
                print(f"   {c[:26]:26s}" + "".join(f"{t.loc[c, k]:11.1f}%" for k in CLASSES) + f"   {e[c]:+6.1f}"
                      + f"      {sk.get(c, float('nan')):+5.1f}  {sk90.get(c, float('nan')):+5.1f}")
    table(d, "all lines")
    for lo, hi, lab in REGIONS:
        table(d[(d.hz >= lo) & (d.hz < hi)], lab)
    for c in configs:
        if not c.startswith("mule"):
            continue
        s = d[d.config == c]
        x = pd.crosstab(s.cause, s.cls, normalize="all").reindex(index=CAUSES, columns=CLASSES).fillna(0) * 100
        print(f"\n{c}: where the lines went (% of all lines)\n   {'':16s}" + "".join(f"{k:>12s}" for k in CLASSES))
        for cause in CAUSES:
            print(f"   {cause:16s}" + "".join(f"{x.loc[cause, k]:11.1f}%" for k in CLASSES))
    print("\nper item, drowned lines (%)")
    p = d.groupby(["item", "config"]).cls.apply(lambda s: (s == "drowned").mean() * 100).unstack()
    print(p.reindex(columns=configs).round(1).to_string())


if __name__ == "__main__":
    main()
