"""Context measurements on the encoder's trace (docs/V3-IDEAS.md M2, M7, M8; M1's rate side).

The C encoder records every coefficient and energy symbol it codes (mule_encode_trace). The
quantized values do not depend on the contexts, so another context rule changes the rate only,
never the sound: its cost is recomputed here with the real adaptive models, reset at every key
packet, each rule's initial tables trained the same way on the `train` corpus.

  python eval/ctx_lab.py trace [--set dev] [--q -7]   # cache the traces (data/trace)
  python eval/ctx_lab.py check                        # the current rule reproduces the stream
  python eval/ctx_lab.py m8                           # moving average y_prev (alpha, kappa)
  python eval/ctx_lab.py m2                           # bits with and without inter-frame context
  python eval/ctx_lab.py m7                           # interpolated energies; two-sided context
  python eval/ctx_lab.py m1                           # rate against the key packet interval
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from functools import partial

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "eval")]
import corpus  # noqa: E402
from mule import native, params as E  # noqa: E402

CACHE = os.path.join(ROOT, "data", "trace2")    # trace format 2 (20 fields)
F = 1024
NC_MAP = np.array([0, 1, 2, 3, 3, 4, 4, 4, 4])
C = {k: i for i, k in enumerate(native.TRACE_FIELDS["coef"])}
EN = {k: i for i, k in enumerate(native.TRACE_FIELDS["energy"])}


# ---------------------------------------------------------------- traces
EXTRA = {}                      # encoder settings over the production's (--params), in every trace


def _suffix():
    return "".join(f"_{k}{v}" for k, v in sorted(EXTRA.items()))


def _trace_job(args):
    name, wav, q, path, extra = args
    if os.path.exists(path):
        return path
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    m, v, fstart, tr = native.c_trace(x, E.Params(q_db=q, **extra))
    keys = fstart[np.arange(0, len(fstart) - 1, 40)]
    total = float(-m[m < 0].sum())                      # raw bits
    init = E.load_init()
    for sname, n, nctx in E.STREAMS:                    # every stream's bits, as coded
        sel = (m >= E.OFF[sname]) & (m < E.OFF[sname] + nctx)
        if sel.any():
            before = np.concatenate([[0], np.cumsum(sel)])[keys]
            total += native.stream_cost(n, nctx, m[sel] - E.OFF[sname], v[sel], before, init.get(sname))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path + ".tmp.npz", trace=tr, keys=keys, total_bits=total,
                        seconds=len(x) / fs)
    os.replace(path + ".tmp.npz", path)
    return path


def trace_paths(subset, q=-7.0):
    return [(n, w, q, os.path.join(CACHE, f"{subset}_q{q:+g}{_suffix()}", n + ".npz"), dict(EXTRA))
            for n, w in corpus.items(subset)]


def ensure(subset, q=-7.0):
    jobs = trace_paths(subset, q)
    todo = [j for j in jobs if not os.path.exists(j[3])]
    if todo:
        print(f"tracing {len(todo)} {subset} items...", file=sys.stderr, flush=True)
        with ProcessPoolExecutor() as ex:
            for k, _ in enumerate(ex.map(_trace_job, todo), 1):
                if k % 10 == 0 or k == len(todo):
                    print(f"  {k}/{len(todo)}", file=sys.stderr, flush=True)
    return [j[3] for j in jobs]


def load(path):
    z = np.load(path)
    tr = z["trace"]
    co = tr[tr[:, 0] == 0]
    en = tr[tr[:, 0] == 1]
    return dict(co=co, en=en, keys=z["keys"], total=float(z["total_bits"]), seconds=float(z["seconds"]))


def coef_resets(co, keys):
    """Positions in the coefficient stream where the models are reset (key packets)."""
    return np.searchsorted(co[:, C["op"]], keys)


# ---------------------------------------------------------------- context rules
def ctx_from(co, pm):
    """The format's context rule with an inter-frame predictor pm (-1: none): ac*6 + class."""
    mctx = 2 * co[:, C["tail1"]].astype(np.int64) + co[:, C["tail2"]]
    p = np.minimum(pm, 31)
    mctx = np.where(pm >= 0, (mctx + 3 * p + 1) >> 1, mctx)
    return co[:, C["ac"]] * 6 + np.where(mctx < 9, NC_MAP[np.minimum(mctx, 8)], 5)


def rule_current(co):
    return ctx_from(co, co[:, C["pm"]].astype(np.int64))


def state_before(co, chain=False):
    """The trellis state before each coefficient (known to the decoder): the previous
    coefficient's state after, 0 at the start of each band call (spec 5.3), or with the v3 chain
    (--params tcq_chain=1) at the start of each frame and channel (short frames' groups
    approximated as one)."""
    t = co[:, C["tstate"]]
    key = co[:, C["frame"]].astype(np.int64) * 2 + co[:, C["ch"]]
    if not chain:
        key = key * 32 + co[:, C["band"]]
    start = np.r_[True, key[1:] != key[:-1]]
    return np.where(start, 0, np.r_[0, t[:-1]])


def rule_parity(co, chain=False):
    """Point 4: the current context, split by the parity of the trellis state (192 contexts)."""
    return rule_current(co) + 96 * (state_before(co, chain) & 1)


def rule_state8(co, chain=False):
    """Point 4, upper variant: split by the full trellis state (768 contexts)."""
    return rule_current(co) + 96 * state_before(co, chain)


def rule_no_inter(co):
    """Counterfactual: no inter-frame context at all (the two previous indices only)."""
    return ctx_from(co, np.full(len(co), -1, np.int64))


def rule_ema(co, alpha, kappa=1.0, mode="ema", integer=False):
    """y_prev replaced by a moving average of |y|^kappa per line, rescaled as y_prev is (2^(e/4)
    in the |y| domain), reset where y_prev is: key packets, after short frames, uncoded bands.
    mode "ema": the average; "max": max(y_prev, average). integer: the state kept as the decoder
    would (Q4, 16 bits)."""
    pm = np.full(len(co), -1, np.int64)
    state = np.zeros((2, F))
    fr, ch, ty = co[:, C["frame"]], co[:, C["ch"]], co[:, C["type"]]
    bounds = np.flatnonzero(np.diff(fr * 2 + ch)) + 1
    for s, e in zip(np.r_[0, bounds], np.r_[bounds, len(co)]):
        c = ch[s]
        if ty[s] != 0:
            continue                                    # short frames: the next long one resets
        lines = co[s:e, C["line"]]
        inter = co[s:e, C["inter"]] == 1
        ex = co[s:e, C["e"]]
        mag = co[s:e, C["mag"]].astype(float)
        prev = state[c, lines] * 2.0 ** (kappa * ex / 4)   # rescaled, in the |y|^kappa domain
        if integer:
            prev = np.floor(prev * 16) / 16
        est = prev ** (1 / kappa)
        if mode == "max":
            est = np.maximum(est, co[s:e, C["pm"]])
        pm[s:e] = np.where(inter, np.floor(est + 0.5).astype(np.int64), -1)
        new = np.zeros(F)
        new[lines] = np.where(inter, alpha * prev + (1 - alpha) * mag ** kappa, mag ** kappa)
        if integer:
            new = np.minimum(np.floor(new * 16), 65535) / 16
        state[c] = new
    return ctx_from(co, pm)


def rule_two_sided(co):
    """Oracle: the next long frame's index at the same line (rescaled back) averaged with y_prev's
    prediction. Costs the decoder a frame of look-ahead (point 23)."""
    pm = co[:, C["pm"]].astype(np.int64)
    out = pm.copy()
    fr, ch, ty = co[:, C["frame"]], co[:, C["ch"]], co[:, C["type"]]
    for c in (0, 1):
        idx = np.flatnonzero((ch == c) & (ty == 0))
        key = fr[idx].astype(np.int64) * F + co[idx, C["line"]]
        order = np.argsort(key, kind="stable")
        idx = idx[order]
        frames = np.unique(fr[idx])
        # for each long frame f, the following long frame g (when g predicts from f)
        rows_by_frame = {f: idx[fr[idx] == f] for f in frames}
        for k in range(len(frames) - 1):
            f, g = frames[k], frames[k + 1]
            a, b = rows_by_frame[f], rows_by_frame[g]
            gi = b[co[b, C["inter"]] == 1]              # g predicted from f: same scale chain
            if not len(gi):
                continue
            look = np.full(F, -1.0)
            look[co[gi, C["line"]]] = co[gi, C["mag"]] * 2.0 ** (-co[gi, C["e"]] / 4)
            la = look[co[a, C["line"]]]
            have = la >= 0
            base = np.where(pm[a] >= 0, pm[a], -1)
            both = have & (base >= 0)
            only = have & (base < 0)
            out[a[both]] = np.floor((base[both] + la[both]) / 2 + 0.5).astype(np.int64)
            out[a[only]] = np.floor(la[only] + 0.5).astype(np.int64)
    return ctx_from(co, out)


# ---------------------------------------------------------------- costs
def train_tables(rule, paths, nctx=96):
    """Trained initial CDFs of a rule (nctx contexts x 16 symbols) from traces."""
    counts = np.zeros((nctx, 16))
    for p in paths:
        d = load(p)
        ctx = rule(d["co"])
        np.add.at(counts, (ctx, np.minimum(d["co"][:, C["mag"]], 15)), 1)
    return native.counts_to_cdf(counts)


def coef_bits(rule, paths, init, each=False, nctx=96):
    """Coefficient symbol bits of every item under a rule (adaptive, resets at key packets)."""
    out = []
    for p in paths:
        d = load(p)
        co = d["co"]
        ctx = rule(co)
        sym = np.minimum(co[:, C["mag"]], 15)
        res = coef_resets(co, d["keys"])
        if each:
            out.append(native.stream_cost_each(16, nctx, ctx, sym, res, init))
        else:
            out.append(native.stream_cost(16, nctx, ctx, sym, res, init))
    return out


def _rule_job(args):
    name, rule, train, dev, nctx = args
    init = train_tables(rule, train, nctx)
    return name, coef_bits(rule, dev, init, nctx=nctx)


def compare(rules, train, dev):
    """{name: per-item bits} for each (name, rule[, nctx]), each with its own trained tables."""
    jobs = [(r[0], r[1], train, dev, r[2] if len(r) > 2 else 96) for r in rules]
    with ProcessPoolExecutor(max_workers=min(len(rules), os.cpu_count())) as ex:
        return dict(ex.map(_rule_job, jobs))


def report(res, dev, base="current"):
    tot = sum(load(p)["total"] for p in dev)
    secs = sum(load(p)["seconds"] for p in dev)
    b0 = np.array(res[base])
    print(f"{len(dev)} items, {secs:.0f} s, all bits {tot / secs / 1000:.1f} kb/s, "
          f"coefficient symbols ({base}) {b0.sum() / secs / 1000:.1f} kb/s")
    print(f"{'rule':34s} {'coef kb/s':>9s} {'coef %':>8s} {'total %':>8s} {'items better':>13s}")
    for k, v in res.items():
        v = np.array(v)
        d = v.sum() - b0.sum()
        print(f"{k:34s} {v.sum() / secs / 1000:9.2f} {100 * d / b0.sum():+8.2f} {100 * d / tot:+8.2f} "
              f"{int((v < b0 - 1e-6).sum()):>6d}/{len(v)}")


# ---------------------------------------------------------------- commands
def cmd_trace(a):
    ensure(a.set, a.q)


def cmd_check(a):
    """The current rule must give the encoder's contexts, and the production tables its bits."""
    dev = ensure("dev")
    ok = True
    for p in dev:
        co = load(p)["co"]
        if not np.array_equal(rule_current(co), co[:, C["ctx"]]):
            ok = False
            print("MISMATCH", p)
    print("contexts reproduced exactly:", ok)
    init = E.load_init()["coef"]
    b_rule = sum(coef_bits(rule_current, dev, init))
    b_ema0 = sum(coef_bits(partial(rule_ema, alpha=0.0), dev, init))
    print(f"coef bits, current rule {b_rule:.0f}; EMA alpha=0 (y_prev in float) {b_ema0:.0f} "
          f"({100 * (b_ema0 / b_rule - 1):+.3f} %)")


def cmd_m8(a):
    train, dev = ensure("train"), ensure(a.set)
    rules = [("current", rule_current), ("ema a=0 (y_prev, float rescale)", partial(rule_ema, alpha=0.0))]
    for kappa in (1.0, 0.5):
        for alpha in (0.5, 0.7, 0.85):
            rules.append((f"ema a={alpha} k={kappa}", partial(rule_ema, alpha=alpha, kappa=kappa)))
    rules.append(("max(y_prev, ema a=0.5)", partial(rule_ema, alpha=0.5, kappa=1.0, mode="max")))
    report(compare(rules, train, dev), dev)


def cmd_m8int(a):
    train, dev = ensure("train"), ensure(a.set)
    rules = [("current", rule_current)]
    for alpha, kappa in a.points:
        rules.append((f"ema a={alpha} k={kappa} float", partial(rule_ema, alpha=alpha, kappa=kappa)))
        rules.append((f"ema a={alpha} k={kappa} Q4", partial(rule_ema, alpha=alpha, kappa=kappa, integer=True)))
    report(compare(rules, train, dev), dev)


def cmd_m2(a):
    dev = ensure(a.set)
    init = E.load_init()["coef"]
    secs = sum(load(p)["seconds"] for p in dev)
    tot = sum(load(p)["total"] for p in dev)
    rows = []
    for p, bits in zip(dev, coef_bits(rule_current, dev, init, each=True)):
        co = load(p)["co"]
        rows.append((co[:, C["type"]], co[:, C["inter"]], co[:, C["band"]], co[:, C["ac"]], bits))
    ty = np.concatenate([r[0] for r in rows])
    it = np.concatenate([r[1] for r in rows])
    band = np.concatenate([r[2] for r in rows])
    bits = np.concatenate([r[4] for r in rows])
    print(f"{len(dev)} items, {secs:.0f} s; coefficient symbols {bits.sum() / secs / 1000:.1f} kb/s "
          f"({100 * bits.sum() / tot:.1f} % of all bits)")
    print(f"{'frames':28s} {'coefs %':>8s} {'bits %':>8s} {'bit/coef':>9s}")
    for lab, sel in (("long, inter (valid = 1)", (ty == 0) & (it == 1)),
                     ("long, no inter (valid = 0)", (ty == 0) & (it == 0)),
                     ("short", ty == 1)):
        print(f"{lab:28s} {100 * sel.mean():8.1f} {100 * bits[sel].sum() / bits.sum():8.1f} "
              f"{bits[sel].mean():9.3f}")
    print("long frames by band group (bit/coef: inter / no inter):")
    for lo, hi in ((0, 8), (8, 14), (14, 18), (18, 22)):
        s1 = (ty == 0) & (it == 1) & (band >= lo) & (band < hi)
        s0 = (ty == 0) & (it == 0) & (band >= lo) & (band < hi)
        print(f"  bands {lo:2d}-{hi - 1:2d}: {bits[s1].mean():.3f} / {bits[s0].mean():.3f}  "
              f"(no-inter share of the group's bits {100 * bits[s0].sum() / max(bits[s0 | s1].sum(), 1):.1f} %)")


def cmd_m2b(a):
    """What the inter-frame context is worth: the same frames coded without it."""
    train, dev = ensure("train"), ensure(a.set)
    report(compare([("current", rule_current), ("no inter-frame context", rule_no_inter)], train, dev), dev)


POW4 = np.array([256, 304, 362, 431], np.int64)


def rescale(y, e):
    """The format's inter-frame rescaling of |y_prev| (core/enc.c, spec 5.3), before the cap."""
    v = y.astype(np.int64) * POW4[e & 3]
    sh = np.floor_divide(e, 4)
    up = np.left_shift(v, np.minimum(np.maximum(sh, 0), 8)) >> 8
    down = np.right_shift(v, np.maximum(8 - sh, 0))
    return np.where(sh >= 0, up, down)


def cmd_m5(a):
    """M5's stake: how much the next frame's coefficient bits depend on the current index, through
    the inter-frame context. For every coefficient predicted from the previous long frame, its
    symbol's cost (trained tables, static) with y_prev as coded and with y_prev +-1."""
    dev = ensure(a.set)
    init = E.load_init()["coef"].astype(np.int64)
    span = 32768 - 16 * 4
    st = (init * span >> 15) + np.arange(17) * 4
    st[:, 16] = 32768
    bits_tab = 15 - np.log2(np.diff(st, axis=1))           # [ctx, sym]
    n = changed = 0
    d_abs = d_gain = 0.0
    total_coef = 0.0
    for p in dev:
        co = load(p)["co"]
        sel = co[:, C["inter"]] == 1
        c = co[sel]
        sym = np.minimum(c[:, C["mag"]], 15)
        base = bits_tab[c[:, C["ctx"]], sym]
        total_coef += base.sum()
        alts = []
        for dy in (-1, 1):
            y = c[:, C["yprev"]] + dy
            ok = y >= 0
            pm = np.where(ok, rescale(np.maximum(y, 0), c[:, C["e"]]), c[:, C["pm"]])
            alts.append(bits_tab[ctx_from(c, pm), sym])
        alt = np.stack(alts)
        diff = alt - base
        n += len(c)
        changed += int((np.abs(diff) > 1e-9).any(axis=0).sum())
        d_abs += np.abs(diff).mean(axis=0).sum()
        d_gain += np.maximum(-diff.min(axis=0), 0).sum()
    print(f"{n} coefficients predicted from the previous long frame ({a.set})")
    print(f"  context changed by y_prev +-1: {100 * changed / n:.1f} % of them")
    print(f"  mean |bits change| per coefficient: {d_abs / n:.4f} bit")
    print(f"  upper bound of M5 (each next coefficient given its cheaper neighbour, free): "
          f"{100 * d_gain / total_coef:.2f} % of these coefficients' bits")


def static_bits(stream):
    """15 - log2(freq) of every (context, symbol) under a stream's trained initial table."""
    init = E.load_init()[stream].astype(np.int64)
    n = init.shape[1] - 1
    span = 32768 - n * 4
    st = (init * span >> 15) + np.arange(n + 1) * 4
    st[:, n] = 32768
    return 15 - np.log2(np.diff(st, axis=1))


def band_class(b):
    return np.where(b < 8, 0, np.where(b < 16, 1, 2))


ALPHAS = np.array([0, 16, 26, 31])


def energy_frame_bits(q, qprev, alpha, cls, tab):
    """Static bits of one channel's energy residuals (bands in order) with weight alpha."""
    left = qprev[0]
    bits, rprev = 0.0, 0
    for b in range(len(q)):
        pred = (alpha * qprev[b] + (32 - alpha) * left) // 32
        r = q[b] - pred
        ctx = cls[b] * 3 + min(abs(rprev), 2)
        bits += tab[ctx, r + 7] if -7 <= r <= 7 else tab[ctx, 15] + 2 * np.log2(abs(r) - 6) + 2
        left, rprev = q[b], r
    return bits


def cmd_m4(a):
    """M4's stakes, frame decisions. (a) The energy prediction weight alpha: chosen by a proxy
    (sum of log2(1 + |r|)); the oracle with the real (static) bits, per frame. alpha has no
    inter-frame effect (the stored energies do not depend on it), so a Viterbi cannot add to
    this. (b) M/S per band: how often a band switches between L/R and M/S from one long frame to
    the next, and what its energies and coefficients cost then (prediction across the switch)."""
    dev = ensure(a.set)
    etab = static_bits("energy")
    ctab = static_bits("coef")
    tot = sum(load(p)["total"] for p in dev)
    chosen = oracle = 0.0
    sw_e, st_e, sw_c, st_c = [], [], [], []
    n_sw = n_bands = 0
    for p in dev:
        d = load(p)
        en, co = d["en"], d["co"]
        g0 = en[en[:, EN["group"]] == 0]
        key = (g0[:, EN["frame"]].astype(np.int64) * 2 + g0[:, EN["ch"]])
        for k in np.unique(key):
            rows = g0[key == k]
            if rows[0, EN["key"]]:
                continue
            rows = rows[np.argsort(rows[:, EN["band"]])]
            q, qp = rows[:, EN["q"]], rows[:, EN["qprev"]]
            cls = band_class(rows[:, EN["band"]])
            al = rows[0, EN["alpha"]]
            b_all = [energy_frame_bits(q, qp, A, cls, etab) for A in ALPHAS]
            chosen += b_all[int(np.flatnonzero(ALPHAS == al)[0])]
            oracle += min(b_all)
        # (b) M/S switches, long frames
        lg = g0[g0[:, EN["type"]] == 0]
        ms = {}
        for row in lg:
            ms[(int(row[EN["frame"]]), int(row[EN["ch"]]), int(row[EN["band"]]))] = row
        cbits = ctab[co[:, C["ctx"]], np.minimum(co[:, C["mag"]], 15)]
        cinter = co[:, C["inter"]] == 1
        ckey = (co[:, C["frame"]].astype(np.int64) * 2 + co[:, C["ch"]]) * 32 + co[:, C["band"]]
        order = np.argsort(ckey, kind="stable")
        sk = ckey[order]
        for (f, c, b), row in ms.items():
            prev = ms.get((f - 1, c, b))
            if prev is None or row[EN["key"]]:
                continue
            n_bands += 1
            switched = row[EN["ms"]] != prev[EN["ms"]]
            n_sw += switched
            r = int(row[EN["r"]])
            eb = etab[int(row[EN["ctx"]]), r + 7] if -7 <= r <= 7 else etab[int(row[EN["ctx"]]), 15] + 6
            lo, hi = np.searchsorted(sk, [(f * 2 + c) * 32 + b, (f * 2 + c) * 32 + b + 1])
            idx = order[lo:hi]
            idx = idx[cinter[idx]]
            (sw_e if switched else st_e).append(eb)
            if len(idx):
                (sw_c if switched else st_c).append((cbits[idx].sum(), len(idx)))
    print(f"{len(dev)} {a.set} items, all bits {tot / 1000:.0f} kbit")
    print(f"(a) alpha: energy bits with the chosen weight {chosen / 1000:.0f} kbit, with the best weight per "
          f"frame (oracle, static costs) {oracle / 1000:.0f} kbit: {100 * (oracle - chosen) / chosen:+.2f} % of "
          f"those bits, {100 * (oracle - chosen) / tot:+.3f} % of all bits")
    cs = sum(b for b, _ in sw_c) / max(sum(n for _, n in sw_c), 1)
    cn = sum(b for b, _ in st_c) / max(sum(n for _, n in st_c), 1)
    print(f"(b) M/S: {100 * n_sw / max(n_bands, 1):.1f} % of band-to-band transitions between consecutive long "
          f"frames switch L/R <-> M/S ({n_sw} of {n_bands})")
    print(f"    energy residual bits per band: switched {np.mean(sw_e):.2f}, kept {np.mean(st_e):.2f}")
    print(f"    coefficient bit/coef (inter frames): switched {cs:.3f}, kept {cn:.3f}")
    extra_e = (np.mean(sw_e) - np.mean(st_e)) * n_sw
    extra_c = (cs - cn) * sum(n for _, n in sw_c)
    print(f"    excess of switched bands over kept ones: {(extra_e + extra_c) / 1000:.0f} kbit = "
          f"{100 * (extra_e + extra_c) / tot:.2f} % of all bits (upper bound of what keeping the "
          f"representation could save, before the stereo gain it gives up)")


def cmd_m5b(a):
    """M5, a realistic bound: flipping a coefficient to the neighbouring level of its union
    (|k| +- 2, index +- 1) costs distortion and its own bits, and changes the next frame's
    context at that line. Count the flips whose total (distortion + lambda x (own + next bits))
    is negative while it is not without the next frame's term (so that only M5's effect counts,
    not the trellis constraint this scalar view ignores), with the next symbol known (oracle
    look-ahead): an optimistic bound of what M5 could find."""
    dev = ensure(a.set)
    ctab = static_bits("coef")
    tot = sum(load(p)["total"] for p in dev)
    coef_total = 0.0
    saved = dist_added = 0.0
    n_cand = n_flip = 0
    for p in dev:
        co = load(p)["co"]
        bits = ctab[co[:, C["ctx"]], np.minimum(co[:, C["mag"]], 15)]
        coef_total += bits.sum()
        key = (co[:, C["frame"]].astype(np.int64) * 2 + co[:, C["ch"]]) * F + co[:, C["line"]]
        long_ = co[:, C["type"]] == 0
        nxt_key = key + 2 * F                    # same channel and line, next frame
        order = np.argsort(key)
        pos = np.searchsorted(key[order], nxt_key)
        pos = np.minimum(pos, len(order) - 1)
        j = order[pos]
        has = long_ & (key[j] == nxt_key) & (co[j, C["inter"]] == 1)
        i = np.flatnonzero(has)
        j = j[has]
        n_cand += len(i)
        k = np.abs(co[i, C["level"]]).astype(np.int64)
        x = np.abs(co[i, C["x256"]]) / 256.0
        lam = co[i, C["lam1e4"]] / 1e4
        mag = co[i, C["mag"]].astype(np.int64)
        best_gain = np.zeros(len(i))
        best_bits = np.zeros(len(i))
        best_dist = np.zeros(len(i))
        for dm in (-1, 1):
            k2 = k + 2 * dm
            m2 = mag + dm
            ok = (k2 >= 0) & (m2 >= 0) & (m2 < 15) & (mag < 15)
            d_dist = (x - k2) ** 2 - (x - k) ** 2
            d_own = ctab[co[i, C["ctx"]], np.clip(m2, 0, 15)] - ctab[co[i, C["ctx"]], np.minimum(mag, 15)]
            pm2 = rescale(np.maximum(m2, 0), co[j, C["e"]])
            sub = co[j].copy()
            ctx2 = ctx_from(sub, pm2)
            d_next = ctab[ctx2, np.minimum(co[j, C["mag"]], 15)] - bits[j]
            g = d_dist + lam * (d_own + d_next)
            alone = d_dist + lam * d_own            # without the next frame's term
            better = ok & (alone >= 0) & (g < best_gain)   # profitable only through M5's term
            best_gain = np.where(better, g, best_gain)
            best_bits = np.where(better, d_own + d_next, best_bits)
            best_dist = np.where(better, d_dist, best_dist)
        flip = best_gain < 0
        n_flip += int(flip.sum())
        saved += -best_bits[flip].sum()
        dist_added += best_dist[flip].sum()
    print(f"{n_cand} coefficients whose line is predicted in the next frame ({a.set})")
    print(f"  profitable flips (optimistic): {100 * n_flip / max(n_cand, 1):.2f} % of them")
    print(f"  bits saved {saved / 1000:.0f} kbit = {100 * saved / coef_total:.2f} % of coefficient bits, "
          f"{100 * saved / tot:.2f} % of all bits; distortion change {dist_added:+.0f} (D/2)^2 units")


def cmd_p4(a):
    """Point 4: contexts that know the trellis state (parity: even states' union holds zero and
    index |k|/2, odd ones no zero and (|k|-1)/2)."""
    train, dev = ensure("train"), ensure(a.set)
    chain = bool(EXTRA.get("tcq_chain"))
    co = load(dev[0])["co"]
    sb = state_before(co, chain)
    print(f"settings {EXTRA or 'production'}; odd-state share {100 * (sb & 1).mean():.1f} %")
    rules = [("current", rule_current), ("parity of the state (192)", partial(rule_parity, chain=chain), 192)]
    if not chain:
        rules.append(("full state (768)", rule_state8, 768))
    report(compare(rules, train, dev), dev)


def _ilog2(v):
    return np.floor(np.log2(np.maximum(v, 1))).astype(np.int64)


def _alpha_bits(paths, t, tables=None):
    """Bits of the coefficient magnitudes with an alphabet of t + 1 symbols (t: the escape) and
    Exp-Golomb escapes (order k in the cesc stream, context ac, then k raw bits), adaptive models,
    resets at key packets. tables: trained (coef, cesc) CDFs, else trained here (returned)."""
    if tables is None:
        cc, ce = np.zeros((96, t + 1)), np.zeros((16, 16))
        for p in paths:
            co = load(p)["co"]
            mag = co[:, C["mag"]].astype(np.int64)
            np.add.at(cc, (co[:, C["ctx"]], np.minimum(mag, t)), 1)
            e = mag >= t
            np.add.at(ce, (co[e, C["ac"]], np.minimum(_ilog2(mag[e] - t + 1), 15)), 1)
        return native.counts_to_cdf(cc), native.counts_to_cdf(ce)
    out = []
    for p in paths:
        d = load(p)
        co = d["co"]
        mag = co[:, C["mag"]].astype(np.int64)
        res = coef_resets(co, d["keys"])
        b = native.stream_cost(t + 1, 96, co[:, C["ctx"]], np.minimum(mag, t), res, tables[0])
        e = mag >= t
        k = np.minimum(_ilog2(mag[e] - t + 1), 15)
        eres = np.searchsorted(np.flatnonzero(e), np.flatnonzero(np.isin(np.arange(len(co)), np.r_[res])))
        b += native.stream_cost(16, 16, co[e, C["ac"]], k, eres, tables[1]) + k.sum()
        out.append(b)
    return out


def cmd_alpha8(a):
    """Point 13: coefficient alphabet of 8 symbols (escape at 7) instead of 16 (escape at 15):
    half the CDF entries to search and update."""
    train, dev = ensure("train"), ensure(a.set)
    tot = sum(load(p)["total"] for p in dev)
    secs = sum(load(p)["seconds"] for p in dev)
    base = None
    print(f"{len(dev)} {a.set} items, all bits {tot / secs / 1000:.1f} kb/s")
    for t in (15, 7, 3):
        b = np.array(_alpha_bits(dev, t, _alpha_bits(train, t)))
        if base is None:
            base = b
        n_esc = sum(int((load(p)["co"][:, C["mag"]] >= t).sum()) for p in dev)
        n = sum(len(load(p)["co"]) for p in dev)
        print(f"  alphabet {t + 1:2d}: coefficient bits (with escapes) {b.sum() / secs / 1000:.2f} kb/s, "
              f"{100 * (b.sum() - base.sum()) / tot:+.2f} % of all bits; escapes {100 * n_esc / n:.2f} % of symbols")


def _entropy(sym, ctx):
    """Static conditional entropy (bits, total) of sym given ctx."""
    tot = 0.0
    for c in np.unique(ctx):
        s = sym[ctx == c]
        _, n = np.unique(s, return_counts=True)
        p = n / n.sum()
        tot += -(n * np.log2(p)).sum()
    return tot


def cmd_m7(a):
    train, dev = ensure("train"), ensure(a.set)
    # (b) two-sided coefficient context (oracle look-ahead)
    report(compare([("current", rule_current), ("two-sided (n-1, n+1)", rule_two_sided)], train, dev), dev)
    # (a) energies of frames 1, 2 of each 4-frame packet interpolated from frames 0 and 3
    n_groups = 0
    cur_r, new_r, ctxs = [], [], []
    for p in dev:
        en = load(p)["en"]
        en = en[(en[:, EN["type"]] == 0) & (en[:, EN["group"]] == 0)]
        q = {}
        for row in en:
            q[(row[EN["frame"]], row[EN["ch"]], row[EN["band"]])] = row
        frames = np.unique(en[:, EN["frame"]])
        fs = set(frames.tolist())
        for f0 in frames[frames % 4 == 0]:
            if not all(f0 + k in fs for k in range(4)):
                continue
            n_groups += 1
            for c in (0, 1):
                for b in range(22):
                    rows = [q.get((f0 + k, c, b)) for k in range(4)]
                    if any(r is None for r in rows):
                        continue
                    qs = [int(r[EN["q"]]) for r in rows]
                    for k in (1, 2):
                        cur_r.append(int(rows[k][EN["r"]]))
                        new_r.append(qs[k] - int(np.floor((qs[0] * (3 - k) + qs[3] * k) / 3 + 0.5)))
                        ctxs.append(int(rows[k][EN["ctx"]]) // 3)
                    # frame 3 predicted from frame 0 instead of frame 2
                    r3 = rows[3]                # same left term, previous frame 0 for 2
                    pred_new = int(r3[EN["pred"]]) + int(np.floor(int(r3[EN["alpha"]]) * (qs[0] - qs[2]) / 32))
                    cur_r.append(int(r3[EN["r"]]))
                    new_r.append(qs[3] - pred_new)
                    ctxs.append(100 + int(r3[EN["ctx"]]) // 3)
    cur_r, new_r, ctxs = map(np.array, (cur_r, new_r, ctxs))
    h_cur = _entropy(np.clip(cur_r, -8, 8), ctxs)
    h_new = _entropy(np.clip(new_r, -8, 8), ctxs)
    tot = sum(load(p)["total"] for p in dev)
    print(f"\nenergies, {n_groups} packets of 4 long frames: residual entropy of frames 1-3 "
          f"{h_cur / len(cur_r):.3f} -> {h_new / len(new_r):.3f} bit/band "
          f"({100 * (h_new / h_cur - 1):+.1f} %, {100 * (h_new - h_cur) / tot:+.2f} % of all bits)")


def _m1_job(args):
    wav, kf = args
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    data, nbytes = native.c_encode(x, E.Params(keyframe=kf))
    return nbytes * 8 / (len(x) / fs)


def cmd_m1(a):
    items = corpus.items(a.set)
    kfs = (20, 40, 80, 160)
    with ProcessPoolExecutor() as ex:
        rates = {kf: list(ex.map(_m1_job, [(w, kf) for _, w in items])) for kf in kfs}
    base = np.mean(rates[40])
    print(f"{len(items)} {a.set} items, q -7 (default); key packet every N frames (23.2 ms each)")
    print(f"{'N':>4s} {'interval':>9s} {'kb/s':>8s} {'vs 40':>8s}")
    for kf in kfs:
        r = np.mean(rates[kf])
        print(f"{kf:4d} {kf * F / 44100:8.2f}s {r / 1000:8.2f} {100 * (r / base - 1):+8.2f} %")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["trace", "check", "m8", "m8int", "m2", "m2b", "m7", "m1", "m5", "m5b", "m4", "p4", "alpha8"])
    ap.add_argument("--set", default="dev")
    ap.add_argument("--q", type=float, default=-7.0)
    ap.add_argument("--params", default="", help="encoder settings over the production's, e.g. "
                    "tcq_chain=1,tcq_states=32 (traces cached apart)")
    ap.add_argument("--points", type=lambda s: [tuple(map(float, p.split(":"))) for p in s.split(",")],
                    default=[(0.7, 1.0), (0.85, 1.0)], help="m8int: alpha:kappa,...")
    a = ap.parse_args()
    for kv in filter(None, a.params.split(",")):
        k, v = kv.split("=")
        EXTRA[k] = int(v)
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
