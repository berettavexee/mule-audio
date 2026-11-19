#!/bin/bash
# M3: production and joint allocation (rd_viterbi) on dev, 4 qualities, then equal-rate comparison.
cd .
echo "$(date +%T) start m3 runs" >> eval/results/m-logs/phase2.log
.venv/bin/python eval/run_eval.py --set dev --tag m3_dev mule_-6 mule_-9 mule_-12 mule_-15 mule-rv_-6 mule-rv_-9 mule-rv_-12 mule-rv_-15 > eval/results/m-logs/m3_run.log 2>&1
rc=$?
echo "$(date +%T) end m3 runs (exit $rc)" >> eval/results/m-logs/phase2.log
.venv/bin/python eval/p4_compare.py eval/results/m3_dev.csv --base mule --vs mule-rv --metric odg odg_adv mms2f visqol nmr_db > eval/results/m-logs/m3.log 2>&1
rc=$?
echo "$(date +%T) end m3 compare (exit $rc)" >> eval/results/m-logs/phase2.log
