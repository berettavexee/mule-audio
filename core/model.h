/* Adaptive multi-symbol models (spec 3): 15-bit CDFs adapted after every symbol, AV1 style. The
 * same code drives the decoder, the rANS coder and the encoder's cost estimates (core/model.c). */
#ifndef MULE_MODEL_H
#define MULE_MODEL_H

#include <stdint.h>

#define MULE_PROB_BITS 15
#define MULE_PROB_ONE  (1u << MULE_PROB_BITS)
#define MULE_MAX_SYMS  16
#define MULE_MIN_FREQ  4                 /* every symbol keeps at least this frequency */

typedef struct {
    uint16_t cdf[MULE_MAX_SYMS + 1];    /* cdf[i] = P(sym < i) * 2^15 before the floor */
    uint8_t n;                           /* symbols */
    uint8_t count;                       /* symbols seen, saturates at 32 (adaptation rate) */
} mule_model;

/* A model of n symbols: uniform, or from a trained CDF (n + 1 values) */
void mule_model_init(mule_model *m, int n);
void mule_model_init_cdf(mule_model *m, int n, const uint16_t *cdf);
/* Start (cumulative) and frequency of `sym` as coded: the CDF with MULE_MIN_FREQ per symbol */
void mule_model_range(const mule_model *m, int sym, uint32_t *start, uint32_t *freq);
/* the symbol whose coded range holds slot (decoder), its start and frequency; -1 if none */
int mule_model_find(const mule_model *m, uint32_t slot, uint32_t *start, uint32_t *freq);
/* adaptation after coding `sym` */
void mule_model_update(mule_model *m, int sym);

#endif
