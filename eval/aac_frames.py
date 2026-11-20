"""What an AAC-LC encoder decides, frame by frame, read from its bitstream: block type (long,
start, eight short, stop) and the grouping of short windows, the bandwidth (max_sfb), M/S per
band, the first channel's codebook per band (zeroed, PNS noise, intensity stereo, coded) and
each frame's size. Compared with MULE's own decisions (encoder trace) on the same excerpts.

    python eval/aac_frames.py aapl_q63,aac_128 --items a,b [--set test] [--mule -7]
                              (prints; encodes in temporary directories)

The parser stops before the spectral data (no Huffman decoding): the second channel of a pair
and anything after it in the frame are not read. Stereo AAC-LC only (one CPE per frame, FIL/DSE
skipped). ISO/IEC 14496-3, 4.4.2 (raw_data_block, ics_info, section_data); 44.1 kHz tables.
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "py")]
import corpus  # noqa: E402
import refcodecs  # noqa: E402

SWB_LONG_44 = [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72, 80, 88, 96, 108, 120, 132, 144,
               160, 176, 196, 216, 240, 264, 292, 320, 352, 384, 416, 448, 480, 512, 544, 576, 608, 640,
               672, 704, 736, 768, 800, 832, 864, 896, 928, 1024]
SWB_SHORT_44 = [0, 4, 8, 12, 16, 20, 28, 36, 44, 56, 68, 80, 96, 112, 128]
WS = {0: "long", 1: "start", 2: "short", 3: "stop"}
ZERO_HCB, NOISE_HCB, INTENSITY_HCB2, INTENSITY_HCB = 0, 13, 14, 15


class Bits:
    def __init__(self, data):
        self.d, self.p = data, 0

    def u(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.p >> 3] >> (7 - (self.p & 7))) & 1)
            self.p += 1
        return v

    def align(self):
        self.p = (self.p + 7) & ~7


def ics_info(b):
    b.u(1)                                      # ics_reserved_bit
    ws = b.u(2)
    b.u(1)                                      # window_shape
    if ws == 2:
        max_sfb, grouping = b.u(4), b.u(7)
        groups = [1]
        for k in range(7):                      # a 0 bit starts a new group
            if grouping >> (6 - k) & 1:
                groups[-1] += 1
            else:
                groups.append(1)
        return dict(ws=ws, max_sfb=max_sfb, groups=groups)
    max_sfb = b.u(6)
    if b.u(1):                                  # predictor_data_present: not in AAC-LC
        raise ValueError("predictor data (AAC Main): not supported")
    return dict(ws=ws, max_sfb=max_sfb, groups=[1])


def section_data(b, info):
    bits, esc = (3, 7) if info["ws"] == 2 else (5, 31)
    cbs = []                                    # per group, the codebook of each band < max_sfb
    for _g in info["groups"]:
        k, row = 0, []
        while k < info["max_sfb"]:
            cb = b.u(4)
            n = 0
            while True:
                inc = b.u(bits)
                n += inc
                if inc != esc:
                    break
            row += [cb] * n
            k += n
        cbs.append(row[:info["max_sfb"]])
    return cbs


def frame(payload):
    """One raw_data_block: the CPE's common ics_info, M/S mask, first channel's section data."""
    b = Bits(payload)
    while True:
        el = b.u(3)
        if el == 6:                             # FIL
            n = b.u(4)
            if n == 15:
                n += b.u(8) - 1
            b.p += 8 * n
        elif el == 4:                           # DSE
            b.u(4)
            align = b.u(1)
            n = b.u(8)
            if n == 255:
                n += b.u(8)
            if align:
                b.align()
            b.p += 8 * n
        elif el == 1:                           # CPE
            break
        else:
            raise ValueError(f"element {el}: only stereo AAC-LC (CPE) is read")
    b.u(4)                                      # element_instance_tag
    common = b.u(1)
    info, ms = None, None
    if common:
        info = ics_info(b)
        mp = b.u(2)
        if mp == 1:
            ms = [b.u(1) for _g in info["groups"] for _s in range(info["max_sfb"])]
        else:
            ms = [mp == 2] * (len(info["groups"]) * info["max_sfb"])
    b.u(8)                                      # global_gain of the first channel
    if not common:
        info = ics_info(b)
    cbs = section_data(b, info)
    return info, ms, cbs


def analyse_aac(cfg, wav):
    with tempfile.TemporaryDirectory() as work:
        _dec, enc, _kbps = refcodecs.run(cfg, wav, work)
        adts = enc if enc.endswith(".aac") else os.path.join(work, "x.aac")
        if adts != enc:                         # MP4 (qaac): the same packets, in ADTS
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", enc, "-c:a", "copy",
                            "-f", "adts", adts], check=True)
        rows = []
        for k, (blocks, payload) in enumerate(refcodecs.adts_frames(adts)):
            if blocks != 1:
                raise ValueError("several raw blocks per ADTS frame: not supported")
            nbytes = len(payload)
            info, ms, cbs = frame(payload)
            flat = [c for row in cbs for c in row]
            n = max(len(flat), 1)
            top = (SWB_SHORT_44 if info["ws"] == 2 else SWB_LONG_44)[info["max_sfb"]]
            scale = 1024 if info["ws"] != 2 else 128
            rows.append(dict(frame=k, ws=WS[info["ws"]], groups=len(info["groups"]), bytes=nbytes,
                             bw_khz=top / scale * 22.05, ms=float(np.mean(ms)) if ms else 0.0,
                             zero=flat.count(ZERO_HCB) / n, pns=flat.count(NOISE_HCB) / n,
                             intensity=(flat.count(INTENSITY_HCB) + flat.count(INTENSITY_HCB2)) / n))
    return pd.DataFrame(rows)


def analyse_mule(wav, q):
    from mule import native, params as E
    x, _fs = sf.read(wav, dtype="float64", always_2d=True)
    m, _v, fstart, tr = native.c_trace(x, E.Params(q_db=q))
    d = pd.DataFrame(tr[tr[:, 0] == 2], columns=native.TRACE_FIELDS["band"])
    f = d[(d.band == 0) & (d.ch == 0)].groupby("frame").agg(type=("type", "first"), groups=("group", "nunique"))
    zero = d.a.eq(0).groupby(d.frame).mean()
    return f.assign(zero=zero)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs")
    ap.add_argument("--items", required=True)
    ap.add_argument("--set", default="test")
    ap.add_argument("--mule", type=float, default=-7.0, help="MULE's quality for the comparison")
    a = ap.parse_args()
    items = corpus.items(a.set, a.items)
    for name, wav in items:
        print(f"\n{name}")
        print(f"   {'':12s} {'short':>6s} {'switches':>8s} {'groups':>6s} {'bandwidth kHz':>15s} "
              f"{'M/S':>5s} {'zeroed':>7s} {'PNS':>5s} {'intens.':>7s} {'bytes: short/long':>18s} {'max/mean':>8s}")
        for cfg in a.configs.split(","):
            d = analyse_aac(cfg, wav)
            sh = d.ws == "short"
            switches = (d.ws != d.ws.shift()).sum() - 1
            lg = d[~sh]
            bw = f"{lg.bw_khz.median():5.1f} ({lg.bw_khz.min():4.1f}-{lg.bw_khz.max():4.1f})"
            ratio = d.bytes[sh].mean() / d.bytes[~sh].mean() if sh.any() else float("nan")
            print(f"   {cfg:12s} {sh.mean() * 100:5.1f}% {switches:8d} "
                  f"{d.groups[sh].mean() if sh.any() else float('nan'):6.1f} {bw:>15s} "
                  f"{d.ms.mean() * 100:4.0f}% {d.zero.mean() * 100:6.1f}% {d.pns.mean() * 100:4.1f}% "
                  f"{d.intensity.mean() * 100:6.1f}% {ratio:18.2f} {d.bytes.max() / d.bytes.mean():8.2f}")
        mu = analyse_mule(wav, a.mule)
        sh = mu.type == 1
        print(f"   {'MULE ' + format(a.mule, 'g'):12s} {sh.mean() * 100:5.1f}% "
              f"{(mu.type != mu.type.shift()).sum() - 1:8d} {mu.groups[sh].mean() if sh.any() else float('nan'):6.1f} "
              f"{'20.0 (fixed)':>15s} {'':>5s} {mu.zero.mean() * 100:6.1f}%  (zeroed = noise-filled)")


if __name__ == "__main__":
    main()
