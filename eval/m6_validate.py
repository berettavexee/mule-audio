"""M6's validation: its best point (mule-m6<tag>) against the base (mule-c64 by default), at equal
rate, on the half of `dev` the search never saw (odd-numbered items) and on `test`.
  python eval/m6_validate.py [--tag v3] [--base mule-c64]"""
import argparse
import os
import subprocess
import sys
import tempfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import corpus  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default="v3")
    ap.add_argument("--base", default="mule-c64")
    a = ap.parse_args()
    held_out = {n for n, _ in corpus.items("dev")[1::2]}
    dev = pd.read_csv(os.path.join(HERE, "results", f"m6{a.tag}_dev.csv"))
    metrics = ["odg", "odg_adv", "mms2f", "visqol", "nmr_db"]
    with tempfile.TemporaryDirectory() as t:
        half = os.path.join(t, "dev_held_out.csv")
        dev[dev.item.isin(held_out)].to_csv(half, index=False)
        for lab, csv in (("dev, held-out half", half),
                         ("test", os.path.join(HERE, "results", f"m6{a.tag}_test.csv"))):
            print(f"##### {lab}", flush=True)
            subprocess.run([sys.executable, os.path.join(HERE, "p4_compare.py"), csv, "--base", a.base,
                            "--vs", f"mule-m6{a.tag}", "--metric", *metrics], check=False)


if __name__ == "__main__":
    main()
