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
    """libopus through opusenc, VBR, decoded with opusdec at 44.1 kHz (its own resampler).
    opusdec dithers its 16-bit output by default (opus_<kbps>, every Opus measurement before
    22/11/2026); opusnd_<kbps> decodes without dither: on tracks whose highs are near -100 dBFS
    (EBU SQAM orchestra, piano) the dither alone adds 8 to 14 dB of energy at 10-20 kHz."""

    def __init__(self, kbps, dither=True):
        self.kbps = kbps
        self.dither = dither
        self.name = f"opus_{kbps}" if dither else f"opusnd_{kbps}"

    def run(self, wav, work):
        enc = os.path.join(work, "enc.opus")
        dec = os.path.join(work, "dec.wav")
        _sh(["opusenc", "--quiet", "--music", "--vbr", "--bitrate", str(self.kbps), wav, enc])
        _sh(["opusdec", "--quiet", "--rate", "44100"] + ([] if self.dither else ["--no-dither"]) + [enc, dec])
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
    (aapl_q<N>: --tvbr N, 0..127) or constrained VBR (aaplc_<kb/s>: --cvbr, aiming at that rate
    file by file), default bandwidth; decoded by ffmpeg. Needs third_party/qaac (git-ignored:
    Apple's libraries are never published). The rate counts the AAC packets only (no MP4)."""

    ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "third_party", "qaac")

    def __init__(self, q, cvbr=False):
        self.q, self.cvbr = q, cvbr
        self.name = f"aaplc_{q}" if cvbr else f"aapl_q{q}"

    @staticmethod
    def _win(path):
        return "Z:" + os.path.abspath(path).replace("/", "\\")

    def run(self, wav, work):
        enc = os.path.join(work, "enc.m4a")
        dec = os.path.join(work, "dec.wav")
        env = dict(os.environ, WINEPREFIX=os.path.join(self.ROOT, "wine"), WINEDEBUG="-all")
        subprocess.run(["wine", os.path.join(self.ROOT, "bin", "qaac64.exe"), "-s",
                        "--cvbr" if self.cvbr else "--tvbr", str(self.q),
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
    VARIANTS = {                # over params.Params; "" = production (format v4)
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
        # check (N-LOG.md): every zero-bit band from 12 (16) up coded at allocation 1 instead of
        # noise-filled, through the tonal guard with its two criteria disabled
        "code12": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 12},
        "code16": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 16},
        "code14": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 14},
        "code18": {"tg": 1, "tg_ton": -100.0, "tg_db": 100.0, "tg_band": 18},
        # envelope guard (N-LOG.md, Garbage): modulated noise-filled bands coded instead
        # eg 5 dB and nf_bias 1 (eg5nfb1) production on 21/11/2026; before them eg6 (guard at 6 dB,
        # nf_bias 0), and eg0nfb0 the frozen v4 without either (sl6v4_test.csv). All of these keep
        # the psychoacoustic settings of before the Zimtohrli tuning (PSY21, merged in below)
        "eg0": {"eg": 0, "nf_bias": 0}, "eg0nfb0": {"eg": 0, "nf_bias": 0},
        "eg4": {"eg": 1, "eg_db": 4.0, "nf_bias": 0}, "eg6": {"eg": 1, "eg_db": 6.0, "nf_bias": 0},
        "eg9": {"eg": 1, "eg_db": 9.0, "nf_bias": 0},
        "eg6b12": {"eg": 1, "eg_db": 6.0, "eg_band": 12, "nf_bias": 0},
        "eg6b19": {"eg": 1, "eg_db": 6.0, "eg_band": 19, "nf_bias": 0},
        # refinements over the production (eg6), Zimtohrli first (N-LOG.md)
        "eg5": {"eg_db": 5.0, "nf_bias": 0}, "eg6a2": {"eg_db": 6.0, "eg_a": 2, "nf_bias": 0},
        "eg6b14": {"eg_db": 6.0, "eg_band": 14, "nf_bias": 0},
        "nfm3": {"eg_db": 6.0, "nf_off_db": -3.0, "nf_bias": 0}, "nfm9": {"eg_db": 6.0, "nf_off_db": -9.0, "nf_bias": 0},
        "nfb1": {"eg_db": 6.0, "nf_bias": 1}, "eg5nfb1": {},
        # format v4 (21/11/2026): the probes of branch v4 (folding, rotation, TNS on the noise,
        # low-pass, split bands, subpartitions, line tracking, Viterbi weights, ...) were removed
        # when the format was frozen; their results are in eval/results/N-LOG.md
        # a second transient detector in the highs (fc kHz, threshold dB), as first measured (memory
        # decay 3 dB, no tonal veto): thf8d85 was the production from 22/11/2026 until the v5, thf0
        # the production before it
        **{f"thf{fc}d{db:g}".replace(".", ""): {"tr_hf": 1, "tr_hf_fc": fc * 1000.0, "tr_hf_db": db}
           for fc in (6, 8, 10) for db in (6.0, 8.5, 11.0)},
        "thf0": {"tr_hf": 0},
        "thf8d7": {"tr_hf": 1, "tr_hf_fc": 8000.0, "tr_hf_db": 7.0},
        "thf7d85": {"tr_hf": 1, "tr_hf_fc": 7000.0, "tr_hf_db": 8.5},
        "thf8d85eg0": {"tr_hf": 1, "tr_hf_fc": 8000.0, "tr_hf_db": 8.5, "eg": 0},
        "thf8d85eg7": {"tr_hf": 1, "tr_hf_fc": 8000.0, "tr_hf_db": 8.5, "eg_db": 7.0},
        "tg0": {"tg": 0},
        "midhi22": {"mid_hi": 22},
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
    # the psychoacoustic settings of the production before the Zimtohrli tuning of 22/11/2026
    # (m6_best_z1.json, rounded, is the production since; N-LOG.md): pinned in the variants
    # measured on 21/11/2026 so that they keep sounding as measured
    PSY21 = {"tcap_db": 25.0, "mid_db": 4.0, "low_db": 10.0, "fft_noise_db": 4.0, "rd_lambda": 2.0,
             "tcq_rdl": 0.5, "pre_db": 10.0}
    for _k in ("eg0", "eg0nfb0", "eg4", "eg6", "eg9", "eg6b12", "eg6b19", "eg5", "eg6a2", "eg6b14",
               "nfm3", "nfm9", "nfb1", "eg5nfb1"):
        VARIANTS[_k] = {**PSY21, **VARIANTS[_k]}
    # the transient detector of every variant above, as measured: the highs pass off (production
    # since 22/11/2026, thf* set it), the memory decaying by 3 dB per block (1 since 22/11/2026: 3 dB
    # took a voice's glottal pulses for attacks), the highs threshold 8.5 dB without tonal veto (6 dB
    # and 10 dB since the v5). Format v5 (22/11/2026): the probes of branch v5 (vertex-centred
    # noise, borrowed envelope, per-band TF, folding criteria, the attack's group cut, hi_db,
    # nf_gate, ...) were removed when the format was frozen, their results are in
    # eval/results/N-LOG.md; the variants now write format v5 (folding in short frames, the noise
    # level modelled) and no longer reproduce their v4 measurements exactly
    PRE_V5 = {"tr_hf": 0, "tr_decay_db": 3.0, "tr_hf_db": 8.5, "tr_hf_ton": 0.0}
    for _k in VARIANTS:
        if _k:
            VARIANTS[_k] = {**PRE_V5, **VARIANTS[_k]}
    del _k
    # the threshold in quiet and the level (23/11/2026, after the 300-track campaign: quiet
    # tracks got far fewer bits than from Opus, their spectrum below the ATH calibrated at 96 dB
    # SPL for full scale), production settings otherwise: ath20 the ATH 20 dB lower everywhere;
    # athrg the ATH moved by minus the track's ReplayGain 2.0 gain (the listener sets the volume
    # so that the track plays at -18 LUFS), in run(); for an excerpt, MULE_TRACK_LUFS names a
    # JSON {excerpt name: {"track_lufs": ...}} of the whole tracks' loudness (campaign.py)
    VARIANTS["ath20"] = {"ath_db": -20.0}
    VARIANTS["athrg"] = {}
    # athl: the relative ATH (Vorbis, LAME): lowered by -14 dBFS minus the passage's level, 24 dB
    # at most, the level follower falling 0.5 dB per frame (core/mule_enc.h, ath_rel_db)
    VARIANTS["athl"] = {"ath_rel_db": 24.0}
    # the band floor (core/mule_enc.h, bf_rel_db; 23/11/2026): bf<snr>r<rel>, m = minus
    for _s, _r in ((0, 20), (0, 30), (-4, 40), (3, 20), (6, 20), (10, 20), (14, 20), (10, 12), (10, 30)):
        VARIANTS[f"bf{'m' if _s < 0 else ''}{abs(_s)}r{_r}"] = {"bf_rel_db": float(_r), "bf_snr_db": float(_s)}
    del _s, _r
    # the rate leveler (core/mule_enc.h, rc_k; 23/11/2026): rc<k x 10>, rc10a = with athl
    for _k in (5, 10, 20, 40):
        VARIANTS[f"rc{_k}"] = {"rc_k": _k / 10}
    VARIANTS["rc10a"] = {"rc_k": 1.0, "ath_rel_db": 24.0}
    for _k in (20, 40, 80, 160):                # rc<k x 10>m15: up to 15 dB of q_db
        VARIANTS[f"rc{_k}m15"] = {"rc_k": _k / 10, "rc_max": 15.0}
    del _k
    # br: mule-br_<kbps>, the target rate mode (params.for_bitrate: mule-enc --bitrate)
    VARIANTS["br"] = {"opa_mode": 0}          # --bitrate before the Opus mix (24/11/2026)
    # Opus' band allocation in the target rate mode (core/mule_enc.h, opa_mode; 23/11/2026):
    # brA the table alone, brB<k x 10> its tilt, brC<alpha x 100> the mix
    VARIANTS.update({"brA": {"opa_mode": 1}, "brB10": {"opa_mode": 2, "opa_k": 1.0},
                     "brB5": {"opa_mode": 2, "opa_k": 0.5}, "brB20": {"opa_mode": 2, "opa_k": 2.0},
                     "brC25": {"opa_mode": 3, "opa_alpha": 0.25}, "brC50": {"opa_mode": 3, "opa_alpha": 0.5},
                     "brC75": {"opa_mode": 3, "opa_alpha": 0.75},
                     "brC65": {"opa_mode": 3, "opa_alpha": 0.65}, "brC85": {"opa_mode": 3, "opa_alpha": 0.85},
                     "brC90": {"opa_mode": 3, "opa_alpha": 0.90}})
    # the CMA-ES searches (eval/m6_tune.py --space b9 --rate R, m6_best_b9_R.json; 24-25/11/2026):
    # brB9r<R>, the best point found at R kb/s
    VARIANTS["brB9r96"] = {"opa_mode": 3, "tcap_db": 18.369, "mid_db": 5.281, "low_db": 16.264, "fft_noise_db": 4.463, "rd_lambda": 2.667, "tcq_rdl": 0.601, "pre_db": 10.271, "opa_alpha": 0.665, "nf_off_db": -4.299}
    VARIANTS["brB9r128"] = {"opa_mode": 3, "tcap_db": 14.113, "mid_db": 7.358, "low_db": 18.409, "fft_noise_db": 3.711, "rd_lambda": 2.163, "tcq_rdl": 0.659, "pre_db": 9.683, "opa_alpha": 0.741, "nf_off_db": -5.016}
    VARIANTS["brB9r160"] = {"opa_mode": 3, "tcap_db": 13.915, "mid_db": 9.323, "low_db": 20.455, "fft_noise_db": 3.082, "rd_lambda": 2.131, "tcq_rdl": 0.652, "pre_db": 9.625, "opa_alpha": 0.631, "nf_off_db": -4.765}
    # the slopes' reallocation (eval/slopes.py, slopes_summary.json; 25/11/2026) without touching
    # 13-20 kHz: brS<R>, the mask offsets (dB) found at R kb/s on Zimtohrli's six lower regions
    # (MULE bands 0-2, 2-6, 6-12, 12-16, 16-19, 19-20)
    for _r, _o in {96: (-3.35, 1.72, -0.82, -0.69, -1.27, -1.81),
                   128: (-3.82, 3.40, -0.65, -0.56, -0.52, -1.24),
                   160: (-3.66, 0.08, -1.88, -1.36, -1.45, -1.77)}.items():
        VARIANTS[f"brS{_r}"] = {"band_db": sum(((_d,) * _n for _d, _n in zip(_o, (2, 4, 6, 4, 3, 1))),
                                               ()) + (0.0, 0.0)}
    # ... 13-20 kHz alone (MULE bands 20-21): brH<R>; and the whole reallocation: brF<R>
    for _r, _h in {96: 6.0, 128: 3.44, 160: 6.0}.items():
        VARIANTS[f"brH{_r}"] = {"band_db": (0.0,) * 20 + (_h, _h)}
        VARIANTS[f"brF{_r}"] = {"band_db": VARIANTS[f"brS{_r}"]["band_db"][:20] + (_h, _h)}
    del _r, _o, _h
    # settings by rate (24/11/2026): the psychoacoustic settings and the high-band tilt around the
    # Opus mix (brC75), measured near 96 kb/s first: brT<name>
    _C75 = {"opa_mode": 3, "opa_alpha": 0.75}
    for _n, _kv in {"hf6": {"hf_db": 6.0}, "hf12": {"hf_db": 12.0}, "hf6b19": {"hf_db": 6.0, "hf_band": 19},
                    "hfm6": {"hf_db": -6.0},
                    "lo10": {"low_db": 10.0}, "lo20": {"low_db": 20.0}, "mid3": {"mid_db": 3.0},
                    "mid9": {"mid_db": 9.0}, "rd17": {"rd_lambda": 1.7}, "rd34": {"rd_lambda": 3.4},
                    "tc12": {"tcap_db": 12.0}, "tc20": {"tcap_db": 20.0}}.items():
        VARIANTS["brT" + _n] = {**_C75, **_kv}
    del _n, _kv
    # on/off hysteresis of the allocations (24/11/2026, Purcell's flicker): brZ<on dB>[k<keep dB>]
    VARIANTS.update({"brZ2": {"zh_db": 2.0}, "brZ4": {"zh_db": 4.0}, "brZ6": {"zh_db": 6.0},
                     "brZ3k3": {"zh_db": 3.0, "zh_keep_db": 3.0}, "brZ0k3": {"zh_keep_db": 3.0}})

    def __init__(self, variant, q):
        from mule import params
        if variant.startswith("m6") and variant not in self.VARIANTS:   # a M6 search's best point
            import json
            tag = variant[2:]                   # "m6v3" -> m6_best_v3.json (m6_tune.py --tag v3)
            path = os.path.join(self.ROOT, "eval", "results", f"m6_best_{tag}.json" if tag else "m6_best.json")
            self.VARIANTS[variant] = {**self.PRE_V5, **{k: (int(v) if k.startswith("tcq_") and k != "tcq_rdl" else v)
                                                    for k, v in json.load(open(path)).items()}}
        self.params = (params.for_bitrate(q, **self.VARIANTS[variant]) if variant.startswith("br")
                       else params.Params(q_db=q, **self.VARIANTS[variant]))
        self.name = f"mule{'-' + variant if variant else ''}_{q:g}"

    def run(self, wav, work):
        from mule import native
        x, fs = sf.read(wav, dtype="float64", always_2d=True)
        dec = os.path.join(work, "dec.wav")
        enc = os.path.join(work, "enc.mule")
        prm = self.params
        if self.name.startswith("mule-athrg_"):
            import dataclasses
            from mule import replaygain
            lufs = None
            if os.environ.get("MULE_TRACK_LUFS"):   # excerpts: the whole track's loudness, as the
                import json                         # encoder of the track would measure it
                with open(os.environ["MULE_TRACK_LUFS"]) as f:
                    lufs = json.load(f)[os.path.splitext(os.path.basename(wav))[0]]["track_lufs"]
            if lufs is None:
                m = replaygain.Meter(fs)
                m.add(x)
                lufs = m.loudness()
            prm = dataclasses.replace(prm, ath_db=prm.ath_db - replaygain.gain(lufs))
        with open(enc, "wb") as f:
            f.write(native.c_encode(x, prm)[0])
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
    if kind == "opusnd":
        return Opus(int(val), dither=False)
    if kind == "aac":
        return AAC(int(val))
    if kind == "aacv":
        return AACVBR(int(val))
    if kind == "aapl":
        return AppleAAC(int(val.lstrip("q")))
    if kind == "aaplc":
        return AppleAAC(int(val), cvbr=True)
    raise ValueError(f"unknown codec configuration {name!r}")


def run(name, wav, work):
    """(decoded wav, encoded file, kb/s of audio payload)."""
    os.makedirs(work, exist_ok=True)
    dec, enc, nbytes = get(name).run(wav, work)
    dur = sf.info(wav).duration
    return dec, enc, nbytes * 8 / dur / 1000
