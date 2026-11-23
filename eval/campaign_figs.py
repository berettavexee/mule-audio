"""Figures of eval/campaign.py's report (from data/campaign/matched.csv, written by the report):

  campaign-means.png   each judge's mean at 96, 128 and 160 kb/s, per codec, with its 95 %
                       interval (bootstrap over artists), one panel per judge
  campaign-diff.png    the paired differences at 128 kb/s, MULE minus each other codec, track by
                       track (sorted), oriented so that above zero MULE is better

  python eval/campaign_figs.py [OUT_DIR]   (default data/campaign/)
Colours as the blog's figures: MULE blue, Opus orange, Apple AAC raspberry."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, MUTED, GRID = "#1e1e1e", "#868e96", "#dee2e6"
CODECS = [("mule", "MULE v5", "#1971c2", "o"), ("opus", "Opus", "#e8590c", "D"),
          ("aac", "AAC (Apple)", "#c2255c", "v")]
JUDGES = [("zimt", "Zimtohrli distance (x 10^4)\nlower is better", 1e4, -1),
          ("odg", "PEAQ basic ODG\nhigher is better", 1, 1),
          ("odg_adv", "PEAQ advanced ODG\nhigher is better", 1, 1)]


def boot_mean_ci(v, clusters, rng, n=5000):
    keys = sorted(set(clusters))
    idx = {k: [i for i, c in enumerate(clusters) if c == k] for k in keys}
    sums = np.array([v[idx[k]].sum() for k in keys])
    cnts = np.array([len(idx[k]) for k in keys])
    pick = rng.integers(0, len(keys), size=(n, len(keys)))
    m = sums[pick].sum(1) / cnts[pick].sum(1)
    return np.percentile(m, [2.5, 97.5])


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def main(out):
    df = pd.read_csv(os.path.join(ROOT, "data", "campaign", "matched.csv"))
    rng = np.random.default_rng(2026)
    n_items = df["item"].nunique()
    rates = sorted(df["rate"].unique())
    fig, axes = plt.subplots(1, len(JUDGES), figsize=(13, 4.4), dpi=150)
    for ax, (col, lab, k, _sgn) in zip(axes, JUDGES):
        for j, (fam, name, color, mk) in enumerate(CODECS):
            means, los, his = [], [], []
            for r in rates:
                s = df[(df.codec == fam) & (df.rate == r)].sort_values("item")
                v = k * s[col].to_numpy()
                lo, hi = boot_mean_ci(v, list(s["artist"]), rng)
                means.append(v.mean())
                los.append(v.mean() - lo)
                his.append(hi - v.mean())
            x = np.array(rates) + (j - 1) * 2.5
            ax.errorbar(x, means, yerr=[los, his], color=color, marker=mk, ms=6, lw=2, capsize=3,
                        label=name, markeredgecolor="white", markeredgewidth=0.8)
        ax.set_xticks(rates)
        ax.set_xlabel("mean rate (kb/s)", color=INK)
        ax.set_title(lab, color=INK, fontsize=11)
        style(ax)
    axes[0].legend(frameon=False, fontsize=10)
    fig.suptitle(f"{n_items} tracks, 30 s each: mean and 95 % interval (bootstrap over artists)",
                 color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "campaign-means.png"), bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, len(JUDGES), figsize=(13, 4.2), dpi=150)
    r = 128
    for ax, (col, lab, k, sgn) in zip(axes, JUDGES):
        m = df[(df.codec == "mule") & (df.rate == r)].set_index("item")[col]
        for fam, name, color, _mk in CODECS[1:]:
            o = df[(df.codec == fam) & (df.rate == r)].set_index("item")[col]
            d = np.sort(sgn * k * (m - o.reindex(m.index)).to_numpy())
            share = np.mean(d > 0)
            ax.plot(np.linspace(0, 100, len(d)), d, color=color, lw=2,
                    label=f"MULE vs {name}: MULE better on {100 * share:.0f} %")
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xlabel("tracks, sorted (%)", color=INK)
        ax.set_title(lab.split("\n")[0] + "\nabove 0: MULE better", color=INK, fontsize=11)
        style(ax)
        ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle(f"Paired differences at {r} kb/s, track by track", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "campaign-diff.png"), bbox_inches="tight")
    plt.close(fig)
    print(f"figures in {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "campaign"))
