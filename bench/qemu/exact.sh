#!/bin/sh
# Bit-exactness of a target build under QEMU: for each stream (corpus excerpts at a few qualities,
# then every test vector of format v2 to v5), the target's output hash against the PC decoder's.
# Usage: bench/qemu/exact.sh CPU [CFLAGS...]   (e.g. cortex-m0 -DMULE_NO_LONG_MUL)
cd "$(dirname "$0")/../.."
CPU=$1; shift
B=build/qemu
mkdir -p $B
cp bench/qemu/packets.h $B/packets.h.keep 2>/dev/null
fail=0; n=0
run() {
    pc=$(.venv/bin/python bench/qemu/make_packets.py "$@" 2>/dev/null | sed -n 's/.*PC hash //p')
    arm-none-eabi-gcc -mcpu=$CPU -mthumb -O2 -std=c99 -ffunction-sections -fdata-sections \
        -DMULE_NO_MALLOC $FLAGS -Icore -Ibench/qemu -nostartfiles -T bench/qemu/link.ld \
        -Wl,--gc-sections bench/qemu/startup.c bench/qemu/bench.c core/dec.c core/model.c core/models.c \
        --specs=nano.specs -lc -lgcc -o $B/exact.elf || { echo "build failed"; exit 1; }
    tg=$(qemu-system-arm -M mps2-an385 -nographic -monitor none -serial none \
        -semihosting-config enable=on,target=native -icount shift=0 -kernel $B/exact.elf 2>&1 < /dev/null | sed -n "s/^hash \([0-9]*\).*/\1/p")
    n=$((n + 1))
    if [ "$pc" = "$tg" ] && [ -n "$pc" ]; then echo "ok   $*"; else echo "DIFF $* (PC $pc, target $tg)"; fail=$((fail + 1)); fi
}
FLAGS="$*"
for it in castanets abba b_belenos glockenspiel; do
    for q in -12 -4 4; do run $it $q 4; done
done
for f in tests/vectors/*.mule tests/vectors/v*/*.mule; do run "$f"; done
cp $B/packets.h.keep bench/qemu/packets.h 2>/dev/null
echo "$n streams, $fail different"
[ $fail = 0 ]
