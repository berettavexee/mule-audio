"""Writes packets.h (MULEHead + audio packets of an excerpt, C encoder) for the QEMU benchmark,
and prints the PC fixed-point decoder's output hash to compare with the target's.
Usage: python bench/qemu/make_packets.py ITEM Q_DB SECONDS"""
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "eval")]
from mule import native, oggfile, params as E   # noqa: E402


def main(item="abba", q="-12", seconds="10"):
    x, fs = sf.read(os.path.join(ROOT, "data", "corpus", item + ".wav"), always_2d=True)
    x = x[: int(float(seconds) * fs)]
    data, nbytes = native.c_encode(x, E.Params(q_db=float(q)))
    pk = [p for p, _ in oggfile.packets(data)]
    head, audio = pk[0], pk[2:]
    offs = np.cumsum([0] + [len(p) for p in audio])
    blob = b"".join(audio)

    def carr(name, b, t="uint8_t"):
        return f"static const {t} {name}[{len(b)}] = {{" + ",".join(str(v) for v in b) + "};\n"
    with open(os.path.join(HERE, "packets.h"), "w") as f:
        f.write(f"/* {item}, q {q}, {seconds} s: {nbytes * 8 / (len(x) / fs) / 1000:.1f} kb/s */\n")
        f.write(f"#define MULE_NPACKETS {len(audio)}u\n")
        f.write(carr("mule_head", head))
        f.write(carr("mule_packets", blob))
        f.write(carr("mule_offsets", [int(v) for v in offs], "uint32_t"))
    d = native.Decoder(head)
    h = 2166136261
    for p in audio:
        for b in d.packet(p).tobytes():
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    print(f"{item} q{q} {seconds}s: {len(audio)} packets, {nbytes * 8 / (len(x) / fs) / 1000:.1f} kb/s, PC hash {h}")


if __name__ == "__main__":
    main(*sys.argv[1:])
