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

/* The primitives, on a model's inner CDF entries c[0 .. n-2] = cdf[1 .. n-1] (cdf[0] = 0 and
 * cdf[n] = 2^15 are implied): the decoder keeps only those, packed (core/dec.c); the mule_model
 * functions below call them on a full model (the encoder). */

/* A model's initial state (spec 3, 4): the trained CDF init (n + 1 values) with a count of 16, so
 * that it skips the fastest adaptation rate, meant for models that start knowing nothing; NULL:
 * the uniform CDF, cdf[i] = 2^15 i / n, with a count of 0. */
static inline void mule_cdf_init(uint16_t *c, int n, const uint16_t *init, uint8_t *count)
{
    for (int i = 1; i < n; i++)
        c[i - 1] = init ? init[i] : (uint16_t)((MULE_PROB_ONE * (uint32_t)i) / (uint32_t)n);
    *count = init ? 16 : 0;
}

/* The symbol whose coded range [start, start + freq) holds slot (the rANS state's low 15 bits),
 * with that range; -1 if none (not possible with a valid model). The coded range is the CDF
 * scaled into 2^15 - n MULE_MIN_FREQ, plus MULE_MIN_FREQ per symbol below. */
static inline int mule_cdf_find(const uint16_t *c, int n, uint32_t slot, uint32_t *start, uint32_t *freq)
{
    const uint32_t span = MULE_PROB_ONE - (uint32_t)n * MULE_MIN_FREQ;
    uint32_t lo = 0;                            /* start of symbol 0: cdf[0] = 0 */
    for (int s = 0; s < n - 1; s++) {
        uint32_t hi = ((uint32_t)c[s] * span >> MULE_PROB_BITS) + (uint32_t)(s + 1) * MULE_MIN_FREQ;
        if (slot < hi) {
            *start = lo;
            *freq = hi - lo;
            return s;
        }
        lo = hi;
    }
    if (slot >= MULE_PROB_ONE)                  /* the last symbol ends at 2^15 */
        return -1;
    *start = lo;
    *freq = MULE_PROB_ONE - lo;
    return n - 1;
}

/* Adaptation after symbol sym: each CDF entry moves towards its target (0 below the symbol, 2^15
 * above) by 2^-rate of the distance. The rate is 4 for the first 16 symbols, then 5, then 6 past
 * 32, plus 1 for alphabets of more than 4 symbols: fast learning after a reset, stable after. */
static inline void mule_cdf_update(uint16_t *c, int n, uint8_t *count, int sym)
{
    int k = *count;                             /* read once: it may alias c for the compiler */
    int rate = 4 + (k > 15) + (k > 31) + (n > 4);
    int below = sym < n - 1 ? sym : n - 1;      /* entries 1 .. sym move down, the others up */
    int j = 0;                                  /* c[j] = cdf[j + 1] */
    for (; j < below; j++)                      /* two loops, no branch inside */
        c[j] -= (uint16_t)(c[j] >> rate);
    for (; j < n - 1; j++)
        c[j] += (uint16_t)((MULE_PROB_ONE - c[j]) >> rate);
    if (k < 32)
        *count = (uint8_t)(k + 1);
}

/* A model of n symbols: uniform, or from a trained CDF (n + 1 values) */
void mule_model_init(mule_model *m, int n);
void mule_model_init_cdf(mule_model *m, int n, const uint16_t *cdf);
/* Start (cumulative) and frequency of `sym` as coded: the CDF with MULE_MIN_FREQ per symbol */
void mule_model_range(const mule_model *m, int sym, uint32_t *start, uint32_t *freq);
/* adaptation after coding `sym` */
void mule_model_update(mule_model *m, int sym);

#endif
