"""Reference codecs for the comparisons: encode a WAV, decode back to 44.1 kHz WAV, report the rate.

Each codec configuration is a name ("vorbis_q4", "opus_128") resolved by get(name). run(cfg, wav, workdir)
returns the decoded WAV path and the audio payload rate in kb/s (Ogg framing and header packets
excluded, so that codecs with large headers - Vorbis setup - are not penalised on short excerpts;
MULE is measured the same way).
"""
import os
import subprocess
import sys

import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "py"))
from mule.oggfile import audio_bytes  # noqa: E402


def _sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Vorbis:
    """libvorbis through oggenc (vorbis-tools). OGGENC can point to an aoTuV build."""

    def __init__(self, q):
        self.q = q
        self.name = f"vorbis_q{q:g}"
        self.exe = os.environ.get("OGGENC", "oggenc")

    def run(self, wav, work):
        enc = os.path.join(work, "enc.ogg")
        dec = os.path.join(work, "dec.wav")
        _sh([self.exe, "-Q", "-q", str(self.q), "-o", enc, wav])
        _sh(["oggdec", "-Q", "-o", dec, enc])
        return dec, enc, audio_bytes(enc, 3)


class Opus:
    """libopus through opusenc, VBR, decoded with opusdec at 44.1 kHz (its own resampler)."""

    def __init__(self, kbps):
        self.kbps = kbps
        self.name = f"opus_{kbps}"

    def run(self, wav, work):
        enc = os.path.join(work, "enc.opus")
        dec = os.path.join(work, "dec.wav")
        _sh(["opusenc", "--quiet", "--music", "--vbr", "--bitrate", str(self.kbps), wav, enc])
        _sh(["opusdec", "--quiet", "--rate", "44100", enc, dec])
        return dec, enc, audio_bytes(enc, 2)


class Mule:
    """MULE: real Ogg file from the C encoder (core/enc.c), decoded by the reference decoder
    (build/mule-dec). Name mule[-variant]_<q_db>, e.g. mule_-9, mule-g8_-9 (VARIANTS below)."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    VARIANTS = {                # over params.Params; "" = production (format v3)
        "": {},
        "g8": {"groups": "8"},
        "g1": {"groups": "1"},
        "lr": {"stereo": "lr"},
        "ms": {"stereo": "ms"},
        "kf20": {"keyframe": 20},
        "kf80": {"keyframe": 80},
        # production = format v3 (64 chained states, 8-symbol coefficients) since 19/11/2026;
        # v2's coding tools (8 states restarted in each band, 16 symbols), in a v3 header:
        "v2": {"tcq_states": 8, "tcq_chain": 0, "coef_a8": 0},
        # points 16-17 and 13 as measured (B-LOG.md, C-LOG.md); c64a8 = production
        "c8": {"tcq_states": 8, "coef_a8": 0}, "c16": {"tcq_states": 16, "coef_a8": 0, "tcq_rd_states": 0},
        "c32": {"tcq_states": 32, "coef_a8": 0, "tcq_rd_states": 0},
        "s32": {"tcq_states": 32, "tcq_chain": 0, "coef_a8": 0, "tcq_rd_states": 0},
        "c64": {"coef_a8": 0, "tcq_rd_states": 0},
        "c64a8": {"tcq_rd_states": 0},
        # encoder speed: the RD choice's estimates on a smaller trellis (8 by default since 19/11/2026)
        "rd8": {"tcq_rd_states": 8}, "rd16": {"tcq_rd_states": 16}, "rd32": {"tcq_rd_states": 32}, "rd64": {"tcq_rd_states": 0},
        "c32rd8": {"tcq_states": 32, "tcq_rd_states": 8}, "c32a8": {"tcq_states": 32, "tcq_rd_states": 0},
        "rd0": {"rd_lambda": 0.0},
        "l0": {"tcq_lam": 0.0},
        "l015": {"tcq_lam": 0.15},
        "l045": {"tcq_lam": 0.45},
        "fft0": {"fft_tonal": False},
        "tc0": {"tcap_db": None},
        "mid0": {"mid_db": 0.0},
        # axis 3 (joint RD): Viterbi with the models' rates (tcq_rdl x rd_lambda), wider RD search
        "r025": {"tcq_rd": 1, "tcq_rdl": 0.25},
        "r05": {"tcq_rd": 1, "tcq_rdl": 0.5},
        "r1": {"tcq_rd": 1, "tcq_rdl": 1.0},
        # axis 1: fine (8-line) masking, power mean exponent -p
        "f1": {"fine_p": 1.0},
        "f2": {"fine_p": 2.0},
        "f4": {"fine_p": 4.0},
        "f8": {"fine_p": 8.0},
        "f16": {"fine_p": 16.0},
        # axis 1b: line-resolution masks in the low bands
        "lf4": {"fine_p": 4.0, "fine_w": 1, "fine_nb": 8},
        "lf8": {"fine_p": 8.0, "fine_w": 1, "fine_nb": 8},
        "lf8n12": {"fine_p": 8.0, "fine_w": 1, "fine_nb": 12},
        "lf8r05": {"fine_p": 8.0, "fine_w": 1, "fine_nb": 8, "tcq_rd": 1, "tcq_rdl": 0.5},
        "lf8n12r05": {"fine_p": 8.0, "fine_w": 1, "fine_nb": 12, "tcq_rd": 1, "tcq_rdl": 0.5},
        "lf8n16": {"fine_p": 8.0, "fine_w": 1, "fine_nb": 16},
        "lf8n16r05": {"fine_p": 8.0, "fine_w": 1, "fine_nb": 16, "tcq_rd": 1, "tcq_rdl": 0.5},
        "lf16n12r05": {"fine_p": 16.0, "fine_w": 1, "fine_nb": 12, "tcq_rd": 1, "tcq_rdl": 0.5},
        # axis 2 (E2-LOG): pre-echo control
        "pe3": {"pre_db": 3.0},
        "pe6": {"pre_db": 6.0},
        "pe10": {"pre_db": 10.0},
        "pe8": {"pre_db": 8.0},
        "pe13": {"pre_db": 13.0},
        "pe16": {"pre_db": 16.0},
        "pe20": {"pre_db": 20.0},
        "pe10nf1": {"pre_db": 10.0, "nf_bias": 1},
        "pe10nf2": {"pre_db": 10.0, "nf_bias": 2},
        "pe10nf3": {"pre_db": 10.0, "nf_bias": 3},
        "pe10nf4": {"pre_db": 10.0, "nf_bias": 4},
        # recalibration with pre_db 10, nf_bias 2
        "pntc20": {"pre_db": 10.0, "nf_bias": 2, "tcap_db": 20.0},
        "pntc30": {"pre_db": 10.0, "nf_bias": 2, "tcap_db": 30.0},
        "pnmid2": {"pre_db": 10.0, "nf_bias": 2, "mid_db": 2.0},
        "pnmid6": {"pre_db": 10.0, "nf_bias": 2, "mid_db": 6.0},
        "pnlow8": {"pre_db": 10.0, "nf_bias": 2, "low_db": 8.0},
        "pnlow12": {"pre_db": 10.0, "nf_bias": 2, "low_db": 12.0},
        # lever G (threshold in quiet), over the production
        "athm6": {"ath_db": -6.0}, "athm3": {"ath_db": -3.0}, "athp3": {"ath_db": 3.0},
        "athp6": {"ath_db": 6.0},
    }

    def __init__(self, variant, q):
        from mule import params
        if variant.startswith("m6") and variant not in self.VARIANTS:   # a M6 search's best point
            import json
            tag = variant[2:]                   # "m6v3" -> m6_best_v3.json (m6_tune.py --tag v3)
            path = os.path.join(self.ROOT, "eval", "results", f"m6_best_{tag}.json" if tag else "m6_best.json")
            self.VARIANTS[variant] = {k: (int(v) if k.startswith("tcq_") and k != "tcq_rdl" else v)
                                      for k, v in json.load(open(path)).items()}
        self.params = params.Params(q_db=q, **self.VARIANTS[variant])
        self.name = f"mule{'-' + variant if variant else ''}_{q:g}"

    def run(self, wav, work):
        from mule import native
        x, fs = sf.read(wav, dtype="float64", always_2d=True)
        dec = os.path.join(work, "dec.wav")
        enc = os.path.join(work, "enc.mule")
        with open(enc, "wb") as f:
            f.write(native.c_encode(x, self.params)[0])
        cmd = [os.path.join(self.ROOT, os.environ.get("MULE_BUILD", "build"), "mule-dec"), enc, dec]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if r.returncode:                        # keep the evidence, retry once (P4 incident)
            import shutil
            import time
            keep = os.path.join(self.ROOT, "eval", "results", "crash")
            os.makedirs(keep, exist_ok=True)
            tag = f"{self.name}_{os.path.basename(wav)}_{int(time.time() * 1000)}"
            shutil.copy(enc, os.path.join(keep, tag + ".mule"))
            with open(os.path.join(keep, tag + ".txt"), "w") as f:
                f.write(f"{cmd}\nreturncode {r.returncode}\nstderr {r.stderr}\nparams {self.params}\n")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        return dec, enc, audio_bytes(enc, 2)


def get(name):
    kind, val = name.split("_", 1)
    if kind.split("-")[0] == "mule":
        return Mule(kind[5:], float(val))
    if kind == "vorbis":
        return Vorbis(float(val.lstrip("q")))
    if kind == "opus":
        return Opus(int(val))
    raise ValueError(f"unknown codec configuration {name!r}")


def run(name, wav, work):
    """(decoded wav, encoded file, kb/s of audio payload)."""
    os.makedirs(work, exist_ok=True)
    dec, enc, nbytes = get(name).run(wav, work)
    dur = sf.info(wav).duration
    return dec, enc, nbytes * 8 / dur / 1000
