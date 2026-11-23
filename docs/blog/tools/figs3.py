"""Figures of the third blog post (docs/blog/03-modele.md), in the style of figs.py (same font,
same palette). Sources: the C encoder's operations and trace on ABBA (EBU SQAM 69, figures 1, 2
and 4), and on the first 20 excerpts of the development set at q -7 (figures 3 and 5: the same
measurement as eval/entropy_gain.py, format v5; only statistics are drawn). Costs are the
adaptive models' (native.stream_cost); rANS codes within 0.01 % of them.

    .venv/bin/python docs/blog/tools/figs3.py [names...]      (default: all)
"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs  # noqa: E402
from figs import (BLUE, FILL_BLUE, FILL_ORANGE, GREEN, INK, MUTED, ORANGE, VIOLET, native,  # noqa: E402
                  params, plt, save)

KEY = 40                                        # frames between key packets (model resets)
COEF = "coef"
ESC = 7                                         # the coefficient alphabet's escape (format v3+)


def fr(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def _abba():
    """ABBA at q -7: operations (m, v), frame starts, trace."""
    if not hasattr(_abba, "d"):
        x = figs.wav("abba")
        m, v, fstart, tr = native.c_trace(x, params.Params(q_db=-7.0))
        _abba.d = x, m, v.astype(np.int64), np.asarray(fstart), tr
    return _abba.d


def _resets(m, fstart, sel):
    """The positions, within the selected operations, of the model resets (each key packet)."""
    keys = fstart[np.arange(0, len(fstart) - 1, KEY)]
    return np.concatenate([[0], np.cumsum(sel)])[keys]


def b3_fig1_histogramme():
    """The coefficient indices' magnitudes on ABBA, their share and their cost by Shannon."""
    _x, _m, _v, _fs, tr = _abba()
    idx = np.abs(tr[tr[:, 0] == 0][:, 13])
    top = ESC                                   # 7 and above: the escape
    k = np.minimum(idx, top)
    share = np.array([(k == i).mean() for i in range(top + 1)])
    cost = -np.log2(np.maximum(share, 1e-12))
    print(f"   abba: {len(idx)} coefficients, 0: {share[0]:.1%}, 1: {share[1]:.1%}, >= {top}: {share[top]:.2%}; "
          f"mean cost {np.sum(share * cost):.2f} bit (signs apart)")
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.bar(np.arange(top + 1), 100 * share, color=FILL_BLUE, edgecolor=BLUE, lw=1.2, width=0.75)
    for i in range(top + 1):
        ax.text(i, 100 * share[i] + 1.5, f"{fr(cost[i])} bit" + ("s" if cost[i] >= 2 else ""), ha="center",
                fontsize=11, color=INK)
    ax.set_xticks(np.arange(top + 1))
    ax.set_xticklabels([str(i) for i in range(top)] + [f"{top} et +\n(échappement)"])
    ax.set_xlabel("index du coefficient (valeur absolue)")
    ax.set_ylabel("part des coefficients (%)")
    ax.set_ylim(0, 100 * share.max() * 1.18)
    ax.text(top - 0.2, 100 * share.max() * 0.75, "au-dessus de chaque barre :\nce qu'il coûte, −log2(p)",
            ha="right", fontsize=11, color=MUTED)
    fig.text(0.5, -0.16, "ABBA (EBU SQAM 69), 15 s au réglage par défaut ; signes à part",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b3-fig1-histogramme")


def _rans_trace(sym, freq, start, L=1 << 16, prob_bits=15):
    """A 32-bit rANS encoder over sym (static table freq/start), state x in [L, 2^32): log2(x)
    after each symbol, and the symbols before which 16 bits went to the file."""
    x, ys, outs = L, [np.log2(L)], []
    for i, s in enumerate(sym):
        f = int(freq[s])
        x_max = ((L >> prob_bits) << 16) * f
        while x >= x_max:
            x >>= 16
            outs.append(i)
        x = ((x // f) << prob_bits) + (x % f) + int(start[s])
        ys.append(np.log2(x))
    return np.array(ys), outs


def b3_fig2_rans():
    """rANS's state on a run of ABBA's coefficient symbols (static table of their frequencies)."""
    _x, m, v, _fs, _tr = _abba()
    off = params.OFF[COEF]
    nsym = dict((n, s) for n, s, _c in params.STREAMS)[COEF]
    sel = (m >= off) & (m < off + 96)
    sym = v[sel]
    cnt = np.bincount(sym, minlength=nsym).astype(float) + 0.5
    freq = np.maximum(1, np.round(cnt / cnt.sum() * 32768)).astype(np.int64)
    freq[np.argmax(freq)] += 32768 - freq.sum()
    start = np.concatenate([[0], np.cumsum(freq)[:-1]])
    # a run of 32 symbols: mostly zeros and ones, a few larger indices, at most one escape
    n_run, best, at = 32, -1, 0
    for i in range(0, len(sym) - n_run, 5):
        r = sym[i:i + n_run]
        if (r == ESC).sum() <= 1 and (r == 0).sum() >= 14:
            sc = ((r >= 2) & (r < ESC)).sum()
            if sc > best:
                best, at = sc, i
    run = sym[at:at + n_run]
    ys, outs = _rans_trace(run, freq, start)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.plot(np.arange(len(ys)), ys, "o-", color=BLUE, lw=2, ms=4)
    for lvl, lab in ((32, "32 bits"), (16, "16 bits")):
        ax.axhline(lvl, color=MUTED, lw=1, ls="--")
        ax.text(n_run + 0.4, lvl, lab, fontsize=11, color=MUTED, va="center")
    for j, i in enumerate(outs):
        ax.plot([i, i + 1], [ys[i], ys[i + 1]], color=ORANGE, lw=2.5)
        ax.text(i + 0.5, ys[i] + 0.7, "16 bits\nvers le fichier" if j == 0 else "16 bits", ha="center",
                va="bottom", fontsize=10, color=ORANGE)
    for i, s in enumerate(run):
        ax.text(i + 1, 13.3, str(s) if s < ESC else "e", ha="center", fontsize=10, color=INK if s else MUTED)
    ax.text(0.3, 13.3, "symbole :", ha="right", fontsize=10, color=MUTED)
    ax.set_xlim(-0.5, n_run + 3)
    ax.set_ylim(12.3, 36)
    ax.set_xlabel("symboles codés")
    ax.set_ylabel("taille de l'état (bits)")
    p0 = freq[0] / 32768
    fig.text(0.5, -0.1, f"{n_run} symboles de coefficients d'ABBA, avec leurs fréquences : un 0 (p = {fr(100 * p0, 0)} %) "
             f"ajoute {fr(-np.log2(p0), 2)} bit, un 3 ou un 4 plusieurs",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b3-fig2-rans")


def _dev_costs():
    """The first 20 excerpts of the development set at q -7: kb/s under the four schemes, and the
    split of MULE's stream by category."""
    if hasattr(_dev_costs, "d"):
        return _dev_costs.d
    import corpus
    init = params.load_init()
    items = corpus.items("dev")[:20]
    tot = dict.fromkeys(("fixed", "static", "noctx", "mule"), 0.0)
    part = dict.fromkeys(("coef", "esc", "signs", "energy", "alloc", "other"), 0.0)
    raw_all, dur = 0.0, 0.0
    for _name, path in items:
        x, fs = sf.read(path, dtype="float64", always_2d=True)
        m, v, fstart = native.c_ops(x, params.Params(q_db=-7.0))
        v = v.astype(np.int64)
        fstart = np.asarray(fstart)
        dur += len(x) / fs
        raw = m < 0
        raw_all += float(-m[raw].sum())
        ce = np.where((m >= params.OFF["cesc"]) & (m < params.OFF["cesc"] + 16))[0]
        ce = ce[ce + 1 < len(m)]
        suf = np.zeros(len(m), bool)
        nx = ce + 1
        suf[nx] = raw[nx] & (-m[nx] == v[ce]) & (v[ce] > 0)
        signs = raw & ~suf & (m == -1)
        part["esc"] += float(-m[suf].sum())
        part["signs"] += float(signs.sum())
        part["other"] += float(-m[raw & ~suf & ~signs].sum())
        for name, n, nctx in params.STREAMS:
            sel = (m >= params.OFF[name]) & (m < params.OFF[name] + nctx)
            if not sel.any():
                continue
            ctx = m[sel] - params.OFF[name]
            sym = v[sel]
            res = _resets(m, fstart, sel)
            tab = init.get(name)
            tot["fixed"] += len(sym) * np.ceil(np.log2(n))
            tot["static"] += sum(_static_bits(tab[c], n, sym[ctx == c]) for c in range(nctx)) \
                if tab is not None else len(sym) * np.log2(n)
            tot["noctx"] += native.stream_cost(n, 1, np.zeros_like(ctx), sym, res, None)
            each = native.stream_cost_each(n, nctx, ctx, sym.astype(np.int32), res, tab)
            tot["mule"] += each.sum()
            if name == COEF:
                e = sym == ESC
                part["esc"] += each[e].sum()
                part["coef"] += each[~e].sum()
            elif name == "cesc":
                part["esc"] += each.sum()
            elif name in ("energy", "alloc"):
                part[name] += each.sum()
            else:
                part["other"] += each.sum()
    kb = {k: (b + raw_all) / dur / 1000 for k, b in tot.items()}
    pk = {k: b / dur / 1000 for k, b in part.items()}
    print(f"   dev (20 excerpts, {dur:.0f} s): " + ", ".join(f"{k} {r:.1f}" for k, r in kb.items())
          + " kb/s; split " + ", ".join(f"{k} {r:.2f}" for k, r in pk.items()))
    _dev_costs.d = kb, pk
    return _dev_costs.d


def _static_bits(cdf, n, sym):
    """15 - log2(freq) under a fixed CDF (MIN_FREQ 4 per symbol), as eval/entropy_gain.py."""
    if not len(sym):
        return 0.0
    span = 32768 - n * 4
    st = (cdf.astype(np.int64) * span >> 15) + np.arange(n + 1) * 4
    st[n] = 32768
    freq = st[1:] - st[:-1]
    return float(np.sum(15 - np.log2(freq[sym])))


def b3_fig3_schemas():
    """The same symbols written four ways (kb/s)."""
    kb, _ = _dev_costs()
    rows = [("codes de longueur fixe", kb["fixed"], MUTED, "#e9ecef"),
            ("tables adaptatives,\nsans contexte", kb["noctx"], ORANGE, FILL_ORANGE),
            ("tables apprises par contexte,\nfigées (à la façon d'AAC)", kb["static"], VIOLET, "#eebefa"),
            ("MULE : contextes\net adaptation", kb["mule"], BLUE, FILL_BLUE)]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for i, (lab, r, ec, fc) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, r, color=fc, edgecolor=ec, lw=1.2, height=0.62)
        ax.text(r + 3, y, f"{fr(r)} kb/s", va="center", fontsize=12, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=12)
    ax.set_xlim(0, kb["fixed"] * 1.2)
    ax.set_xlabel("débit (kb/s)")
    fig.text(0.5, -0.08, "les mêmes symboles, 20 extraits du corpus de réglage au réglage par défaut "
             "(bits bruts compris)", ha="center", color=MUTED, fontsize=11)
    save(fig, "b3-fig3-schemas")


def b3_fig4_adaptation():
    """The cost of the n-th symbol after a key packet, in ABBA's busiest coefficient context,
    starting from the trained table or from a uniform one (mean over the key packets)."""
    _x, m, v, fstart, _tr = _abba()
    off = params.OFF[COEF]
    nsym, nctx = [(s, c) for n, s, c in params.STREAMS if n == COEF][0]
    sel = (m >= off) & (m < off + nctx)
    ctx = (m[sel] - off).astype(np.int32)
    sym = v[sel].astype(np.int32)
    res = _resets(m, fstart, sel)
    init = params.load_init()[COEF]
    c0 = np.bincount(ctx).argmax()
    curves = {}
    for lab, tab in (("trained", init), ("uniform", None)):
        each = native.stream_cost_each(nsym, nctx, ctx, sym, res, tab)
        rank = np.zeros(len(sym), np.int64)          # rank of each symbol of context c0 since the reset
        seg = np.searchsorted(res, np.arange(len(sym)), side="right") - 1
        pick = np.where(ctx == c0)[0]
        cnt = {}
        for i in pick:
            k = seg[i]
            rank[i] = cnt.get(k, 0)
            cnt[k] = rank[i] + 1
        N = 160
        curves[lab] = np.array([each[pick][rank[pick] == n].mean() for n in range(N)])
    p = np.bincount(sym[ctx == c0], minlength=nsym) / (ctx == c0).sum()
    h = -np.sum(p[p > 0] * np.log2(p[p > 0]))
    k = 12                                            # smoothing for the drawing
    sm = {key: np.convolve(c, np.ones(k) / k, mode="valid") for key, c in curves.items()}
    n = np.arange(len(sm["trained"])) + k / 2
    print(f"   abba context {c0}: {(ctx == c0).sum()} symbols, entropy {h:.2f} bit; first 8 symbols "
          f"{curves['trained'][:8].mean():.2f} (trained) / {curves['uniform'][:8].mean():.2f} (uniform)")
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(n, sm["uniform"], color=ORANGE, lw=2)
    ax.plot(n, sm["trained"], color=BLUE, lw=2)
    ax.axhline(h, color=GREEN, lw=1.2, ls="--")
    ax.text(n[-1], h - 0.18, "entropie du contexte sur tout l'extrait", ha="right", va="top", fontsize=11, color=GREEN)
    ax.text(n[3], sm["uniform"][3] + 0.05, "départ uniforme", fontsize=12, color=ORANGE, va="bottom")
    ax.text(n[len(n) // 5], sm["trained"].max() + 0.12, "départ appris", fontsize=12, color=BLUE, va="bottom")
    ax.set_ylim(0, None)
    ax.set_xlabel("rang du symbole depuis le dernier paquet clé")
    ax.set_ylabel("coût moyen (bits)")
    fig.text(0.5, -0.08, f"ABBA (EBU SQAM 69), le contexte de coefficients le plus utilisé : coût moyen du n-ième "
             f"symbole après la remise à zéro", ha="center", color=MUTED, fontsize=11)
    save(fig, "b3-fig4-adaptation")


def b3_fig5_paquet():
    """MULE's stream by category (20 excerpts of the development set, q -7)."""
    _, pk = _dev_costs()
    tot = sum(pk.values())
    rows = [("index de coefficients (rANS)", pk["coef"], BLUE, FILL_BLUE),
            ("signes (bits bruts)", pk["signs"], BLUE, "#d0ebff"),
            ("grands index (échappements)", pk["esc"], VIOLET, "#eebefa"),
            ("énergies des bandes", pk["energy"], ORANGE, FILL_ORANGE),
            ("allocations", pk["alloc"], ORANGE, "#ffe8cc"),
            ("le reste (stéréo, type de bloc…)", pk["other"], MUTED, "#e9ecef")]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for i, (lab, r, ec, fc) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, r, color=fc, edgecolor=ec, lw=1.2, height=0.62)
        ax.text(r + 0.8, y, f"{fr(r)} kb/s ({fr(100 * r / tot, 0)} %)", va="center", fontsize=12, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=12)
    ax.set_xlim(0, max(pk.values()) * 1.45)
    ax.set_xlabel("débit (kb/s)")
    fig.text(0.5, -0.08, f"tout le flux, {fr(tot)} kb/s : 20 extraits du corpus de réglage au réglage par défaut",
             ha="center", color=MUTED, fontsize=11)
    save(fig, "b3-fig5-paquet")


ALL = [b3_fig1_histogramme, b3_fig2_rans, b3_fig3_schemas, b3_fig4_adaptation, b3_fig5_paquet]

if __name__ == "__main__":
    figs.style()
    want = sys.argv[1:]
    for fn in ALL:
        if not want or any(w in fn.__name__ for w in want):
            fn()
