"""Objective metrics: alignment, SNR, an internal NMR, and hooks to ViSQOL / PEAQ when installed.

The internal NMR is a crude Johnston-style model (0.5-Bark bands, Schroeder spreading, global
tonality from spectral flatness, Terhardt threshold in quiet with full scale = 96 dB SPL). It is a
fast regression metric for comparing variants of our own encoder, not a validated quality score:
the decisions (G1, G2) rest on ViSQOL / PEAQ and listening.

External tools (both need 48 kHz input; files are resampled with soxr VHQ):
  VISQOL=/path/to/visqol (default: third_party/visqol/bazel-bin/visqol, audio mode, its built-in
         SVR model; VISQOL_MODEL overrides the model)                   -> "visqol" (MOS-LQO, 1..5)
  PEAQ=/path/to/peaq (GstPEAQ; default third_party/peaq-install/bin/peaq) -> "odg" (basic
       version, -4..0), "odg_adv" (advanced version) and "mms2f" (the 2f-model, ~0..100, from
       two MOVs of the basic version: relative comparisons only, see mms_2f)
  Zimtohrli (pyohrli, from third_party/zimtohrli) -> "zimt" (distance, lower is better; ZIMT=0
       turns it off)
"""
import os
import re
import subprocess
import tempfile
from functools import lru_cache

import numpy as np
import soundfile as sf
import soxr
from scipy.signal import butter, correlate, sosfiltfilt

N_FFT, HOP = 2048, 1024
SPL_FS = 96.0                                   # dB SPL of a full-scale sine


def load(path):
    x, fs = sf.read(path, dtype="float64", always_2d=True)
    return x, fs


def align(ref, deg, max_lag=8192):
    """deg shifted onto ref (integer delay found by cross-correlation of the mono sums); both cut
    to their common length. Returns (ref, deg, delay)."""
    a, b = ref.mean(axis=1), deg.mean(axis=1)
    n = min(len(a), len(b), 10 * 44100)
    c = correlate(b[:n + max_lag], a[:n], mode="full", method="fft")
    zero = n - 1                                # index of lag 0
    lo, hi = zero - max_lag, zero + max_lag + 1
    lag = int(np.argmax(np.abs(c[lo:hi]))) - max_lag
    if lag >= 0:
        deg = deg[lag:]
    else:
        ref = ref[-lag:]
    m = min(len(ref), len(deg))
    return ref[:m], deg[:m], lag


def snr_db(ref, deg):
    e = np.sum((deg - ref) ** 2)
    return 10 * np.log10(np.sum(ref ** 2) / max(e, 1e-30))


def _bark(f):
    return 13 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


@lru_cache(maxsize=4)
def _model(fs):
    f = np.fft.rfftfreq(N_FFT, 1 / fs)
    z = _bark(f)
    band = np.minimum((z * 2).astype(int), int(_bark(fs / 2) * 2))   # 0.5-Bark bands
    nb = band.max() + 1
    zc = np.array([z[band == i].mean() if np.any(band == i) else i / 2 for i in range(nb)])
    dz = zc[:, None] - zc[None, :]              # masker j -> maskee i
    sf_db = 15.81 + 7.5 * (dz + 0.474) - 17.5 * np.sqrt(1 + (dz + 0.474) ** 2)
    spread = 10 ** (sf_db / 10)
    # full-scale sine -> band power, to place the threshold in quiet
    t = np.arange(N_FFT) / fs
    w = np.hanning(N_FFT)
    ps = np.abs(np.fft.rfft(w * np.sin(2 * np.pi * 1000 * t))) ** 2
    fs_power = ps.sum()
    fk = np.maximum(f, 20) / 1000
    ath_db = 3.64 * fk ** -0.8 - 6.5 * np.exp(-0.6 * (fk - 3.3) ** 2) + 1e-3 * fk ** 4
    ath_bin = fs_power * 10 ** ((np.minimum(ath_db, 120) - SPL_FS) / 10)
    ath = np.array([ath_bin[band == i].min() * np.sum(band == i) if np.any(band == i) else np.inf
                    for i in range(nb)])
    return band, nb, zc, spread, ath, w


def _frames(x):
    n = 1 + max(0, (len(x) - N_FFT) // HOP)
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    return x[idx]


def nmr(ref, deg, fs):
    """Internal NMR on aligned signals. Returns dict: nmr_db (total, power mean over frames and
    bands), nmr_max_db (mean over frames of the worst band), adf (fraction of frames whose worst
    band is above 1.5 dB, i.e. likely audible)."""
    band, nb, zc, spread, ath, w = _model(fs)
    tot, worst, disturbed, count = 0.0, 0.0, 0, 0
    for ch in range(ref.shape[1]):
        R = np.abs(np.fft.rfft(_frames(ref[:, ch]) * w, axis=1)) ** 2
        E = np.abs(np.fft.rfft(_frames(deg[:, ch] - ref[:, ch]) * w, axis=1)) ** 2
        Rb = np.zeros((len(R), nb))
        Eb = np.zeros((len(R), nb))
        for i in range(nb):
            m = band == i
            Rb[:, i] = R[:, m].sum(axis=1)
            Eb[:, i] = E[:, m].sum(axis=1)
        C = Rb @ spread.T
        geo = np.exp(np.mean(np.log(R[:, 1:] + 1e-20), axis=1))
        sfm_db = 10 * np.log10(geo / (R[:, 1:].mean(axis=1) + 1e-20) + 1e-20)
        alpha = np.clip(sfm_db / -60.0, 0, 1)[:, None]
        offset = alpha * (14.5 + zc[None, :]) + (1 - alpha) * 5.5
        T = np.maximum(C * 10 ** (-offset / 10), ath[None, :])
        r = Eb / T
        keep = Rb.sum(axis=1) > 1e-9 * N_FFT    # ignore digital silence
        r = r[keep]
        if not len(r):
            continue
        frame = r.mean(axis=1)
        tot += frame.sum()
        worst += (10 * np.log10(r.max(axis=1) + 1e-20)).sum()
        disturbed += int(np.sum(r.max(axis=1) > 10 ** 0.15))
        count += len(r)
    if not count:
        return {"nmr_db": float("nan"), "nmr_max_db": float("nan"), "adf": float("nan")}
    return {"nmr_db": 10 * np.log10(tot / count), "nmr_max_db": worst / count,
            "adf": disturbed / count}


_VISQOL_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "third_party", "visqol", "bazel-bin", "visqol")
_PEAQ_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "third_party", "peaq-install", "bin", "peaq")
_VISQOL_MODEL_DEFAULT = _VISQOL_DEFAULT + ".runfiles/__main__/model/libsvm_nu_svr_model.txt"


def _to48k(x, fs, path):
    y = soxr.resample(x, fs, 48000, quality="VHQ") if fs != 48000 else x
    sf.write(path, np.clip(y, -1, 1), 48000, subtype="PCM_16")


def external(ref, deg, fs):
    """ViSQOL / PEAQ scores for the tools configured in the environment ({} if none)."""
    out = {}
    vis, peaq = os.environ.get("VISQOL", _VISQOL_DEFAULT), os.environ.get("PEAQ", _PEAQ_DEFAULT)
    if vis and not os.path.exists(vis):
        vis = None
    if peaq and not os.path.exists(peaq):
        peaq = None
    if not vis and not peaq:
        return out
    with tempfile.TemporaryDirectory() as d:
        r, g = os.path.join(d, "ref.wav"), os.path.join(d, "deg.wav")
        _to48k(ref, fs, r)
        _to48k(deg, fs, g)
        if vis:
            cmd = [vis, "--reference_file", r, "--degraded_file", g]
            model = os.environ.get("VISQOL_MODEL", _VISQOL_MODEL_DEFAULT)
            if os.path.exists(model):           # else the binary looks in ./model/ (cwd)
                cmd += ["--similarity_to_quality_model", model]
            txt = _run_retry(cmd, timeout=1800)
            m = re.search(r"MOS-LQO:\s*([-\d.]+)", txt)
            out["visqol"] = float(m.group(1)) if m else float("nan")
        if peaq:
            env = dict(os.environ)
            plug = os.path.join(os.path.dirname(os.path.dirname(peaq)), "lib", "gstreamer-1.0")
            if os.path.isdir(plug):
                env["GST_PLUGIN_PATH"] = plug + os.pathsep + env.get("GST_PLUGIN_PATH", "")
            for key, extra in (("odg", []), ("odg_adv", ["--advanced"])):
                txt = _run_retry([peaq, *extra, r, g], env=dict(env, PEAQ_MOVS="1") if not extra else env)
                m = re.search(r"Objective Difference Grade:\s*([-\d.]+)", txt)
                out[key] = float(m.group(1)) if m else float("nan")
                if not extra:
                    out["mms2f"] = mms_2f(_mov(txt, "AvgModDiff1B"), _mov(txt, "ADBB"))
    return out


def _mov(txt, name):
    """The last value of a MOV printed by the local GstPEAQ (PEAQ_MOVS), NaN if absent"""
    m = re.findall(rf"^\s*{re.escape(name)}:\s*([-\d.einf]+)", txt, re.M)
    return float(m[-1]) if m else float("nan")


def mms_2f(avg_mod_diff1, adb):
    """The 2f-model (Kastner and Herre, WASPAA 2019): an estimated MUSHRA score from two MOVs of
    PEAQ Basic. Its constants were fitted on another PEAQ implementation: with GstPEAQ the score
    is only meaningful relatively (codec A against codec B, variant against base). Not clipped to
    0..100 (unlike seabass-2f), so that near transparency differences stay visible."""
    if not np.isfinite(avg_mod_diff1) or not np.isfinite(adb):
        return float("nan")
    s = 56.1345 / (1 + (-0.0282 * avg_mod_diff1 - 0.8628) ** 2) - 27.1451 * adb + 86.3515
    return float(s)


def subsonic(x, fs, fc=20.0):
    """Zero-phase high-pass below fc: DC and rumble are inaudible, and some codecs (Opus: 3 Hz DC
    reject) remove them, which would otherwise dominate the error and fool the alignment."""
    sos = butter(4, fc, "highpass", fs=fs, output="sos")
    return sosfiltfilt(sos, x, axis=0)


def _run_retry(cmd, env=None, timeout=600, tries=3):
    """stdout of an external measurement tool; GstPEAQ hangs now and then (seen twice, idle for
    hours): killed after `timeout` s and run again"""
    for _ in range(tries):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, env=env,
                                  timeout=timeout).stdout
        except subprocess.TimeoutExpired:
            continue
    return ""


def evaluate(ref_path, deg_path):
    ref, fs = load(ref_path)
    deg, fs2 = load(deg_path)
    if fs2 != fs:
        deg = soxr.resample(deg, fs2, fs, quality="VHQ")
    if deg.shape[1] == 1:
        deg = np.repeat(deg, ref.shape[1], axis=1)
    ref, deg = subsonic(ref, fs), subsonic(deg, fs)
    ref, deg, lag = align(ref, deg)
    res = {"delay": lag, "snr_db": snr_db(ref, deg)}
    res.update(nmr(ref, deg, fs))
    res.update(external(ref, deg, fs))
    res.update(zimtohrli(ref, deg, fs))
    return res


def zimtohrli(ref, deg, fs):
    """Zimtohrli (Google; third_party/zimtohrli, its pyohrli module installed in the venv):
    "zimt", the distance (0 = identical, lower is better), mean of the channels, at 48 kHz.
    {} if pyohrli is missing or ZIMT=0."""
    if os.environ.get("ZIMT", "1") == "0":
        return {}
    try:
        import pyohrli
    except ImportError:
        return {}
    z = pyohrli.Pyohrli()
    r48 = soxr.resample(ref, fs, 48000, quality="VHQ")
    d48 = soxr.resample(deg, fs, 48000, quality="VHQ")
    d = [z.distance(np.clip(r48[:, c], -1, 1), np.clip(d48[:, c], -1, 1)) for c in range(ref.shape[1])]
    return {"zimt": float(np.mean(d))}
