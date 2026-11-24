"""Figures of eval/campaign.py's report (from data/campaign/matched.csv, written by the report):

  campaign-means.png   each judge's mean at 96, 128 and 160 kb/s, per codec, with its 95 %
                       interval (bootstrap over artists), one panel per judge
  campaign-diff.png    the paired differences at 128 kb/s, MULE minus each other codec, track by
                       track (sorted), oriented so that above zero MULE is better
  campaign-rates.png   each track's rate at 96, 128 and 160 kb/s (equal mean rate), sorted: how
                       far each codec's VBR moves a track from the target (MULE -q dashed)

  python eval/campaign_figs.py [OUT_DIR] [--csv MATCHED.csv] [--mule FAMILY]
  (default data/campaign/, its matched.csv, MULE = family "mule"; the target rate mode:
  --csv data/campaign/matched_mule-mule_br-opus-aac.csv --mule mule_br)
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


def main(out, csv=None, mule="mule"):
    global CODECS
    df = pd.read_csv(csv or os.path.join(ROOT, "data", "campaign", "matched.csv"))
    base = df[df.codec == "mule"].copy()
    CODECS = [(mule, "MULE v5" + (" (--bitrate)" if mule.startswith("mule_br") else ""), *CODECS[0][2:])] + CODECS[1:]
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
        m = df[(df.codec == CODECS[0][0]) & (df.rate == r)].set_index("item")[col]
        for fam, name, color, _mk in CODECS[1:]:
            o = df[(df.codec == fam) & (df.rate == r)].set_index("item")[col]
            d = np.sort(sgn * k * (m - o.reindex(m.index)).to_numpy())
            share = np.mean(d > 0)
            ax.plot(np.linspace(0, 100, len(d)), d, color=color, lw=2,
                    label=f"vs {name}: MULE better on {100 * share:.0f} %")
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xlabel("tracks, sorted (%)", color=INK)
        ax.set_title(lab.split("\n")[0] + "\nabove 0: MULE better", color=INK, fontsize=11)
        style(ax)
        ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle(f"{CODECS[0][1]} minus each other codec at {r} kb/s, track by track", color=INK,
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "campaign-diff.png"), bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(1, len(rates), figsize=(13, 4.2), dpi=150, sharey=False)
    for ax, r in zip(axes, rates):
        for fam, name, color, _mk in CODECS:
            v = np.sort(df[(df.codec == fam) & (df.rate == r)]["kbps"].to_numpy())
            sd = v.std(ddof=1)
            ax.plot(np.linspace(0, 100, len(v)), v, color=color, lw=2, label=f"{name}: sd {sd:.1f} kb/s")
        if mule != "mule" and len(base):
            v = np.sort(base[base.rate == r]["kbps"].to_numpy())
            ax.plot(np.linspace(0, 100, len(v)), v, color=CODECS[0][2], lw=1.5, ls="--",
                    label=f"MULE v5 (-q): sd {v.std(ddof=1):.1f} kb/s")
        ax.axhline(r, color=INK, lw=0.8)
        ax.set_xlabel("tracks, sorted by rate (%)", color=INK)
        ax.set_ylabel("rate of the track (kb/s)", color=INK)
        ax.set_title(f"{r} kb/s on average", color=INK, fontsize=11)
        style(ax)
        ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.suptitle("Each track's rate at equal mean rate (audio payload, 30 s excerpts)", color=INK,
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "campaign-rates.png"), bbox_inches="tight")
    plt.close(fig)
    print(f"figures in {out}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=os.path.join(ROOT, "data", "campaign"))
    ap.add_argument("--csv")
    ap.add_argument("--mule", default="mule")
    a = ap.parse_args()
    main(a.out, a.csv, a.mule)
