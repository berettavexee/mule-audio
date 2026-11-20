"""Builds the evaluation corpus: short 44.1 kHz / 16-bit stereo WAV excerpts from lossless sources.

Two parts: ITEMS (the P0 corpus, 36 hand-picked excerpts) and eval/corpus_p4.json (60 excerpts
drawn at random, seed 2026, from the FLAC library, P4). Sets: "dev" = the P0 items + half of the
P4 ones (tuning), "test" = the other half (milestones only), "p0" = the P0 items.

Usage: python eval/corpus.py            (writes data/corpus/*.wav, skips items whose source is missing)
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
import soxr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQAM = os.path.join(ROOT, "data", "sqam")
OUT = os.path.join(ROOT, "data", "corpus")
DP = os.path.expanduser("~/FlashdanceDownloads/Daft Punk - 2001 - Discovery [FLAC]")
LIB = os.environ.get("MULE_LIBRARY", "LIBRARY")   # root of a FLAC library (beets layout)

# name, source file, start (s), duration (s), why it is in the corpus
ITEMS = [
    ("castanets",   f"{SQAM}/27.flac",  0.0, 10.0, "transients, pre-echo"),
    ("glockenspiel", f"{SQAM}/35.flac", 0.0, 12.0, "tonal attacks, HF partials"),
    ("harpsichord", f"{SQAM}/40.flac",  0.0, 12.0, "pre-echo + dense tonal"),
    ("triangles",   f"{SQAM}/32.flac",  0.0, 10.0, "sparse HF tones"),
    ("pitchpipe_gong5k", f"{SQAM}/05.flac", 0.0, 8.0, "pure tone, birdies"),
    ("violin",      f"{SQAM}/08.flac", 20.0, 12.0, "tonal, vibrato"),
    ("trumpet",     f"{SQAM}/21.flac",  0.0, 12.0, "strong harmonics"),
    ("piano",       f"{SQAM}/60.flac",  0.0, 15.0, "piano (Schubert)"),
    ("organ_bach",  f"{SQAM}/57.flac",  0.0, 12.0, "stationary, dense harmonics"),
    ("guitar",      f"{SQAM}/58.flac",  0.0, 12.0, "plucked"),
    ("female_en",   f"{SQAM}/49.flac",  0.0, 10.0, "speech, mono-in-stereo"),
    ("male_en",     f"{SQAM}/50.flac",  0.0, 10.0, "speech, mono-in-stereo"),
    ("quartet",     f"{SQAM}/48.flac",  0.0, 12.0, "vocal ensemble"),
    ("orchestra",   f"{SQAM}/65.flac",  0.0, 15.0, "orchestra (R. Strauss)"),
    ("abba",        f"{SQAM}/69.flac",  0.0, 15.0, "pop, wide stereo"),
    ("rabbitt",     f"{SQAM}/70.flac",  0.0, 15.0, "pop/country"),
    ("dp_onemoretime", f"{DP}/01. Daft Punk - One More Time.flac", 60.0, 15.0, "dense, compressed"),
    ("dp_hbfs",     f"{DP}/04. Daft Punk - Harder, Better, Faster, Stronger.flac", 45.0, 15.0, "vocoder, beats"),
    ("dp_digitallove", f"{DP}/03. Daft Punk - Digital Love.flac", 90.0, 15.0, "synth, guitar solo"),
    ("dp_veridisquo", f"{DP}/11. Daft Punk - Veridis Quo.flac", 60.0, 15.0, "sustained synth"),
    ("metallica", f"{LIB}/Metallica/Metallica - 1988 - …And Justice for All/03 Eye of the Beholder.flac",
     90.0, 15.0, "distorted guitars, dense"),
    ("slayer", f"{LIB}/Slayer/Slayer - 1985 - Hell Awaits/03 At Dawn They Sleep.flac", 60.0, 15.0,
     "thrash, cymbals"),
    ("tool", f"{LIB}/Tool/Tool - 2019 - Lateralus/03 The Patient.flac", 120.0, 15.0, "modern rock"),
    ("satie", f"{LIB}/Erik Satie; Pascal Rogé/Erik Satie; Pascal Rogé - 1984 - 3 Gymnopédies & Other Piano Works/03 Gymnopédie no. 3.flac",
     20.0, 15.0, "quiet solo piano"),
    ("pires_concerto", f"{LIB}/Maria João Pires/Maria João Pires - 2015 - Piano Concerto No. 2/03 Piano Concerto No. 2 in B-Flat major, Op. 19_ III. Rondo_ Molto allegro.flac",
     60.0, 15.0, "piano + orchestra, 48 kHz source"),
    ("emerson_fugue", f"{LIB}/Emerson String Quartet/Emerson String Quartet - 2003 - Bach_ The Art of Fugue/03 The Art of Fugue, BWV 1080 - Contrapunctus III.flac",
     30.0, 15.0, "string quartet"),
    ("brandenburg", f"{LIB}/Johann Sebastian Bach; Concerto Italiano, Rinaldo Alessandrini/Johann Sebastian Bach; Concerto Italiano, Rinaldo Alessandrini - 2005 - Brandenburg Concertos/03 Concerto No. 1 in F major, BWV 1046_ Allegro.flac",
     60.0, 15.0, "baroque ensemble, harpsichord"),
    ("vivaldi", f"{LIB}/Antonio Vivaldi; Fabio Biondi, Europa Galante/Antonio Vivaldi; Fabio Biondi, Europa Galante - 2004 - Les Quatre Saisons/03 Concerto, RV 269 _le printemps__ III.flac",
     60.0, 15.0, "baroque strings"),
    ("beethoven5", f"{LIB}/Ludwig van Beethoven; Wiener Philharmoniker, Carlos Kleiber/Ludwig van Beethoven; Wiener Philharmoniker, Carlos Kleiber - 1995 - Symphonien nos. 5 & 7/03 Symphonie Nr. 5 c‐Moll, op. 67_ III. Allegro.flac",
     60.0, 15.0, "symphony orchestra"),
    ("aphex", f"{LIB}/Aphex Twin/Aphex Twin - 1998 - 51_13 Aphex Singles Collection/03 Ventolin (Crowsmangegus mix edit).flac",
     30.0, 15.0, "harsh electronic"),
    ("massive_teardrop", f"{LIB}/Massive Attack/Massive Attack - 1998 - Mezzanine/03 Teardrop.flac",
     60.0, 15.0, "trip-hop, harpsichord, voice"),
    ("wutang", f"{LIB}/Wu‐Tang Clan/Wu‐Tang Clan - 1994 - Enter the Wu‐Tang (36 Chambers)/03 Can It Be All So Simple.flac",
     60.0, 15.0, "hip-hop, lo-fi samples"),
    ("pinkfloyd", f"{LIB}/Pink Floyd/Pink Floyd - 2016 - Echoes_ The Best of Pink Floyd/03 The Happiest Days of Our Lives.flac",
     30.0, 15.0, "classic rock"),
    ("heilung", f"{LIB}/Heilung/Heilung - 2015 - Ofnir/03 Hakkerskaldyr.flac", 30.0, 15.0,
     "drums, throat voice, ambience"),
    ("kraftwerk", f"{LIB}/Kraftwerk/Kraftwerk - 1974 - Autobahn/03 Kometenmelodie 2.flac", 60.0, 15.0,
     "analog synth"),
    ("bjork_medulla", f"{LIB}/Björk/Björk - 2006 - Medúlla/03 Where Is the Line.flac", 60.0, 15.0,
     "voices only"),
]


P4_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus_p4.json")


def _p4_items():
    if not os.path.exists(P4_JSON):
        return []
    with open(P4_JSON) as f:
        return json.load(f)


def _all():
    """(name, src, start, dur, why, set)"""
    out = [(n, s, a, d, w, "p0") for n, s, a, d, w in ITEMS]
    out += [(e["name"], os.path.join(LIB, e["path"]), e["start"], e["dur"], "library (random)", e["set"])
            for e in _p4_items()]
    return out


def build(verbose=True):
    os.makedirs(OUT, exist_ok=True)
    made = []
    for name, src, start, dur, _why, _set in _all():
        dst = os.path.join(OUT, name + ".wav")
        if os.path.exists(dst):
            made.append(dst)
            continue
        if not os.path.exists(src):
            if verbose:
                print(f"skip {name}: {src} missing", file=sys.stderr)
            continue
        info = sf.info(src)
        x, fs = sf.read(src, start=int(start * info.samplerate), frames=int(dur * info.samplerate),
                        dtype="float64", always_2d=True)
        if fs != 44100:                         # the codec is tuned at 44.1 kHz
            x, fs = soxr.resample(x, fs, 44100, quality="VHQ"), 44100
        if x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        x = x[:, :2]
        fade = int(0.01 * fs)                   # 10 ms fades: no clicks at the cut points
        ramp = np.linspace(0.0, 1.0, fade)[:, None]
        x[:fade] *= ramp
        x[-fade:] *= ramp[::-1]
        sf.write(dst, x, fs, subtype="PCM_16")
        made.append(dst)
        if verbose:
            print(f"{name:18s} {dur:5.1f} s  {_why}")
    return made


def train_items():
    """(name, wav) of the CDF training corpus (eval/corpus_train.py, data/train)."""
    d = os.path.join(os.path.dirname(OUT), "train")
    return [(f[:-4], os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(".wav")] \
        if os.path.isdir(d) else []


def items(subset="p0", only=None):
    """(name, wav path) of the corpus items that exist. subset: "p0" (default, the P0 corpus),
    "dev" (p0 + P4 dev half), "test" (P4 test half), "all", "train" (CDF training corpus).
    only: item names to keep (a comma-separated string or an iterable; None: all)."""
    if only:
        keep = set(only.split(",") if isinstance(only, str) else only)
        return [it for it in items(subset) if it[0] in keep]
    if subset == "train":
        return train_items()
    def keep(s):
        return (subset == "all" or s == subset or (subset == "dev" and s in ("p0", "dev")))
    return [(n, os.path.join(OUT, n + ".wav")) for n, _s, _a, _d, _w, st in _all()
            if keep(st) and os.path.exists(os.path.join(OUT, n + ".wav"))]


if __name__ == "__main__":
    build()
