"""Figures of the blog post on the encoder's optimizations (notes in docs/blog/PLAN.md), in the
style of figs.py (Excalidraw-like: matplotlib's xkcd mode, the Virgil font). Sources: the
test-set result CSVs (eval/results).

    .venv/bin/python docs/blog/tools/figs_enc.py [names...]      (default: all)
"""
import functools
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from figs import (APPLE, BLUE, FS, GREEN, GRID, INK, MUTED, ORANGE, RESULTS, VIOLET, plt, save,  # noqa: E402
                  style)
import corpus  # noqa: E402  (eval/, put on the path by figs)


def odg_at(df, fam, rate, col="odg"):
    """Each item's ODG (or another metric, col) at a mean rate: interpolated between the family's
    two configurations whose mean rates bracket it (the same weights for every item: VBR rates
    differ per item)."""
    x = df[df.fam == fam]
    mean = x.groupby("config").kbps.mean().sort_values()
    cs, ks = list(mean.index), mean.values
    if not ks[0] <= rate <= ks[-1]:             # no extrapolation (run_eval.at_rates: NaN)
        raise ValueError(f"{fam}: {rate} kb/s outside the measured {ks[0]:.1f}-{ks[-1]:.1f} kb/s")
    i = int(np.clip(np.searchsorted(ks, rate) - 1, 0, len(ks) - 2))
    t = (rate - ks[i]) / (ks[i + 1] - ks[i])
    lo = x[x.config == cs[i]].set_index("item")[col]
    hi = x[x.config == cs[i + 1]].set_index("item")[col].loc[lo.index]
    return lo * (1 - t) + hi * t


@functools.lru_cache(maxsize=None)
def _artists():
    """{item: artist}: the library folder of each item of the corpus (eval/corpus_p4.json), cut at
    the performers (Toru Takemitsu - Hiroshi Wakasugi... -> Toru Takemitsu)."""
    return {it["name"]: re.split(r"[;,&]| - ", it["path"].split("/")[0])[0].strip()
            for it in corpus._p4_items()}


def _names(item):
    return _artists().get(item, item)


def _results(*names):
    """The test-set results of these CSVs (eval/results), with a family column ("mule" for
    mule_<q>)."""
    df = pd.concat([pd.read_csv(os.path.join(RESULTS, n)) for n in names])
    df["fam"] = df.config.str.split("_").str[0]
    return df


def _v4(df):
    """The current v4 production (prod5_test.csv, mule_<q>, 22/11/2026: the Zimtohrli tuning, the highs
    transient detector (tr_hf; prod4_test.csv was the production before it), the
    envelope guard at 5 dB, nf_bias 1) added to df as family "mule-v4" (df's "mule" is v3's)."""
    p = pd.read_csv(os.path.join(RESULTS, "prod5_test.csv"))
    p["fam"] = "mule-v4"
    return pd.concat([df, p])


def _v5(df):
    """The v5 production (prod6_test.csv, mule_<q>, 22/11/2026: folding in short frames, the zeros'
    noise level modelled, the corrected transient detector with its highs pass at 6 dB and its
    tonal veto) added to df as family "mule-v5"."""
    p = pd.read_csv(os.path.join(RESULTS, "prod6_test.csv"))
    p["fam"] = "mule-v5"
    return pd.concat([df, p])


def _strip(rows, rate, name, figsize=(9, 5.2), lang="fr", zimt=False):
    """One row of dots per (values: item -> ODG, label, colour, marker): the median, the 10-90 %
    range, the hardest and the easiest item named. lang "en": English captions (the README).
    zimt: the values are Zimtohrli distances (lower = better), drawn as -distance x 1e4 so that
    better stays on the right, the ticks labelled with the distances themselves."""
    if zimt:
        rows = [(-v * 1e4, lab, c, mk) for v, lab, c, mk in rows]
    vals = [r[0] for r in rows]
    lo = np.floor(min(v.min() for v in vals) * 10) / 10
    hi = max(v.max() for v in vals)
    xlab = (hi + 0.08 * (hi - lo)) if zimt else max(hi, 0.0) + 0.08   # the rows' names, right of every dot
    fig, ax = plt.subplots(figsize=figsize)
    if not zimt:
        ax.axvline(0, color=GRID, lw=1, zorder=0)
    rng = np.random.default_rng(7)
    span = (xlab + 0.32 * (hi - lo + 0.1)) - (lo - 0.05)
    for k, (v, lab, c, mk) in enumerate(rows):
        y = len(rows) - 1 - k
        jit = rng.uniform(-0.16, 0.16, len(v))
        ax.scatter(v, y + jit, s=34, color=c, marker=mk, edgecolor="white", linewidth=0.8, zorder=3)
        p10, med, p90 = v.quantile(0.1), v.median(), v.quantile(0.9)
        ax.plot([p10, p90], [y - 0.32, y - 0.32], color=INK, lw=2, zorder=2)
        ax.plot([med, med], [y - 0.42, y - 0.22], color=INK, lw=2.5, zorder=2)
        ax.text(xlab, y, lab, color=INK, fontsize=13, ha="left", va="center")
        worst, best = v.idxmin(), v.idxmax()    # the hardest and the easiest item
        nw, nb = _names(worst), _names(best)
        close = v[worst] + len(nw) * span * 0.0055 > v[best] - len(nb) * span * 0.011
        pos = list(v.index)
        ax.annotate(nw, (v[worst], y + jit[pos.index(worst)]),
                    xytext=(0, 24 if close else 12), textcoords="offset points", ha="center",
                    va="bottom", fontsize=10, color=MUTED,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=1, shrinkB=4,
                                    relpos=(0.5, 0)))
        ax.annotate(nb, (v[best], y + jit[pos.index(best)]),     # leftwards: the row's name
                    xytext=(4, 12), textcoords="offset points", ha="right", va="bottom",  # is on
                    fontsize=10, color=MUTED,                                            # the right
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=1, shrinkB=4,
                                    relpos=(1, 0)))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    en = lang == "en"
    if zimt:
        ticks = np.arange(np.floor(lo), np.ceil(hi) + 1e-9, 1.0 if hi - lo > 4 else 0.5)
        ax.set_xticks(ticks, [f"{abs(t):g}" for t in ticks])
        ax.set_xlim(lo - 0.05 * (hi - lo), xlab + 0.32 * (hi - lo))
        ax.set_xlabel(f"Zimtohrli distance of each track (x 1e-4, lower = better), at {rate} kb/s" if en else
                      f"distance Zimtohrli de chaque extrait (x 1e-4, plus bas = mieux), à {rate} kb/s")
    else:
        step = 0.2 if hi - lo > 0.8 else 0.1
        ax.set_xticks(np.round(np.arange(lo, max(hi, 0.0) + 1e-9, step), 2))
        ax.set_xlim(lo - 0.05, xlab + 0.32 * (hi - lo + 0.1))
        ax.set_xlabel(f"PEAQ's ODG of each track, at {rate} kb/s" if en else f"ODG (PEAQ) de chaque extrait, à {rate} kb/s")
    ax.set_ylim(-0.7, len(rows) - 0.45)
    notes = (("one dot = one track;  line = 10 to 90 % of the tracks;  bar = median",
              "the 30 tracks of the test set, never used for tuning") if en else
             ("un point = un extrait ;  trait = de 10 à 90 % des extraits ;  barre = médiane",
              "les 30 extraits du jeu de test, jamais utilisés pour les réglages"))
    for k, txt in enumerate(notes):
        ax.annotate(txt, (0.5, 0), xycoords="axes fraction", xytext=(0, -52 - 18 * k),
                    textcoords="offset points", ha="center", va="top", color=MUTED, fontsize=11)
    save(fig, name)


def enc_fig1_distributions(rate=128):
    """Each test item's ODG, codec by codec. MULE: the tuned production of 20/11/2026
    (prod2_test.csv)."""
    df = _results("prod2_test.csv", "ref_test.csv", "aapl_test.csv", "aac_test.csv")
    rows = [(odg_at(df, fam, rate), lab, c, mk) for fam, lab, c, mk in
            (("opus", "Opus", ORANGE, "D"), ("mule", "MULE", BLUE, "o"), ("aapl", "AAC (Apple)", APPLE, "v"),
             ("vorbis", "Vorbis", GREEN, "^"), ("aac", "AAC (FDK)", VIOLET, "s"))]
    _strip(rows, rate, "enc-fig1-distributions" + ("" if rate == 128 else f"-{rate}"))


def enc_fig1b_distributions_160():
    """The same at 160 kb/s."""
    enc_fig1_distributions(160)


def enc_fig2_avant_apres(rate=128):
    """MULE before and after the day's tuning (20/11/2026), with Opus: the morning's production
    (tg_test.csv, mule_<q>) against the tuned one (prod2_test.csv)."""
    morning = pd.read_csv(os.path.join(RESULTS, "tg_test.csv"))
    morning = morning[morning.config.str.match(r"mule_")].copy()
    morning["config"] = morning.config.str.replace("mule_", "morning_", regex=False)
    morning["fam"] = "morning"
    df = pd.concat([_results("prod2_test.csv", "ref_test.csv"), morning])
    rows = [(odg_at(df, "opus", rate), "Opus", ORANGE, "D"),
            (odg_at(df, "mule", rate), "MULE réglé", BLUE, "o"),
            (odg_at(df, "morning", rate), "MULE avant", MUTED, "o")]
    _strip(rows, rate, "enc-fig2-avant-apres" + ("" if rate == 128 else f"-{rate}"), figsize=(9, 3.6))


def enc_fig2b_avant_apres_160():
    """The same at 160 kb/s."""
    enc_fig2_avant_apres(160)


def enc_fig3_v4(rate=128, lang="fr"):
    """Format v4's production (_v4: noise in coded bands' zeros, sloped noise filling, the tonal and
    envelope guards, the Zimtohrli tuning) against MULE v3's production, Opus and Apple's AAC
    (docs/V4.md). Before 22/11/2026: the frozen format's encoder, sl6v4_test.csv."""
    df = _v4(_results("prod2_test.csv", "ref_test.csv", "aapl_test.csv"))
    rows = [(odg_at(df, "opus", rate), "Opus", ORANGE, "D"),
            (odg_at(df, "mule-v4", rate), "MULE v4", GREEN, "o"),
            (odg_at(df, "mule", rate), "MULE v3", BLUE, "o"),
            (odg_at(df, "aapl", rate), "AAC (Apple)", APPLE, "v")]
    _strip(rows, rate, "enc-fig3-v4" + ("" if rate == 128 else f"-{rate}") + ("-en" if lang == "en" else ""),
           figsize=(9, 4.4), lang=lang)


def enc_fig3b_v4_160():
    """The same at 160 kb/s."""
    enc_fig3_v4(160)


def enc_fig5_zimt(rate=128, lang="fr"):
    """The distribution figure of format v4 (enc_fig3_v4) with Zimtohrli instead of PEAQ: each
    test item's distance at a mean rate, Opus, MULE v4 (the production, _v4), MULE v3 and Apple's
    AAC. Opus and Apple from ref2_test.csv and aapl2_test.csv: ref_test and aapl_test
    hold Zimtohrli rounded to 1e-4 (written before run_eval's %.6g)."""
    df = _v4(_results("prod2_test.csv", "ref2_test.csv", "aapl2_test.csv"))
    rows = [(odg_at(df, "opus", rate, "zimt"), "Opus", ORANGE, "D"),
            (odg_at(df, "mule-v4", rate, "zimt"), "MULE v4", GREEN, "o"),
            (odg_at(df, "mule", rate, "zimt"), "MULE v3", BLUE, "o"),
            (odg_at(df, "aapl", rate, "zimt"), "AAC (Apple)", APPLE, "v")]
    _strip(rows, rate, "enc-fig5-zimt" + ("" if rate == 128 else f"-{rate}") + ("-en" if lang == "en" else ""),
           figsize=(9, 4.4), lang=lang, zimt=True)


def enc_fig5b_zimt_160():
    """The same at 160 kb/s."""
    enc_fig5_zimt(160)


def enc_fig5c_zimt_en():
    """The same at 128 kb/s, in English (the README)."""
    enc_fig5_zimt(128, "en")


def enc_fig3c_v4_en():
    """The same at 128 kb/s, in English (the README)."""
    enc_fig3_v4(128, "en")


def enc_fig6_v5(rate=128, lang="fr", zimt=False):
    """Format v5's production (_v5) against v4's (_v4), Opus and Apple's AAC, each test item at a
    mean rate (docs/V5.md): PEAQ's basic ODG, or (zimt) Zimtohrli. Opus and Apple from ref2_test.csv
    and aapl2_test.csv (Zimtohrli at full precision)."""
    df = _v5(_v4(_results("prod2_test.csv", "ref2_test.csv", "aapl2_test.csv")))
    col = "zimt" if zimt else "odg"
    rows = [(odg_at(df, "opus", rate, col), "Opus", ORANGE, "D"),
            (odg_at(df, "mule-v5", rate, col), "MULE v5", GREEN, "o"),
            (odg_at(df, "mule-v4", rate, col), "MULE v4", BLUE, "o"),
            (odg_at(df, "aapl", rate, col), "AAC (Apple)", APPLE, "v")]
    _strip(rows, rate, ("enc-fig7-zimt-v5" if zimt else "enc-fig6-v5") + ("" if rate == 128 else f"-{rate}")
           + ("-en" if lang == "en" else ""), figsize=(9, 4.4), lang=lang, zimt=zimt)


def enc_fig6b_v5_160():
    """The same at 160 kb/s."""
    enc_fig6_v5(160)


def enc_fig6c_v5_en():
    """The same at 128 kb/s, in English (the README)."""
    enc_fig6_v5(128, "en")


def enc_fig7_zimt_v5():
    """enc_fig6_v5 with Zimtohrli."""
    enc_fig6_v5(128, zimt=True)


def enc_fig7b_zimt_v5_160():
    """The same at 160 kb/s."""
    enc_fig6_v5(160, zimt=True)


def enc_fig7c_zimt_v5_en():
    """The same at 128 kb/s, in English (the README)."""
    enc_fig6_v5(128, "en", zimt=True)


def enc_fig4_spectro_en(item="harpsichord", seconds=6.0, mule="MULE v4", name="enc-fig4-spectro-en", lang="en"):
    """Where each codec puts its bits: spectrograms of an EBU SQAM excerpt (free of rights), the
    original, MULE (the production encoder: its label mule), Opus and Apple's AAC (qaac --cvbr 128),
    the three at Apple's rate on this excerpt (MULE's q and Opus' nominal rate found by bisection).
    English (the README) or French (lang "fr"). The figure enc-fig4 was made with format v4: since
    the v5 encoder, regenerating it would label v5's sound "MULE v4" (enc_fig8_spectro_v5 instead)."""
    import tempfile
    import refcodecs
    from scipy.signal import stft
    from matplotlib.colors import LinearSegmentedColormap
    from tonal_lines import mule_q
    w = dict(corpus.items("all"))[item]
    with tempfile.TemporaryDirectory() as t:
        target = refcodecs.run("aaplc_128", w, t)[2]

    def opus_rate(k):
        with tempfile.TemporaryDirectory() as t:
            return refcodecs.run(f"opus_{k}", w, t)[2]
    lo, hi = 64, 256                            # Opus' nominal rate whose real rate is nearest
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if opus_rate(mid) <= target else (lo, mid)
    ok = min((lo, hi), key=lambda k: abs(opus_rate(k) - target))
    cfgs = [(mule, f"mule_{mule_q('mule_-7', w, target):g}"), ("Opus", f"opus_{ok}"),
            ("AAC (Apple)", "aaplc_128")]
    panels = []
    for lab, c in cfgs:
        r, y, fs, kb, _lag = refcodecs.run_aligned(c, w)
        if not panels:
            panels.append(("original", r))
        panels.append((f"{lab}, {kb:.0f} kb/s", y))
    cmap = LinearSegmentedColormap.from_list("ink", ["#ffffff", "#a5d8ff", "#1971c2", "#0b2e59", "#000000"])
    fig, axs = plt.subplots(2, 2, figsize=(11, 7), sharex=True, sharey=True)
    top = None
    for ax, (lab, x) in zip(axs.flat, panels):
        n = int(seconds * FS)
        f, tt, Z = stft(x[:n].mean(axis=1), FS, window="hann", nperseg=2048, noverlap=1536)
        S = 10 * np.log10(np.abs(Z) ** 2 + 1e-20)
        top = S.max() if top is None else top
        ax.pcolormesh(tt, f / 1000, S, vmin=top - 90, vmax=top, cmap=cmap, shading="auto", rasterized=True)
        ax.set_title(lab, fontsize=13)
        ax.set_ylim(0, 22.05)
    for ax in axs[1]:
        ax.set_xlabel("time (s)" if lang == "en" else "temps (s)")
    for ax in axs[:, 0]:
        ax.set_ylabel("frequency (kHz)" if lang == "en" else "fréquence (kHz)")
    cap = (f"EBU SQAM harpsichord, first {seconds:g} s; darker = louder, 90 dB from white to black;"
           " the three codecs at the same rate") if lang == "en" else (
           f"Clavecin EBU SQAM, {seconds:g} premières secondes ; plus sombre = plus fort, 90 dB du blanc au"
           " noir ; les trois codecs au même débit")
    fig.text(0.5, -0.02, cap, ha="center", color=MUTED, fontsize=11)
    fig.tight_layout()
    save(fig, name)


def enc_fig8_spectro_v5_en():
    """enc_fig4's spectrograms with format v5's encoder (the production since 22/11/2026)."""
    enc_fig4_spectro_en(mule="MULE v5", name="enc-fig8-spectro-v5-en")


def enc_fig8b_spectro_v5_fr():
    """The same, in French (the blog)."""
    enc_fig4_spectro_en(mule="MULE v5", name="enc-fig8-spectro-v5", lang="fr")


# (enc_fig4_spectro_en is left out: made with format v4, it would now encode v5; see enc_fig8)
ALL = [enc_fig1_distributions, enc_fig1b_distributions_160, enc_fig2_avant_apres, enc_fig2b_avant_apres_160,
       enc_fig3_v4, enc_fig3b_v4_160, enc_fig3c_v4_en, enc_fig5_zimt,
       enc_fig5b_zimt_160, enc_fig5c_zimt_en, enc_fig6_v5, enc_fig6b_v5_160, enc_fig6c_v5_en,
       enc_fig7_zimt_v5, enc_fig7b_zimt_v5_160, enc_fig7c_zimt_v5_en, enc_fig8_spectro_v5_en,
       enc_fig8b_spectro_v5_fr]

if __name__ == "__main__":
    style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
