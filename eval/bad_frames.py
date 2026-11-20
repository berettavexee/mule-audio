"""PEAQ's "disturbed frames" (RelDistFramesB: a frame whose worst band has noise more than 1.5 dB
above PEAQ's mask), frame by frame: which items, which frequencies, how far above the mask.
Needs the local GstPEAQ patch that prints each frame's worst band (PEAQ_FRAMES=1, src/movs.c).

    python eval/bad_frames.py mule_-7,opus_128,aapl_q63 [--set test] [--items a,b] [-j N]
                              [--dump frames.csv]   (prints; encodes in temporary directories)

A PEAQ frame is 2048 samples at 48 kHz with a hop of 1024 (21.3 ms); frame i starts at
i * 1024 / 48000 s of the aligned signals.
"""
import argparse
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import metrics  # noqa: E402
import refcodecs  # noqa: E402

LIMIT_DB = 10 * np.log10(1.41253754462275)       # 1.5 dB, PEAQ's threshold
REGIONS = [(0, 500), (500, 2000), (2000, 6000), (6000, 12000), (12000, 24000)]


def frames(ref, deg, fs):
    """Per frame and channel: worst band NMR (dB), its centre frequency, mean NMR (dB)."""
    with tempfile.TemporaryDirectory() as d:
        r, g = os.path.join(d, "r.wav"), os.path.join(d, "g.wav")
        metrics._to48k(ref, fs, r)
        metrics._to48k(deg, fs, g)
        peaq = metrics._PEAQ_DEFAULT
        env = dict(os.environ, PEAQ_FRAMES="1",
                   GST_PLUGIN_PATH=os.path.join(os.path.dirname(os.path.dirname(peaq)), "lib", "gstreamer-1.0"))
        txt = metrics._run_retry([peaq, r, g], env=env)
    rows, count = [], {}
    for line in txt.splitlines():
        if line.startswith("NMRF "):
            _, c, vmax, f, nmr = line.split()
            c = int(c)
            i = count.get(c, 0)
            count[c] = i + 1
            rows.append((i, c, float(vmax), float(f), float(nmr)))
    return rows


def job(args):
    cfg, name, wav = args
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    with tempfile.TemporaryDirectory() as work:
        dec, _enc, kbps = refcodecs.run(cfg, wav, work)
        y, fs2 = metrics.load(dec)
        if fs2 != fs:
            import soxr
            y = soxr.resample(y, fs2, fs, quality="VHQ")
        ref0 = metrics.subsonic(x, fs)
        r, y, lag = metrics.align(ref0, metrics.subsonic(y, fs))
        return [dict(config=cfg, item=name, kbps=kbps, lag=lag, frame=i, ch=c, worst_db=v, freq=f, nmr_db=n)
                for i, c, v, f, n in frames(r, y, fs)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--set", default="test")
    ap.add_argument("--items")
    ap.add_argument("--dump")
    ap.add_argument("-j", type=int, default=min(os.cpu_count(), 8))
    a = ap.parse_args()
    configs = a.configs.split(",")
    items = corpus.items(a.set)
    if a.items:
        keep = set(a.items.split(","))
        items = [it for it in items if it[0] in keep]
    with ProcessPoolExecutor(a.j) as ex:
        d = pd.DataFrame([r for rows in ex.map(job, [(c, n, w) for c in configs for n, w in items]) for r in rows])
    if a.dump:
        d.to_csv(a.dump, index=False)
    # counted per frame and channel, as PEAQ averages the channels' 0/1 (it also skips the
    # first frames and the silent ones: the shares here are close to RelDistFramesB, not equal)
    f, bad = d, d[d.worst_db > LIMIT_DB]
    print(f"{len(items)} items of '{a.set}'; disturbed frame: worst band noise > mask + 1.5 dB (PEAQ's FFT ear model)")
    print("\nshare of disturbed frames, and how far above the mask they go (median / 90th percentile of the worst band)")
    for c in configs:
        fc, bc = f[f.config == c], bad[bad.config == c]
        print(f"   {c:10s} {len(bc) / len(fc) * 100:5.2f} %   {len(bc):5d} frame-channels   "
              f"{bc.worst_db.median():+5.1f} / {bc.worst_db.quantile(0.9):+5.1f} dB")
    print("\nwhere the worst band of the disturbed frames lies (share of the codec's disturbed frames)")
    print("   " + " ".join(f"{lo:>5d}-{hi:<5d}" for lo, hi in REGIONS))
    for c in configs:
        bc = bad[bad.config == c]
        sh = [((bc.freq >= lo) & (bc.freq < hi)).mean() * 100 for lo, hi in REGIONS]
        print(f"   {c:10s} " + " ".join(f"{s:10.0f}%" for s in sh))
    print("\nper item: disturbed frames (%)")
    t = (bad.groupby(["item", "config"]).size() / f.groupby(["item", "config"]).size() * 100).unstack().fillna(0)
    t = t.reindex(columns=configs).fillna(0)
    print(t.sort_values(configs[0], ascending=False).round(1).to_string())


if __name__ == "__main__":
    main()
