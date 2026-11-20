"""Figures of the blog post on the encoder's optimizations (notes in docs/blog/PLAN.md), in the
style of figs.py (Excalidraw-like: matplotlib's xkcd mode, the Virgil font). Sources: the
test-set result CSVs (eval/results).

    .venv/bin/python docs/blog/tools/figs3.py [names...]      (default: all)
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from figs import (APPLE, BLUE, GREEN, GRID, INK, MUTED, ORANGE, RESULTS, VIOLET, plt, save,  # noqa: E402
                  style)


def odg_at(df, fam, rate):
    """Each item's ODG at a mean rate: interpolated between the family's two configurations whose
    mean rates bracket it (the same weights for every item: VBR rates differ per item)."""
    x = df[df.fam == fam]
    mean = x.groupby("config").kbps.mean().sort_values()
    cs, ks = list(mean.index), mean.values
    i = int(np.clip(np.searchsorted(ks, rate) - 1, 0, len(ks) - 2))
    t = (rate - ks[i]) / (ks[i + 1] - ks[i])
    lo = x[x.config == cs[i]].set_index("item").odg
    hi = x[x.config == cs[i + 1]].set_index("item").odg.loc[lo.index]
    return lo * (1 - t) + hi * t


def _names(item):
    """An item's artist as the corpus has it (eval/corpus_p4.json: the library folder), cut at the
    performers (Toru Takemitsu - Hiroshi Wakasugi... -> Toru Takemitsu)."""
    import json
    import re
    if not _ARTIST:
        for it in json.load(open(os.path.join(os.path.dirname(RESULTS), "corpus_p4.json"))):
            _ARTIST[it["name"]] = re.split(r"[;,&]| - ", it["path"].split("/")[0])[0].strip()
    return _ARTIST.get(item, item)


_ARTIST = {}


def b3_fig1_distributions(rate=128):
    """Each test item's ODG at 128 kb/s, codec by codec: one dot per item, the median and the
    10-90 % range; the hardest and the easiest item named. MULE: the production of 20/11/2026 (short windows grouped per region)."""
    gr = pd.read_csv(os.path.join(RESULTS, "gr_test.csv"))
    gr = gr[gr.config.str.startswith("mule-gr1d12")].copy()
    gr["config"] = gr.config.str.replace("mule-gr1d12", "mule")
    df = pd.concat([gr] + [pd.read_csv(os.path.join(RESULTS, f)) for f in
                           ("ref_test.csv", "aapl_test.csv", "aac_test.csv")])
    df["fam"] = df.config.str.split("_").str[0]
    rows = [("opus", "Opus", ORANGE, "D"), ("mule", "MULE", BLUE, "o"), ("aapl", "AAC (Apple)", APPLE, "v"),
            ("vorbis", "Vorbis", GREEN, "^"), ("aac", "AAC (FDK)", VIOLET, "s")]
    vals = {fam: odg_at(df, fam, rate) for fam, *_ in rows}
    lo = np.floor(min(v.min() for v in vals.values()) * 10) / 10
    hi = max(v.max() for v in vals.values())
    xlab = max(hi, 0.0) + 0.08                            # the codecs' names, right of every dot
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.axvline(0, color=GRID, lw=1, zorder=0)
    rng = np.random.default_rng(7)
    for k, (fam, lab, c, mk) in enumerate(rows):
        v = vals[fam]
        y = len(rows) - 1 - k
        jit = rng.uniform(-0.16, 0.16, len(v))
        ax.scatter(v, y + jit, s=34, color=c, marker=mk, edgecolor="white", linewidth=0.8, zorder=3)
        p10, med, p90 = v.quantile(0.1), v.median(), v.quantile(0.9)
        ax.plot([p10, p90], [y - 0.32, y - 0.32], color=INK, lw=2, zorder=2)
        ax.plot([med, med], [y - 0.42, y - 0.22], color=INK, lw=2.5, zorder=2)
        ax.text(xlab, y, lab, color=INK, fontsize=13, ha="left", va="center")
        worst, best = v.idxmin(), v.idxmax()    # the hardest and the easiest item
        nw, nb = _names(worst), _names(best)
        span = (xlab + 0.32 * (hi - lo + 0.1)) - (lo - 0.05)
        close = v[worst] + len(nw) * span * 0.0055 > v[best] - len(nb) * span * 0.011
        ax.annotate(nw, (v[worst], y + jit[list(v.index).index(worst)]),
                    xytext=(0, 24 if close else 12), textcoords="offset points", ha="center",
                    va="bottom", fontsize=10, color=MUTED,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=1, shrinkB=4,
                                    relpos=(0.5, 0)))
        ax.annotate(nb, (v[best], y + jit[list(v.index).index(best)]),     # leftwards: the
                    xytext=(4, 12), textcoords="offset points", ha="right", va="bottom",  # codec's name
                    fontsize=10, color=MUTED,                                        # is on the right
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=1, shrinkB=4,
                                    relpos=(1, 0)))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    step = 0.2 if hi - lo > 0.8 else 0.1
    ax.set_xticks(np.round(np.arange(lo, max(hi, 0.0) + 1e-9, step), 2))
    ax.set_xlim(lo - 0.05, xlab + 0.32 * (hi - lo + 0.1))
    ax.set_ylim(-0.7, len(rows) - 0.45)
    ax.set_xlabel(f"ODG (PEAQ) de chaque extrait, à {rate} kb/s")
    fig.text(0.5, -0.04, "un point = un extrait ;  trait = de 10 à 90 % des extraits ;  barre = médiane",
             ha="center", color=MUTED, fontsize=11)
    fig.text(0.5, -0.09, "les 30 extraits du jeu de test, jamais utilisés pour les réglages",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b3-fig1-distributions" + ("" if rate == 128 else f"-{rate}"))


def b3_fig1b_distributions_160():
    """The same at 160 kb/s."""
    b3_fig1_distributions(160)


ALL = [b3_fig1_distributions, b3_fig1b_distributions_160]

if __name__ == "__main__":
    style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
