"""P4: compares codec families at equal rate, with bootstrap confidence intervals over items.

  python eval/p4_compare.py RESULTS.csv [MORE.csv ...] --base mule --vs mule-x [--metric odg]

For each family (config prefix before "_"), the corpus curve is (mean kb/s, mean metric) over
its configurations (quality settings); a family is compared with the base at 128 and 160 kb/s by
interpolating both curves. The confidence interval resamples the items (1000 times). Per item,
the variant's change is made rate-fair with the base's own local slope:
  delta = (m_var - m_base) - slope_base * (kbps_var - kbps_base), same quality setting;
items regressing by more than --regress are listed.
"""
import argparse
import sys

import numpy as np
import pandas as pd


def curve(df, fam, metric):
    g = df[df.family == fam].groupby("config")[["kbps", metric]].mean().sort_values("kbps")
    return g["kbps"].to_numpy(), g[metric].to_numpy()


def at(df, fam, metric, rate):
    k, m = curve(df, fam, metric)
    return np.interp(rate, k, m) if k.min() <= rate <= k.max() else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--base", default="mule")
    ap.add_argument("--vs", nargs="+", required=True)
    ap.add_argument("--metric", nargs="+", default=["odg", "odg_adv", "nmr_db"])
    ap.add_argument("--rates", type=float, nargs="+", default=[128, 160])
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--regress", type=float, default=0.05)
    a = ap.parse_args()
    df = pd.concat([pd.read_csv(f) for f in a.csv]).drop_duplicates(["config", "item"], keep="last")
    df["family"] = df.config.str.rsplit("_", n=1).str[0]
    df["q"] = df.config.str.rsplit("_", n=1).str[1]
    rng = np.random.default_rng(0)
    items = sorted(set(df[df.family == a.base].item))
    for vs in a.vs:
        common = sorted(set(items) & set(df[df.family == vs].item))
        sub = df[df.item.isin(common)]
        print(f"\n=== {vs} vs {a.base}  ({len(common)} items)")
        for metric in a.metric:
            sign = -1 if metric.startswith("nmr") else 1          # NMR: lower is better
            row = []
            for r in a.rates:
                d0 = sign * (at(sub, vs, metric, r) - at(sub, a.base, metric, r))
                boots = []
                for _ in range(a.boot):
                    pick = rng.choice(common, len(common))
                    idx = np.concatenate([np.flatnonzero(sub.item.to_numpy() == it) for it in pick])
                    bs = sub.iloc[idx]
                    boots.append(sign * (at(bs, vs, metric, r) - at(bs, a.base, metric, r)))
                lo, hi = np.nanpercentile(boots, [2.5, 97.5])
                row.append(f"@{r:g}: {d0:+.4f} [{lo:+.4f}, {hi:+.4f}]")
            print(f"  {metric:8s} " + "   ".join(row) + ("   (+ = better)"))
        # per-item, rate-fair at the same quality settings
        b = sub[sub.family == a.base].set_index(["item", "q"])
        v = sub[sub.family == vs].set_index(["item", "q"])
        j = b.join(v, lsuffix="_b", rsuffix="_v", how="inner")
        m = a.metric[0]
        out = []
        for it, g in j.groupby(level=0):
            g = g.sort_values("kbps_b")
            slope = np.polyfit(g.kbps_b, g[m + "_b"], 1)[0] if len(g) > 1 else 0.0
            dlt = ((g[m + "_v"] - g[m + "_b"]) - slope * (g.kbps_v - g.kbps_b)).mean()
            out.append((it, dlt, 100 * (g.kbps_v / g.kbps_b - 1).mean()))
        out = pd.DataFrame(out, columns=["item", f"d_{m}", "rate_%"]).set_index("item")
        print(f"  rate change at equal settings: {out['rate_%'].mean():+.2f} %")
        bad = out[out[f"d_{m}"] < -a.regress].sort_values(f"d_{m}")
        good = out.sort_values(f"d_{m}", ascending=False).head(5)
        print(f"  regressions (< -{a.regress} {m}): {len(bad)}")
        if len(bad):
            print(bad.round(3).to_string())
        print("  best:\n" + good.round(3).to_string())


if __name__ == "__main__":
    sys.exit(main())
