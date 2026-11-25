"""The C encoder's settings as seen from Python (native.c_params maps them onto
mule_enc_params, core/mule_enc.h, which documents each), the model streams of the format, and
the trained initial CDFs (py/mule/init_cdf.npz, the source of core/init_cdf.h)."""
import os
from dataclasses import dataclass

import numpy as np


@dataclass
class Params:
    """Defaults: the production encoder (eval/results/E-LOG.md, E2-LOG.md)."""
    q_db: float = -7.0          # noise target relative to the masking threshold (quality)
    keyframe: int = 40          # frames between key packets (multiple of 4; 40 = 0.93 s)
    groups: str = "adaptive"    # short frames: "8" (one energy per block), "adaptive", "1"
    group_db: float = 12.0      # adaptive grouping: a new group past this energy jump
    stereo: str = "auto"        # "lr", "ms", "auto" (per band, perceptual entropy)
    ath_db: float = 0.0         # threshold in quiet shift (dB)
    tonal: str = "flatness"     # psy tonality: "flatness" or "all"
    low_db: float = 15.0        # extra masking offset in bands 0-7 (dB)
    mid_db: float = 6.1         # extra masking offset in bands 8 .. mid_hi-1 (dB)
    mid_hi: int = 17
    ton_scale: float = 20.0     # flatness (dB below noise's) of a fully tonal band
    tcap_db: float = 15.3       # cap of the tonal masking offset 14.5 + z (None: none)
    alloc_mode: str = "auto"    # allocation reference: "auto" (cheaper of band or frame), "freq"
    alloc_hyst: int = 1         # keep the previous frame's a_b within +-alloc_hyst
    fft_tonal: bool = True      # tonality from a Hann FFT power spectrum's flatness
    fft_noise_db: float = 3.4   # flatness reference of noise in that spectrum
    rd_lambda: float = 2.42     # RD choice of a-1/a/a+1 per band (0: off)
    tcq_lam: float = 0.3        # TCQ Viterbi rate weight without tcq_rd
    tcq_rd: int = 1             # Viterbi rate from the tracked models
    tcq_rdl: float = 0.48       # its rate weight relative to rd_lambda's
    fine_p: float = 8.0         # low-band line-resolution masks, power mean exponent (0: off)
    fine_w: int = 1             # lines per sub-band
    fine_nb: int = 12           # below this band only
    pre_db: float = 9.7         # pre-echo control, mask rise per long frame (0: off)
    nf_bias: int = 1            # noise-filled bands' energy lower (1.5 dB steps; production 1)
    tcq_states: int = 64        # trellis states (8, 16, 32, 64), format v3
    tcq_chain: int = 1          # trellis state across the bands, one Viterbi (0: comparisons only)
    coef_a8: int = 1            # 8-symbol coefficient alphabet (0: 16 symbols, comparisons only)
    tcq_rd_states: int = 8      # encoder speed: trellis of the RD choice's estimates (0: tcq_states)
    tg: int = 1                 # zero-bit tonal bands: 1 guard (production, v4), 2 muted, 0 off
    tg_db: float = 6.0          # guard: strongest line within this of the mask target (dB)
    tg_a: int = 1               # guard: the allocation given
    tg_band: int = 0            # guard: from this band up only
    spread_mode: int = 3        # band masks' spreading: 0 Schroeder, 1 Terhardt, 2 min, 3 Schroeder then Terhardt
    sp_dz: float = 2.0          # spread_mode 3: Schroeder up to this many Bark above the masker
    dyn_a: float = 0.0          # Opus-like: masks lowered by dyn_a x a band's excess over the follower
    nf_off_db: float = -6.0     # v4: the zeros' noise level, the measured one plus this (dB)
    eg: int = 1                 # envelope guard (production): a modulated noise-filled band from eg_band up coded at eg_a
    eg_band: int = 16
    eg_db: float = 5.0          # its energy's peak over its mean across the 8 short blocks (dB)
    eg_a: int = 1
    tr_hf: int = 1              # second transient detector pass, high-passed at tr_hf_fc (production 22/11/2026)
    tr_hf_fc: float = 8000.0
    tr_hf_db: float = 6.0       # 8.5 before the v5
    tr_hf_ton: float = 10.0     # tonal veto of the highs pass's frames (dB, 0 off; v5)
    tr_decay_db: float = 1.0    # the detector's memory decay per block of 128 (22/11/2026; 3 before)
    nf_top: int = 22            # from this band up, uncoded bands silent instead of noise (22: none)
    group_mode: int = 1         # adaptive grouping: 0 window energy, 1 also per frequency region
    tr_db: float = 8.5          # transient detector threshold (dB; 10 before 20/11/2026)
    short_db: float = 0.0       # noise target offset in short frames (dB; < 0: more bits)
    tg_ton: float = 5.0         # a lone line: peak this many dB above a noise's (2 ln n x mean)
    ath_rel_db: float = 0.0     # relative ATH: lowered by ath_ref_db - passage level, at most this (0: off)
    ath_ref_db: float = -14.0   # its reference level (dBFS)
    ath_rel_rel: float = 0.5    # its level follower's fall (dB per frame)
    bf_rel_db: float = 0.0      # band floor: bands within this of the strongest (0: off) ...
    bf_snr_db: float = 0.0      # ... get a mask at most this under their power (dB)
    rc_k: float = 0.0           # rate leveler: q_db moved by rc_k x rc_slope x log2(R / R(q)) (0: off)
    rc_tau: float = 200.0       # its rate average (frames)
    rc_max: float = 9.0         # its largest move of q_db (dB)
    rc_r0: float = 76.4         # R(q) = rc_r0 2^(-q / rc_slope) kb/s
    rc_slope: float = 9.21
    opa_mode: int = 0           # Opus' band allocation: 1 replaces the masks, 2 its tilt, 3 the mix (0: off)
    opa_kbps: float = 0.0       # its target rate (0: R(q_db))
    opa_eta: float = 0.8        # share of half the rate for a channel's coefficients
    opa_k: float = 1.0          # mode 2: the tilt's scale
    opa_alpha: float = 0.5      # mode 3: the masks' share (log)
    hf_db: float = 0.0          # high-band tilt: masks raised up to this in the last band (0: off)
    hf_band: int = 16           # its first band
    zh_db: float = 0.0          # on/off hysteresis: margin to turn a noise-filled band on, dB (0: off)
    zh_keep_db: float = 0.0     # ... and to keep a coded band on below its target, dB (0: off)
    band_db: tuple = ()         # per-band mask offsets, dB (measurements: eval/slopes.py)



# --bitrate's reallocation between bands (25/11/2026, eval/results/B9-REPORT.md 4-10): per-band mask
# offsets in dB (- = more bits), found by the slopes of our model against Zimtohrli (eval/slopes.py)
# on its six regions below 13 kHz (MULE bands 0-2, 2-6, 6-12, 12-16, 16-19, 19-20) at 96, 128 and
# 160 kb/s, interpolated in log2 of the rate (held outside); 13-20 kHz (bands 20-21) +6 dB up to
# 96 kb/s, falling linearly to 0 at REALLOC_HF_END. Better than without on Zimtohrli and NMR at every
# rate of 80-192 kb/s on the 300-track campaign, PEAQ within a few hundredths, ABX at 96 kb/s 46/96.
REALLOC_RATES = (96, 128, 160)
REALLOC_REGIONS = (2, 4, 6, 4, 3, 1)
REALLOC_DB = {96: (-3.35, 1.72, -0.82, -0.69, -1.27, -1.81),
              128: (-3.82, 3.40, -0.65, -0.56, -0.52, -1.24),
              160: (-3.66, 0.08, -1.88, -1.36, -1.45, -1.77)}
REALLOC_HF_DB = 6.0
REALLOC_HF_END = 128.0


def realloc_below(rate):
    """The offsets of bands 0-19 found at one of REALLOC_RATES."""
    return sum(((d,) * n for d, n in zip(REALLOC_DB[rate], REALLOC_REGIONS)), ())


def realloc_db(kbps, hf_end=REALLOC_HF_END):
    """--bitrate's per-band mask offsets (22 bands, dB) at kbps."""
    pts = REALLOC_RATES
    low = np.array([realloc_below(r) for r in pts])
    x = np.clip(np.log2(kbps), np.log2(pts[0]), np.log2(pts[-1]))
    below = [float(np.interp(x, np.log2(pts), low[:, b])) for b in range(low.shape[1])]
    hf = REALLOC_HF_DB * float(np.clip((hf_end - kbps) / (hf_end - pts[0]), 0.0, 1.0))
    return tuple(round(v, 3) for v in below) + (hf, hf)


def for_bitrate(kbps, **kw):
    """The settings for a target rate in kb/s, as opusenc's --bitrate: q_db from the rate curve
    R(q) = rc_r0 2^(-q / rc_slope) (the 300-track campaign, 23/11/2026), and the rate leveler
    (rc_k 2, up to 15 dB) that draws each track's rate toward it (core/mule_enc.h), the Opus
    band allocation mixed with the masks (opa_mode 3, 75 % MULE: better on every judge at 96, 128
    and 160 kb/s on the 300-track campaign, 24/11/2026), and the reallocation between bands
    realloc_db(kbps) (25/11/2026); kw: other settings (band_db=() for none)."""
    import math
    d = Params()
    q = -d.rc_slope * math.log2(kbps / d.rc_r0)
    return Params(**{"q_db": q, "rc_k": 2.0, "rc_max": 15.0, "opa_mode": 3, "opa_alpha": 0.75,
                     "band_db": realloc_db(kbps), **kw})

# the model streams in the decoder's order: (name, symbols, contexts) (core/models.c)
STREAMS = [("btype", 2, 1), ("alpha", 4, 1), ("stereo", 2, 3), ("energy", 16, 9),
           ("alloc", 16, 6), ("amode", 2, 1), ("cesc", 16, 16), ("coef", 16, 96),
           ("eaesc", 16, 1), ("nflev", 8, 1)]
OFF = {}                        # first model of each stream
_o = 0
for _n, _s, _c in STREAMS:
    OFF[_n] = _o
    _o += _c
NMODELS = _o

INIT_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "init_cdf.npz")
_INIT_CACHE = {}


def load_init(spec="default"):
    """The trained initial CDFs ({stream: (contexts, symbols + 1) array}) of a .npz file
    ("default": the format's tables), or None."""
    path = INIT_DEFAULT if spec == "default" else spec
    if not path or not os.path.exists(path):
        return None
    if path not in _INIT_CACHE:
        with np.load(path) as z:
            _INIT_CACHE[path] = {k: z[k] for k in z.files}
    return _INIT_CACHE[path]
