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
from figs import (APPLE, BLUE, GREEN, GRID, INK, MUTED, ORANGE, RESULTS, VIOLET, plt, save,  # noqa: E402
                  style)
import corpus  # noqa: E402  (eval/, put on the path by figs)


def odg_at(df, fam, rate):
    """Each item's ODG at a mean rate: interpolated between the family's two configurations whose
    mean rates bracket it (the same weights for every item: VBR rates differ per item)."""
    x = df[df.fam == fam]
    mean = x.groupby("config").kbps.mean().sort_values()
    cs, ks = list(mean.index), mean.values
    if not ks[0] <= rate <= ks[-1]:             # no extrapolation (run_eval.at_rates: NaN)
        raise ValueError(f"{fam}: {rate} kb/s outside the measured {ks[0]:.1f}-{ks[-1]:.1f} kb/s")
    i = int(np.clip(np.searchsorted(ks, rate) - 1, 0, len(ks) - 2))
    t = (rate - ks[i]) / (ks[i + 1] - ks[i])
    lo = x[x.config == cs[i]].set_index("item").odg
    hi = x[x.config == cs[i + 1]].set_index("item").odg.loc[lo.index]
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


def _strip(rows, rate, name, figsize=(9, 5.2)):
    """One row of dots per (values: item -> ODG, label, colour, marker): the median, the 10-90 %
    range, the hardest and the easiest item named."""
    vals = [r[0] for r in rows]
    lo = np.floor(min(v.min() for v in vals) * 10) / 10
    hi = max(v.max() for v in vals)
    xlab = max(hi, 0.0) + 0.08                  # the rows' names, right of every dot
    fig, ax = plt.subplots(figsize=figsize)
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
    step = 0.2 if hi - lo > 0.8 else 0.1
    ax.set_xticks(np.round(np.arange(lo, max(hi, 0.0) + 1e-9, step), 2))
    ax.set_xlim(lo - 0.05, xlab + 0.32 * (hi - lo + 0.1))
    ax.set_ylim(-0.7, len(rows) - 0.45)
    ax.set_xlabel(f"ODG (PEAQ) de chaque extrait, à {rate} kb/s")
    for k, txt in enumerate(("un point = un extrait ;  trait = de 10 à 90 % des extraits ;  barre = médiane",
                             "les 30 extraits du jeu de test, jamais utilisés pour les réglages")):
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


ALL = [enc_fig1_distributions, enc_fig1b_distributions_160, enc_fig2_avant_apres, enc_fig2b_avant_apres_160]

if __name__ == "__main__":
    style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
