"""Axis 2, step 0: PEAQ basic's 11 MOVs for codec configurations on a corpus set (CSV), then the
MULE / Opus gap at equal rate attributed to each MOV (the basic network evaluated with one MOV of
MULE replaced by Opus's). Usage:
  python eval/peaq_movs.py run --set dev --tag TAG CONFIG ...
  python eval/peaq_movs.py gap TAG.csv [--a mule --b opus --rate 128]
Needs the local peaq with PEAQ_MOVS (third_party/gstpeaq/src/peaq.c)."""
import argparse
import os
import re
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # eval/ (this script: eval/archive/)
sys.path[:0] = [HERE]
import corpus                                    # noqa: E402
import metrics as Mx                             # noqa: E402
import refcodecs                                 # noqa: E402

MOVS = ["BandwidthRefB", "BandwidthTestB", "Total NMRB", "WinModDiff1B", "ADBB", "EHSB",
        "AvgModDiff1B", "AvgModDiff2B", "RmsNoiseLoudB", "MFPDB", "RelDistFramesB"]
AMIN = [393.916656, 361.965332, -24.045116, 1.110661, -0.206623, 0.074318, 1.113683, 0.950345,
        0.029985, 0.000101, 0.]
AMAX = [921, 881.131226, 16.212030, 107.137772, 2.886017, 13.933351, 63.257874, 1145.018555,
        14.819740, 1., 1.]
WX = np.array([[-0.502657, 0.436333, 1.219602], [4.307481, 3.246017, 1.123743],
               [4.984241, -2.211189, -0.192096], [0.051056, -1.762424, 4.331315],
               [2.321580, 1.789971, -0.754560], [-5.303901, -3.452257, -10.814982],
               [2.730991, -6.111805, 1.519223], [0.624950, -1.331523, -5.955151],
               [3.102889, 0.871260, -5.922878], [-1.051468, -0.939882, -0.142913],
               [-1.804679, -0.503610, -0.620456]])
WXB = np.array([-2.518254, 0.654841, -2.207228])
WY = np.array([-3.817048, 4.107138, 4.629582])
WYB = -0.307594


def odg_of(m, clamp=False):              # GstPEAQ: CLAMP_MOVS 0
    x = (np.asarray(m, float) - AMIN) / (np.subtract(AMAX, AMIN))
    if clamp:
        x = np.clip(x, 0, 1)
    h = WXB + x @ WX
    di = WYB + np.sum(WY / (1 + np.exp(-h)))
    return -3.98 + (0.22 + 3.98) / (1 + np.exp(-di))


def job(args):
    cfg, name, wav = args
    with tempfile.TemporaryDirectory() as work:
        dec, _enc, kbps = refcodecs.run(cfg, wav, work)
        ref, fs = Mx.load(wav)
        deg, fs2 = Mx.load(dec)
        if fs2 != fs:
            import soxr
            deg = soxr.resample(deg, fs2, fs, quality="VHQ")
        ref, deg = Mx.subsonic(ref, fs), Mx.subsonic(deg, fs)
        ref, deg, _ = Mx.align(ref, deg)
        r, g = os.path.join(work, "r.wav"), os.path.join(work, "g.wav")
        Mx._to48k(ref, fs, r)
        Mx._to48k(deg, fs, g)
        env = dict(os.environ, PEAQ_MOVS="1")
        peaq = Mx._PEAQ_DEFAULT
        plug = os.path.join(os.path.dirname(os.path.dirname(peaq)), "lib", "gstreamer-1.0")
        env["GST_PLUGIN_PATH"] = plug
        txt = Mx._run_retry([peaq, r, g], env=env)
    row = {"config": cfg, "item": name, "kbps": kbps}
    for k in MOVS:
        m = re.findall(rf"^\s*{re.escape(k)}:\s*([-\d.einf]+)", txt, re.M)
        row[k] = float(m[-1]) if m else np.nan
    m = re.findall(r"Objective Difference Grade:\s*([-\d.]+)", txt)
    row["odg"] = float(m[-1]) if m else np.nan
    return row


def run(a):
    tasks = [(c, n, w) for n, w in corpus.items(a.set) for c in a.configs]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(job, tasks))
    out = os.path.join(HERE, "results", a.tag + ".csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(len(rows), "rows ->", out)


def at_rate(df, fam, item, rate, cols):
    g = df[(df.fam == fam) & (df.item == item)].sort_values("kbps")
    return np.array([np.interp(rate, g.kbps, g[c]) for c in cols])


def gap(a):
    df = pd.read_csv(a.csv)
    df["fam"] = df.config.str.rsplit("_", n=1).str[0]
    items = sorted(set(df[df.fam == a.a].item) & set(df[df.fam == a.b].item))
    A = np.array([at_rate(df, a.a, i, a.rate, MOVS + ["odg"]) for i in items])
    B = np.array([at_rate(df, a.b, i, a.rate, MOVS + ["odg"]) for i in items])
    oa = np.array([odg_of(r[:11]) for r in A])
    ob = np.array([odg_of(r[:11]) for r in B])
    print(f"{len(items)} items at {a.rate:g} kb/s (per item interpolation)")
    print(f"ODG measured {a.a} {A[:, 11].mean():+.3f}  {a.b} {B[:, 11].mean():+.3f};"
          f" network on interpolated MOVs: {oa.mean():+.3f} / {ob.mean():+.3f}")
    print(f"{'MOV':16s} {a.a:>9s} {a.b:>9s}   ODG gain if {a.a} had {a.b}'s value")
    for k, name in enumerate(MOVS):
        sw = A[:, :11].copy()
        sw[:, k] = B[:, k]
        d = np.array([odg_of(r) for r in sw]) - oa
        print(f"{name:16s} {A[:, k].mean():9.3f} {B[:, k].mean():9.3f}   {d.mean():+.4f}")
    worst = pd.Series(B[:, 11] - A[:, 11], index=items).sort_values(ascending=False)
    print("items where", a.b, "leads most (ODG):")
    print(worst.head(12).round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("configs", nargs="+")
    r.add_argument("--set", default="dev")
    r.add_argument("--tag", required=True)
    g = sub.add_parser("gap")
    g.add_argument("csv")
    g.add_argument("--a", default="mule")
    g.add_argument("--b", default="opus")
    g.add_argument("--rate", type=float, default=128)
    a = ap.parse_args()
    run(a) if a.cmd == "run" else gap(a)


if __name__ == "__main__":
    main()
