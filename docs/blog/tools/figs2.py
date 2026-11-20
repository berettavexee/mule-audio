"""Figures of the second blog post (docs/blog/02-treillis.md), in the style of figs.py (same font,
same palette). Sources: synthetic illustrations (1 to 3), the C encoder's trace in format v2
(8 states, restarted at each band; figure 4, an EBU SQAM excerpt), the development-set CSVs
(figure 5: bc_dev.csv and p4_refs_dev.csv) and the numbers logged in eval/results/B-LOG.md
(figures 6 and 7).

    .venv/bin/python docs/blog/tools/figs2.py [names...]      (default: all)
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs  # noqa: E402
from figs import BLUE, GREEN, INK, MUTED, ORANGE, RESULTS, VIOLET, plt, save  # noqa: E402

FAM = [BLUE, ORANGE, GREEN, VIOLET]            # families D0 .. D3 (k mod 4)
V2 = {"tcq_states": 8, "tcq_chain": 0, "coef_a8": 0}


def nxt(t, br, n=8):
    return (2 * t + br) % n


def fam(t, br, mask=0x6):
    return (t & 1) + 2 * (br ^ (bin(t & mask).count("1") & 1))


def b2_fig1_scalaire():
    """The scalar quantizer: a ruler of step D, each value to the nearest mark."""
    fig, ax = plt.subplots(figsize=(10, 2.6))
    ax.axhline(0, color=INK, lw=1.4)
    for k in range(-3, 4):
        ax.plot([k, k], [-0.12, 0.12], color=INK, lw=1.8)
        ax.text(k, -0.32, f"{k}D" if k not in (0, 1, -1) else ("0" if k == 0 else ("D" if k == 1 else "−D")),
                ha="center", fontsize=12, color=INK)
    ax.axvspan(0.5, 1.5, ymin=0.38, ymax=0.62, color="#e7f5ff", lw=0, zorder=0)
    vals = [-2.35, -0.8, 0.62, 1.38, 2.1]
    for v in vals:
        q = round(v)
        ax.plot(v, 0.5, "o", color=MUTED, ms=7)
        ax.annotate("", xy=(q, 0.14), xytext=(v, 0.44), arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.4))
    ax.text(1.0, 0.82, "tout ce qui tombe ici devient D :\nerreur d'au plus D/2", ha="center", fontsize=11, color=INK)
    ax.text(-3.4, 0.55, "valeurs", color=MUTED, fontsize=12)
    ax.set_xlim(-3.6, 3.6)
    ax.set_ylim(-0.5, 1.15)
    ax.axis("off")
    save(fig, "b2-fig1-scalaire")


def b2_fig2_familles():
    """Marks at half the step, coloured by family; the even and the odd rulers."""
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ks = range(-5, 6)
    rows = [(2.6, "règle fine (pas D/2)", lambda k: True),
            (1.3, "règle paire : D0 et D2 (pas D)", lambda k: k % 2 == 0),
            (0.0, "règle impaire : D1 et D3 (pas D)", lambda k: k % 2 == 1)]
    for y, lab, keep in rows:
        ax.plot([-5.6, 5.6], [y, y], color=INK, lw=1.2)
        ax.text(-5.8, y + 0.3, lab, fontsize=12, color=INK)
        for k in ks:
            if keep(k):
                ax.plot(k, y, "o", color=FAM[k % 4], ms=11, zorder=3)
                if y == 2.6:
                    ax.text(k, y - 0.42, f"D{k % 4}", ha="center", fontsize=11, color=FAM[k % 4])
    for k in ks:
        if k % 2 == 0:
            lab = {0: "0", 2: "D", -2: "−D"}.get(k, f"{k // 2}D".replace("-", "−"))
        else:
            lab = {1: "D/2", -1: "−D/2"}.get(k, f"{k}D/2".replace("-", "−"))
        ax.text(k, -0.55, lab, ha="center", fontsize=10, color=MUTED)
    ax.text(0.5, -0.95, "la règle impaire n'a pas de zéro", ha="center", fontsize=11, color=MUTED)
    ax.set_xlim(-6, 6)
    ax.set_ylim(-1.1, 3.2)
    ax.axis("off")
    save(fig, "b2-fig2-familles")


def _v2_band():
    """A band of a long frame of the trumpet (SQAM 21) coded in format v2 (8 states): values
    before quantization and TCQ levels (in D/2 units) and the states after each coefficient."""
    if not hasattr(_v2_band, "d"):
        from mule import native, params
        x = figs.wav("trumpet")
        _, _, _, tr = native.c_trace(x, params.Params(**V2))
        co = tr[(tr[:, 0] == 0) & (tr[:, 4] == 0) & (tr[:, 3] == 0)]
        best = None
        for (f, b), g in pd.DataFrame(co).groupby([2, 5]):
            g = g.sort_values(6)
            if len(g) != 16:
                continue
            v = g[17].to_numpy() / 256
            if not 4 <= np.abs(v).max() <= 9:
                continue
            lv = g[16].to_numpy()
            sc = 2 * np.round(v / 2)
            gain = np.mean((v - sc) ** 2) / max(np.mean((v - lv) ** 2), 1e-9)
            best = best or []
            best.append((gain, f, b, v, lv, g[19].to_numpy()))
        best.sort(key=lambda r: r[0])
        _v2_band.d = best[len(best) // 2]                # the median gain: a typical band
    return _v2_band.d


def b2_fig3_treillis():
    """The 8-state trellis over a few coefficients, branches coloured by family; in bold, the
    path of figure 4's first coefficients."""
    _, _, _, v, lv, st = _v2_band()
    steps = 5
    path = [0] + list(st[:steps])
    fig, ax = plt.subplots(figsize=(10, 5))
    for c in range(steps):
        for t in range(8):
            for br in (0, 1):
                u = nxt(t, br)
                on = path[c] == t and path[c + 1] == u
                ax.plot([c, c + 1], [7 - t, 7 - u], color=FAM[fam(t, br)], lw=3.2 if on else 1.0,
                        alpha=1.0 if on else 0.55, zorder=4 if on else 2)
    for c in range(steps + 1):
        for t in range(8):
            ax.plot(c, 7 - t, "o", color="white", mec=INK, ms=13, zorder=5)
            ax.text(c, 7 - t, str(t), ha="center", va="center", fontsize=9, color=INK, zorder=6)
    for c in range(steps):
        ax.text(c + 0.5, 7.75, str(c + 1), ha="center", fontsize=12, color=MUTED)
    ax.text(-0.5, 7.75, "coefficient", ha="left", fontsize=11, color=MUTED)
    ax.text(-0.55, 3.5, "état", rotation=90, va="center", fontsize=12, color=INK)
    for i, col in enumerate(FAM):
        ax.plot([5.5, 5.8], [7.0 - 0.7 * i] * 2, color=col, lw=3)
        ax.text(5.9, 7.0 - 0.7 * i, f"D{i}", va="center", fontsize=12, color=INK)
    ax.text(5.5, 3.2, "branches :\nla famille\nimposée\n\nen gras : le\nchemin choisi\npar l'encodeur\n(figure 4)",
            fontsize=11, color=INK, va="top")
    ax.set_xlim(-0.6, 6.8)
    ax.set_ylim(-0.6, 8.1)
    ax.axis("off")
    save(fig, "b2-fig3-treillis")


def b2_fig4_viterbi():
    """One real band: values, scalar rounding, TCQ levels, and the path of states."""
    gain, f, b, v, lv, st = _v2_band()
    n = len(v)
    i = np.arange(1, n + 1)
    sc = 2 * np.round(v / 2)
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, gridspec_kw={"height_ratios": [2.3, 1]})
    for y in range(int(np.floor(min(v.min(), lv.min()))) - 1, int(np.ceil(max(v.max(), lv.max()))) + 2):
        ax.axhline(y, color="#f1f3f5" if y % 2 else "#dee2e6", lw=1, zorder=0)
    ax.plot(i - 0.12, sc, "s", color=ORANGE, ms=8, label="arrondi scalaire (pas D)")
    ax.plot(i + 0.12, lv, "o", color=BLUE, ms=8, label="TCQ")
    ax.plot(i, v, "x", color=INK, ms=9, mew=2, label="valeur à quantifier")
    ax.set_ylabel("en demi-pas (D/2)")
    ax.legend(loc="upper right", fontsize=11, ncol=3, bbox_to_anchor=(1.0, 1.18))
    ax.text(0.6, ax.get_ylim()[0] + 0.3,
            "état pair : niveau pair (règle paire) ; état impair : niveau impair, entre deux graduations du scalaire",
            fontsize=11, color=INK)
    before = np.r_[0, st[:-1]]                  # the state that imposes each coefficient's ruler
    bx.step(i, before, where="mid", color=MUTED, lw=1.2)
    bx.plot(i, before, "o", color=BLUE, ms=7)
    bx.set_ylim(-0.6, 7.6)
    bx.set_yticks([0, 2, 4, 6])
    bx.set_ylabel("état avant\nle coefficient")
    bx.set_xlabel("coefficient de la bande")
    bx.set_xticks(range(1, n + 1))
    figs.plt.gcf().text(0.5, -0.03, f"trompette (EBU SQAM), trame longue {f}, bande {b}, format v2 "
                        "(8 états, treillis remis à zéro en début de bande)", ha="center", color=MUTED, fontsize=11)
    save(fig, "b2-fig4-viterbi")


def b2_fig5_v2():
    """ODG at equal rate on the development set (66 excerpts): scalar (v1), TCQ (v2), PVQ, Opus,
    Vorbis."""
    sys.path.insert(0, os.path.join(figs.ROOT, "eval"))
    from run_eval import at_rates
    bc = pd.read_csv(os.path.join(RESULTS, "bc_dev.csv"))
    bc = bc[bc.config.str.match(r"^mule(-Bl03|-C)?_")].copy()
    bc["config"] = bc.config.str.replace("mule-Bl03_", "tcq_").str.replace("mule-C_", "pvq_").str.replace("mule_", "scalaire_")
    ref = pd.read_csv(os.path.join(RESULTS, "p4_refs_dev.csv"))
    r = at_rates(pd.concat([bc, ref]), metric="odg")
    print("   dev ODG at equal rate:\n", r.round(3).to_string())
    order = [("vorbis", "Vorbis", GREEN), ("pvq", "PVQ", VIOLET), ("scalaire", "scalaire (v1)", MUTED),
             ("tcq", "TCQ (v2)", BLUE), ("opus", "Opus", ORANGE)]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for j, (rate, hatch) in enumerate(((128, None), (160, "//"))):
        for i, (k, lab, col) in enumerate(order):
            y = r.loc[k, f"odg@{rate}"]
            ax.bar(i + (j - 0.5) * 0.38, y, width=0.36, color=col, alpha=0.85 if j == 0 else 0.45,
                   edgecolor=col, lw=1.2)
            ax.text(i + (j - 0.5) * 0.38, y - 0.03, f"{y:.2f}".replace(".", ",").replace("-", "−"),
                    ha="center", va="top", fontsize=9, color=INK)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([o[1] for o in order], fontsize=12)
    ax.axhline(0, color=INK, lw=1)
    ax.set_ylabel("ODG (PEAQ)")
    ax.set_ylim(-0.52, 0.02)
    ax.text(2.0, -0.47, "barre pleine : 128 kb/s ; barre claire : 160 kb/s", fontsize=11, color=INK, ha="center")
    figs.plt.gcf().text(0.5, -0.09, "corpus de réglage (66 extraits), à débit égal ; plus près de 0, mieux c'est",
                        ha="center", color=MUTED, fontsize=11)
    save(fig, "b2-fig5-v2")


def b2_fig6_simulateur():
    """Simulated gain over scalar quantization at 1.25 bit per coefficient (eval/results/B-LOG.md,
    eval/tcq_sim.py): restarted at each band, chained over the frame (joint Viterbi), and the
    48-state and greedy-chain points."""
    restart = {8: -0.06, 16: -0.02, 32: -0.00}
    chain = {8: 0.03, 16: 0.12, 32: 0.17, 64: 0.23}
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.axhline(0, color=MUTED, lw=1, ls="--")
    ax.text(8.3, 0.005, "quantificateur scalaire", fontsize=10, color=MUTED, ha="left", va="bottom")
    ax.plot(list(restart), list(restart.values()), "o-", color=ORANGE, lw=2, ms=7)
    ax.plot(list(chain), list(chain.values()), "o-", color=BLUE, lw=2, ms=7)
    ax.plot(48, 0.12, "D", color=VIOLET, ms=9)
    ax.annotate("48 états :\nmoins bien que 32", xy=(48, 0.12), xytext=(50, 0.035), fontsize=11, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK))
    ax.plot(8, -0.14, "x", color=INK, ms=10, mew=2)
    ax.text(9.5, -0.145, "8 états enchaînés sans Viterbi conjoint", fontsize=11, color=INK, va="center")
    ax.text(33, -0.035, "remis à zéro à chaque bande (v2)", fontsize=11, color=ORANGE)
    ax.text(40, 0.2, "en chaîne sur la trame (v3)", fontsize=11, color=BLUE, ha="right")
    ax.set_xscale("log", base=2)
    ax.set_xticks([8, 16, 32, 48, 64])
    ax.set_xticklabels(["8", "16", "32", "48", "64"])
    ax.minorticks_off()
    ax.set_xlabel("états du treillis")
    ax.set_ylabel("gain sur le scalaire (dB)")
    ax.set_ylim(-0.19, 0.27)
    figs.plt.gcf().text(0.5, -0.09, "simulateur : sources laplaciennes découpées en bandes de MULE, "
                        "1,25 bit par coefficient", ha="center", color=MUTED, fontsize=11)
    save(fig, "b2-fig6-simulateur")


def b2_fig7_etats():
    """ODG gain in the codec at 128 kb/s against format v2, by number of states of the chained
    trellis (development set, eval/results/B-LOG.md), with the 95 % bootstrap intervals."""
    pts = [(8, 0.015, 0.010, 0.020), (16, 0.026, 0.017, 0.035), (32, 0.037, 0.028, 0.046),
           (64, 0.040, 0.029, 0.051)]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = [p[0] for p in pts]
    y = [p[1] for p in pts]
    ax.errorbar(x, y, yerr=[[p[1] - p[2] for p in pts], [p[3] - p[1] for p in pts]], fmt="o-", color=BLUE,
                lw=2, ms=8, capsize=5)
    ax.plot(32, 0.012, "s", color=ORANGE, ms=8)
    ax.text(34, 0.012, "32 états sans chaîne", fontsize=11, color=INK, va="center")
    for xi, yi in zip(x, y, strict=True):
        ax.text(xi * 1.07, yi, f"+{yi:.3f}".replace(".", ","), ha="left", va="center", fontsize=11, color=INK)
    ax.axhline(0.01, color=MUTED, lw=1, ls="--")
    ax.text(64, 0.006, "seuil d'adoption : +0,01", fontsize=10, color=MUTED, ha="right")
    ax.set_xscale("log", base=2)
    ax.set_xticks(x)
    ax.set_xlim(6.5, 90)
    ax.set_xticklabels([str(v) for v in x])
    ax.minorticks_off()
    ax.set_ylim(0, 0.062)
    ax.set_xlabel("états du treillis, en chaîne sur la trame")
    ax.set_ylabel("gain d'ODG à 128 kb/s")
    figs.plt.gcf().text(0.5, -0.09, "corpus de réglage (66 extraits), à débit égal, contre le format v2 ; "
                        "barres : intervalles à 95 %", ha="center", color=MUTED, fontsize=11)
    save(fig, "b2-fig7-etats")


ALL = [b2_fig1_scalaire, b2_fig2_familles, b2_fig3_treillis, b2_fig4_viterbi, b2_fig5_v2,
       b2_fig6_simulateur, b2_fig7_etats]

if __name__ == "__main__":
    figs.style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
