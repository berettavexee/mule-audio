"""PEAQ basic model outputs (MOVs) of Opus at 128 kb/s and of MULE at the same rate on each item
(frame_diag.mule_at), whole items: which of PEAQ's variables separate the two codecs
(eval/results/D-LOG.md). Also the share of MULE's short frames.

    python eval/mov_diag.py item1,item2,...       (items of the test set)

The transient-detector experiment of D-LOG.md (TR) needed a scratch build of the encoder with a
settable detector threshold; it is not part of the codec."""
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus        # noqa: E402
import frame_diag    # noqa: E402
import metrics       # noqa: E402
import refcodecs     # noqa: E402

MOVS = ["BandwidthRefB", "BandwidthTestB", "Total NMRB", "WinModDiff1B", "ADBB", "EHSB",
        "AvgModDiff1B", "AvgModDiff2B", "RmsNoiseLoudB", "MFPDB", "RelDistFramesB"]


def movs(ref, deg, fs):
    """PEAQ basic's ODG and MOVs of deg against ref (metrics.peaq_movs; "TotalNMRB" until
    20/11/2026, which GstPEAQ prints "Total NMRB": that column was empty in D-LOG.md)."""
    m = metrics.peaq_movs(ref, deg, fs)
    return dict(odg=m["odg"], **{k: m.get(k, float("nan")) for k in MOVS})


def job(item):
    """One item: rows (item, codec, MOVs...) for Opus and MULE, and MULE's short-frame share."""
    name, wav = item
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    with tempfile.TemporaryDirectory() as work:
        odec, _enc, okbps = refcodecs.run("opus_128", wav, work)
        mdec, _q, _kbps, ftype = frame_diag.mule_at(x, wav, okbps, work)
        ref0 = metrics.subsonic(x, fs)
        res = {"short": {"odg": float((ftype.values > 0).mean())}}
        for tag, path in (("opus", odec), ("mule", mdec)):
            y, fs2 = metrics.load(path)
            if fs2 != fs:
                import soxr
                y = soxr.resample(y, fs2, fs, quality="VHQ")
            r, y, _lag = metrics.align(ref0, metrics.subsonic(y, fs))
            res[tag] = movs(r, y, fs)
    return [dict(item=name, codec=t, **v) for t, v in res.items()]


def main():
    keep = sys.argv[1].split(",")
    items = [it for it in corpus.items("test") if it[0] in keep]
    with ProcessPoolExecutor(len(items)) as ex:
        rows = [r for rs in ex.map(job, items) for r in rs]
    d = pd.DataFrame(rows).set_index(["item", "codec"])
    print(d.round(3).T.to_string())


if __name__ == "__main__":
    main()
