"""Writes packets.h (MULEHead + audio packets of an excerpt, C encoder) for the QEMU benchmark,
and prints the PC fixed-point decoder's output hash to compare with the target's.
Usage: python bench/qemu/make_packets.py ITEM Q_DB SECONDS
       python bench/qemu/make_packets.py FILE.mule      (a MULE file as it is: the test vectors)
MULE_PARAMS (environment) sets encoder settings over the production's, e.g.
"tcq_states=32"."""
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "eval")]
from mule import native, oggfile, params as E   # noqa: E402


def main(item="abba", q="-12", seconds="10"):
    """Writes bench/qemu/packets.h for an excerpt and prints the PC decoder's hash."""
    if item.endswith(".mule"):
        data = open(item, "rb").read()
        pk = [p for p, _ in oggfile.packets(data)]
        nbytes, fs, x = sum(len(p) for p in pk[2:]), 44100, np.zeros(1024 * max(1, len(pk) - 2))
    else:
        x, fs = sf.read(os.path.join(ROOT, "data", "corpus", item + ".wav"), always_2d=True)
        x = x[: int(float(seconds) * fs)]
        extra = {k: int(v) for k, v in (kv.split("=") for kv in filter(None, os.environ.get("MULE_PARAMS", "").split(",")))}
        data, nbytes = native.c_encode(x, E.Params(q_db=float(q), **extra))
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
