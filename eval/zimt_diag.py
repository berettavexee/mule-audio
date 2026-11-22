"""Where an item loses Zimtohrli: its passages and its time-frequency error, MULE against a
witness codec (Opus) at the same rate.

For each item: MULE at --rate kb/s on that item (q by bisection, tonal_lines.mule_q) and each
witness configuration, aligned on the original, 48 kHz. Per configuration:

    windows   Zimtohrli distance of windows of --win s (hop win / 2), mean of the channels
    regions   Zimtohrli's own similarity, cell by cell, on its spectrogram (pyohrli analyze: 128
              channels from 18 Hz to 20 kHz, steps of 11.6 ms; NSIM of zimtohrli.cc, windows of 8
              steps x 5 channels, without its time warping): per region the loss 1 - intensity x
              structure (x 1e4, Zimtohrli's units: the regions' mean over all 128 channels is the
              distance), and its parts 1 - intensity (local level) and 1 - structure (local
              correlation: texture); the whole item, and its worst windows (the 3 worst of MULE)
    context   (MULE) in each window, the share of short frames and of noise-filled bands from
              2.8 kHz up (the production encoder's trace, first coded channel)

    python eval/zimt_diag.py --items a,b [--set test] [--rate 128] [--witness opus_128] [--win 2]
                             [--png dir]   (prints; with --png, the worst window's spectrograms
                             and error maps as images in dir; encodes in temporary directories)
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402

REGIONS = [(0, 250), (250, 1000), (1000, 2800), (2800, 6000), (6000, 10000), (10000, 15000), (15000, 21000)]


def freqs():
    import re
    src = open(os.path.join(os.path.dirname(HERE), "third_party", "zimtohrli", "cpp", "zimt", "zimtohrli.h")).read()
    body = re.search(r"kFreq\[130\]\s*=\s*\{([^}]*)\}", src).group(1)
    return np.array([float(v) for v in body.replace("\n", " ").split(",") if v.strip()])[1:129]


def window_mean(x, sw=8, cw=5):
    """zimtohrli.cc WindowMean: the mean over the sw steps and cw channels ending at each cell."""
    c = np.cumsum(np.cumsum(np.pad(x, ((1, 0), (1, 0))), axis=0), axis=1)
    i, j = np.arange(1, x.shape[0] + 1), np.arange(1, x.shape[1] + 1)
    i0, j0 = np.maximum(i - sw, 0), np.maximum(j - cw, 0)
    s = c[i][:, j] - c[i0][:, j] - c[i][:, j0] + c[i0][:, j0]
    return s / (sw * cw)


def nsim_map(a, b):
    """(intensity, structure) per cell of spectrograms a, b (steps, channels), zimtohrli.cc's
    NSIM (constants and clamping included)."""
    ma, mb = window_mean(a), window_mean(b)
    va, vb = window_mean((a - ma) ** 2), window_mean((b - mb) ** 2)
    cv = window_mean((a - ma) * (b - mb))
    C1, C3, C8, P0, P1 = 26.426389124321354, 1.9522719384622791, 0.6325126087671703, 1.0500187278772866, 0.25808223975919764
    inten = ((2 * np.sqrt(np.maximum(ma * mb, 0)) + C1) / (np.abs(ma) + np.abs(mb) + C1)) ** P0
    st = (cv + C3) / (np.sqrt(va) * np.sqrt(vb) + C3)
    return inten, np.maximum(st, C8) ** P1


def spec(z, x48):
    return np.stack([z.analyze(np.ascontiguousarray(np.clip(x48[:, c], -1, 1), np.float32))
                     for c in range(x48.shape[1])])          # (ch, steps, 128)


def trace_context(wav, q):
    import soundfile as sf
    from mule import native, params as E
    x, _ = sf.read(wav, dtype="float64", always_2d=True)
    tr = native.c_trace(x, E.Params(q_db=q))[3]
    b = pd.DataFrame(tr[tr[:, 0] == 2], columns=native.TRACE_FIELDS["band"])
    b = b[b.ch == b.ch.min()]
    qmin = b.q.min()
    per = b.groupby("frame").agg(short=("type", "max"))
    hi = b[(b.band >= 12) & (b.type == 0)]
    per["noise"] = hi.groupby("frame").apply(lambda g: ((g.a == 0) & (g.q > qmin)).mean(), include_groups=False)
    return per


def job(args):
    import soxr
    import pyohrli
    from tonal_lines import mule_q
    name, wav, rate, witnesses, win, png = args
    q = mule_q("mule_-7", wav, rate)
    cfgs = [f"mule_{q:g}"] + witnesses
    z = pyohrli.Pyohrli()
    F = freqs()
    out = {"item": name, "cfgs": cfgs, "win": {}, "reg": {}, "kb": {}}
    S0 = None
    decs = {}
    for cfg in cfgs:
        r, y, fs, kb, _lag = refcodecs.run_aligned(cfg, wav)
        n = min(len(r), len(y))
        r48 = soxr.resample(r[:n], fs, 48000, quality="VHQ")      # as metrics.zimtohrli
        y48 = soxr.resample(y[:n], fs, 48000, quality="VHQ")
        out["kb"][cfg] = kb
        W, H = int(win * 48000), int(win * 48000 / 2)
        out["win"][cfg] = np.array([np.mean([z.distance(np.clip(r48[s:s + W, c], -1, 1).astype(np.float32),
                                                        np.clip(y48[s:s + W, c], -1, 1).astype(np.float32))
                                             for c in range(r48.shape[1])])
                                    for s in range(0, len(r48) - W + 1, H)])
        if S0 is None:
            S0 = spec(z, r48)
            out["steps_per_s"] = S0.shape[1] / (len(r48) / 48000)
        Sd = spec(z, y48)
        m = min(S0.shape[1], Sd.shape[1])
        it, st = zip(*[nsim_map(S0[c, :m], Sd[c, :m]) for c in range(S0.shape[0])])
        decs[cfg] = (np.stack(it), np.stack(st))
    worst = np.argsort(out["win"][cfgs[0]])[::-1][:3]
    sps = out["steps_per_s"]
    for cfg, (IT, ST) in decs.items():
        rows = []
        for scope, sel in [("item", slice(None))] + [(f"w{int(w)}", slice(int(w * win / 2 * sps), int((w * win / 2 + win) * sps)))
                                                     for w in worst]:
            it, st = IT[:, sel], ST[:, sel]
            for lo, hi in REGIONS:
                ch = (F >= lo) & (F < hi)
                share = ch.mean() * 1e4             # the region's part of the 128 channels' mean
                rows.append(dict(scope=scope, region=f"{lo / 1000:g}-{hi / 1000:g}k",
                                 loss=(1 - it[:, :, ch] * st[:, :, ch]).mean() * share,
                                 inten=(1 - it[:, :, ch]).mean() * share, struct=(1 - st[:, :, ch]).mean() * share))
        out["reg"][cfg] = pd.DataFrame(rows)
    ctx = trace_context(wav, q)
    out["ctx"] = []
    for w in worst:
        t0, t1 = w * win / 2, w * win / 2 + win
        fr = ctx[(ctx.index * 1024 / 44100 >= t0) & (ctx.index * 1024 / 44100 < t1)]
        out["ctx"].append((int(w), t0, fr.short.mean(), fr.noise.mean()))
    out["ctx_item"] = (ctx.short.mean(), ctx.noise.mean())
    if png:
        draw(png, name, out, decs, S0, F, worst[0], win, sps)
    return out


def draw(png, name, out, decs, S0, F, w, win, sps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(png, exist_ok=True)
    a, b = int(w * win / 2 * sps), int((w * win / 2 + win) * sps)
    cfgs = list(decs)
    fig, ax = plt.subplots(1 + len(cfgs), 1, figsize=(10, 3.2 * (1 + len(cfgs))), sharex=True)
    ext = [w * win / 2, w * win / 2 + win, 0, 127]
    ax[0].imshow(S0[:, a:b].mean(axis=0).T, origin="lower", aspect="auto", extent=ext, cmap="magma")
    ax[0].set_title(f"{name}: original (Zimtohrli spectrogram)")
    for i, cfg in enumerate(cfgs):
        IT, ST = decs[cfg]
        L = (1 - IT[:, a:b] * ST[:, a:b]).mean(axis=0) * 1e4
        im = ax[i + 1].imshow(L.T, origin="lower", aspect="auto", extent=ext, cmap="viridis", vmin=0, vmax=40)
        zw = out["win"][cfg][w]
        ax[i + 1].set_title(f"{cfg} ({out['kb'][cfg]:.0f} kb/s): local loss 1 - NSIM, x1e4 (window Zimtohrli {zw * 1e4:.2f})")
        fig.colorbar(im, ax=ax[i + 1], fraction=0.02)
    ticks = [0, 32, 64, 80, 96, 112, 127]
    for x in ax:
        x.set_yticks(ticks)
        x.set_yticklabels([f"{F[t]:.0f}" for t in ticks])
        x.set_ylabel("Hz")
    ax[-1].set_xlabel("s")
    fig.tight_layout()
    fig.savefig(os.path.join(png, f"{name}.png"), dpi=80)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", required=True)
    ap.add_argument("--set", default="test")
    ap.add_argument("--rate", type=float, default=128.0)
    ap.add_argument("--witness", default="opus_128")
    ap.add_argument("--win", type=float, default=2.0)
    ap.add_argument("--png")
    ap.add_argument("-j", type=int, default=4)
    a = ap.parse_args()
    items = corpus.items(a.set, a.items)
    wit = [w for w in a.witness.split(",") if w]
    with ProcessPoolExecutor(a.j) as ex:
        res = list(ex.map(job, [(n, w, a.rate, wit, a.win, a.png) for n, w in items]))
    pd.set_option("display.width", 200)
    for o in res:
        m = o["cfgs"][0]
        print(f"\n=== {o['item']}  " + "  ".join(f"{c} {o['kb'][c]:.1f} kb/s, mean of windows {o['win'][c].mean() * 1e4:.2f}"
                                               for c in o["cfgs"]))
        print(f"  short frames {o['ctx_item'][0]:.1%}, noise-filled bands from 2.8 kHz {o['ctx_item'][1]:.1%}")
        for w, t0, sh, nz in o["ctx"]:
            zs = "  ".join(f"{c} {o['win'][c][w] * 1e4:.2f}" for c in o["cfgs"])
            print(f"  worst window {t0:.0f}-{t0 + a.win:.0f} s: {zs} | short {sh:.0%}, noise-filled {nz:.0%}")
        t = pd.concat({c: o["reg"][c].set_index(["scope", "region"]) for c in o["cfgs"]}, axis=1)
        print(t.round(2).to_string())


if __name__ == "__main__":
    main()
