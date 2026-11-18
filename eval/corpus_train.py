"""Training corpus for the final initial CDFs (P4.7): ~200 random 15 s excerpts from the FLAC
library, disjoint from the dev/test sets (other tracks; artists may repeat). Writes
eval/corpus_train.json and data/train/*.wav. Usage: python eval/corpus_train.py [N]"""
import glob
import json
import os
import random
import sys

import numpy as np
import soundfile as sf
import soxr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB = os.environ.get("MULE_LIBRARY", "LIBRARY")   # root of a FLAC library
OUT = os.path.join(ROOT, "data", "train")


def main(n=200):
    used = {os.path.join(LIB, e["path"]) for e in json.load(open(os.path.join(HERE, "corpus_p4.json")))}
    sys.path.insert(0, HERE)
    import corpus
    used |= {src for _, src, *_ in corpus.ITEMS}
    files = sorted(glob.glob(LIB + "/**/*.flac", recursive=True))
    rng = random.Random(4242)
    rng.shuffle(files)
    os.makedirs(OUT, exist_ok=True)
    items = []
    for f in files:
        if len(items) >= n:
            break
        if f in used:
            continue
        try:
            info = sf.info(f)
        except Exception:
            continue
        if info.channels != 2 or info.duration < 45:
            continue
        start = rng.uniform(0.15, 0.75) * (info.duration - 15)
        x, fs = sf.read(f, start=int(start * info.samplerate), frames=int(15 * info.samplerate),
                        dtype="float64", always_2d=True)
        if fs != 44100:
            x, fs = soxr.resample(x, fs, 44100, quality="VHQ"), 44100
        if np.max(np.abs(x)) < 1e-3:
            continue                                    # silence
        name = f"t{len(items):03d}"
        fade = int(0.01 * fs)
        r = np.linspace(0, 1, fade)[:, None]
        x[:fade] *= r
        x[-fade:] *= r[::-1]
        sf.write(os.path.join(OUT, name + ".wav"), x, fs, subtype="PCM_16")
        items.append({"name": name, "path": os.path.relpath(f, LIB), "start": round(start, 1)})
    json.dump(items, open(os.path.join(HERE, "corpus_train.json"), "w"), ensure_ascii=False, indent=0)
    print(len(items), "training excerpts ->", OUT)


if __name__ == "__main__":
    main(*map(int, sys.argv[1:]))
