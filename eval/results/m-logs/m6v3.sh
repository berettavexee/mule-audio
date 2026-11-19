#!/bin/bash
# M6 overnight around the v3 candidate (c64), then validation of its best point on the other half
# of dev and on test, against c64 with the production settings.
cd .
L=eval/results/m-logs
until grep -q "end p4 chain64" $L/phaseB.log; do sleep 20; done
echo "$(date +%T) start m6 v3 search" >> $L/phaseB.log
.venv/bin/python eval/m6_tune.py search --gens 10 --pop 8 --base tcq_chain=1,tcq_states=64 --tag v3 > $L/m6v3.log 2>&1
echo "$(date +%T) end m6 v3 search (exit $?)" >> $L/phaseB.log
cfg=""
for v in -c64 -m6v3; do for q in -6 -9 -12 -15; do cfg="$cfg mule${v}_$q"; done; done
.venv/bin/python eval/run_eval.py --set dev --tag m6v3_dev $cfg > $L/m6v3_dev_run.log 2>&1
.venv/bin/python eval/run_eval.py --set test --tag m6v3_test $cfg > $L/m6v3_test_run.log 2>&1
echo "$(date +%T) end m6 v3 validation runs" >> $L/phaseB.log
.venv/bin/python eval/m6_validate.py --tag v3 > $L/m6v3_validation.log 2>&1
echo "$(date +%T) end m6 v3 validation (exit $?)" >> $L/phaseB.log
