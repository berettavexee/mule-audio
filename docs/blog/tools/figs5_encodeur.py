"""Figures of the fifth blog post (docs/blog/05-encodeur.md, « Derrière chaque format se cache un
encodeur »), in the style of figs.py (same font, same palette). Sources:
- figure 1: the 30-track format table of docs/RESULTS-HISTORY.md (FDK-AAC and Apple's AAC);
- figure 2: a diagram (no data);
- figure 3: the 300-track campaign's results (data/campaign/results.csv, statistics only: the
  excerpts are copyrighted), c224 left out as in eval/campaign.py's EXCLUDE;
- figure 4: ABBA (EBU SQAM 69) through the C encoder's trace, --bitrate 128 with and without the
  Opus table and the reallocation;
- figure 5: eval/results/slopes_summary.json (eval/slopes.py);
- figure 6: the brH validation on `test` (eval/results/B9-REPORT.md, section 7);
- figure 7: params.realloc_db;
- figure 8: the campaign reports on 299 tracks (docs/RESULTS-HISTORY.md).

    .venv/bin/python docs/blog/tools/figs5_encodeur.py [names...]      (default: all)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs  # noqa: E402
from figs import (BLUE, FILL_BLUE, FILL_ORANGE, GREEN, INK, MUTED, ORANGE, ROOT, VIOLET,  # noqa: E402
                  native, params, plt, save)
from figs4 import _arrow, _box, fr  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "data", "campaign")
EXCLUDE = {"c224"}                              # eval/campaign.py EXCLUDE
RED = "#c92a2a"


def b5e_fig1_aac():
    """Same format, same decoder, two encoders: FDK-AAC and Apple's AAC at 128 kb/s (30 tracks)."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(9, 3.6))
    names = ["FDK-AAC", "Apple"]
    for a, vals, lab, better in ((ax, [-0.54, -0.31], "ODG de PEAQ (plus haut = mieux)", "haut"),
                                 (bx, [5.08, 4.11], "distance Zimtohrli (plus bas = mieux)", "bas")):
        a.bar([0, 1], vals, color=[FILL_BLUE, FILL_ORANGE], edgecolor=[BLUE, ORANGE], lw=1.4, width=0.6)
        for i, v in enumerate(vals):
            a.text(i, v + (0.03 if v > 0 else -0.03), fr(v, 2), ha="center",
                   va="bottom" if v > 0 else "top", fontsize=12, color=INK)
        a.set_xticks([0, 1])
        a.set_xticklabels(names)
        a.set_title(lab, fontsize=12)
        a.axhline(0, color=INK, lw=1)
    ax.set_ylim(-0.7, 0.05)
    bx.set_ylim(0, 6)
    fig.text(0.5, -0.08, "le même format AAC, le même décodeur, 30 morceaux à 128 kb/s : seul l'encodeur change",
             ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, "b5e-fig1-aac")


def b5e_fig2_decisions():
    """What the encoder decides (orange) and what the format imposes (blue)."""
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    dec = dict(ec=ORANGE, fc=FILL_ORANGE, fs=10.5)
    fmt = dict(ec=BLUE, fc=FILL_BLUE, fs=10.5)
    _box(ax, 0.1, 3.7, 1.5, 0.8, "signal", fs=11)
    _box(ax, 2.0, 3.7, 2.1, 0.8, "blocs longs ou courts,\nleur regroupement", **dec)
    _box(ax, 4.5, 3.7, 1.6, 0.8, "MDCT", **fmt)
    _box(ax, 6.5, 3.7, 2.3, 0.8, "masques\n(psychoacoustique)", **dec)
    _box(ax, 9.2, 3.7, 2.6, 0.8, "allocation par bande,\nchoix a−1 / a / a+1", **dec)
    _box(ax, 9.2, 2.2, 2.6, 0.8, "stéréo M/S\npar bande", **dec)
    _box(ax, 6.5, 2.2, 2.3, 0.8, "quantification TCQ :\nle chemin du Viterbi", **dec)
    _box(ax, 4.5, 2.2, 1.6, 0.8, "bruit de\nremplissage", **dec)
    _box(ax, 2.0, 2.2, 2.1, 0.8, "codage entropique\n(rANS, modèles)", **fmt)
    _box(ax, 0.1, 2.2, 1.5, 0.8, "flux Ogg", **fmt)
    for x0, x1 in ((1.6, 2.0), (4.1, 4.5), (6.1, 6.5), (8.8, 9.2)):
        _arrow(ax, x0, 4.1, x1, 4.1)
    _arrow(ax, 10.5, 3.7, 10.5, 3.0)
    for x0, x1 in ((9.2, 8.8), (6.5, 6.1), (4.5, 4.1), (2.0, 1.6)):
        _arrow(ax, x0, 2.6, x1, 2.6)
    ax.annotate("", (7.65, 3.7), (0.85, 2.2), arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.4, ls="--",
                                                             connectionstyle="arc3,rad=0.25"))
    ax.text(4.2, 1.15, "niveleur de débit : trop de bits ? on relève les masques", ha="center",
            color=ORANGE, fontsize=11)
    ax.add_patch(plt.Rectangle((2.2, 0.25), 0.35, 0.3, ec=ORANGE, fc=FILL_ORANGE, lw=1.2))
    ax.text(2.7, 0.4, "décidé par l'encodeur", va="center", fontsize=11)
    ax.add_patch(plt.Rectangle((6.2, 0.25), 0.35, 0.3, ec=BLUE, fc=FILL_BLUE, lw=1.2))
    ax.text(6.7, 0.4, "imposé par le format", va="center", fontsize=11)
    save(fig, "b5e-fig2-decisions")


def _rates():
    r = pd.read_csv(os.path.join(CAMPAIGN, "results.csv"))
    return r[~r.item.isin(EXCLUDE)]


def b5e_fig3_debits():
    """Each track's rate: quality mode at the setting whose mean is nearest 128 kb/s, against the
    rate leveler (--bitrate 128 before the Opus mix: mule-br_128)."""
    r = _rates()
    q = r[r.config.str.match(r"^mule_-?[0-9.]+$")]
    m = q.groupby("config").kbps.mean()
    cq = (m - 128).abs().idxmin()
    a = q[q.config == cq].set_index("item").kbps
    b = r[r.config == "mule-br_128"].set_index("item").kbps
    bins = np.arange(60, 220, 5)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for v, lab, c, fc in ((a, f"qualité constante (-q {cq.split('_')[1]})", BLUE, FILL_BLUE),
                          (b, "--bitrate 128 (niveleur)", ORANGE, FILL_ORANGE)):
        inside = np.mean(np.abs(v / v.mean() - 1) <= 0.10)
        ax.hist(np.clip(v, 60, 215), bins=bins, color=fc, edgecolor=c, lw=1.2, alpha=0.75,
                label=f"{lab} : moyenne {v.mean():.0f} kb/s, {inside * 100:.0f} % à ±10 % de la moyenne")
        print(f"   {lab}: mean {v.mean():.1f}, P5-P95 {np.percentile(v, 5):.0f}-{np.percentile(v, 95):.0f}, "
              f"within 10 %: {inside:.1%}")
    ax.axvspan(128 * 0.9, 128 * 1.1, color="#f1f3f5", zorder=0)
    ax.set_xlabel("débit de chaque morceau (kb/s)")
    ax.set_ylabel("morceaux")
    ax.legend(loc="upper left", fontsize=11)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.3)
    fig.text(0.5, -0.1, "299 morceaux de 30 s ; la bande grise : 128 kb/s ± 10 %",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b5e-fig3-debits")


def _kbps_per_band(x, p):
    """kb/s spent on each band's coefficients (the trace's coefficient records, as figs.fig9_bits)."""
    m, v, fstart, tr = native.c_trace(x, p)
    bits = figs._op_bits((m, v))
    co, en = tr[tr[:, 0] == 0], tr[tr[:, 0] == 1]
    ev_op = np.concatenate([co[:, 1], en[:, 1], fstart[:-1]])
    ev_lab = np.concatenate([co[:, 5], np.full(len(en), -1), np.full(len(fstart) - 1, -2)])
    o = np.lexsort((ev_lab < 0, ev_op))
    ev_op, ev_lab = ev_op[o], ev_lab[o]
    lab = ev_lab[np.searchsorted(ev_op, np.arange(len(bits)), side="right") - 1]
    dur = len(x) / figs.FS
    return np.array([bits[lab == b].sum() for b in range(22)]) / dur / 1000, bits.sum() / dur / 1000


def b5e_fig4_opus():
    """Where --bitrate 128 spends its bits on ABBA: our masks alone, Opus's table alone, the mix
    (C75), and the mix with the reallocation (today's --bitrate)."""
    x = figs._abba()[0]
    sets = [("nos masques seuls", dict(opa_mode=0, band_db=()), MUTED, "--"),
            ("table d'Opus seule", dict(opa_mode=1, band_db=()), VIOLET, ":"),
            ("mélange 75/25 (24/11)", dict(band_db=()), BLUE, "-"),
            ("mélange + réallocation (25/11)", dict(), ORANGE, "-")]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for lab, kw, c, ls in sets:
        kb, tot = _kbps_per_band(x, params.for_bitrate(128, **kw))
        ax.plot(np.arange(22), kb, color=c, ls=ls, lw=2.2, marker="o", ms=4, label=f"{lab} ({tot:.0f} kb/s)")
        print(f"   {lab}: total {tot:.1f} kb/s, bands 0-1 {kb[:2].sum():.1f}, 20-21 {kb[20:].sum():.1f}")
    ax.set_xticks([0, 4, 8, 12, 16, 20])
    ax.set_xticklabels(["0\n0 Hz", "4\n690 Hz", "8\n1,4 kHz", "12\n2,8 kHz", "16\n6 kHz", "20\n13,4 kHz"],
                       fontsize=11)
    ax.set_xlabel("bande")
    ax.set_ylabel("kb/s dépensés dans la bande")
    ax.legend(fontsize=10.5, loc="upper left")
    fig.text(0.5, -0.1, "ABBA (EBU SQAM 69), 15 s, --bitrate 128 : le débit des coefficients de chaque bande",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b5e-fig4-opus")


REGIONS = ["0-250", "250-1k", "1k-2.8k", "2.8k-6k", "6k-10k", "10k-13k", "13k-20k"]
REGION_LABELS = ["0-250\nHz", "250 Hz\n-1 kHz", "1-2,8\nkHz", "2,8-6\nkHz", "6-10\nkHz", "10-13\nkHz", "13-20\nkHz"]


def b5e_fig5_pentes():
    """What one kb/s buys in Zimtohrli distance, per region and rate (eval/slopes.py)."""
    s = json.load(open(os.path.join(ROOT, "eval", "results", "slopes_summary.json")))
    fig, ax = plt.subplots(figsize=(11, 4.6))
    w = 0.26
    for k, (r, c, fc) in enumerate(((96, BLUE, FILL_BLUE), (128, ORANGE, FILL_ORANGE), (160, GREEN, "#b2f2bb"))):
        fit = {f["dir"]: f for f in s[str(r)]["fit"]}
        v = np.array([-fit[d]["slope"] for d in REGIONS])
        u = -fit["uniform"]["slope"]
        x = np.arange(len(REGIONS)) + (k - 1) * w
        ax.bar(x, v, width=w, color=fc, edgecolor=c, lw=1.2, label=f"{r} kb/s")
        ax.plot([-0.5, len(REGIONS) - 0.5], [u, u], color=c, lw=1.2, ls="--")
        print(f"   {r}: " + " ".join(f"{d} {x_:.3f}" for d, x_ in zip(REGIONS, v)) + f" | uniform {u:.3f}")
    ax.set_xticks(range(len(REGIONS)))
    ax.set_xticklabels(REGION_LABELS, fontsize=11)
    ax.set_ylabel("distance gagnée par kb/s\n(× 10 000, plus haut = bits mieux placés)")
    ax.legend(fontsize=11, loc="upper right")
    ax.set_xlim(-0.6, len(REGIONS) - 0.4)
    fig.text(0.5, -0.1, "en tirets : le gain d'un kb/s réparti partout comme aujourd'hui ; une barre au-dessus "
             "de son tiret = une région sous-dotée,\nen dessous = sur-dotée (masques décalés de ±3 dB par région, "
             "33 extraits de dev, à débit fixe)", ha="center", color=MUTED, fontsize=11)
    save(fig, "b5e-fig5-pentes")


def b5e_fig6_aigu():
    """Taking bits from 13-20 kHz (brH) on `test`: Zimtohrli and NMR for, both PEAQ against."""
    rates = [96, 128, 160]
    data = [("Zimtohrli\n(distance, %)", [4.9, 3.0, 2.7]), ("NMR\n(dB)", [0.27, 0.33, 0.64]),
            ("PEAQ avancé\n(ODG × 10)", [-0.21, -0.09, -0.20]), ("PEAQ basique\n(ODG × 10)", [-0.14, -0.34, -1.12])]
    fig, axs = plt.subplots(1, 4, figsize=(12, 3.8), sharey=False)
    for a, (lab, v) in zip(axs, data):
        cols = [GREEN if x > 0 else RED for x in v]
        a.bar(range(3), v, color=[c + "55" for c in cols], edgecolor=cols, lw=1.3, width=0.6)
        a.axhline(0, color=INK, lw=1)
        a.set_xticks(range(3))
        a.set_xticklabels([f"{r}" for r in rates], fontsize=11)
        a.set_title(lab, fontsize=12)
        lim = max(abs(min(v)), abs(max(v))) * 1.3
        a.set_ylim(-lim, lim)
    axs[0].set_ylabel("gain (+ = mieux)")
    fig.text(0.5, -0.08, "masques de 13-20 kHz relevés (moins de bits à l'aigu), 30 extraits de test, à débit égal, "
             "par débit (kb/s) ; vert : le juge approuve, rouge : il désapprouve", ha="center", color=MUTED,
             fontsize=11)
    fig.tight_layout()
    save(fig, "b5e-fig6-aigu")


def b5e_fig7_loi():
    """--bitrate's per-region mask offsets against the rate (params.realloc_db)."""
    kb = np.linspace(80, 192, 113)
    d = np.array([params.realloc_db(k) for k in kb])
    groups = [("0-250 Hz (bandes 0-1)", slice(0, 2), BLUE, "-"), ("250 Hz-1 kHz (2-5)", slice(2, 6), VIOLET, "-"),
              ("1-2,8 kHz (6-11)", slice(6, 12), GREEN, "-"), ("2,8-6 kHz (12-15)", slice(12, 16), GREEN, "--"),
              ("6-10 kHz (16-18)", slice(16, 19), GREEN, ":"), ("10-13 kHz (19)", slice(19, 20), GREEN, "-."),
              ("13-20 kHz (20-21)", slice(20, 22), ORANGE, "-")]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for lab, sl, c, ls in groups:
        ax.plot(kb, d[:, sl].mean(1), color=c, ls=ls, lw=2.2, label=lab)
    ax.axhline(0, color=INK, lw=1)
    ax.set_xlabel("débit visé (kb/s)")
    ax.set_ylabel("décalage du masque (dB)\nnégatif : plus de bits")
    ax.legend(fontsize=10, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    for r in (96, 128, 160):
        ax.axvline(r, color="#e9ecef", lw=1, zorder=0)
    fig.text(0.45, -0.1, "mesuré à 96, 128 et 160 kb/s, interpolé entre ; l'aigu est relevé de 6 dB "
             "jusqu'à 96 kb/s, puis rendu progressivement", ha="center", color=MUTED, fontsize=11)
    save(fig, "b5e-fig7-loi")


def b5e_fig8_etapes():
    """Zimtohrli's distance at each encoder step since the format froze, 299 tracks, Opus dashed."""
    steps = ["-q\n22/11", "niveleur\n23/11", "+ Opus\n24/11", "+ réalloc.\n25/11"]
    z = {96: [6.16, 6.15, 5.86, 5.31], 128: [2.76, 2.76, 2.59, 2.47], 160: [1.40, 1.38, 1.32, 1.25]}
    opus = {96: 5.82, 128: 3.22, 160: 2.14}
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.2))
    for a, (r, v) in zip(axs, z.items()):
        a.plot(range(4), v, color=BLUE, lw=2.4, marker="o", ms=7)
        a.axhline(opus[r], color=ORANGE, lw=2, ls="--")
        a.text(-0.3, opus[r], "Opus", color=ORANGE, va="bottom", ha="left", fontsize=11)
        for i, x in enumerate(v):
            a.annotate(fr(x, 2), (i, x), xytext=(0, 9), textcoords="offset points", ha="center",
                       fontsize=10.5, color=INK)
        a.set_title(f"{r} kb/s  ({(v[-1] / v[0] - 1) * 100:+.0f} %)".replace(".", ","), fontsize=13)
        a.set_xticks(range(4))
        a.set_xticklabels(steps, fontsize=10.5)
        a.set_xlim(-0.4, 3.4)
        lo, hi = min(v + [opus[r]]), max(v + [opus[r]])
        a.set_ylim(lo - 0.12 * (hi - lo), hi + 0.2 * (hi - lo))
    axs[0].set_ylabel("distance Zimtohrli (× 10 000)\nplus bas = mieux")
    fig.text(0.5, -0.1, "299 morceaux, à débit moyen égal ; le format (v5) ne change pas d'un point à l'autre",
             ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, "b5e-fig8-etapes")


def b5e_fig9_morceaux():
    """The per-track figure of the README, in French (figs_enc.enc_fig11_campaign)."""
    import figs_enc
    figs_enc.enc_fig11_campaign(128, lang="fr", zimt=True)


ALL = [b5e_fig1_aac, b5e_fig2_decisions, b5e_fig3_debits, b5e_fig4_opus, b5e_fig5_pentes, b5e_fig6_aigu,
       b5e_fig7_loi, b5e_fig8_etapes, b5e_fig9_morceaux]

if __name__ == "__main__":
    figs.style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
