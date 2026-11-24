"""Figures of the fourth blog post (docs/blog/04-juges.md), in the style of figs.py (same font,
same palette). Sources:
- figure 2: the PEAQ MOV attribution of eval/results/E2-LOG.md (17/11/2026, dev, 128 kb/s);
- figure 3: the 300-track campaign (data/campaign/matched_mule-mule_br-mule_brC75-opus-aac.csv,
  statistics only: the excerpts are copyrighted);
- figure 4: the two CMA-ES searches (eval/results/m6_search_extrapolated.csv, m6_search.csv);
- figure 5: the ABX scores of eval/results/G3-ABX.md and N-LOG.md (m6z1, 22/11/2026);
- figure 6: EBU SQAM string quartet, MULE --bitrate and Opus near 96 kb/s, Zimtohrli on 1 s
  windows and its similarity split into intensity and structure (eval/zimt_diag.py's NSIM).

    .venv/bin/python docs/blog/tools/figs4.py [names...]      (default: all)
"""
import functools
import os
import sys

import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs  # noqa: E402
from figs import (BLUE, FILL_BLUE, FILL_ORANGE, GREEN, INK, MUTED, ORANGE, ROOT, VIOLET,  # noqa: E402
                  plt, save)

CAMPAIGN = os.path.join(ROOT, "data", "campaign", "matched_mule-mule_br-mule_brC75-opus-aac.csv")


def fr(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def _box(ax, x, y, w, h, text, ec=INK, fc="white", fs=12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                ec=ec, fc=fc, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK)


def _arrow(ax, x0, y0, x1, y1):
    ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="->", color=INK, lw=1.4))


def b4_fig1_schema():
    """What every judge does: two signals through a model of the ear, compared, then a score."""
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    _box(ax, 0.1, 2.6, 1.9, 0.9, "original")
    _box(ax, 0.1, 0.7, 1.9, 0.9, "décodé", ec=BLUE, fc=FILL_BLUE)
    _box(ax, 2.8, 2.6, 2.4, 0.9, "modèle d'oreille\n(filtres, sonie, masque)", fs=11)
    _box(ax, 2.8, 0.7, 2.4, 0.9, "modèle d'oreille\n(le même)", fs=11)
    _box(ax, 6.0, 1.45, 2.0, 1.3, "comparaison\ndes deux images\ninternes", fs=11)
    _box(ax, 8.8, 1.6, 2.1, 1.0, "une note\n(ODG, distance)", ec=ORANGE, fc=FILL_ORANGE, fs=11)
    _arrow(ax, 2.0, 3.05, 2.8, 3.05)
    _arrow(ax, 2.0, 1.15, 2.8, 1.15)
    _arrow(ax, 5.2, 3.05, 6.0, 2.4)
    _arrow(ax, 5.2, 1.15, 6.0, 1.8)
    _arrow(ax, 8.0, 2.1, 8.8, 2.1)
    ax.text(7.0, 0.55, "calibrée sur des tests d'écoute\n(PEAQ : un petit réseau de neurones)", ha="center",
            fontsize=10.5, color=MUTED)
    save(fig, "b4-fig1-schema")


def b4_fig2_mov():
    """The MULE-Opus PEAQ basic gap at 128 kb/s, attributed to each MOV (E2-LOG.md, step 0)."""
    rows = [("ADBB (distorsion des\ntrames dégradées)", 0.066), ("BandwidthTestB\n(bande passante)", 0.025),
            ("EHSB (structure\nharmonique de l'erreur)", 0.007), ("les sept autres\n(chacune)", 0.005),
            ("Total NMRB\n(bruit sur masque)", -0.033)]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for i, (lab, v) in enumerate(rows):
        y = len(rows) - 1 - i
        good = v < 0
        ax.barh(y, v, color=FILL_BLUE if good else FILL_ORANGE, edgecolor=BLUE if good else ORANGE,
                lw=1.2, height=0.6)
        ax.text(v + (0.002 if v >= 0 else -0.002), y, ("< " if i == 3 else "") + fr(v, 3).replace("-", "−"),
                va="center", ha="left" if v >= 0 else "right", fontsize=12, color=INK)
    ax.axvline(0, color=INK, lw=1.2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=11.5)
    ax.set_xlim(-0.05, 0.085)
    ax.set_xlabel("ODG que MULE gagnerait avec la valeur d'Opus")
    ax.text(0.084, -0.45, "à droite : Opus meilleur\nà gauche : MULE meilleur", ha="right", fontsize=10.5,
            color=MUTED)
    fig.text(0.5, -0.06, "PEAQ de base à 128 kb/s, 66 extraits du corpus de réglage, MULE v2",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b4-fig2-mov")


def _wins():
    m = pd.read_csv(CAMPAIGN)
    out = {}
    for r in (96, 128, 160):
        d = m[m.rate == r].pivot(index="item", columns="codec", values=["zimt", "odg", "odg_adv", "nmr_db"])
        a, b = "mule_brC75", "opus"
        out[r] = {"Zimtohrli": (d.zimt[a] < d.zimt[b]).mean(), "PEAQ de base": (d.odg[a] > d.odg[b]).mean(),
                  "PEAQ avancé": (d.odg_adv[a] > d.odg_adv[b]).mean(), "NMR": (d.nmr_db[a] < d.nmr_db[b]).mean()}
    return out


def b4_fig3_juges():
    """The share of the 300 tracks where MULE beats Opus, judge by judge, at each rate."""
    w = _wins()
    judges = ["Zimtohrli", "PEAQ de base", "PEAQ avancé", "NMR"]
    cols = [BLUE, ORANGE, GREEN, VIOLET]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for j, (jn, c) in enumerate(zip(judges, cols)):
        for i, r in enumerate((96, 128, 160)):
            v = 100 * w[r][jn]
            x = i + (j - 1.5) * 0.2
            ax.bar(x, v, width=0.17, color="white", edgecolor=c, lw=1.6, hatch="//" if j % 2 else None,
                   label=jn if i == 0 else None)
            ax.text(x, v + 1.5, f"{v:.0f}", ha="center", fontsize=10, color=INK)
        print(f"   {jn}: " + " / ".join(f"{100 * w[r][jn]:.0f} %" for r in (96, 128, 160)))
    ax.axhline(50, color=MUTED, lw=1.2, ls="--")
    ax.text(-0.5, 51.5, "50 %", color=MUTED, fontsize=10.5, ha="left")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["96 kb/s", "128 kb/s", "160 kb/s"])
    ax.set_ylim(0, 112)
    ax.set_ylabel("morceaux où MULE bat Opus (%)")
    ax.legend(loc="upper left", ncol=4, fontsize=11, bbox_to_anchor=(0, 1.08))
    fig.text(0.5, -0.04, "300 morceaux de 30 s, chaque codec à débit moyen égal", ha="center", color=MUTED,
             fontsize=11)
    save(fig, "b4-fig3-juges")


def b4_fig4_cmaes():
    """CMA-ES's apparent gains against each candidate's rate at fixed quality: extrapolated
    (first search) and bracketed (second search)."""
    e = pd.read_csv(os.path.join(figs.RESULTS, "m6_search_extrapolated.csv"))
    s = pd.read_csv(os.path.join(figs.RESULTS, "m6_search.csv"))
    ge = e.objective - e.objective.iloc[0]
    gs = s.objective - s.objective.iloc[0]
    rho = np.corrcoef(e.rate_q7, ge)[0, 1]
    print(f"   extrapolated: max gain {ge.max():+.3f}, r(rate, gain) {rho:.2f}; bracketed: max {gs.max():+.4f}")
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [2.2, 1]}, sharey=True)
    a.scatter(e.rate_q7, ge, s=40, color=ORANGE, zorder=3)
    a.scatter([e.rate_q7.iloc[0]], [0], s=90, color=INK, zorder=4)
    a.annotate("le réglage de départ", (e.rate_q7.iloc[0], 0), (103, 0.022), fontsize=11, color=INK,
               arrowprops=dict(arrowstyle="->", color=INK, lw=1))
    a.axhline(0, color=MUTED, lw=1)
    a.axvline(128, color=MUTED, lw=1, ls="--")
    a.text(128.5, -0.058, "128 kb/s", color=MUTED, fontsize=10.5)
    a.set_xlabel("débit du candidat au réglage de qualité fixe (kb/s)")
    a.set_ylabel("gain annoncé (ODG)")
    a.set_title("1er essai : note extrapolée", fontsize=13, color=INK)
    b.scatter(np.zeros(len(gs)) + np.random.default_rng(1).uniform(-0.25, 0.25, len(gs)), gs, s=40, color=BLUE,
              zorder=3)
    b.axhline(0, color=MUTED, lw=1)
    b.set_xlim(-1, 1)
    b.set_xticks([])
    b.set_title("2e essai : 128 kb/s encadré", fontsize=13, color=INK)
    fig.text(0.5, -0.17, "recherche CMA-ES sur cinq réglages de l'encodeur, 33 extraits ;\n"
             "gain = moyenne de l'ODG de base et avancé, par rapport au départ", ha="center", color=MUTED,
             fontsize=11)
    save(fig, "b4-fig4-cmaes")


def b4_fig5_abx():
    """ABX scores out of 16 (12 or more: a difference heard, p < 0.05)."""
    rows = [("MULE 128 contre l'original", [("voix féminine", 9), ("Joy Division", 8), ("Wolfmother", 10),
                                                         ("Moussorgski", 5), ("Body Count", 9), ("Heilung", 8)], BLUE),
            ("MULE 128 contre Opus 128", [("voix féminine", 7), ("Joy Division", 8), ("Wolfmother", 11),
                                                      ("Moussorgski", 6), ("Body Count", 9), ("Heilung", 6)], ORANGE),
            ("deux réglages de MULE à 128", [("Monster Magnet", 7), ("Red Fang", 6), ("Zombie Zombie", 9),
                                                     ("Heilung", 8), ("Belenos", 8), ("clavecin", 6)], GREEN)]
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.8), sharey=True)
    for ax, (title, items, c) in zip(axs, rows):
        for i, (lab, v) in enumerate(items):
            ax.bar(i, v, color="white", edgecolor=c, lw=1.6, width=0.65)
            ax.text(i, v + 0.3, str(v), ha="center", fontsize=11, color=INK)
        ax.axhline(12, color=INK, lw=1.2, ls="--")
        ax.axhline(8, color=MUTED, lw=1, ls=":")
        ax.set_xticks(range(len(items)))
        ax.set_xticklabels([x[0] for x in items], rotation=40, ha="right", fontsize=10.5)
        ax.set_title(title, fontsize=11.5, color=INK)
        ax.set_ylim(0, 16.5)
    axs[0].set_ylabel("bonnes réponses sur 16")
    axs[2].text(5.7, 12, "seuil :\n12/16", ha="left", va="center", fontsize=10.5, color=INK)
    axs[2].text(5.7, 8, "hasard :\n8/16", ha="left", va="center", fontsize=10.5, color=MUTED)
    fig.text(0.5, -0.2, "squishyball, 16 essais par série, une seule paire d'oreilles", ha="center", color=MUTED,
             fontsize=11)
    save(fig, "b4-fig5-abx")


@functools.lru_cache(maxsize=1)
def _quartet():
    """Quartet: MULE --bitrate and Opus near the same rate, aligned; per-second Zimtohrli and the
    region split of its similarity."""
    import pyohrli
    import soxr
    import corpus
    import refcodecs
    import zimt_diag as Z
    w = dict(corpus.items("all"))["quartet"]
    z, F = pyohrli.Pyohrli(), Z.freqs()
    out = {}
    S0 = None
    for lab, cfg in (("MULE", "mule-brC75_101"), ("Opus", "opusnd_96")):
        r, y, fs, kb, _ = refcodecs.run_aligned(cfg, w)
        n = min(len(r), len(y))
        r48, y48 = (soxr.resample(v[:n], fs, 48000, quality="VHQ") for v in (r, y))
        W, H = 48000, 24000
        sec = np.array([np.mean([z.distance(np.clip(r48[s:s + W, c], -1, 1).astype(np.float32),
                                            np.clip(y48[s:s + W, c], -1, 1).astype(np.float32)) for c in (0, 1)])
                        for s in range(0, len(r48) - W + 1, H)]) * 1e4
        if S0 is None:
            S0 = Z.spec(z, r48)
        Sd = Z.spec(z, y48)
        m = min(S0.shape[1], Sd.shape[1])
        it, st = zip(*[Z.nsim_map(S0[c, :m], Sd[c, :m]) for c in range(2)])
        it, st = np.stack(it), np.stack(st)
        reg = []
        for lo, hi in Z.REGIONS:
            ch = (F >= lo) & (F < hi)
            share = ch.mean() * 1e4
            reg.append(((1 - it[:, :, ch]).mean() * share, (1 - st[:, :, ch]).mean() * share))
        out[lab] = dict(kb=kb, sec=sec, reg=np.array(reg), it=it.mean(axis=0), st=st.mean(axis=0))
        print(f"   quartet {lab} ({cfg}): {kb:.1f} kb/s, mean of 1 s windows {sec.mean():.2f}")
    return out


def b4_fig6_secondes():
    q = _quartet()
    import zimt_diag as Z
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 8), gridspec_kw={"height_ratios": [1.2, 1]})
    for lab, c in (("MULE", BLUE), ("Opus", ORANGE)):
        s = q[lab]["sec"]
        t = np.arange(len(s)) * 0.5 + 0.5
        a.plot(t, s, color=c, lw=2, marker="o", ms=4, label=f"{lab}, {fr(q[lab]['kb'])} kb/s")
    a.set_ylim(0)
    a.set_xlabel("temps (s)")
    a.set_ylabel("distance Zimtohrli (× 10 000)")
    a.legend(loc="lower center", fontsize=11, ncol=2)
    regs = [f"{lo / 1000:g}-{hi / 1000:g}" for lo, hi in Z.REGIONS]
    x = np.arange(len(regs))
    for k, (lab, c, fc) in enumerate((("MULE", BLUE, FILL_BLUE), ("Opus", ORANGE, FILL_ORANGE))):
        rg = q[lab]["reg"]
        b.bar(x + (k - 0.5) * 0.38, rg[:, 1], width=0.36, color=fc, edgecolor=c, lw=1.2, label=f"{lab} : structure")
        b.bar(x + (k - 0.5) * 0.38, rg[:, 0], width=0.36, bottom=rg[:, 1], color=c, edgecolor=c, lw=1.2,
              label=f"{lab} : intensité")
    b.set_xticks(x)
    b.set_xticklabels(regs)
    b.set_xlabel("région (kHz)")
    b.set_ylabel("part de la distance")
    b.legend(loc="upper left", fontsize=10.5, ncol=2)
    fig.tight_layout()
    fig.text(0.5, -0.03, "quatuor à cordes (EBU SQAM), fenêtres de 1 s ; en bas, la dissemblance de Zimtohrli "
             "par région, séparée en intensité (niveau local) et structure (texture)", ha="center", color=MUTED,
             fontsize=11)
    save(fig, "b4-fig6-secondes")


def b4_fig7_repartition():
    """The spread of Zimtohrli's distance over the 300 tracks, per codec and rate: one dot per
    track, the box from the first to the third quartile, the median, whiskers 5 % to 95 %."""
    m = pd.read_csv(CAMPAIGN)
    codecs = [("mule_brC75", "MULE", BLUE), ("opus", "Opus", ORANGE), ("aac", "AAC (Apple)", GREEN)]
    rng = np.random.default_rng(1)
    fig, axs = plt.subplots(1, 3, figsize=(13, 5), sharey=True)
    for ax, r in zip(axs, (96, 128, 160)):
        d = m[m.rate == r]
        for i, (c, lab, col) in enumerate(codecs):
            v = d[d.codec == c].zimt.to_numpy() * 1e4
            ax.scatter(i + rng.uniform(-0.28, 0.28, len(v)), v, s=9, color=col, alpha=0.35, lw=0, zorder=2)
            p5, q1, med, q3, p95 = np.percentile(v, [5, 25, 50, 75, 95])
            ax.add_patch(plt.Rectangle((i - 0.33, q1), 0.66, q3 - q1, fill=False, ec=INK, lw=1.3, zorder=3))
            ax.plot([i - 0.33, i + 0.33], [med, med], color=INK, lw=2.2, zorder=3)
            ax.plot([i, i], [p5, q1], color=INK, lw=1, zorder=3)
            ax.plot([i, i], [q3, p95], color=INK, lw=1, zorder=3)
            print(f"   {r} {lab}: median {med:.2f}, 5-95 % {p5:.2f}-{p95:.2f}, max {v.max():.2f}")
        ax.set_xticks(range(len(codecs)))
        ax.set_xticklabels([x[1] for x in codecs])
        ax.set_xlim(-0.6, len(codecs) - 0.4)
        ax.set_ylim(0)
        ax.set_title(f"{r} kb/s", fontsize=13, color=INK)
    axs[0].set_ylabel("distance Zimtohrli (× 10 000), plus bas = mieux")
    fig.text(0.5, -0.06, "300 morceaux de 30 s, chaque codec à débit moyen égal ; un point par morceau, la boîte "
             "va du premier au troisième quartile,\nle trait épais est la médiane, les moustaches vont de 5 à 95 %",
             ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, "b4-fig7-repartition")


def b4_fig8_purcell_spectro():
    """Purcell's ode (a copyrighted track: its spectrograms only, no audio), the original, MULE
    --bitrate 96 and Opus 96 from the listening kit data/listen/c75opus (mid channel, 2048-point
    STFT, one dB scale for the three). Saved as PNG: a spectrogram is an image."""
    import soundfile as sf
    from scipy.signal import stft
    d = os.path.join(ROOT, "data", "listen", "c75opus")
    rates = {ln.split()[0]: ln.split()[2] for ln in open(os.path.join(d, "rates.txt"))}

    def spec(name):
        x, fs = sf.read(os.path.join(d, name))
        f, t, z = stft(x.mean(1), fs, nperseg=2048, noverlap=1536)
        return f, t, 20 * np.log10(np.abs(z) + 1e-9)
    f, t, so = spec("purcell_ode__orig.wav")
    vmax = so.max()
    panels = [("original", so),
              (f"MULE, --bitrate 96 ({fr(float(rates['purcell_ode__mule96.wav']))} kb/s)",
               spec("purcell_ode__mule96.wav")[2]),
              (f"Opus, 96 kb/s ({fr(float(rates['purcell_ode__opus96.wav']))} kb/s)",
               spec("purcell_ode__opus96.wav")[2])]
    fig, axs = plt.subplots(3, 1, figsize=(12, 11), sharex=True, constrained_layout=True)
    for ax, (lab, s) in zip(axs, panels):
        im = ax.pcolormesh(t, f / 1000, s, vmin=vmax - 100, vmax=vmax, cmap="magma", shading="auto",
                           rasterized=True)
        ax.set_title(lab, loc="left", fontsize=13, color=INK)
        ax.set_ylabel("fréquence (kHz)")
        ax.set_ylim(0, 22.05)
    axs[-1].set_xlabel("temps (s)")
    fig.colorbar(im, ax=axs, shrink=0.5, label="niveau (dB, même échelle pour les trois)")
    path = os.path.join(figs.FIG, "b4-fig8-purcell-spectro.png")
    fig.savefig(path, dpi=90)
    plt.close(fig)
    print("->", os.path.relpath(path, ROOT))


def b4_fig9_beethoven_raie():
    """Pires's Beethoven (copyrighted: spectrogram only), the original from the listening kit: its
    spectrogram, and beside it the mean spectrum, where the 15 625 Hz line (a CRT's line rate)
    stands out of the hiss."""
    import soundfile as sf
    from scipy.signal import stft
    x, fs = sf.read(os.path.join(ROOT, "data", "listen", "c75opus", "pires_beethoven__orig.wav"))
    f, t, z = stft(x.mean(1), fs, nperseg=4096, noverlap=3072)
    s = 20 * np.log10(np.abs(z) + 1e-9)
    mean = 10 * np.log10(np.mean(np.abs(z) ** 2, axis=1) + 1e-18)
    vmax = s.max()
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 6), sharey=True, gridspec_kw={"width_ratios": [3, 1]},
                               constrained_layout=True)
    a.pcolormesh(t, f / 1000, s, vmin=vmax - 110, vmax=vmax, cmap="magma", shading="auto", rasterized=True)
    a.set_ylim(0, 22.05)
    a.set_xlabel("temps (s)")
    a.set_ylabel("fréquence (kHz)")
    a.set_title("spectrogramme de l'original", loc="left", fontsize=13, color=INK)
    a.annotate("15 625 Hz", (t[-1] * 0.97, 15.625), (t[-1] * 0.72, 18.6), color="white", fontsize=12,
               arrowprops=dict(arrowstyle="->", color="white", lw=1.2))
    b.plot(mean, f / 1000, color=INK, lw=1)
    b.axhline(15.625, color=ORANGE, lw=1, ls="--")
    b.text(mean.max() - 3, 14.4, "15 625 Hz", color=ORANGE, fontsize=11, ha="right")
    b.set_xlabel("niveau moyen (dB)")
    b.set_title("spectre moyen", loc="left", fontsize=13, color=INK)
    path = os.path.join(figs.FIG, "b4-fig9-beethoven-raie.png")
    fig.savefig(path, dpi=90)
    plt.close(fig)
    print("->", os.path.relpath(path, ROOT))


def b4_fig10_carte():
    """Where the judge hurts: Zimtohrli's structure loss (1 - structure term of its NSIM, mean of
    the two channels) over time and channel, MULE and Opus on the SQAM quartet, and their
    difference. PNG (an image)."""
    import zimt_diag as Z
    q = _quartet()
    F = Z.freqs()
    lm, lo = 1 - q["MULE"]["st"], 1 - q["Opus"]["st"]
    n = min(len(lm), len(lo))
    lm, lo = lm[:n], lo[:n]
    t = np.arange(n) * 0.0116
    ext = [0, t[-1], 0, len(F) - 1]
    vmax = np.percentile(np.concatenate([lm, lo]), 99)
    fig, axs = plt.subplots(3, 1, figsize=(12, 11), sharex=True, constrained_layout=True)
    for ax, (lab, m) in zip(axs[:2], (("MULE (91,9 kb/s)", lm), ("Opus (91,9 kb/s)", lo))):
        im = ax.imshow(m.T, origin="lower", aspect="auto", extent=ext, cmap="magma", vmin=0, vmax=vmax)
        ax.set_title(f"{lab} : perte de structure", loc="left", fontsize=13, color=INK)
    fig.colorbar(im, ax=axs[:2], shrink=0.6, label="perte de structure (plus clair = pire)")
    d = lm - lo
    v = np.percentile(np.abs(d), 99)
    im2 = axs[2].imshow(d.T, origin="lower", aspect="auto", extent=ext, cmap="RdBu_r", vmin=-v, vmax=v)
    axs[2].set_title("différence : rouge, MULE pire ; bleu, Opus pire", loc="left", fontsize=13, color=INK)
    fig.colorbar(im2, ax=axs[2], shrink=0.9, label="MULE − Opus")
    ticks = [int(np.argmin(np.abs(F - f))) for f in (100, 500, 1000, 2800, 6000, 10000, 15000)]
    for ax in axs:
        ax.set_yticks(ticks)
        ax.set_yticklabels(["100 Hz", "500 Hz", "1 kHz", "2,8 kHz", "6 kHz", "10 kHz", "15 kHz"])
    axs[-1].set_xlabel("temps (s)")
    path = os.path.join(figs.FIG, "b4-fig10-carte.png")
    fig.savefig(path, dpi=90)
    plt.close(fig)
    print("->", os.path.relpath(path, ROOT))


def b4_fig11_extrapolation():
    """Why extrapolating overestimates: a concave quality-rate curve, the chord through two points
    both above the target rate (extended down to it) against two points around it."""
    R = np.linspace(95, 175, 300)

    def Q(r):
        return -3.0 * np.exp(-(r - 85) / 22)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, (pts, title, col) in zip(axs, (((150, 168), "1er essai : deux points au-delà de 128", ORANGE),
                                           ((120, 136), "2e essai : 128 kb/s encadré", BLUE))):
        ax.plot(R, Q(R), color=INK, lw=2, label="la vraie courbe qualité-débit")
        (r1, r2) = pts
        slope = (Q(r2) - Q(r1)) / (r2 - r1)
        rr = np.linspace(min(r1, 128) - 2, max(r2, 128) + 2, 50)
        ax.plot(rr, Q(r1) + slope * (rr - r1), color=col, lw=1.6, ls="--", label="la droite par les deux mesures")
        ax.scatter([r1, r2], [Q(r1), Q(r2)], s=70, color=col, zorder=4)
        est = Q(r1) + slope * (128 - r1)
        ax.axvline(128, color=MUTED, lw=1, ls=":")
        ax.scatter([128], [est], s=80, marker="x", color=col, zorder=5, lw=2.5)
        ax.scatter([128], [Q(128)], s=60, color=INK, zorder=5)
        ax.annotate("", (128, est), (128, Q(128)), arrowprops=dict(arrowstyle="<->", color=col, lw=1.4))
        if r1 > 128:
            ax.text(126.5, (est + Q(128)) / 2, "note annoncée\ntrop haute", color=col, fontsize=11, va="center",
                    ha="right")
        else:
            ax.text(131, Q(128) - 0.25, "écart\nnégligeable", color=col, fontsize=11, va="top", ha="left")
        ax.set_title(title, fontsize=13, color=INK)
        ax.set_xlabel("débit (kb/s)")
        ax.set_xticks([100, 120, 128, 150, 170])
    axs[0].set_ylabel("qualité (plus haut = mieux)")
    axs[0].set_yticks([])
    axs[0].legend(loc="lower right", fontsize=10.5)
    fig.text(0.5, -0.05, "schéma : courbe concave de forme réaliste ; la croix est la note estimée à 128 kb/s, "
             "le point noir la vraie", ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, "b4-fig11-extrapolation")


def b4_fig12_binomiale():
    """ABX: the scores out of 16 that chance gives (binomial, p = 1/2), the 12/16 threshold, and the
    18 real scores of figure b4-fig5-abx."""
    from math import comb
    real = [9, 8, 10, 5, 9, 8, 7, 8, 11, 6, 9, 6, 7, 6, 9, 8, 8, 6]
    k = np.arange(17)
    p = np.array([comb(16, int(i)) for i in k]) / 2 ** 16
    tail = p[12:].sum()
    print(f"   P(>= 12/16) = {tail:.4f}")
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.bar(k, p * len(real), width=0.75, color=[FILL_ORANGE if i >= 12 else "white" for i in k],
           edgecolor=[ORANGE if i >= 12 else MUTED for i in k], lw=1.4,
           label=f"au hasard : nombre de séries attendu sur {len(real)}")
    obs = np.bincount(real, minlength=17)
    ax.scatter(k[obs > 0], obs[obs > 0], s=90, color=BLUE, zorder=4, label="mes séries réelles")
    ax.axvline(11.5, color=INK, lw=1.2, ls="--")
    ax.text(11.7, ax.get_ylim()[1] * 0.85, f"12/16 ou plus : {fr(100 * tail)} % de chances\nau hasard", fontsize=11,
            color=INK)
    ax.set_xticks(k)
    ax.set_xlabel("bonnes réponses sur 16")
    ax.set_ylabel("nombre de séries")
    ax.legend(loc="upper left", fontsize=11)
    fig.text(0.5, -0.09, "loi binomiale, 16 essais, une chance sur deux à chaque essai ; points : les 18 séries de la "
             "figure ABX", ha="center", color=MUTED, fontsize=11)
    save(fig, "b4-fig12-binomiale")


ALL = [b4_fig1_schema, b4_fig2_mov, b4_fig3_juges, b4_fig4_cmaes, b4_fig5_abx, b4_fig6_secondes,
       b4_fig7_repartition, b4_fig8_purcell_spectro, b4_fig9_beethoven_raie,
       b4_fig10_carte, b4_fig11_extrapolation, b4_fig12_binomiale]

if __name__ == "__main__":
    figs.style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
