"""Point 13 (docs/V3-IDEAS.md), rate side: the stream's bits when the adaptive models are updated
after one symbol in N only (mule_model_every), optionally adapting faster (mule_model_rate_adj),
every stream, real resets and trained initial tables, on the encoder's operations (`dev`, default
settings or --params). The experiment (core/model.c) was removed after the measurement
(eval/results/C-LOG.md); this script needs commit 05dd7a1 to run. The instruction side is measured on QEMU (bench/qemu/run.sh with
MULE_MODEL_EVERY). The symbols are those of the every-symbol encoder: the encoder's own decisions
under the other rule would differ slightly.
  python eval/c_models.py [--params tcq_chain=1,tcq_states=64]"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (eval/archive/)
sys.path[:0] = [os.path.join(ROOT, "py"), os.path.join(ROOT, "eval")]
import corpus  # noqa: E402
from mule import native, params as E  # noqa: E402

VARIANTS = [(1, 0), (2, 0), (2, -1), (4, 0), (4, -1), (4, -2)]


def job(args):
    wav, extra = args
    x, fs = sf.read(wav, dtype="float64", always_2d=True)
    m, v, fstart = native.c_ops(x, E.Params(**extra))
    keys = fstart[np.arange(0, len(fstart) - 1, 40)]
    init = E.load_init()
    raw = float(-m[m < 0].sum())
    out = []
    for every, adj in VARIANTS:
        native.lib.mule_model_every, native.lib.mule_model_rate_adj = every, adj
        tot = raw
        for name, n, nctx in E.STREAMS:
            sel = (m >= E.OFF[name]) & (m < E.OFF[name] + nctx)
            if sel.any():
                before = np.concatenate([[0], np.cumsum(sel)])[keys]
                tot += native.stream_cost(n, nctx, m[sel] - E.OFF[name], v[sel], before, init.get(name))
        out.append(tot)
    native.lib.mule_model_every, native.lib.mule_model_rate_adj = 1, 0
    return np.array(out), len(x) / fs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--params", default="")
    a = ap.parse_args()
    extra = {k: int(v) for k, v in (kv.split("=") for kv in filter(None, a.params.split(",")))}
    items = corpus.items("dev")
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(job, [(w, extra) for _, w in items]))
    bits = np.array([r[0] for r in res])
    secs = sum(r[1] for r in res)
    base = bits[:, 0].sum()
    print(f"{len(items)} dev items, {secs:.0f} s, settings {extra or 'production'}: "
          f"{base / secs / 1000:.2f} kb/s with every-symbol updates")
    print(f"{'update every':>12s} {'rate adj':>9s} {'kb/s':>8s} {'change':>8s} {'items worse':>12s}")
    for k, (every, adj) in enumerate(VARIANTS):
        t = bits[:, k].sum()
        print(f"{every:12d} {adj:9d} {t / secs / 1000:8.2f} {100 * (t / base - 1):+7.2f} % "
              f"{int((bits[:, k] > bits[:, 0] + 1e-6).sum()):>6d}/{len(items)}")


if __name__ == "__main__":
    main()
