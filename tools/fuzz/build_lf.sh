#!/bin/sh
# Builds tools/fuzz/fuzz_dec.c as a libFuzzer target with clang: build/fuzz/lf_dec, the decoder
# as the player builds it (MULE_NO_MALLOC) under AddressSanitizer and UndefinedBehaviorSanitizer,
# every input also decoded by the MULE_NO_LONG_MUL build and compared sample for sample
# (FUZZ_DIFF). Run: build/fuzz/lf_dec -max_total_time=SECONDS -timeout=2 CORPUS_DIR [SEEDS_DIR]
set -e
cd "$(dirname "$0")/../.."
B=build/fuzz
mkdir -p $B
SAN="-fsanitize=fuzzer-no-link,address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer"
for f in dec model models; do
    clang -O1 -g -std=c99 -Wall -Wextra $SAN -DMULE_NO_MALLOC -Icore -c core/$f.c -o $B/lf_$f.o
done
clang -O1 -g -std=c99 -Wall -Wextra $SAN -DMULE_NO_MALLOC -DMULE_NO_LONG_MUL \
    -include tools/fuzz/nlm_rename.h -Icore -c core/dec.c -o $B/lf_nlm_dec.o
clang -O1 -g -std=c11 -Wall -Wextra $SAN -DLIBFUZZER -DFUZZ_DIFF -Icore -c tools/fuzz/fuzz_dec.c \
    -o $B/lf_fuzz_dec.o
clang -fsanitize=fuzzer,address,undefined $B/lf_dec.o $B/lf_model.o $B/lf_models.o $B/lf_nlm_dec.o \
    $B/lf_fuzz_dec.o -o $B/lf_dec
echo "$B/lf_dec"
