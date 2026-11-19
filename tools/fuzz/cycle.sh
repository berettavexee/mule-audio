#!/bin/sh
# One short fuzzing cycle in a work directory: build, then SECONDS of fuzzing from the corpus.
# Usage: tools/fuzz/cycle.sh WORKDIR SECONDS SEED   (WORKDIR/corpus: the seeds and new inputs)
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
"$ROOT/tools/fuzz/build.sh" > /dev/null
cd "$1"
"$ROOT/build/fuzz/fuzz_dec" corpus "$2" "$3"
