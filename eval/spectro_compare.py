"""Spectrograms of several audio files side by side, on one colour scale, with MULE's band edges:
to compare an original with its decodings by eye (N-LOG.md, the highs of ABBA and the castanets).

    python eval/spectro_compare.py a.wav b.wav [...] [-o out.png] [--fmin 8] [--fmax 22]
                                   [--tmin 0] [--tmax 0] [--nfft 2048] [--range 80] [--diff]
                                   [--rows] [--no-edges] [--dpi 160] [--scale linear|log|bark]

The first file is the reference: the colour scale runs from its maximum down by --range dB in the
frequency range shown. --diff adds, under each other file, its difference to the reference in dB
(blue: missing, red: added; files assumed aligned, as eval/refcodecs.run_aligned writes them).
--scale: the frequency axis, linear (the default), log, or Bark (Traunmueller's formula: the
critical bands of hearing, each the same height). Reads the files, writes the image only (default: spectro_compare.png in the current directory).
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from scipy.signal import stft  # noqa: E402

EDGES_KHZ = [e * 8 * 22.05 / 1024 for e in (60, 78, 100, 116)]   # bands 19-21 and the top: 10.3 to 20 kHz
BARK_TICKS_KHZ = [0.1, 0.2, 0.5, 1, 2, 3, 5, 8, 10, 13, 16, 20]


def bark(f_khz):
    """Traunmueller (1990): critical band rate (Bark) of a frequency in kHz."""
    f = np.asarray(f_khz, float) * 1000
    return 26.81 * f / (1960 + f) - 0.53


def spectrogram(path, nfft, tmin, tmax):
    x, fs = sf.read(path, dtype="float64", always_2d=True)
    x = x.mean(axis=1)
    s0 = int(tmin * fs)
    s1 = int(tmax * fs) if tmax > 0 else len(x)
    f, t, Z = stft(x[s0:s1], fs, window="hann", nperseg=nfft, noverlap=nfft * 3 // 4)
    return f / 1000, t + tmin, 20 * np.log10(np.abs(Z) + 1e-9)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default="spectro_compare.png")
    ap.add_argument("--fmin", type=float, default=0.0, help="kHz")
    ap.add_argument("--fmax", type=float, default=22.05, help="kHz")
    ap.add_argument("--tmin", type=float, default=0.0, help="s")
    ap.add_argument("--tmax", type=float, default=0.0, help="s (0: the end)")
    ap.add_argument("--nfft", type=int, default=2048)
    ap.add_argument("--range", type=float, default=80.0, help="dB shown under the reference's maximum")
    ap.add_argument("--diff", action="store_true", help="add the difference to the first file")
    ap.add_argument("--rows", action="store_true", help="one file per row (default: per column)")
    ap.add_argument("--dpi", type=int, default=160, help="image resolution (160)")
    ap.add_argument("--no-edges", action="store_true", help="no MULE band edges")
    ap.add_argument("--scale", choices=("linear", "log", "bark"), default="linear",
                    help="frequency axis (log: from --fmin, at least 0.05 kHz)")
    a = ap.parse_args()
    if a.scale == "log":
        a.fmin = max(a.fmin, 0.05)
    fy = bark if a.scale == "bark" else (lambda v: v)

    specs = [spectrogram(p, a.nfft, a.tmin, a.tmax) for p in a.files]
    f = specs[0][0]
    sel = (f >= a.fmin) & (f <= a.fmax)
    top = specs[0][2][sel].max()
    n = len(specs)
    nr = 2 if a.diff and n > 1 else 1
    shape = (n, nr) if a.rows else (nr, n)
    size = (6 * nr, 2.8 * n) if a.rows else (4.5 * n, 3.6 * nr)
    fig, axs = plt.subplots(*shape, figsize=size, squeeze=False, sharex=True, sharey=True,
                            layout="constrained")
    for k, (path, (fk, t, S)) in enumerate(zip(a.files, specs)):
        ax = axs[k, 0] if a.rows else axs[0, k]
        m = min(S.shape[1], specs[0][2].shape[1])
        im = ax.pcolormesh(t[:m], fy(fk[sel]), S[sel][:, :m], vmin=top - a.range, vmax=top, shading="auto",
                           cmap="magma")
        ax.set_title(os.path.splitext(os.path.basename(path))[0], fontsize=9)
        if nr == 2:
            dx = axs[k, 1] if a.rows else axs[1, k]
            if k == 0:
                dx.axis("off")
            else:
                d = S[sel][:, :m] - specs[0][2][sel][:, :m]
                live = specs[0][2][sel][:, :m] > top - a.range
                dim = dx.pcolormesh(t[:m], fy(fk[sel]), np.where(live, d, 0), vmin=-20, vmax=20,
                                    shading="auto", cmap="RdBu_r")
                dx.set_title("difference (dB)", fontsize=9)
        for x in (axs[k] if a.rows else axs[:, k]):
            if not a.no_edges and x.axison:
                for e in EDGES_KHZ:
                    if a.fmin <= e <= a.fmax:
                        x.axhline(fy(e), color="cyan", lw=0.5, ls="--")
    for x in axs.flat:
        if x.axison:
            if a.scale == "log":
                x.set_yscale("log")
            x.set_ylim(fy(a.fmin), fy(a.fmax))
            if a.scale == "bark":
                ticks = [v for v in BARK_TICKS_KHZ if a.fmin <= v <= a.fmax]
                x.set_yticks(bark(ticks), [f"{v:g}" for v in ticks])
    fig.supxlabel("s")
    fig.supylabel("kHz" + (" (Bark scale)" if a.scale == "bark" else ""))
    if not a.no_edges:
        fig.suptitle("dashed: MULE's band edges, 10.3 / 13.4 / 17.2 / 20 kHz", fontsize=9, color="0.4")
    fig.colorbar(im, ax=axs[:, 0] if a.rows else axs[0, :], shrink=0.8, label="dB")
    if nr == 2 and n > 1:
        fig.colorbar(dim, ax=axs[:, 1] if a.rows else axs[1, :], shrink=0.8, label="dB vs first")
    fig.savefig(a.out, dpi=a.dpi)
    print("->", a.out)


if __name__ == "__main__":
    main()
