#!/bin/sh
# QEMU Cortex-M3 benchmark of the fixed-point decoder.
# Usage: bench/qemu/run.sh [ITEM Q_DB SECONDS]   (default: abba -12 10)
set -e
cd "$(dirname "$0")/../.."
ROOT=$(pwd)
B=build/qemu
mkdir -p $B
.venv/bin/python bench/qemu/make_packets.py "${1:-abba}" "${2:--12}" "${3:-10}"
arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -O2 -std=c99 -Wall -ffunction-sections -fdata-sections \
    -DMULE_NO_MALLOC -Icore -Ibench/qemu -nostartfiles -T bench/qemu/link.ld -Wl,--gc-sections \
    bench/qemu/startup.c bench/qemu/bench.c core/dec.c core/model.c core/models.c \
    --specs=nano.specs -lc -lgcc -o $B/bench.elf
arm-none-eabi-size $B/bench.elf
qemu-system-arm -M mps2-an385 -nographic -monitor none -serial none \
    -semihosting-config enable=on,target=native -icount shift=0 -kernel $B/bench.elf
