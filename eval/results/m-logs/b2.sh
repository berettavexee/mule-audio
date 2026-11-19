#!/bin/bash
# Points 16-17: production and the v3 trellis variants on dev, 4 qualities, then equal-rate comparison.
cd .
L=eval/results/m-logs
echo "$(date +%T) start b2 runs" >> $L/phaseB.log
cfg=""
for v in "" -c8 -c16 -c32 -s32; do for q in -6 -9 -12 -15; do cfg="$cfg mule${v}_$q"; done; done
.venv/bin/python eval/run_eval.py --set dev --tag b2_dev $cfg > $L/b2_run.log 2>&1
rc=$?
echo "$(date +%T) end b2 runs (exit $rc)" >> $L/phaseB.log
.venv/bin/python eval/p4_compare.py eval/results/b2_dev.csv --base mule --vs mule-c8 mule-c16 mule-c32 mule-s32 --metric odg odg_adv mms2f visqol nmr_db > $L/b2.log 2>&1
rc=$?
echo "$(date +%T) end b2 compare (exit $rc)" >> $L/phaseB.log
