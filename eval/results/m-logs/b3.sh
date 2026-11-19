#!/bin/bash
# 64 states on dev; production, c32 and c64 on test (confirmation, Zimtohrli included).
cd .
L=eval/results/m-logs
echo "$(date +%T) start b3 runs" >> $L/phaseB.log
.venv/bin/python eval/run_eval.py --set dev --tag b3_dev mule-c64_-6 mule-c64_-9 mule-c64_-12 mule-c64_-15 > $L/b3_dev_run.log 2>&1
echo "$(date +%T) end b3 dev runs (exit $?)" >> $L/phaseB.log
cfg=""
for v in "" -c32 -c64; do for q in -6 -9 -12 -15; do cfg="$cfg mule${v}_$q"; done; done
.venv/bin/python eval/run_eval.py --set test --tag b3_test $cfg > $L/b3_test_run.log 2>&1
echo "$(date +%T) end b3 test runs (exit $?)" >> $L/phaseB.log
.venv/bin/python eval/p4_compare.py eval/results/b2_dev.csv eval/results/b3_dev.csv --base mule --vs mule-c32 mule-c64 --metric odg odg_adv mms2f visqol nmr_db > $L/b3_dev.log 2>&1
.venv/bin/python eval/p4_compare.py eval/results/b3_test.csv --base mule --vs mule-c32 mule-c64 --metric odg odg_adv mms2f visqol zimt nmr_db > $L/b3_test.log 2>&1
echo "$(date +%T) end b3 compare (exit $?)" >> $L/phaseB.log
