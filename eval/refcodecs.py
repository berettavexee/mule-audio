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


def adts_frames(path):
    """The frames of an ADTS stream: (raw data blocks in the frame, payload bytes without the
    header)."""
    data = open(path, "rb").read()
    i, out = 0, []
    while i + 7 <= len(data):
        if data[i] != 0xFF or data[i + 1] & 0xF0 != 0xF0:
            raise ValueError(f"{path}: lost ADTS sync at byte {i}")
        hlen = 7 if data[i + 1] & 1 else 9                  # protection_absent = 1: no CRC
        flen = ((data[i + 3] & 3) << 11) | (data[i + 4] << 3) | (data[i + 5] >> 5)
        out.append(((data[i + 6] & 3) + 1, data[i + hlen:i + flen]))
        i += flen
    return out


def adts_payload(path):
    """Bytes of raw AAC data in an ADTS stream (frame headers excluded, as for Ogg)."""
    return sum(len(p) for _n, p in adts_frames(path))


class AAC:
    """Fraunhofer FDK-AAC (aac-enc frontend of libfdk-aac), AAC-LC, constant bitrate, afterburner
    on, default bandwidth; ADTS decoded by ffmpeg's AAC decoder. The encoder delay is removed by the
    alignment in metrics.evaluate."""

    def __init__(self, kbps):
        self.kbps = kbps
        self.name = f"aac_{kbps}"

    def run(self, wav, work):
        enc = os.path.join(work, "enc.aac")
        dec = os.path.join(work, "dec.wav")
        _sh(["aac-enc", "-r", str(self.kbps * 1000), "-t", "2", "-a", "1", wav, enc])
        _sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", enc, "-c:a", "pcm_s16le", dec])
        return dec, enc, adts_payload(enc)


class AACVBR(AAC):
    """FDK-AAC in its variable bitrate modes (aac-enc -v 1 .. 5), AAC-LC, afterburner on."""

    def __init__(self, mode):
        self.mode = mode
        self.name = f"aacv_{mode}"

    def run(self, wav, work):
        enc = os.path.join(work, "enc.aac")
        dec = os.path.join(work, "dec.wav")
        _sh(["aac-enc", "-v", str(self.mode), "-t", "2", "-a", "1", wav, enc])
        _sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", enc, "-c:a", "pcm_s16le", dec])
        return dec, enc, adts_payload(enc)


class AppleAAC:
    """Apple's AAC encoder (CoreAudioToolbox) through qaac under wine, AAC-LC in true VBR
    (--tvbr N, 0..127), default bandwidth; decoded by ffmpeg. Needs third_party/qaac (git-ignored:
    Apple's libraries are never published). The rate counts the AAC packets only (no MP4)."""

    ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "third_party", "qaac")

    def __init__(self, q):
        self.q = q
        self.name = f"aapl_q{q}"

    @staticmethod
    def _win(path):
        return "Z:" + os.path.abspath(path).replace("/", "\\")

    def run(self, wav, work):
        enc = os.path.join(work, "enc.m4a")
        dec = os.path.join(work, "dec.wav")
        env = dict(os.environ, WINEPREFIX=os.path.join(self.ROOT, "wine"), WINEDEBUG="-all")
        subprocess.run(["wine", os.path.join(self.ROOT, "bin", "qaac64.exe"), "-s", "--tvbr", str(self.q),
                        "-o", self._win(enc), self._win(wav)], check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", enc, "-c:a", "pcm_s16le", dec])
        sizes = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "packet=size", "-of", "csv=p=0", enc], check=True, capture_output=True,
                               text=True).stdout.split()
        return dec, enc, sum(int(s.split(",")[0]) for s in sizes if s.split(",")[0].isdigit())


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
        # zero-bit tonal bands (N-LOG.md): 1 guard (allocation 1, line within tg_db of the target), 2 muted
        "tg1": {"tg": 1}, "tg1d0": {"tg": 1, "tg_db": 0.0}, "tg1d12": {"tg": 1, "tg_db": 12.0},
        "tg1d18": {"tg": 1, "tg_db": 18.0}, "tg2": {"tg": 2},
        "tg1b19": {"tg": 1, "tg_band": 19}, "tg1b20": {"tg": 1, "tg_band": 20},
        "tg1t3": {"tg": 1, "tg_ton": 3.0}, "tg1t8": {"tg": 1, "tg_ton": 8.0},
        # Lebanon Hanover (N-LOG.md): fewer short frames, or more bits in them
        # production since 20/11/2026 = gr1d12; gr0 = the grouping before (whole window, 6 dB).
        # A variant sets only its own fields: it inherits every other production default (tr_db
        # 8.5 since 20/11/2026; the measurements before used 10, see N-LOG.md). run_eval.py writes
        # the settings each configuration resolved to next to its CSV (<tag>.params.json)
        "gr0": {"group_mode": 0, "group_db": 6.0},
        # v4 probe (branch v4): noise in the coded bands' zero coefficients, level offset (dB)
        "lp15": {"lp_hz": 15000.0}, "lp16": {"lp_hz": 16000.0}, "lp17": {"lp_hz": 17000.0},
        "lp18": {"lp_hz": 18000.0},
        "lpd0": {"lpd": 1}, "lpd6": {"lpd": 1, "lpd_db": 6.0}, "lpdm6": {"lpd": 1, "lpd_db": -6.0},
        # v4 probe: folding of zero-bit bands (start band, mix 0 fold .. 8 noise)
        "fd0": {"fold": 1, "fold_mix": 0}, "fd2": {"fold": 1, "fold_mix": 2},
        "fd4": {"fold": 1, "fold_mix": 4}, "fd2s16": {"fold": 1, "fold_mix": 2, "fold_start": 16},
        "fd2tg": {"fold": 1, "fold_mix": 2, "tg": 1},
        # check (N-LOG.md): every zero-bit band from 12 (16) up coded at allocation 1 instead of
        # noise-filled, through the tonal guard with its two criteria disabled
        "code12": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 12},
        "code16": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 16},
        # code rather than fill (Apple), with noise in the zeros: allocation 2 or 3 (N-LOG.md)
        "code12a2nf": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 12, "tg_a": 2,
                       "nf_coded": 1, "nf_off_db": -6.0},
        "code12a3nf": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 12, "tg_a": 3,
                       "nf_coded": 1, "nf_off_db": -6.0},
        "code16a3nf": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 16, "tg_a": 3,
                       "nf_coded": 1, "nf_off_db": -6.0},
        # v4 probe: rotation of low-allocation coded bands (Opus' spreading), R0 fixed level,
        # R1 per channel and frame (rtd), R2 combinations
        # v4 probe: TNS on the noise of zero-bit bands (order, gain threshold), and with the candidate
        "tn8g0": {"tnf": 1, "tnf_gain_db": 0.0}, "tn8g0b16": {"tnf": 1, "tnf_gain_db": 0.0, "tnf_b0": 16},
        "tn8": {"tnf": 1}, "tn4": {"tnf": 1, "tnf_order": 4}, "tn8g3": {"tnf": 1, "tnf_gain_db": 3.0},
        "tn8nfm6tg": {"tnf": 1, "tg": 1, "nf_coded": 1, "nf_off_db": -6.0},
        "tn4g0b16": {"tnf": 1, "tnf_gain_db": 0.0, "tnf_b0": 16, "tnf_order": 4},
        "tn8g0b16nfm6tg": {"tnf": 1, "tnf_gain_db": 0.0, "tnf_b0": 16, "tg": 1, "nf_coded": 1, "nf_off_db": -6.0},
        "tn4g0b16nfm6tg": {"tnf": 1, "tnf_gain_db": 0.0, "tnf_b0": 16, "tnf_order": 4, "tg": 1, "nf_coded": 1,
                           "nf_off_db": -6.0},
        "rt20": {"rot": 1, "rot_deg": 20}, "rt40": {"rot": 1, "rot_deg": 40}, "rt60": {"rot": 1, "rot_deg": 60},
        "rt40a6": {"rot": 1, "rot_deg": 40, "rot_amax": 6},
        "rtd40": {"rot": 1, "rot_deg": 40, "rot_dyn": 1}, "rtd60": {"rot": 1, "rot_deg": 60, "rot_dyn": 1},
        "rtd40tg": {"rot": 1, "rot_deg": 40, "rot_dyn": 1, "tg": 1},
        "rtd40nfm6tg": {"rot": 1, "rot_deg": 40, "rot_dyn": 1, "tg": 1, "nf_coded": 1, "nf_off_db": -6.0},
        "fdd0": {"fold": 1, "fold_mix": 0, "fold_dyn": 1}, "fdd2": {"fold": 1, "fold_mix": 2, "fold_dyn": 1},
        "fdd2t5": {"fold": 1, "fold_mix": 2, "fold_dyn": 1, "fold_ton_db": 5.0},
        "fdd2t12": {"fold": 1, "fold_mix": 2, "fold_dyn": 1, "fold_ton_db": 12.0},
        "fdd2nfm6tg": {"fold": 1, "fold_mix": 2, "fold_dyn": 1, "tg": 1, "nf_coded": 1, "nf_off_db": -6.0},
        "fd2nfm6tg": {"fold": 1, "fold_mix": 2, "tg": 1, "nf_coded": 1, "nf_off_db": -6.0},
        "nfc": {"nf_coded": 1}, "nfcm3": {"nf_coded": 1, "nf_off_db": -3.0},
        "nfcm6": {"nf_coded": 1, "nf_off_db": -6.0},
        "nfctg": {"nf_coded": 1, "tg": 1}, "nfcm3tg": {"nf_coded": 1, "nf_off_db": -3.0, "tg": 1},
        "nfcm9": {"nf_coded": 1, "nf_off_db": -9.0}, "nfcm12": {"nf_coded": 1, "nf_off_db": -12.0},
        "nfcm6tg": {"nf_coded": 1, "nf_off_db": -6.0, "tg": 1},
        "nfcm9tg": {"nf_coded": 1, "nf_off_db": -9.0, "tg": 1},
        "gr1": {"group_mode": 1, "group_db": 6.0}, "gr1d8": {"group_mode": 1, "group_db": 8.0},
        "gr1d10": {"group_mode": 1, "group_db": 10.0}, "gr1d12": {"group_mode": 1, "group_db": 12.0}, "gd4": {"group_mode": 0, "group_db": 4.0}, "gd3": {"group_mode": 0, "group_db": 3.0},
        # production since 20/11/2026 = tr85; tr10 = the detector before
        "tr7": {"tr_db": 7.0}, "tr85": {"tr_db": 8.5}, "tr10": {"tr_db": 10.0},
        "nf21": {"nf_top": 21}, "nf20": {"nf_top": 20},
        # production since 20/11/2026 = sp3d2; sp0 = Schroeder's spreading alone, as before
        "sp0": {"spread_mode": 0}, "sp1": {"spread_mode": 1}, "sp2": {"spread_mode": 2},
        "sp3": {"spread_mode": 3, "sp_dz": 1.0}, "sp3d2": {"spread_mode": 3, "sp_dz": 2.0},
        "dy05": {"dyn_a": 0.5}, "dy1": {"dyn_a": 1.0},
        "tr13": {"tr_db": 13.0}, "tr16": {"tr_db": 16.0}, "tr20": {"tr_db": 20.0}, "tr99": {"tr_db": 99.0},
        "sh3": {"short_db": -3.0}, "sh6": {"short_db": -6.0}, "sh9": {"short_db": -9.0},
        "tg1a2": {"tg": 1, "tg_a": 2}, "tg1a3": {"tg": 1, "tg_a": 3}, "tg1a4": {"tg": 1, "tg_a": 4},
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


def run_aligned(name, wav):
    """wav encoded and decoded with configuration `name` (temporary files): (ref, deg, fs, kbps,
    lag), the two signals prepared as metrics.evaluate measures them."""
    import tempfile
    import metrics
    ref, fs = metrics.load(wav)
    with tempfile.TemporaryDirectory() as work:
        dec, _enc, kbps = run(name, wav, work)
        ref, deg, lag = metrics.prepare(ref, fs, dec)
    return ref, deg, fs, kbps, lag


def get(name):
    kind, val = name.split("_", 1)
    if kind.split("-")[0] == "mule":
        return Mule(kind[5:], float(val))
    if kind == "vorbis":
        return Vorbis(float(val.lstrip("q")))
    if kind == "opus":
        return Opus(int(val))
    if kind == "aac":
        return AAC(int(val))
    if kind == "aacv":
        return AACVBR(int(val))
    if kind == "aapl":
        return AppleAAC(int(val.lstrip("q")))
    raise ValueError(f"unknown codec configuration {name!r}")


def run(name, wav, work):
    """(decoded wav, encoded file, kb/s of audio payload)."""
    os.makedirs(work, exist_ok=True)
    dec, enc, nbytes = get(name).run(wav, work)
    dur = sf.info(wav).duration
    return dec, enc, nbytes * 8 / dur / 1000
