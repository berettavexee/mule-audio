"""The reference decoder (core/dec.c, integers only): its output on frozen test vectors (exact, so
any change of a decoded sample shows), packet handling (seek, pre-roll), its state's size, and the
external FFT hook (HIFIACC's contract)."""
import hashlib
import json
import os

import numpy as np
import pytest

from mule import native, oggfile, params as E

HERE = os.path.dirname(os.path.abspath(__file__))
VECTORS = os.path.join(HERE, "vectors")       # format v3 (the encoder's output)
VECTORS_V2 = os.path.join(VECTORS, "v2")       # format v2, frozen: the decoder still reads it
FS = 44100


def signals():
    """Synthetic test signals, 3 s stereo (deterministic)."""
    rng = np.random.default_rng(7)
    n = FS * 3
    t = np.arange(n) / FS
    clicks = np.zeros((n, 2))
    clicks[::7000] = 0.9
    sweep = 0.5 * np.sin(2 * np.pi * (50 + 8000 * t / 3) * t)
    return {
        "silence": np.zeros((n, 2)),
        "noise": 0.3 * rng.standard_normal((n, 2)),
        "clicks": clicks,
        "sine_lr": np.stack([0.5 * np.sin(2 * np.pi * 440 * t), 0.4 * np.sin(2 * np.pi * 3000 * t)], 1),
        "sweep_mono": np.stack([sweep, sweep], 1),
        "clipping": np.clip(2 * rng.standard_normal((n, 2)), -1, 1),
        "short": 0.2 * rng.standard_normal((3000, 2)),
    }


def decode(data):
    """The whole stream's int16 output (pre-skip included) and its packets."""
    pk = [p for p, _ in oggfile.packets(data)]
    d = native.Decoder(pk[0])
    return np.concatenate([d.packet(p) for p in pk[2:]]), pk


def make_vectors():
    """Writes tests/vectors (run by hand only when the format changes; tests/vectors/v2 stays as
    it is): each signal encoded at two qualities, and the SHA-256 of its decoded int16 output."""
    os.makedirs(VECTORS, exist_ok=True)
    ref = {}
    for name, x in signals().items():
        for q in (-12.0, 0.0):
            data, _ = native.c_encode(x, E.Params(q_db=q))
            f = f"{name}_q{q:+g}.mule"
            open(os.path.join(VECTORS, f), "wb").write(data)
            ref[f] = hashlib.sha256(decode(data)[0].tobytes()).hexdigest()
    json.dump(ref, open(os.path.join(VECTORS, "sha256.json"), "w"), indent=1, sort_keys=True)


def _vectors():
    out = []
    for d in (VECTORS, VECTORS_V2):
        path = os.path.join(d, "sha256.json")
        if os.path.exists(path):
            out += [(os.path.relpath(os.path.join(d, k), VECTORS), v) for k, v in sorted(json.load(open(path)).items())]
    return out


@pytest.mark.parametrize("name,digest", _vectors())
def test_vectors_decode_exactly(name, digest):
    """The decoder's output on the frozen vectors (v3, and v2's) is unchanged, sample for sample"""
    y, _ = decode(open(os.path.join(VECTORS, name), "rb").read())
    assert hashlib.sha256(y.tobytes()).hexdigest() == digest


def test_seek_matches_continuous():
    """After a seek: two packets dropped, then from the key packet's second frame on, the same
    samples as continuous decoding"""
    x = signals()["sweep_mono"] + 0.05 * signals()["noise"]
    data, _ = native.c_encode(x, E.Params(q_db=-9))
    full, pk = decode(data)
    audio = pk[2:]
    nfr = [(p[0] >> 1 & 7) + 1 for p in audio]
    starts = np.cumsum([0] + nfr)
    key = [i for i, p in enumerate(audio) if p[0] & 1][1]
    d = native.Decoder(pk[0])
    d.seek()
    out = [d.packet(p) for p in audio[key - 2:]]
    assert len(out[0]) == 0 and len(out[1]) == 0
    seeked = np.concatenate(out)
    f0 = (starts[key] + 1) * 1024
    assert np.array_equal(seeked, full[f0:f0 + len(seeked)])


def test_rejects_unknown_header():
    """Another version, another table of initial CDFs, a trellis size or a flag it does not know,
    or a v3 header cut to v2's length, is refused"""
    data, _ = native.c_encode(signals()["sine_lr"], E.Params(q_db=-9))
    h = bytearray(oggfile.packets(data)[0][0])
    assert h[8] == 3 and len(h) == 22 and h[20] == 6 and h[21] == 3
    native.Decoder(bytes(h))
    for pos, val in ((8, 4), (8, 1), (19, h[19] ^ 1), (20, 2), (20, 7), (21, 4)):
        bad = bytearray(h)
        bad[pos] = val
        with pytest.raises(ValueError):
            native.Decoder(bytes(bad))
    with pytest.raises(ValueError):
        native.Decoder(bytes(h[:20]))


def test_state_size():
    """The decoder's state fits the 50 KiB the firmware's codec image gives it"""
    assert native.lib.mule_dec_size() < 50 * 1024


def test_external_fft_hook():
    """The hook's contract (as HIFIACC): bit-reversed input, natural-order unscaled forward FFT.
    An exact (double, rounded) FFT through it stays within 1 LSB of the software FFT."""
    calls = []

    @native.ffi.callback("int(int32_t *, int32_t *, int)")
    def fft(re, im, bits):
        n = 1 << bits
        r = np.frombuffer(native.ffi.buffer(re, 4 * n), np.int32)
        i = np.frombuffer(native.ffi.buffer(im, 4 * n), np.int32)
        rev = np.array([int(f"{k:0{bits}b}"[::-1], 2) for k in range(n)])
        z = np.empty(n, complex)
        z[rev] = r + 1j * i                     # undo the bit-reversed order
        f = np.fft.fft(z)
        r[:] = np.round(f.real).astype(np.int32)
        i[:] = np.round(f.imag).astype(np.int32)
        calls.append(bits)
        return 1

    x = signals()["sine_lr"] + 0.05 * signals()["noise"]
    data, _ = native.c_encode(x, E.Params(q_db=-9))
    soft, _ = decode(data)
    native.lib.mule_dec_set_fft(fft)
    try:
        hooked, _ = decode(data)
    finally:
        native.lib.mule_dec_set_fft(native.ffi.NULL)
    assert calls and set(calls) <= {6, 9}
    assert np.abs(hooked.astype(np.int64) - soft).max() <= 1


if __name__ == "__main__":
    make_vectors()
