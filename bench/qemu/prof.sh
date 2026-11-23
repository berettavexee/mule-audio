#!/bin/sh
# Per-section profile of the fixed-point decoder under QEMU (instructions per frame), for a CPU
# (cortex-m3 or cortex-m0: the M0's Thumb subset runs on the M3 machine) and extra flags.
# Usage: bench/qemu/prof.sh CPU [CFLAGS...]   (packets: bench/qemu/make_packets.py first)
set -e
cd "$(dirname "$0")/../.."
CPU=$1; shift
B=build/qemu
mkdir -p $B
arm-none-eabi-gcc -mcpu=$CPU -mthumb -O2 -std=c99 -Wall -ffunction-sections -fdata-sections \
    -DMULE_NO_MALLOC -DMULE_PROF "$@" -Icore -Ibench/qemu -nostartfiles -T bench/qemu/link.ld \
    -Wl,--gc-sections bench/qemu/startup.c bench/qemu/bench.c core/dec.c core/model.c core/models.c \
    --specs=nano.specs -lc -lgcc -o $B/prof.elf
qemu-system-arm -M mps2-an385 -nographic -monitor none -serial none \
    -semihosting-config enable=on,target=native -icount shift=0 -kernel $B/prof.elf
