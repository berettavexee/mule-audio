"""Seeds for tools/fuzz/fuzz_dec.c: real streams in the harness's format ([header length][MULEHead]
then [op][length LE16][packet]...): the test vectors (v3 and v2), and short excerpts encoded with
every header variant the decoder accepts (trellis of 8 to 64 states, chained or not, 8 or 16
coefficient symbols) at low, mid and high rates, so that every path starts from a valid stream.

    python tools/fuzz/mkseeds.py OUT_DIR"""
import glob
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "py"))
from mule import native, oggfile, params as E   # noqa: E402


def harness_input(data, ops=None):
    """An Ogg MULE file as one fuzz input; ops[i] the op byte of audio packet i (default 0)."""
    pk = [p for p, _ in oggfile.packets(data)]
    head, audio = pk[0], pk[2:]
    out = bytes([len(head)]) + head
    for i, p in enumerate(audio):
        op = ops[i] if ops else 0
        out += bytes([op]) + struct.pack("<H", min(len(p), 65535)) + p[:65535]
    return out


def signals(fs=44100):
    """Short synthetic excerpts: noise, a sweep, clicks (short blocks), a tone, silence."""
    rng = np.random.default_rng(3)
    n = fs // 2
    t = np.arange(n) / fs
    clicks = np.zeros((n, 2))
    clicks[::5000] = 0.9
    sweep = 0.5 * np.sin(2 * np.pi * (50 + 15000 * t) * t)
    return {"noise": 0.3 * rng.standard_normal((n, 2)), "clicks": clicks + 0.01 * rng.standard_normal((n, 2)),
            "sweep": np.stack([sweep, -sweep], 1), "tone": np.stack([0.5 * np.sin(2 * np.pi * 440 * t)] * 2, 1),
            "silence": np.zeros((n, 2))}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    k = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "tests", "vectors", "**", "*.mule"), recursive=True)):
        open(os.path.join(out, f"seed-{k:03d}.bin"), "wb").write(harness_input(open(f, "rb").read()))
        k += 1
    variants = [dict(), dict(tcq_states=8, tcq_chain=0, coef_a8=0), dict(tcq_states=16, coef_a8=0),
                dict(tcq_states=32, tcq_chain=0), dict(tcq_states=8, coef_a8=1)]
    for x in signals().values():
        for v in variants:
            for q in (-20.0, -7.0, 6.0):
                data, _ = native.c_encode(x, E.Params(q_db=q, **v))
                ops = [1 if i == 3 else 0 for i in range(64)]       # a seek in the middle
                open(os.path.join(out, f"seed-{k:03d}.bin"), "wb").write(harness_input(data, ops))
                k += 1
    print(f"{k} seeds in {out}")


if __name__ == "__main__":
    main()
