"""P4.1 / A1: where does a codec lose on an item? NMR per 0.5-Bark band (power mean over frames)
and share of frames above the mask, for several codec configurations side by side.
Usage: python eval/p4_diag.py ITEM CONFIG [CONFIG ...]"""
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import corpus                                    # noqa: E402
import metrics as Mx                             # noqa: E402
import refcodecs                                 # noqa: E402


def band_nmr(ref, deg, fs):
    band, nb, zc, spread, ath, w = Mx._model(fs)
    f = np.fft.rfftfreq(Mx.N_FFT, 1 / fs)
    lo = np.array([f[band == i].min() if np.any(band == i) else np.nan for i in range(nb)])
    num = np.zeros(nb)
    above = np.zeros(nb)
    cnt = 0
    for ch in range(ref.shape[1]):
        R = np.abs(np.fft.rfft(Mx._frames(ref[:, ch]) * w, axis=1)) ** 2
        E = np.abs(np.fft.rfft(Mx._frames(deg[:, ch] - ref[:, ch]) * w, axis=1)) ** 2
        Rb = np.stack([R[:, band == i].sum(1) for i in range(nb)], 1)
        Eb = np.stack([E[:, band == i].sum(1) for i in range(nb)], 1)
        C = Rb @ spread.T
        geo = np.exp(np.mean(np.log(R[:, 1:] + 1e-20), axis=1))
        sfm = 10 * np.log10(geo / (R[:, 1:].mean(axis=1) + 1e-20) + 1e-20)
        al = np.clip(sfm / -60.0, 0, 1)[:, None]
        off = al * (14.5 + zc[None, :]) + (1 - al) * 5.5
        T = np.maximum(C * 10 ** (-off / 10), ath[None, :])
        keep = Rb.sum(1) > 1e-9 * Mx.N_FFT
        r = (Eb / T)[keep]
        num += r.sum(0)
        above += (r > 10 ** 0.15).sum(0)
        cnt += len(r)
    return lo, 10 * np.log10(num / cnt + 1e-20), above / cnt


def main():
    item, cfgs = sys.argv[1], sys.argv[2:]
    wav = dict(corpus.items("all"))[item]
    ref, fs = Mx.load(wav)
    cols = {}
    for c in cfgs:
        with tempfile.TemporaryDirectory() as w:
            dec, _, kb = refcodecs.run(c, wav, w)
            deg, fs2 = Mx.load(dec)
        r_, d_, _ = Mx.align(Mx.subsonic(ref, fs), Mx.subsonic(deg, fs))
        lo, nmr, ab = band_nmr(r_, d_, fs)
        cols[c] = (kb, nmr, ab)
    print(f"{item}: " + "  ".join(f"{c} {kb:.0f} kb/s" for c, (kb, _, _) in cols.items()))
    print("  f_lo(Hz) " + "".join(f"{c[:14]:>16s}" for c in cols) + "    (NMR dB / % frames > +1.5 dB)")
    for i in range(len(lo)):
        if np.isnan(lo[i]):
            continue
        print(f"  {lo[i]:8.0f} " + "".join(f"{cols[c][1][i]:8.1f} {100 * cols[c][2][i]:5.0f}%  " for c in cols))


if __name__ == "__main__":
    main()
