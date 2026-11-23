"""A large comparison of MULE, Opus and Apple AAC on a music library: tracks drawn at random, a
30-second excerpt from the middle of each, every codec at several settings, the judges of
eval/metrics.py (Zimtohrli, PEAQ basic and advanced, NMR), then each codec interpolated per item
at the setting whose mean rate over the corpus is 96, 128 and 160 kb/s, and paired statistics.

  campaign.py prepare LIBRARY [--n 300] [--seed 2026]   tracks and excerpts (data/campaign/)
  campaign.py calibrate [--items 40]                    rates only: the settings' mean kb/s
  campaign.py run [-j N]                                every item x configuration (resumable;
                                                        VISQOL= to leave ViSQOL out)
  campaign.py report                                    rate matching and statistics (Markdown)

Selection by rounds: the artists that have FLAC tracks (artist = first folder below LIBRARY) in a
random order (the seed), one track of each per round, until n tracks: no artist weighs more than
another (a large box set no more than a single album); tracks of at least 40 s. Excerpts: 44.1 kHz, 16-bit stereo (mono duplicated), from the middle of the track.
Everything is written under data/campaign/ (git-ignored): the track list stays private, and the
excerpts are never published (copyrighted music); only the statistics are.
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "campaign")
SRC = os.path.join(OUT, "src")
RESULTS = os.path.join(OUT, "results.csv")
EXCERPT_S = 30.0
RATES = (96, 128, 160)

# the settings of each codec, from the calibration on the first 40 excerpts (their mean rates
# must bracket RATES): Opus 88.0 96.3 128.7 160.8 176.7 kb/s; Apple AAC (TVBR: its steps of 9)
# 92.1 106.9 120.8 137.2 152.9 185.7; MULE about 90 103 121 136 150 171
CONFIGS = {                     # (MULE first: A in the report's comparisons)
    "mule": [f"mule_{q:g}" for q in (-2.5, -4, -6, -7.5, -9, -11)],
    "opus": [f"opusnd_{k}" for k in (88, 96, 128, 160, 176)],
    "aac": [f"aapl_q{q}" for q in (45, 54, 63, 73, 82, 91)],
}
# encoder variants measured after the campaign (run --families NAME, report --families ...): the
# threshold in quiet (refcodecs.Mule's ath20, athrg), a wider q range since their rates move
FAMILIES = {**CONFIGS, **{f"mule_{v}": [f"mule-{v}_{q:g}" for q in (-1, -2.5, -4, -6, -7.5, -9, -11, -12.5)]
                          for v in ("ath20", "athrg", "athl")},
            # the target rate mode (params.for_bitrate, mule-enc --bitrate: the rate leveler)
            "mule_br": [f"mule-br_{k}" for k in (80, 96, 112, 128, 144, 160, 176, 192)]}


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def prepare(a):
    lib = os.path.abspath(a.library)
    rng = random.Random(a.seed)
    pools = []                                  # per artist: its FLAC tracks, shuffled
    for art in sorted(d for d in os.listdir(lib) if os.path.isdir(os.path.join(lib, d))):
        tracks = sorted(os.path.join(dp, f) for dp, _dn, fs in os.walk(os.path.join(lib, art))
                        for f in fs if f.lower().endswith(".flac"))
        if tracks:
            rng.shuffle(tracks)
            pools.append(tracks)
    rng.shuffle(pools)
    os.makedirs(SRC, exist_ok=True)
    chosen = []
    while len(chosen) < a.n and any(pools):
        for pool in pools:                      # a round: the next track of each artist
            if len(chosen) >= a.n:
                break
            while pool:
                t = pool.pop(0)
                dur = probe_duration(t)
                if dur >= 40:
                    break
            else:
                continue
            item = f"c{len(chosen):03d}"
            start = max(0.0, dur / 2 - EXCERPT_S / 2)
            wav = os.path.join(SRC, item + ".wav")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t",
                            str(EXCERPT_S), "-i", t, "-ac", "2", "-ar", "44100", "-af",
                            "aresample=resampler=soxr:precision=28", "-c:a", "pcm_s16le", wav],
                           check=True)
            chosen.append({"item": item, "path": os.path.relpath(t, lib),
                           "artist": os.path.relpath(t, lib).split(os.sep)[0],
                           "duration": round(dur, 1), "start": round(start, 3)})
            print(item, os.path.relpath(t, lib), flush=True)
    with open(os.path.join(OUT, "tracks.json"), "w") as f:
        json.dump({"library": lib, "seed": a.seed, "excerpt_s": EXCERPT_S, "tracks": chosen}, f,
                  indent=1, ensure_ascii=False)
    print(f"{len(chosen)} excerpts in {SRC}")


def items():
    with open(os.path.join(OUT, "tracks.json")) as f:
        return [t["item"] for t in json.load(f)["tracks"]]


def all_configs(families=None):
    return [c for fam in (families or CONFIGS) for c in FAMILIES[fam]]


def _rate_job(args):
    sys.path.insert(0, HERE)
    import refcodecs
    cfg, item = args
    wav = os.path.join(SRC, item + ".wav")
    with tempfile.TemporaryDirectory() as work:
        _dec, _enc, kbps = refcodecs.run(cfg, wav, work)
    return cfg, item, kbps


def calibrate(a):
    its = items()[:a.items]
    jobs = [(c, i) for c in all_configs() for i in its]
    rates = {}
    with ProcessPoolExecutor(a.j) as ex:
        for cfg, _item, kbps in ex.map(_rate_job, jobs):
            rates.setdefault(cfg, []).append(kbps)
    for cfg in all_configs():
        print(f"{cfg:14s} {np.mean(rates[cfg]):6.1f} kb/s")


def _job(args):
    # athrg: the whole track's loudness (loudness.json: BS.1770 of each source track and excerpt)
    os.environ.setdefault("MULE_TRACK_LUFS", os.path.join(OUT, "loudness.json"))
    sys.path.insert(0, HERE)
    import metrics
    import refcodecs
    cfg, item = args
    wav = os.path.join(SRC, item + ".wav")
    t0 = time.time()
    with tempfile.TemporaryDirectory() as work:
        dec, _enc, kbps = refcodecs.run(cfg, wav, work)
        res = metrics.evaluate(wav, dec)
    return {"config": cfg, "item": item, "kbps": kbps, **res, "seconds": round(time.time() - t0, 1)}


FIELDS = ["config", "item", "kbps", "delay", "snr_db", "nmr_db", "nmr_max_db", "adf", "odg",
          "odg_adv", "mms2f", "zimt", "seconds"]


def run(a):
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            done = {(r["config"], r["item"]) for r in csv.DictReader(f)}
    # item by item (all configurations of an item together): a partial run already holds
    # complete items for the report
    jobs = [(c, i) for i in items() for c in all_configs(a.families) if (c, i) not in done]
    print(f"{len(jobs)} jobs to do ({len(done)} done)", flush=True)
    new = not os.path.exists(RESULTS)
    with open(RESULTS, "a", newline="") as f, ProcessPoolExecutor(a.j) as ex:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        futs = {ex.submit(_job, j): j for j in jobs}
        n, t0 = 0, time.time()
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception as e:                  # noqa: BLE001 (logged, the run goes on)
                print(f"FAILED {futs[fut]}: {e!r}", flush=True)
                continue
            w.writerow(row)
            f.flush()
            n += 1
            if n % 50 == 0:
                el = time.time() - t0
                print(f"progress {n}/{len(jobs)} ({el / 3600:.2f} h, "
                      f"{el / n * (len(jobs) - n) / 3600:.2f} h left)", flush=True)
    print("run complete", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare")
    p.add_argument("library")
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=2026)
    p = sp.add_parser("calibrate")
    p.add_argument("--items", type=int, default=40)
    p.add_argument("-j", type=int, default=10)
    p = sp.add_parser("run")
    p.add_argument("-j", type=int, default=10)
    p.add_argument("--families", nargs="+", choices=list(FAMILIES))
    p = sp.add_parser("report")
    p.add_argument("--families", nargs="+", choices=list(FAMILIES), help="(default: " + " ".join(CONFIGS)
                   + "); other than that, written to report_<families>.md and matched_<...>.csv")
    a = ap.parse_args()
    if a.cmd == "report":
        sys.path.insert(0, HERE)
        import campaign_report
        fams = a.families or list(CONFIGS)
        tag = "" if fams == list(CONFIGS) else "_" + "-".join(fams)
        campaign_report.main(RESULTS, os.path.join(OUT, "tracks.json"),
                             {f: FAMILIES[f] for f in fams}, RATES, tag)
    else:
        {"prepare": prepare, "calibrate": calibrate, "run": run}[a.cmd](a)
