#!/bin/sh
# Builds tools/fuzz/fuzz_dec.c into build/fuzz/fuzz_dec: the decoder as the player builds it
# (MULE_NO_MALLOC), with AddressSanitizer, UndefinedBehaviorSanitizer (aborting at the first
# report) and gcc's edge coverage on the decoder only.
set -e
cd "$(dirname "$0")/../.."
B=build/fuzz
mkdir -p $B
SAN="-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer"
COV="-fsanitize-coverage=trace-pc"
for f in dec model models; do
    gcc -O1 -g -std=c99 -Wall -Wextra $SAN $COV -DMULE_NO_MALLOC -Icore -c core/$f.c -o $B/$f.o
done
gcc -O1 -g -std=c11 -Wall -Wextra $SAN -Icore -c tools/fuzz/fuzz_dec.c -o $B/fuzz_dec.o
gcc $SAN $B/dec.o $B/model.o $B/models.o $B/fuzz_dec.o -o $B/fuzz_dec
echo "$B/fuzz_dec"
