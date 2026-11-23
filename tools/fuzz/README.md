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

**The decoder under libFuzzer, differential** (`build_lf.sh`, clang): the same harness built as a
libFuzzer target, sanitized, and every input decoded twice: by the reference build and by the
build for cores without a 32x32->64 multiply (`MULE_NO_LONG_MUL`, renamed `nlm_*` by
`nlm_rename.h`). Any difference in header acceptance, return value or a single sample aborts:
the Cortex-M0 variant must stay bit-exact on hostile streams too.

```sh
tools/fuzz/build_lf.sh
mkdir -p work/lf/corpus work/lf/seeds && .venv/bin/python tools/fuzz/mkseeds.py work/lf/seeds
cd work/lf && ../../build/fuzz/lf_dec -max_total_time=7200 -timeout=5 -rss_limit_mb=2048 \
    -artifact_prefix=artifacts/ corpus seeds        # add -use_value_profile=1 for a second pass
```

Passes of 23/11/2026 on the v5 decoder: 2 h plain (91,714 inputs, 754 edges) then 2 h with
`-use_value_profile=1` (211,798 inputs, 755 edges, corpus of 1,647); no sanitizer report and no
difference between the two builds.
