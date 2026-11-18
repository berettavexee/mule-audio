CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c99
BUILD ?= build
CORE := core/model.c core/models.c core/rans.c core/dec.c core/enc.c
# the device decoder: no encoder, no allocation
DECODER := core/model.c core/models.c core/dec.c
HDRS := core/model.h core/mule.h core/mule_enc.h core/init_cdf.h core/fx_tables.h

all: $(BUILD)/libmule.so $(BUILD)/mule-dec

$(BUILD)/libmule.so: $(CORE) $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) -shared -fPIC -o $@ $(CORE) -lm

$(BUILD)/mule-dec: tools/mule_dec.c $(CORE) $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) -Icore -o $@ tools/mule_dec.c $(CORE) -lm

core/init_cdf.h: py/mule/init_cdf.npz tools/gen_init_cdf.py
	.venv/bin/python tools/gen_init_cdf.py

$(BUILD):
	mkdir -p $@

# Cortex-M3 size check of the decoder
m3size: $(CORE) $(HDRS) | $(BUILD)
	arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -Os -std=c99 -ffunction-sections -c core/models.c -o $(BUILD)/models-m3.o
	arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -Os -std=c99 -ffunction-sections -DMULE_NO_MALLOC -c core/dec.c -o $(BUILD)/dec-m3.o
	arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -Os -std=c99 -ffunction-sections -c core/model.c -o $(BUILD)/model-m3.o
	arm-none-eabi-size $(BUILD)/*-m3.o

test: all
	.venv/bin/python -m pytest -q tests

clean:
	rm -rf $(BUILD)

.PHONY: all test clean m3size
