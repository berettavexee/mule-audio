"""Where each codec puts its coding noise: per 0.5-Bark band, the noise-to-mask ratio of the
evaluation's internal model (eval/metrics.py: Schroeder spreading, tonality offset, threshold in
quiet), the same judge for every codec and not MULE's own encoder model. Codecs near 128 kb/s.

    python eval/noise_placement.py [--set test] [--configs mule_-7,opus_128,...] [-j N]
                                   (prints only; encodes in temporary directories)

Per band and codec: the mean NMR in dB (power mean over frames and channels, then over items),
the share of frames where the band's noise exceeds its mask (NMR > 0 dB), and the noise-to-signal
ratio. Then the same in a few frequency regions, and per codec the rate actually spent.
"""
import argparse
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import corpus  # noqa: E402
import metrics  # noqa: E402
import refcodecs  # noqa: E402

DEFAULT = ["mule_-7", "opus_128", "vorbis_q4", "aac_128"]
REGIONS = [(0, 500), (500, 2000), (2000, 6000), (6000, 12000), (12000, 16000), (16000, 20000)]


def per_band(ref, deg, fs):
    """Per 0.5-Bark band: sum over frames of noise/mask, of noise power, of signal power, count of
    frames above the mask, and the frame count (both channels)."""
    band, nb, zc, spread, ath, w = metrics._model(fs)
    acc = np.zeros((5, nb))
    for ch in range(ref.shape[1]):
        R = np.abs(np.fft.rfft(metrics._frames(ref[:, ch]) * w, axis=1)) ** 2
        E = np.abs(np.fft.rfft(metrics._frames(deg[:, ch] - ref[:, ch]) * w, axis=1)) ** 2
        Rb = np.zeros((len(R), nb))
        Eb = np.zeros((len(R), nb))
        for i in range(nb):
            m = band == i
            Rb[:, i] = R[:, m].sum(axis=1)
            Eb[:, i] = E[:, m].sum(axis=1)
        C = Rb @ spread.T
        geo = np.exp(np.mean(np.log(R[:, 1:] + 1e-20), axis=1))
        sfm_db = 10 * np.log10(geo / (R[:, 1:].mean(axis=1) + 1e-20) + 1e-20)
        alpha = np.clip(sfm_db / -60.0, 0, 1)[:, None]
        offset = alpha * (14.5 + zc[None, :]) + (1 - alpha) * 5.5
        T = np.maximum(C * 10 ** (-offset / 10), ath[None, :])
        keep = Rb.sum(axis=1) > 1e-9 * metrics.N_FFT
        r = (Eb / T)[keep]
        acc[0] += r.sum(axis=0)
        acc[1] += Eb[keep].sum(axis=0)
        acc[2] += Rb[keep].sum(axis=0)
        acc[3] += (r > 1).sum(axis=0)
        acc[4] += keep.sum()
    return acc


def job(args):
    cfg, name, wav = args
    with tempfile.TemporaryDirectory() as work:
        dec, _enc, kbps = refcodecs.run(cfg, wav, work)
        ref, fs = sf.read(wav, dtype="float64", always_2d=True)
        deg, _ = sf.read(dec, dtype="float64", always_2d=True)
        ref, deg, _ = metrics.align(ref, deg)
    return cfg, name, kbps, per_band(ref, deg, fs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default="test")
    ap.add_argument("--configs", default=",".join(DEFAULT))
    ap.add_argument("--items")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set)
    if a.items:
        keep = set(a.items.split(","))
        items = [it for it in items if it[0] in keep]
    jobs = [(c, n, w) for c in configs for n, w in items]
    with ProcessPoolExecutor(a.j) as ex:
        res = list(ex.map(job, jobs))
    fs = 44100
    band, nb, zc, *_ = metrics._model(fs)
    f = np.fft.rfftfreq(metrics.N_FFT, 1 / fs)
    lo = np.array([f[band == i].min() if np.any(band == i) else np.nan for i in range(nb)])
    hi = np.array([f[band == i].max() if np.any(band == i) else np.nan for i in range(nb)])
    per = {}
    for cfg, name, kbps, acc in res:
        d = per.setdefault(cfg, {"kbps": [], "nmr": [], "above": [], "nsr": []})
        d["kbps"].append(kbps)
        d["nmr"].append(10 * np.log10(acc[0] / acc[4] + 1e-20))       # per item, per band (dB)
        d["above"].append(acc[3] / acc[4])
        d["nsr"].append(10 * np.log10(acc[1] / (acc[2] + 1e-20) + 1e-20))
    print(f"{len(items)} items of '{a.set}'; judge: the internal model of eval/metrics.py")
    print("rate: " + ", ".join(f"{c} {np.mean(per[c]['kbps']):.1f} kb/s" for c in configs))
    print("\nper 0.5-Bark band: mean NMR (dB, mean over items) / share of frames above the mask")
    print(f"{'band':>14s} " + " ".join(f"{c:>17s}" for c in configs))
    for i in range(nb):
        if np.isnan(lo[i]) or lo[i] > 20500:
            continue
        cells = [f"{np.mean([v[i] for v in per[c]['nmr']]):+6.1f} / {np.mean([v[i] for v in per[c]['above']]):5.1%}"
                 for c in configs]
        print(f"{lo[i]:6.0f}-{hi[i]:5.0f} Hz " + " ".join(f"{s:>17s}" for s in cells))
    print("\nper region: mean NMR (dB) / share above the mask / noise-to-signal (dB)")
    print(f"{'region':>14s} " + " ".join(f"{c:>24s}" for c in configs))
    for rlo, rhi in REGIONS:
        sel = (lo >= rlo) & (lo < rhi)
        cells = []
        for c in configs:
            nmr = np.mean([v[sel].mean() for v in per[c]["nmr"]])
            above = np.mean([v[sel].mean() for v in per[c]["above"]])
            nsr = np.mean([v[sel].mean() for v in per[c]["nsr"]])
            cells.append(f"{nmr:+6.1f} / {above:5.1%} / {nsr:+6.1f}")
        print(f"{rlo:6d}-{rhi:5d} Hz " + " ".join(f"{s:>24s}" for s in cells))


if __name__ == "__main__":
    main()
