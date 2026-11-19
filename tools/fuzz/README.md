# Robustness tests

Two sanitized checks (AddressSanitizer and UndefinedBehaviorSanitizer, aborting at the first
report), with gcc alone: no libFuzzer or AFL needed. `make fuzz` runs both (FUZZ_SECONDS of
fuzzing, 300 by default).

**The encoder on hostile inputs** (`enc_edge.c`, `enc_edge.sh`): NaN, infinities, values of
1e30, denormals, full-scale squares, DC, clipping, an empty or one-sample input, at three
qualities; each stream must decode in full.

**The decoder, coverage-guided fuzzing** (`fuzz_dec.c`, `build.sh`, `mkseeds.py`): the decoder
as the player builds it (`MULE_NO_MALLOC`), its edges counted through gcc's
`-fsanitize-coverage=trace-pc`; an input that reaches a new edge joins the corpus. Inputs are a
header and packets, with seeks and short output buffers; seeds are real streams of every header
variant (`mkseeds.py`). A failing input is written to `crash-*.bin`; replay it with
`build/fuzz/fuzz_dec crash-*.bin`.

```sh
tools/fuzz/build.sh
mkdir -p work/corpus && .venv/bin/python tools/fuzz/mkseeds.py work/corpus
cd work && ../build/fuzz/fuzz_dec corpus 1800 1      # 30 minutes, seed 1
```

Findings (fixed; `eval/results/F-LOG.md`): a signed overflow in the
fixed-point FFT on malformed streams; NaN input samples reaching an integer conversion in the
encoder.
