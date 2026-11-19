#!/bin/sh
# Builds and runs tools/fuzz/enc_edge.c: the encoder and decoder on hostile inputs, sanitized.
set -e
cd "$(dirname "$0")/../.."
mkdir -p build/fuzz
SAN="-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer"
gcc -O1 -g -std=c99 -Wall -Wextra $SAN -Icore -o build/fuzz/enc_edge tools/fuzz/enc_edge.c \
    core/model.c core/models.c core/rans.c core/dec.c core/enc.c core/enc_dsp.c core/enc_psy.c \
    core/enc_tcq.c core/enc_ogg.c -lm
build/fuzz/enc_edge
