"""Figures 2 to 11 of the first blog post (docs/blog/01-anatomie.md), in a hand-drawn style close
to Excalidraw's (matplotlib's xkcd mode, the Virgil font). Sources: EBU SQAM excerpts of the
corpus (trumpet, castanets, ABBA), synthetic signals, the C encoder's trace (band records:
mask, power, allocation, stereo) and the test-set result CSVs. Text is drawn as paths: the SVGs
are self-contained.

    .venv/bin/python docs/blog/tools/figs.py [names...]      (default: all)

The Virgil font is expected at docs/blog/tools/fonts/Virgil.ttf (see README.md)."""
import os
import subprocess
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import soundfile as sf  # noqa: E402
from matplotlib import font_manager  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIG = os.path.join(os.path.dirname(HERE), "fig")
CORPUS = os.path.join(ROOT, "data", "corpus")
RESULTS = os.path.join(ROOT, "eval", "results")
sys.path.insert(0, os.path.join(ROOT, "py"))
sys.path.insert(0, os.path.join(ROOT, "eval"))
from mule import native, params  # noqa: E402

# Excalidraw's stroke colours; categorical order fixed (validated: dataviz validate_palette.js,
# CVD worst pair 7.0 -> every series is also labelled directly)
INK, MUTED, GRID = "#1e1e1e", "#868e96", "#dee2e6"
BLUE, ORANGE, GREEN, VIOLET = "#1971c2", "#e8590c", "#2f9e44", "#9c36b5"
FILL_BLUE, FILL_ORANGE = "#a5d8ff", "#ffd8a8"
APPLE = "#c2255c"                                # 5th series (figure 11), validated with the four above

EDGES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 100, 116, 128]
FS = 44100


def style():
    font_manager.fontManager.addfont(os.path.join(HERE, "fonts", "Virgil.ttf"))
    plt.xkcd(scale=0.6, length=120, randomness=2)
    plt.rcParams.update({
        "font.family": "Virgil 3 YOFF", "font.size": 13, "svg.fonttype": "path",
        "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "axes.linewidth": 1.2, "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "legend.frameon": False, "path.effects": [],
    })


def save(fig, name):
    os.makedirs(FIG, exist_ok=True)
    path = os.path.join(FIG, name + ".svg")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.15)
    if os.environ.get("FIG_PNG"):               # previews: FIG_PNG=<directory>
        os.makedirs(os.environ["FIG_PNG"], exist_ok=True)
        fig.savefig(os.path.join(os.environ["FIG_PNG"], name + ".png"), dpi=80, bbox_inches="tight")
    plt.close(fig)
    print("->", os.path.relpath(path, ROOT))


# ---------------------------------------------------------------- signal tools

def vorbis_window(n):
    i = np.arange(n)
    return np.sin(np.pi / 2 * np.sin(np.pi * (i + 0.5) / n) ** 2)


_C = {}


def _basis(n):
    if n not in _C:
        m = n // 2
        i, k = np.arange(n), np.arange(m)
        _C[n] = np.sqrt(2 / m) * np.cos(np.pi / m * (i[:, None] + 0.5 + m / 2) * (k[None, :] + 0.5))
    return _C[n]


def mdct_frames(x, n):
    """MDCT (orthonormal, Vorbis window, hop n/2) of a mono signal: (frames, n/2). Frame t covers
    samples [(t - 1) n/2, (t + 1) n/2), as MULE's long frames for n = 2048."""
    m = n // 2
    xp = np.concatenate([np.zeros(m), x, np.zeros(2 * m)])
    t = (len(x) + m - 1) // m + 1
    w = vorbis_window(n)
    return np.array([(xp[j * m:j * m + n] * w) @ _basis(n) for j in range(t)])


def imdct_frames(X, n, length):
    m = n // 2
    w = vorbis_window(n)
    y = np.zeros((len(X) + 1) * m)
    for j, c in enumerate(X):
        y[j * m:j * m + n] += w * (_basis(n) @ c)
    return y[m:m + length]


def band_slices(n):
    """Lines of the 22 bands in a transform of n coefficients (1024 long, 128 short)."""
    f = n // 128
    return [slice(EDGES[b] * f, EDGES[b + 1] * f) for b in range(22)]


def wav(name):
    x, fs = sf.read(os.path.join(CORPUS, name + ".wav"), always_2d=True)
    assert fs == FS
    return x


def encode(x, q_db=-7.0):
    """MULE at q_db: (decoded (L, 2), operations (m, v), frame starts, trace, file bytes)."""
    p = params.Params(q_db=q_db)
    data, _ = native.c_encode(x, p)
    m, v, fstart, tr = native.c_trace(x, p)
    with tempfile.TemporaryDirectory() as d:
        enc, dec = os.path.join(d, "a.mule"), os.path.join(d, "a.wav")
        open(enc, "wb").write(data)
        subprocess.run([os.path.join(ROOT, "build", "mule-dec"), enc, dec], check=True,
                       stdout=subprocess.DEVNULL)
        y, _ = sf.read(dec, always_2d=True)
    return y[:len(x)], (m, v), fstart, tr, data


def db(p):
    return 10 * np.log10(np.maximum(p, 1e-20))


# ---------------------------------------------------------------- figures

def fig2_fenetres():
    """Three overlapping long windows; their squares sum to 1."""
    n, m = 2048, 1024
    w = vorbis_window(n)
    t = np.arange(4 * m)
    fig, ax = plt.subplots(figsize=(9, 3.4))
    tot = np.zeros(4 * m)
    for j, c in enumerate((BLUE, ORANGE, GREEN)):
        s = np.zeros(4 * m)
        s[j * m:j * m + n] = w
        tot += s ** 2
        ax.plot(t / FS * 1000, s, color=c, lw=2)
        ax.text((j * m + m) / FS * 1000, 1.06, f"fenêtre {j + 1}", color=INK, ha="center", fontsize=12)
    ax.plot(t[m:3 * m] / FS * 1000, tot[m:3 * m], color=INK, lw=1.6, ls="--")
    ax.text(3 * m / FS * 1000 + 1, 0.93, "somme des carrés = 1", color=INK, fontsize=12, va="top")
    ax.set_xlabel("temps (ms)")
    ax.set_ylim(0, 1.2)
    ax.set_yticks([0, 0.5, 1])
    ax.set_xlim(0, 4 * m / FS * 1000)
    save(fig, "fig2-fenetres")


def fig3_temps_frequence():
    """Waterfall of a synthetic signal (two tones 80 Hz apart, a click at 70 ms) seen through
    long and short windows."""
    L = int(0.14 * FS)
    t = np.arange(L) / FS
    x = 0.3 * np.sin(2 * np.pi * 1000 * t) + 0.3 * np.sin(2 * np.pi * 1080 * t)
    click = int(0.07 * FS)
    x[click:click + 40] += np.hanning(40) * 2.0 * np.random.default_rng(1).standard_normal(40)
    f = np.fft.rfftfreq(8192, 1 / FS)
    keep = (f >= 500) & (f <= 1600)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    for ax, n, hop, title, note in (
            (axes[0], 2048, 512, "fenêtre longue (2 048 points, 46 ms)",
             "les deux notes sont séparées,\nle clic s'étale sur toute la fenêtre"),
            (axes[1], 256, 256, "fenêtres courtes (256 points, 6 ms)",
             "le clic tient dans une tranche,\nles deux notes se confondent")):
        w = np.hanning(n)
        starts = np.arange(0, L - n + 1, hop)
        spec = np.array([db(np.abs(np.fft.rfft(x[s0:s0 + n] * w, 8192)) ** 2 / (w ** 2).sum())
                         for s0 in starts])[:, keep]
        spec = np.maximum(spec - spec.max(), -50)
        k = len(spec)
        off = 4.0 if n == 2048 else 2.2
        amp = 14.0 if n == 2048 else 7.0
        for j in range(k - 1, -1, -1):
            base = j * off
            yy = base + (spec[j] + 50) / 50 * amp
            hit = starts[j] <= click < starts[j] + n
            z = 2 * (k - j)
            ax.fill_between(f[keep], base, yy, color="white", lw=0, zorder=z)
            ax.plot(f[keep], yy, color=ORANGE if hit else BLUE, lw=1.6 if hit else 1.1, zorder=z + 1)
        ax.set_title(title, fontsize=13, pad=38)
        ax.text(0.5, 1.02, note, transform=ax.transAxes, ha="center", va="bottom", fontsize=11,
                color=MUTED)
        ax.set_xlabel("fréquence (Hz)")
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlim(500, 1600)
        ax.set_ylim(-1, k * off + amp + 1)
    fig.text(0.5, -0.13, "signal synthétique : deux notes à 1 000 et 1 080 Hz, un clic à 70 ms ;\nune ligne "
             "par analyse, le temps monte vers le haut ; en orange, celles qui contiennent le clic",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "fig3-temps-frequence")


def _noisy(x, n, rel_db=-12.0, seed=3):
    """x through MDCTs of size n, with uniform noise rel_db under each band's energy: the
    quantization noise of a codec, without the codec (as eval/results/P1-BLOCKS.md)."""
    rng = np.random.default_rng(seed)
    X = mdct_frames(x, n)
    for c in X:
        for sl in band_slices(n // 2):
            p = np.mean(c[sl] ** 2)
            a = np.sqrt(3 * p * 10 ** (rel_db / 10))
            c[sl] += rng.uniform(-a, a, sl.stop - sl.start)
    return imdct_frames(X, n, len(x))


def fig4_blocs_courts():
    """A castanet attack (SQAM 27): the noise of long windows spreads before it, short blocks
    keep it close."""
    x = wav("castanets").mean(axis=1)
    env = np.convolve(np.abs(x), np.ones(64) / 64, "same")
    i = int(np.argmax((env[2048:] > 0.1) & (env[:-2048] < 0.004))) + 2048   # attack after a quiet
    sl = slice(i - int(0.03 * FS), i + int(0.015 * FS))
    t = (np.arange(len(x))[sl] - i) / FS * 1000
    rows = [("original", x, INK)]
    for n, lab, c in ((2048, "erreur, fenêtres longues", ORANGE), (256, "erreur, blocs courts", BLUE)):
        rows.append((lab, _noisy(x, n) - x, c))
    fig, axes = plt.subplots(3, 1, figsize=(9, 5.6), sharex=True)
    lim = np.abs(x[sl]).max() * 1.05
    for ax, (lab, s, c) in zip(axes, rows, strict=True):
        ax.plot(t, s[sl], color=c, lw=1.0)
        ax.set_ylim(-lim if lab == "original" else -lim / 4, lim if lab == "original" else lim / 4)
        ax.axvline(0, color=MUTED, lw=1, ls="--")
        ax.set_yticks([])
        ax.text(-29.5, (lim if lab == "original" else lim / 4) * 0.72, lab, color=INK, fontsize=12)
    axes[1].annotate("pré-écho : du bruit\navant l'attaque", xy=(-12, lim / 8), xytext=(-27, -lim / 5.5),
                     fontsize=11, color=INK, arrowprops=dict(arrowstyle="->", color=INK))
    axes[0].text(-0.6, -lim * 0.8, "attaque", color=MUTED, fontsize=11, ha="right")
    axes[2].set_xlabel("temps autour de l'attaque (ms)")
    fig.text(0.5, -0.03, "erreurs à l'échelle × 4 ; simulation : bruit 12 dB sous l'énergie de chaque bande",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "fig4-blocs-courts")


def _trumpet():
    if not hasattr(_trumpet, "d"):
        x = wav("trumpet")
        y, ops, fstart, tr, _ = encode(x)
        _trumpet.d = x, y, tr
    return _trumpet.d


def _loud_long_frame(x, tr):
    bd = tr[(tr[:, 0] == 2) & (tr[:, 3] == 0)]
    frames = np.unique(bd[:, 2])
    types = {f: bd[bd[:, 2] == f, 4].max() for f in frames}
    ok = [f for f in frames[2:-2] if types[f] == 0 and types[f - 1] == 0 and types[f + 1] == 0]
    e = [np.sum(x[max(0, 1024 * (f - 1)):1024 * (f + 1)] ** 2) for f in ok]
    return ok[int(np.argsort(e)[len(e) * 3 // 4])]


def fig5_raies():
    """What a spectral line is: a synthetic note (220 Hz and its harmonics) over one long block,
    and its first 64 MDCT coefficients, one stem per line, grouped by 8 into MULE's lowest
    bands."""
    n = np.arange(4096)
    amps = [1.0, 0.6, 0.45, 0.3, 0.2, 0.12]
    x = sum(a * np.sin(2 * np.pi * 220 * (h + 1) * n / FS + h) for h, a in enumerate(amps)) * 0.3
    seg = x[1024:3072]
    X = mdct_frames(x, 2048)[2]                  # frame 2 covers samples [1024, 3072)
    a = np.abs(X[:64])
    a /= a.max()
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1, 1.7], "wspace": 0.35})
    ms = np.arange(2048) / FS * 1000
    top = np.abs(seg).max()
    ax.plot(ms, seg, color=MUTED, lw=1.0)
    ax.plot(ms, vorbis_window(2048) * top, color=ORANGE, lw=1.4, ls="--")
    ax.set_title("2 048 échantillons (46 ms)", fontsize=13)
    ax.set_xlabel("temps (ms)")
    ax.set_yticks([])
    ax.text(23, -top * 1.2, "fenêtre", color=ORANGE, fontsize=11, ha="center")
    ax.set_ylim(-top * 1.35, top * 1.2)
    fig.patches.append(matplotlib.patches.FancyArrowPatch(
        (0.355, 0.5), (0.425, 0.5), transform=fig.transFigure, arrowstyle="->", mutation_scale=18,
        color=INK, lw=1.5))
    fig.text(0.39, 0.56, "MDCT", ha="center", fontsize=13, color=INK)
    k = np.arange(64)
    for b in range(0, 8, 2):
        bx.axvspan(8 * b - 0.5, 8 * b + 7.5, color="#f1f3f5", lw=0, zorder=0)
    bx.vlines(k, 0, a, color=BLUE, lw=1.6)
    bx.plot(k, a, "o", color=BLUE, ms=3.5)
    bx.set_xlim(-1, 64)
    bx.set_ylim(0, 1.35)
    bx.set_yticks([])
    bx.set_xticks([0, 8, 16, 24, 32, 40, 48, 56, 64])
    bx.set_xticklabels([f"{round(i * FS / 2048)}" for i in range(0, 65, 8)], fontsize=10)
    bx.set_xlabel("fréquence (Hz) : une raie tous les 21,5 Hz")
    bx.set_title("les 64 premières raies (sur 1 024)", fontsize=13)
    p = int(np.argmax(a))
    bx.annotate("une raie = un coefficient :\nla quantité de son à cette\nfréquence (ici, la note\nà 220 Hz)",
                xy=(p + 0.3, a[p]), xytext=(17, 0.78), fontsize=11, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK))
    bx.text(44, 0.42, "ses harmoniques :\n440, 660, 880 Hz…", fontsize=11, color=INK)
    bx.annotate("", xy=(-0.4, 1.22), xytext=(7.4, 1.22), arrowprops=dict(arrowstyle="<->", color=INK))
    bx.text(8.5, 1.18, "8 raies = la bande 0 de MULE (172 Hz)", fontsize=11, color=INK)
    save(fig, "fig5-raies")


def fig6_bandes():
    """A trumpet frame's MDCT spectrum (SQAM 21) with MULE's 22 bands."""
    x, _, tr = _trumpet()
    t = _loud_long_frame(x, tr)
    X = mdct_frames(x[:, 0], 2048)[t]
    f = (np.arange(1024) + 0.5) * FS / 2048 / 1000
    p = db(X ** 2)
    p -= p.max()
    fig, ax = plt.subplots(figsize=(10, 4))
    for b, sl in enumerate(band_slices(1024)):
        if b % 2 == 0:
            ax.axvspan(f[sl.start] - 0.0108, f[sl.stop - 1] + 0.0108, color="#f1f3f5", lw=0, zorder=0)
    ax.plot(f, p, color=BLUE, lw=1.0, zorder=3)
    for b in (12, 14, 16, 17, 18, 19, 20, 21):
        sl = band_slices(1024)[b]
        mid = (f[sl.start] + f[sl.stop - 1]) / 2
        ax.text(mid, 3, str(b), ha="center", fontsize=11, color=MUTED)
    ax.axvspan(20.0, 22.05, color="none", hatch="//", ec=GRID, lw=0, zorder=1)
    ax.text(21.0, -60, "non\ncodé", ha="center", fontsize=11, color=MUTED, zorder=4)
    ax.annotate("bandes 0 à 7 :\n172 Hz chacune", xy=(0.7, -8), xytext=(2.5, -20), fontsize=11,
                color=INK, arrowprops=dict(arrowstyle="->", color=INK))
    ax.set_xlim(0, 22.05)
    ax.set_ylim(-95, 10)
    ax.set_xlabel("fréquence (kHz)")
    ax.set_ylabel("niveau (dB)")
    ax.text(17.35, -12, "bande 21 :\n17,2 à 20 kHz", fontsize=11, color=INK)
    save(fig, "fig6-bandes")


def fig7_masque():
    """One trumpet frame: signal per line, MULE's mask per band, the coding noise measured on the
    decoded file."""
    x, y, tr = _trumpet()
    t = _loud_long_frame(x, tr)
    r = tr[(tr[:, 0] == 2) & (tr[:, 2] == t) & (tr[:, 3] == 0)]
    r = r[np.argsort(r[:, 5])]
    XL, XR = (mdct_frames(x[:, c], 2048)[t] for c in (0, 1))
    YL, YR = (mdct_frames(y[:, c], 2048)[t] for c in (0, 1))
    f = (np.arange(1024) + 0.5) * FS / 2048
    sig, mk, nz = np.zeros(1024), np.zeros(1024), np.zeros(1024)
    for b, sl in enumerate(band_slices(1024)):
        ms = r[b, 7]
        xs = (XL[sl] + XR[sl]) / np.sqrt(2) if ms else XL[sl]
        ys = (YL[sl] + YR[sl]) / np.sqrt(2) if ms else YL[sl]
        sig[sl] = xs ** 2
        mk[sl] = 10 ** (r[b, 9] / 1000)
        nz[sl] = np.mean((xs - ys) ** 2)
    ref = db(sig).max()
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(f, db(sig) - ref, color=MUTED, lw=0.8, label="signal")
    ax.step(f, db(mk) - ref, where="mid", color=ORANGE, lw=2.2, label="seuil de masquage")
    ax.step(f, db(nz) - ref, where="mid", color=BLUE, lw=2.2, label="bruit de codage")
    ax.set_xscale("log")
    ax.set_xlim(60, 20000)
    ax.set_ylim(-110, 5)
    ax.set_xticks([100, 300, 1000, 3000, 10000])
    ax.set_xticklabels(["100 Hz", "300 Hz", "1 kHz", "3 kHz", "10 kHz"])
    ax.set_ylabel("niveau (dB)")
    ax.minorticks_off()
    box = dict(facecolor="white", edgecolor="none", pad=1.5)
    ax.text(70, -5, "signal (trompette)", color=MUTED, fontsize=12)
    ax.text(66, -63, "seuil de masquage", color=ORANGE, fontsize=12, bbox=box, zorder=10)
    ax.text(66, -97, "bruit de codage", color=BLUE, fontsize=12, bbox=box, zorder=10)
    fig.text(0.5, -0.03, "une trame de MULE au réglage par défaut (128 kb/s en moyenne) ; bruit mesuré sur le fichier décodé, par bande",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "fig7-masque")


def fig8_quantification():
    """The same signal rounded with a coarse and a fine step: the error stays within ±D/2."""
    t = np.linspace(0, 1, 400)
    s = 0.8 * np.sin(2 * np.pi * t) + 0.3 * np.sin(2 * np.pi * 3 * t + 0.5)
    fig, axes = plt.subplots(2, 2, figsize=(10, 4.8), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1]})
    for j, (d, lab) in enumerate(((0.5, "pas D = 0,5"), (0.125, "pas D = 0,125"))):
        q = d * np.round(s / d)
        a, e = axes[0, j], axes[1, j]
        a.plot(t, s, color=MUTED, lw=1.5)
        a.step(t, q, where="mid", color=BLUE, lw=2)
        a.set_title(lab, fontsize=13)
        a.set_yticks([])
        a.set_ylim(-1.3, 1.3)
        e.plot(t, s - q, color=ORANGE, lw=1.4)
        e.axhspan(-d / 2, d / 2, color="#fff4e6", lw=0, zorder=0)
        e.set_ylim(-0.3, 0.3)
        e.set_yticks([])
        e.set_xticks([])
        e.text(1.0, 0.18, f"erreur, entre ± D/2", ha="right", color=INK, fontsize=11)
    axes[0, 0].text(0.02, 1.05, "signal", color=MUTED, fontsize=12)
    axes[0, 0].text(0.30, -1.2, "valeur arrondie", color=BLUE, fontsize=12)
    fig.text(0.5, -0.02, "pas divisé par 4 : erreur 4 fois plus petite, bruit 12 dB plus bas (D²/12) ; "
             "chaque division par 2 coûte environ 1 bit par coefficient", ha="center", color=MUTED, fontsize=11)
    save(fig, "fig8-quantification")


def _abba():
    if not hasattr(_abba, "d"):
        x = wav("abba")
        y, ops, fstart, tr, data = encode(x)
        _abba.d = x, ops, fstart, tr, data
    return _abba.d


def _op_bits(ops):
    """Bits of each coding operation: adaptive models from uniform (no reset), raw bits as is."""
    m, v = ops
    bits = np.zeros(len(m))
    raw = m < 0
    bits[raw] = -m[raw]
    off = params.OFF
    for name, nsym, nctx in params.STREAMS:
        sel = (m >= off[name]) & (m < off[name] + nctx)
        if sel.any():
            bits[sel] = native.stream_cost_each(nsym, nctx, m[sel] - off[name], v[sel].astype(np.int32))
    return bits


def fig9_bits():
    """Where the budget goes (ABBA, SQAM 69, at 128 kb/s): mean rate per band, and the split of
    the whole stream."""
    x, ops, fstart, tr, data = _abba()
    bits = _op_bits(ops)
    dur = len(x) / FS
    co = tr[tr[:, 0] == 0]
    en = tr[tr[:, 0] == 1]
    bd = tr[tr[:, 0] == 2]
    # label of each op: band of the last coefficient record, side info after an energy record or a
    # frame start, until the next coefficient
    ev_op = np.concatenate([co[:, 1], en[:, 1], fstart[:-1]])
    ev_lab = np.concatenate([co[:, 5], np.full(len(en), -1), np.full(len(fstart) - 1, -2)])
    o = np.lexsort((ev_lab < 0, ev_op))         # at equal op: side info first, then the coefficient
    ev_op, ev_lab = ev_op[o], ev_lab[o]
    lab = ev_lab[np.searchsorted(ev_op, np.arange(len(bits)), side="right") - 1]
    raw = ops[0] < 0
    kb = len(data) * 8 / dur / 1000
    per_band = np.array([bits[(lab == b)].sum() for b in range(22)]) / dur / 1000
    side = bits[lab == -1].sum() / dur / 1000
    head = bits[lab == -2].sum() / dur / 1000
    signs = bits[(lab >= 0) & raw].sum() / dur / 1000
    tot = bits.sum() / dur / 1000
    print(f"   abba: file {kb:.1f} kb/s, estimated {tot:.1f}; bands {per_band.sum():.1f} "
          f"(signs {signs:.1f}), energies+alloc {side:.1f}, frame headers {head:.1f}; "
          f"short frames {np.mean(bd[:, 4] > 0):.2%}")
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [3.2, 1]})
    ax.bar(np.arange(22), per_band, color=FILL_BLUE, edgecolor=BLUE, lw=1.2, width=0.8)
    ax.set_xticks([0, 4, 8, 12, 16, 20])
    ax.set_xticklabels(["0\n0 Hz", "4\n690 Hz", "8\n1,4 kHz", "12\n2,8 kHz", "16\n6 kHz", "20\n13,4 kHz"],
                       fontsize=11)
    ax.set_ylabel("kb/s")
    ax.set_xlabel("bande")
    ax.set_title("coefficients, par bande", fontsize=13)
    parts = [("coefficients\n(sans les signes)", per_band.sum() - signs, FILL_BLUE, BLUE),
             ("signes", signs, "#d0ebff", BLUE),
             ("énergies et\nallocations", side, FILL_ORANGE, ORANGE),
             ("en-têtes de trame", head, "#ffe8cc", ORANGE)]
    y0, ylab = 0, -1e9
    for name, v, fc, ec in parts:
        bx.bar(0, v, bottom=y0, color=fc, edgecolor=ec, lw=1.2, width=0.6)
        ylab = max(y0 + v / 2, ylab + 0.15 * tot)        # labels kept apart
        bx.annotate(f"{name} : {v / tot:.0%}", xy=(0.3, y0 + v / 2), xytext=(0.5, ylab), va="center",
                    fontsize=11, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
        y0 += v
    bx.set_xlim(-0.4, 2.2)
    bx.set_ylim(0, tot * 1.3)
    bx.set_xticks([])
    bx.set_title(f"tout le flux, {tot:.0f} kb/s", fontsize=13)
    bx.spines["bottom"].set_visible(False)
    fig.text(0.5, -0.15, "ABBA (EBU SQAM 69), 15 s au réglage par défaut : débit moyen de chaque partie du flux",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "fig9-bits")


def fig10_stereo():
    """The encoder's stereo choice per band and frame (ABBA, SQAM 69)."""
    x, ops, fstart, tr, data = _abba()
    bd = tr[(tr[:, 0] == 2) & (tr[:, 3] == 0) & (tr[:, 8] == 0)]
    T = int(bd[:, 2].max()) + 1
    grid = np.full((22, T), np.nan)
    grid[bd[:, 5], bd[:, 2]] = bd[:, 7]
    # coefficient share in M/S (bands weighted by their width)
    w = np.diff(EDGES[:23])
    share = np.nansum(grid * w[:, None]) / np.sum(w[:, None] * ~np.isnan(grid))
    fig, ax = plt.subplots(figsize=(10, 4))
    from matplotlib.colors import ListedColormap
    ax.imshow(grid, aspect="auto", origin="lower", cmap=ListedColormap(["#f1f3f5", ORANGE]),
              extent=(0, T * 1024 / FS, -0.5, 21.5), interpolation="nearest")
    ax.set_yticks([0, 8, 12, 16, 20])
    ax.set_yticklabels(["0 (0 Hz)", "8 (1,4 kHz)", "12 (2,8 kHz)", "16 (6 kHz)", "20 (13,4 kHz)"],
                       fontsize=11)
    ax.set_xlabel("temps (s)")
    ax.set_ylabel("bande")
    ax.set_title(f"en orange : M/S ; en gris : L/R ({share:.0%} des coefficients en M/S)", fontsize=13)
    save(fig, "fig10-stereo")


def fig11_courbes():
    """ODG against the real rate, on the 30 test excerpts: MULE v3, Opus, Vorbis, FDK-AAC and Apple's AAC
    (qaac, TVBR)."""
    ref = pd.read_csv(os.path.join(RESULTS, "ref_test.csv"))
    aac = pd.read_csv(os.path.join(RESULTS, "aac_test.csv"))
    v3 = pd.read_csv(os.path.join(RESULTS, "v3_test.csv"))
    aapl = pd.read_csv(os.path.join(RESULTS, "aapl_test.csv"))
    df = pd.concat([ref, aac, aapl, v3])
    df["fam"] = df.config.str.split("_").str[0]
    g = df.groupby(["fam", "config"])[["kbps", "odg"]].mean().reset_index()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color=GRID, lw=1, zorder=0)
    ax.text(86, 0.01, "0 : imperceptible", fontsize=11, color=MUTED, ha="left", va="bottom")
    for fam, lab, c, mk in (("aac", "AAC (FDK)", VIOLET, "s"), ("aapl", "AAC (Apple)", APPLE, "v"),
                            ("vorbis", "Vorbis", GREEN, "^"),
                            ("opus", "Opus", ORANGE, "D"), ("mule", "MULE v3", BLUE, "o")):
        s = g[g.fam == fam].sort_values("kbps")
        s = s[(s.kbps > 95) & (s.kbps < 205)]
        ax.plot(s.kbps, s.odg, color=c, lw=2, marker=mk, ms=7)
        ax.text(s.kbps.iloc[0] - 2, s.odg.iloc[0], lab, color=INK, fontsize=12, ha="right", va="center")
    for r in (128, 160):
        ax.axvline(r, color=MUTED, lw=1, ls="--", zorder=0)
    ax.set_xlim(85, 202)
    ax.set_ylim(-1.0, 0.1)
    ax.text(201, -0.98, "−1 : perceptible, pas gênant", fontsize=11, color=MUTED, ha="right", va="bottom")
    ax.set_xlabel("débit réel (kb/s)")
    ax.set_ylabel("ODG (PEAQ)")
    fig.text(0.5, -0.07, "moyenne sur les 30 extraits du jeu de test, jamais utilisés pour les réglages",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "fig11-courbes")


ALL = [fig2_fenetres, fig3_temps_frequence, fig4_blocs_courts, fig5_raies, fig6_bandes, fig7_masque,
       fig8_quantification, fig9_bits, fig10_stereo, fig11_courbes]

if __name__ == "__main__":
    style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
