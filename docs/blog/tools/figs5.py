"""Figures of the fifth blog post (docs/blog/05-ossuaire.md), in the style of figs.py. Audio from
the EBU SQAM excerpts only (violin, female_en); the numbers of figure 1 are those of the post,
from the logs it cites (eval/results/*-LOG.md, docs/LESSONS.md, docs/V4-IDEAS.md, docs/V5-512.md).

    .venv/bin/python docs/blog/tools/figs5.py [names...]      (default: all)
"""
import os
import sys

import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs  # noqa: E402
from figs import BLUE, FILL_BLUE, FILL_ORANGE, GREEN, INK, MUTED, ORANGE, ROOT, plt, save  # noqa: E402

sys.path[:0] = [os.path.join(ROOT, "eval"), os.path.join(ROOT, "py")]
GREY = "#adb5bd"


def _png(fig, name, dpi=90):
    path = os.path.join(figs.FIG, name + ".png")
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print("->", os.path.relpath(path, ROOT))


def _sqam(name):
    import corpus
    import soundfile as sf
    x, fs = sf.read(dict(corpus.items("all"))[name])
    return x, fs


def b5_fig1_carte():
    """The ossuary's map: each idea's measured effect, in the unit of its time; kept ideas in
    colour, buried ones in grey. Bars: a range where the log gives one."""
    panels = [
        ("ODG à 128 kb/s (plus haut = mieux)", 0.01, "seuil d'adoption", [
            ("contrôle du pré-écho (AAC)", 0.010, 0.014, True),
            ("tf_change d'Opus, sur tout dev", 0.003, 0.003, False),
            ("une cible de bruit par trame", 0.004, 0.004, False),
            ("TNS d'AAC", -0.005, -0.005, False),
            ("masques en loi de puissance", -0.03, -0.18, False),
            ("masquage temporel", -0.016, -0.178, False),
            ("tonalité par imprévisibilité (violon)", -0.24, -0.24, False)]),
        ("distance Zimtohrli (plus bas = mieux)", None, None, [
            ("détecteur corrigé + passe des aigus", -3.0, -3.0, True),
            ("table d'Opus en mélange (C75, 96 kb/s)", -4.5, -4.5, True),
            ("blocs de 512, découpage mixte (jouet)", -0.5, -0.5, False),
            ("mixage TF par bande, dans MULE", 0.8, 0.8, False),
            ("table d'Opus seule (environ +60 %)", 10, 10, False)]),
        ("débit (plus bas = mieux)", None, None, [
            ("prédiction des signes", -0.04, -0.04, False),
            ("paquets clés espacés", -0.17, -0.26, False),
            ("contextes appris", -0.3, -0.5, False)]),
    ]
    fig, axs = plt.subplots(3, 1, figsize=(11, 11), gridspec_kw={"height_ratios": [7, 5, 3]})
    for ax, (unit, thr, thr_lab, rows) in zip(axs, panels):
        for i, (lab, a, b, kept) in enumerate(rows):
            y = len(rows) - 1 - i
            lo, hi = min(a, b), max(a, b)
            c = GREEN if kept else GREY
            if hi - lo < 1e-9:
                ax.barh(y, a, height=0.55, color=c, edgecolor=INK if kept else MUTED, lw=1.2)
            else:
                ax.barh(y, hi - lo, left=lo, height=0.55, color=c, edgecolor=INK if kept else MUTED, lw=1.2,
                        hatch="//")
            ax.text(-0.02, y, lab, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=11,
                    color=INK)
        ax.axvline(0, color=INK, lw=1)
        if thr is not None:
            ax.axvline(thr, color=ORANGE, lw=1.3, ls="--")
            ax.text(thr, len(rows) - 0.35, " " + thr_lab, color=ORANGE, fontsize=10.5)
        ax.set_yticks([])
        ax.set_title(unit, loc="left", fontsize=12.5, color=INK)
        ax.spines["left"].set_visible(False)
    axs[1].set_xlim(-5.5, 4)
    axs[1].text(3.9, 0, "hors cadre >", ha="right", va="center", fontsize=10.5, color=MUTED)
    axs[1].set_xlabel("%")
    axs[2].set_xlabel("% du débit")
    axs[0].set_xlabel("ODG")
    fig.text(0.5, -0.03, "vert : gardé ; gris : enterré ; hachures : la fourchette donnée par le journal",
             ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, "b5-fig1-carte")


def b5_fig2_detecteur():
    """The revenant: female speech (EBU SQAM), the frames the transient detector makes short with
    its old memory (3 dB per block) and with the corrected one (1 dB, production)."""
    import dataclasses
    from scipy.signal import stft
    from mule import native
    from mule.params import Params
    x, fs = _sqam("female_en")
    seg = x[: int(8 * fs)]
    short = {}
    for lab, kw in (("ancien", {"tr_decay_db": 3.0}), ("corrigé", {})):
        p = dataclasses.replace(Params(), **kw)
        tr = native.c_trace(np.ascontiguousarray(seg), p)[3]
        band = tr[tr[:, 0] == 2]
        types = {}
        for fr_, bt in zip(band[:, 2], band[:, 4]):
            types[int(fr_)] = int(bt)
        short[lab] = sorted(f for f, t in types.items() if t)
        print(f"   {lab}: {len(short[lab])} short frames of {len(types)}")
    f, t, z = stft(seg.mean(1), fs, nperseg=1024, noverlap=768)
    s = 20 * np.log10(np.abs(z) + 1e-9)
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.pcolormesh(t, f / 1000, s, vmin=s.max() - 90, vmax=s.max(), cmap="magma", shading="auto", rasterized=True)
    ax.set_ylim(0, 8)
    hop = 1024 / fs
    for lab, y, c in (("ancien détecteur", 7.3, ORANGE), ("détecteur corrigé", 6.6, FILL_BLUE)):
        for fr_ in short["ancien" if lab.startswith("ancien") else "corrigé"]:
            ax.add_patch(Rectangle((fr_ * hop, y), hop, 0.45, color=c, lw=0))
        ax.text(t[-1] + 0.1, y + 0.22, lab, color=INK, fontsize=11, va="center")
    ax.set_xlabel("temps (s)")
    ax.set_ylabel("fréquence (kHz)")
    ax.set_title("voix féminine (EBU SQAM) : les trames passées en blocs courts", loc="left", fontsize=13,
                 color=INK)
    _png(fig, "b5-fig2-detecteur")


def b5_fig3_pliage():
    """Schema: an empty high band filled with flat noise (MULE's long frames) or with a copy of
    the spectrum below at the band's energy (folding, as Opus)."""
    rng = np.random.default_rng(3)
    k = np.arange(0, 160)
    harm = sum(np.exp(-0.5 * ((k - c) / 1.2) ** 2) * (1.0 - c / 260) for c in range(9, 160, 11))
    base = 0.08 + 0.9 * harm * np.exp(-k / 120) + 0.05 * rng.random(len(k))
    lo, hi = 120, 160
    src = base[lo - 40:hi - 40]
    energy = np.sqrt(np.mean(base[lo:hi] ** 2))
    noise = np.abs(rng.normal(0, 1, hi - lo))
    noise *= energy / np.sqrt(np.mean(noise ** 2))
    fold = src * energy / np.sqrt(np.mean(src ** 2))
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    for ax, (title, fill, col) in zip(axs, (("l'original", base[lo:hi], INK),
                                            ("rempli de bruit plat", noise, ORANGE),
                                            ("rempli par pliage", fold, BLUE))):
        ax.bar(k[:lo], base[:lo], width=1, color=GREY, lw=0)
        ax.bar(k[lo:hi], fill, width=1, color=col, lw=0)
        ax.axvspan(lo - 0.5, hi - 0.5, color=FILL_ORANGE if col == ORANGE else (FILL_BLUE if col == BLUE else "#f1f3f5"),
                   alpha=0.35, lw=0)
        ax.set_title(title, fontsize=13, color=INK)
        ax.set_xticks([])
        ax.set_xlabel("fréquence")
    axs[2].annotate("", (lo + 20, 0.62), (lo - 20, 0.62), arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.5))
    axs[2].text(lo, 0.67, "copie", color=BLUE, ha="center", fontsize=11)
    axs[0].set_ylabel("niveau")
    axs[0].set_yticks([])
    fig.text(0.5, -0.05, "schéma : la bande de droite n'a reçu aucun bit ; le décodeur ne connaît que son énergie",
             ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, "b5-fig3-pliage")


def b5_fig4_vibrato():
    """MPEG psychoacoustic model 2's unpredictability on the EBU SQAM violin: magnitude and phase
    predicted linearly from the two previous FFT frames; c = |X - X_pred| / (|X| + |X_pred|),
    0 for a perfectly predictable (tonal) line, 1 for noise."""
    x, fs = _sqam("violin")
    seg = x[int(2 * fs): int(6 * fs)].mean(1)
    n, h = 2048, 512
    w = np.hanning(n)
    frames = np.array([np.fft.rfft(seg[i:i + n] * w) for i in range(0, len(seg) - n, h)])
    r, ph = np.abs(frames), np.angle(frames)
    rp = 2 * r[1:-1] - r[:-2]
    pp = 2 * ph[1:-1] - ph[:-2]
    xp = np.maximum(rp, 0) * np.exp(1j * pp)
    c = np.abs(frames[2:] - xp) / (r[2:] + np.abs(rp) + 1e-12)
    s = 20 * np.log10(r[2:] + 1e-9)
    c = np.where(s > s.max() - 50, c, np.nan)
    f = np.fft.rfftfreq(n, 1 / fs) / 1000
    t = (np.arange(len(c)) * h + 2 * h) / fs
    fig, (a, b) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    a.pcolormesh(t, f, s.T, vmin=s.max() - 70, vmax=s.max(), cmap="magma", shading="auto", rasterized=True)
    a.set_title("violon (EBU SQAM) : spectrogramme ; les harmoniques ondulent (vibrato)", loc="left", fontsize=13,
                color=INK)
    im = b.pcolormesh(t, f, c.T, vmin=0, vmax=1, cmap="RdYlBu_r", shading="auto", rasterized=True)
    b.set_title("imprévisibilité selon le modèle 2 de MPEG : bleu = tonal, rouge = « bruit »", loc="left",
                fontsize=13, color=INK)
    fig.colorbar(im, ax=b, shrink=0.9, label="imprévisibilité")
    for ax in (a, b):
        ax.set_ylim(0, 6)
        ax.set_ylabel("fréquence (kHz)")
    b.set_xlabel("temps (s)")
    print(f"   median unpredictability of the strong lines: {np.nanmedian(c):.2f}")
    _png(fig, "b5-fig4-vibrato")


def b5_fig5_decoupages():
    """Schema: one 2048-sample window cut four ways (MULE's long frame, its 8 short blocks, 4
    blocks of 512, and the mixed tiling: 256 around the attack, 512 elsewhere)."""
    rows = [("une trame longue (MULE)", [2048]),
            ("8 blocs courts (MULE)", [256] * 8),
            ("4 blocs de 512 (essayé)", [512] * 4),
            ("découpage mixte (essayé)", [512, 256, 256, 512, 512])]
    fig, ax = plt.subplots(figsize=(12, 4.2))
    for i, (lab, sizes) in enumerate(rows):
        y = len(rows) - 1 - i
        x0 = 0
        for sz in sizes:
            c = FILL_ORANGE if sz == 256 else (FILL_BLUE if sz == 512 else "#e9ecef")
            ax.add_patch(Rectangle((x0 + 8, y + 0.12), sz - 16, 0.66, fc=c, ec=INK, lw=1.2))
            ax.text(x0 + sz / 2, y + 0.45, str(sz), ha="center", va="center", fontsize=10.5, color=INK)
            x0 += sz
        ax.text(-30, y + 0.45, lab, ha="right", va="center", fontsize=11.5, color=INK)
    ax.axvline(640, color=ORANGE, lw=1.5, ls="--")
    ax.text(640, len(rows) + 0.05, "attaque", color=ORANGE, ha="center", fontsize=11)
    ax.set_xlim(-10, 2058)
    ax.set_ylim(-0.2, len(rows) + 0.4)
    ax.axis("off")
    fig.text(0.5, 0.0, "schéma : la même portion de 2 048 échantillons (46 ms), découpée en blocs de transformée",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b5-fig5-decoupages")


def b5_fig6_plan():
    """The ossuary's plan, drawn: five alleys and their tombs."""
    alleys = [("Allée des emprunts", ["tf_change", "mixage TF", "blocs de 512", "TNS", "signes", "dynalloc"]),
              ("Allée de la psychoacoustique", ["imprévisibilité", "loi de puissance", "masquage\ntemporel",
                                                "seuil relatif", "plancher", "aigus inclinés"]),
              ("Allée des bits déplacés", ["trames\nd'attaque", "cible par\ntrame", "contextes\nappris",
                                           "stéréo", "paquets clés", "hystérésis"]),
              ("Allée des mirages", ["23e bande", "pente du bruit", "CMA-ES\nextrapolé"])]
    fig, ax = plt.subplots(figsize=(13, 8.5))
    for j, (name, tombs) in enumerate(alleys):
        y = 8 - 2.1 * j
        ax.add_patch(Rectangle((0.2, y - 1.05), 12.2, 0.35, color="#e9ecef", lw=0))
        ax.text(0.3, y + 0.75, name, fontsize=13, color=INK)
        for i, tb in enumerate(tombs):
            x = 0.6 + i * 2.0
            ax.add_patch(FancyBboxPatch((x, y - 0.6), 1.5, 1.1, boxstyle="round,pad=0,rounding_size=0.45",
                                        fc="#f8f9fa", ec=MUTED, lw=1.3))
            ax.text(x + 0.75, y - 0.05, tb, ha="center", va="center", fontsize=9.5, color=INK)
            ax.text(x + 0.75, y + 0.33, "RIP", ha="center", va="center", fontsize=9, color=MUTED)
    # the revenants' corner
    ax.add_patch(FancyBboxPatch((12.9, 0.6), 3.0, 7.9, boxstyle="round,pad=0,rounding_size=0.3", fc="#ebfbee",
                                ec=GREEN, lw=1.5, ls="--"))
    ax.text(14.4, 8.1, "Carré des\nrevenants", ha="center", va="center", fontsize=13, color=GREEN)
    for k, tb in enumerate(["détecteur de\ntransitoires", "table d'Opus\n(en mélange)", "pliage de\nbande (bientôt ?)"]):
        y = 6.3 - 2.0 * k
        ax.add_patch(FancyBboxPatch((13.4, y - 0.6), 2.0, 1.2, boxstyle="round,pad=0,rounding_size=0.45",
                                    fc="white", ec=GREEN, lw=1.3, ls=":"))
        ax.text(14.4, y, tb, ha="center", va="center", fontsize=9.5, color=INK)
    ax.text(6.3, -0.55, "entrée : débit égal encadré, dev puis test, plusieurs juges", ha="center", fontsize=11,
            color=ORANGE)
    ax.set_xlim(0, 16.2)
    ax.set_ylim(-1, 9.2)
    ax.axis("off")
    save(fig, "b5-fig6-plan")


ALL = [b5_fig1_carte, b5_fig2_detecteur, b5_fig3_pliage, b5_fig4_vibrato, b5_fig5_decoupages, b5_fig6_plan]

if __name__ == "__main__":
    figs.style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
