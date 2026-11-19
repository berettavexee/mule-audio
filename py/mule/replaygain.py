"""ReplayGain 2.0: loudness by ITU-R BS.1770-4 (K-weighting, 400 ms blocks with 75 % overlap,
absolute gate -70 LUFS, relative gate -10 LU), gain to the -18 LUFS reference, sample peak.

    m = Meter(44100); m.add(x)       # x: (L, channels) float, full scale 1.0, any number of calls
    m.loudness()                     # LUFS of everything added (-inf if all of it is gated out)
    album = Meter.merge([m1, m2])    # an album: the blocks of all its tracks, gated together
    gain(m.loudness()), m.peak       # dB to -18 LUFS, and the sample peak (1.0 = full scale)
"""
import math

import numpy as np
from scipy.signal import lfilter

REFERENCE_LUFS = -18.0


def _k_filter(fs):
    """The K-weighting's two biquads at any rate, from their analog prototypes (the published
    48 kHz coefficients are these at fs = 48000)"""
    # stage 1: high shelf, +4 dB above ~1.7 kHz
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / fs)
    vh = 10 ** (g / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    b1 = [(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
    a1 = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    # stage 2: high pass (RLB), ~38 Hz
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / fs)
    a0 = 1 + k / q + k * k
    b2 = [1, -2, 1]
    a2 = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    return (b1, a1), (b2, a2)


class Meter:
    """ITU-R BS.1770-4 loudness meter of one track: K-filtered mean squares per 100 ms step, fed
    in parts (add); blocks of 400 ms, gated (loudness); the sample peak."""
    def __init__(self, fs):
        self.fs = fs
        self.filters = _k_filter(fs)
        self.state = None               # filter states, per channel (the signal may come in parts)
        self.tail = None                # samples not yet in a complete 100 ms step
        self.steps = []                 # mean square of each 100 ms step, summed over channels
        self.peak = 0.0

    def add(self, x):
        """Feeds samples x (n, channels) or (n,), continuing the filters' state."""
        x = np.asarray(x, np.float64)
        if x.ndim == 1:
            x = x[:, None]
        if len(x) == 0:
            return
        self.peak = max(self.peak, float(np.abs(x).max()))
        (b1, a1), (b2, a2) = self.filters
        if self.state is None:
            self.state = [(np.zeros(2), np.zeros(2)) for _ in range(x.shape[1])]
        y = np.empty_like(x)
        for c in range(x.shape[1]):
            z1, z2 = self.state[c]
            v, z1 = lfilter(b1, a1, x[:, c], zi=z1)
            y[:, c], z2 = lfilter(b2, a2, v, zi=z2)
            self.state[c] = (z1, z2)
        if self.tail is not None:
            y = np.concatenate([self.tail, y])
        step = int(round(self.fs * 0.1))
        n = len(y) // step
        if n:
            # channel weights: 1 for left, right and centre (the surround ones are not used here)
            ms = (y[:n * step] ** 2).reshape(n, step, -1).mean(axis=1).sum(axis=1)
            self.steps.extend(ms.tolist())
        self.tail = y[n * step:]

    def blocks(self):
        """Mean squares of the 400 ms blocks (4 steps, a new one every 100 ms)"""
        s = np.asarray(self.steps)
        if len(s) < 4:
            return np.zeros(0)
        return (s[:-3] + s[1:-2] + s[2:-1] + s[3:]) / 4

    @staticmethod
    def gated(z):
        """BS.1770-4 loudness of block mean squares z: absolute then relative gate"""
        lk = lambda v: -0.691 + 10 * np.log10(v)          # noqa: E731
        z = z[z > 0]
        z = z[lk(z) > -70]
        if not len(z):
            return -math.inf
        z = z[lk(z) > lk(z.mean()) - 10]
        return float(lk(z.mean())) if len(z) else -math.inf

    def loudness(self):
        """The track's gated loudness (LUFS)."""
        return self.gated(self.blocks())

    @classmethod
    def merge(cls, meters):
        """An album's loudness and peak: its tracks' blocks gated together"""
        z = np.concatenate([m.blocks() for m in meters]) if meters else np.zeros(0)
        return cls.gated(z), max((m.peak for m in meters), default=0.0)


def gain(lufs):
    """ReplayGain 2.0 gain (dB) for a loudness: to -18 LUFS; 0 for silence"""
    return 0.0 if not math.isfinite(lufs) else REFERENCE_LUFS - lufs


def tags(track_lufs, track_peak, album=None):
    """The REPLAYGAIN_* comments (album: (lufs, peak) or None)"""
    out = {"REPLAYGAIN_TRACK_GAIN": f"{gain(track_lufs):+.2f} dB",
           "REPLAYGAIN_TRACK_PEAK": f"{track_peak:.6f}"}
    if album is not None:
        out["REPLAYGAIN_ALBUM_GAIN"] = f"{gain(album[0]):+.2f} dB"
        out["REPLAYGAIN_ALBUM_PEAK"] = f"{album[1]:.6f}"
    return out
