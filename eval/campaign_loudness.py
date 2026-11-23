"""The loudness (ITU-R BS.1770, mule.replaygain) of each campaign excerpt and of its whole source
track, to data/campaign/loudness.json; the athrg variant (refcodecs.Mule) reads the tracks' from it,
as the encoder of the whole track would measure it. Needs the library of tracks.json mounted.

  python eval/campaign_loudness.py      (from the repository root)
"""
import json, os, sys, subprocess, numpy as np, soundfile as sf
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "py")
from mule import replaygain
meta = json.load(open("data/campaign/tracks.json"))
lib = meta["library"]
def one(t):
    pr = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", os.path.join(lib, t["path"]), "-ac", "2",
                           "-ar", "44100", "-f", "f32le", "-"], stdout=subprocess.PIPE)
    m = replaygain.Meter(44100)
    while True:
        raw = pr.stdout.read(44100 * 8 * 10)      # 10 s
        if not raw:
            break
        raw = raw[:len(raw) // 8 * 8]
        m.add(np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64))
    pr.wait()
    full = m.loudness()
    e, _ = sf.read(f"data/campaign/src/{t['item']}.wav", dtype="float64", always_2d=True)
    m = replaygain.Meter(44100); m.add(e)
    return t["item"], full, m.loudness()
if __name__ == "__main__":
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(one, meta["tracks"]))
    json.dump({i: {"track_lufs": f, "excerpt_lufs": x} for i, f, x in res}, open("data/campaign/loudness.json", "w"), indent=1)
    d = np.array([x - f for _, f, x in res])
    print("excerpt minus track LUFS: mean %+.2f, median %+.2f, sd %.2f, p5 %+.1f, p95 %+.1f, min %+.1f, max %+.1f"
          % (d.mean(), np.median(d), d.std(), *np.percentile(d, [5, 95]), d.min(), d.max()))
    print("|diff| > 3 LU: %d tracks, > 6 LU: %d" % ((abs(d) > 3).sum(), (abs(d) > 6).sum()))
