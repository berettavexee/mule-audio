"""Where MULE loses to Opus, window by window (2 s windows, 1 s hop).

For each item: Opus at 128 kb/s, MULE (c64 + a8) at the same rate on that item (q found by
bisection), both aligned on the reference. In every window: PEAQ basic ODG of each codec, the
internal NMR per region (0.5-Bark bands grouped: < 2, 2-6, 6-10, 10-16, > 16 kHz), and signal
features (MULE short-block share from the encoder trace, crest of the 23 ms envelope, high-frequency
energy share, spectral flatness).

    python eval/frame_diag.py [--set test] [--items a,b] [-j 8] [--out eval/results/frame_diag.csv]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus      # noqa: E402
import metrics     # noqa: E402
import refcodecs   # noqa: E402
from mule import native, params as E   # noqa: E402

WIN, HOP_S = 2.0, 1.0
REGIONS = [(0, 2000), (2000, 6000), (6000, 10000), (10000, 16000), (16000, 22050)]
V3 = dict(tcq_chain=1, tcq_states=64, coef_a8=1)


def mule_at(x, wav, kbps, work):
    """MULE decode of x at kbps (bisection on q_db), and the encoder trace's block types."""
    dur = len(x) / 44100
    lo, hi = -20.0, 6.0
    best = None
    for _ in range(9):
        q = (lo + hi) / 2
        data = native.c_encode(x, E.Params(q_db=q, **V3))[0]
        enc = os.path.join(work, "m.mule")
        open(enc, "wb").write(data)
        r = refcodecs.audio_bytes(enc, 2) * 8 / dur / 1000
        if best is None or abs(r - kbps) < abs(best[1] - kbps):
            best = (q, r)
        if abs(r - kbps) < 0.5:
            break
        if r > kbps:                            # q_db lower = finer = more bits
            lo = q
        else:
            hi = q
    q, r = best
    open(enc, "wb").write(native.c_encode(x, E.Params(q_db=q, **V3))[0])
    dec = os.path.join(work, "m.wav")
    subprocess.run([os.path.join(os.path.dirname(HERE), "build", "mule-dec"), enc, dec],
                   check=True, stdout=subprocess.DEVNULL)
    _, _, fstart, tr = native.c_trace(x, E.Params(q_db=q, **V3))
    en = tr[tr[:, 0] == np.unique(tr[:, 0])[1]]          # energy records
    ftype = pd.Series(en[:, 4]).groupby(en[:, 2]).max()   # frame -> 0 long, else short
    return dec, q, r, ftype


def peaq_odg(ref, deg, fs):
    with tempfile.TemporaryDirectory() as d:
        r, g = os.path.join(d, "r.wav"), os.path.join(d, "g.wav")
        metrics._to48k(ref, fs, r)
        metrics._to48k(deg, fs, g)
        env = dict(os.environ)
        peaq = metrics._PEAQ_DEFAULT
        env["GST_PLUGIN_PATH"] = os.path.join(os.path.dirname(os.path.dirname(peaq)), "lib", "gstreamer-1.0")
        txt = metrics._run_retry([peaq, r, g], env=env)
    import re
    m = re.search(r"Objective Difference Grade:\s*([-\d.]+)", txt)
    return float(m.group(1)) if m else float("nan")


def region_nmr(ref, deg, fs):
    """NMR (dB, power mean over frames) per frequency region, internal masking model."""
    band, nb, zc, spread, ath, w = metrics._model(fs)
    f = np.fft.rfftfreq(metrics.N_FFT, 1 / fs)
    fc = np.array([f[band == i].mean() for i in range(nb)])
    acc = np.zeros(len(REGIONS)); cnt = 0
    for ch in range(ref.shape[1]):
        R = np.abs(np.fft.rfft(metrics._frames(ref[:, ch]) * w, axis=1)) ** 2
        Er = np.abs(np.fft.rfft(metrics._frames(deg[:, ch] - ref[:, ch]) * w, axis=1)) ** 2
        Rb = np.stack([R[:, band == i].sum(1) for i in range(nb)], 1)
        Eb = np.stack([Er[:, band == i].sum(1) for i in range(nb)], 1)
        C = Rb @ spread.T
        geo = np.exp(np.mean(np.log(R[:, 1:] + 1e-20), axis=1))
        sfm = 10 * np.log10(geo / (R[:, 1:].mean(axis=1) + 1e-20) + 1e-20)
        a = np.clip(sfm / -60.0, 0, 1)[:, None]
        T = np.maximum(C * 10 ** (-(a * (14.5 + zc[None, :]) + (1 - a) * 5.5) / 10), ath[None, :])
        keep = Rb.sum(1) > 1e-9 * metrics.N_FFT
        r = (Eb / T)[keep]
        if not len(r):
            continue
        for k, (lo, hi) in enumerate(REGIONS):
            m = (fc >= lo) & (fc < hi)
            acc[k] += r[:, m].mean(1).sum()
        cnt += len(r)
    return 10 * np.log10(acc / max(cnt, 1) + 1e-20)


def features(ref, fs):
    mono = ref.mean(1)
    env = np.sqrt(np.convolve(mono ** 2, np.ones(1024) / 1024, "valid")[::512] + 1e-12)
    crest = 20 * np.log10(env.max() / np.median(env))
    S = np.abs(np.fft.rfft(metrics._frames(mono) * np.hanning(metrics.N_FFT), axis=1)) ** 2
    f = np.fft.rfftfreq(metrics.N_FFT, 1 / fs)
    hf = S[:, f > 10000].sum() / max(S.sum(), 1e-20)
    flat = np.mean(np.exp(np.mean(np.log(S[:, 1:] + 1e-20), 1)) / (S[:, 1:].mean(1) + 1e-20))
    loud = 10 * np.log10(np.mean(mono ** 2) + 1e-12)
    return crest, 10 * np.log10(hf + 1e-12), flat, loud


def job(args):
    name, wav = args
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    rows = []
    with tempfile.TemporaryDirectory() as work:
        odec, _enc, okbps = refcodecs.run("opus_128", wav, work)
        mdec, q, mkbps, ftype = mule_at(x, wav, okbps, work)
        ref0 = metrics.subsonic(x, fs)
        decs = {}
        for tag, path in (("opus", odec), ("mule", mdec)):
            y, fs2 = metrics.load(path)
            if fs2 != fs:
                import soxr
                y = soxr.resample(y, fs2, fs, quality="VHQ")
            r, y, lag = metrics.align(ref0, metrics.subsonic(y, fs))
            # put both on the reference timeline (lag >= 0: decoder delay removed)
            if lag < 0:
                r = ref0[:len(y)]; y = np.vstack([np.zeros((-lag, y.shape[1])), y])[:len(r)]
            decs[tag] = (r, y)
        n = min(len(decs["opus"][0]), len(decs["mule"][0]))
        ref = decs["opus"][0][:n]
        W, H = int(WIN * fs), int(HOP_S * fs)
        for s in range(0, n - W + 1, H):
            seg = slice(s, s + W)
            rr = ref[seg]
            if np.mean(rr ** 2) < 1e-7:
                continue
            row = {"item": name, "t": s / fs, "opus_kbps": okbps, "mule_kbps": mkbps, "mule_q": q}
            for tag in ("opus", "mule"):
                y = decs[tag][1][:n][seg]
                row[f"odg_{tag}"] = peaq_odg(rr, y, fs)
                for k, v in enumerate(region_nmr(rr, y, fs)):
                    row[f"nmr{k}_{tag}"] = v
            fr0, fr1 = int(s / 1024), int((s + W) / 1024)
            ft = ftype.reindex(range(fr0, fr1 + 1)).dropna()
            row["short"] = float((ft > 0).mean()) if len(ft) else np.nan
            row["crest_db"], row["hf_db"], row["flat"], row["loud_db"] = features(rr, fs)
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="test")
    ap.add_argument("--items")
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(HERE, "results", "frame_diag.csv"))
    a = ap.parse_args()
    items = corpus.items(a.set)
    if a.items:
        keep = a.items.split(",")
        items = [it for it in items if it[0] in keep]
    with ProcessPoolExecutor(a.j) as ex:
        rows = [r for rs in ex.map(job, items) for r in rs]
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    print(f"{len(df)} windows -> {a.out}")


if __name__ == "__main__":
    main()
