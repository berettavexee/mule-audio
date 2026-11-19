#!/bin/bash
# Phase 1 of the M measurements, in order; each step's output in its own log.
cd .
while pgrep -f "ctx_lab.py trace --set train" > /dev/null; do sleep 20; done
for step in m8 m2 m7 m1; do
    echo "$(date +%T) start $step" >> eval/results/m-logs/phase1.log
    .venv/bin/python eval/ctx_lab.py $step > eval/results/m-logs/$step.log 2>&1
    echo "$(date +%T) end $step (exit $?)" >> eval/results/m-logs/phase1.log
done
echo "$(date +%T) phase 1 done" >> eval/results/m-logs/phase1.log
