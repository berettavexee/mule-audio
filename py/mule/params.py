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
    low_db: float = 10.0        # extra masking offset in bands 0-7 (dB)
    mid_db: float = 4.0         # extra masking offset in bands 8 .. mid_hi-1 (dB)
    mid_hi: int = 17
    ton_scale: float = 20.0     # flatness (dB below noise's) of a fully tonal band
    tcap_db: float = 25.0       # cap of the tonal masking offset 14.5 + z (None: none)
    alloc_mode: str = "auto"    # allocation reference: "auto" (cheaper of band or frame), "freq"
    alloc_hyst: int = 1         # keep the previous frame's a_b within +-alloc_hyst
    fft_tonal: bool = True      # tonality from a Hann FFT power spectrum's flatness
    fft_noise_db: float = 4.0   # flatness reference of noise in that spectrum
    rd_lambda: float = 2.0      # RD choice of a-1/a/a+1 per band (0: off)
    tcq_lam: float = 0.3        # TCQ Viterbi rate weight without tcq_rd
    tcq_rd: int = 1             # Viterbi rate from the tracked models
    tcq_rdl: float = 0.5        # its rate weight relative to rd_lambda's
    fine_p: float = 8.0         # low-band line-resolution masks, power mean exponent (0: off)
    fine_w: int = 1             # lines per sub-band
    fine_nb: int = 12           # below this band only
    pre_db: float = 10.0        # pre-echo control, mask rise per long frame (0: off)
    nf_bias: int = 0            # noise-filled bands' energy lower (1.5 dB steps)
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
    nf_top: int = 22            # from this band up, uncoded bands silent instead of noise (22: none)
    group_mode: int = 1         # adaptive grouping: 0 window energy, 1 also per frequency region
    tr_db: float = 8.5          # transient detector threshold (dB; 10 before 20/11/2026)
    short_db: float = 0.0       # noise target offset in short frames (dB; < 0: more bits)
    tg_ton: float = 5.0         # a lone line: peak this many dB above a noise's (2 ln n x mean)


# the model streams in the decoder's order: (name, symbols, contexts) (core/models.c)
STREAMS = [("btype", 2, 1), ("alpha", 4, 1), ("stereo", 2, 3), ("energy", 16, 9),
           ("alloc", 16, 6), ("amode", 2, 1), ("cesc", 16, 16), ("coef", 16, 96),
           ("eaesc", 16, 1)]
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
