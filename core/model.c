/* Adaptive multi-symbol models (spec 3), shared by the encoder and the decoder: 15-bit CDFs
 * adapted after every symbol, AV1 style, every symbol keeping at least MULE_MIN_FREQ. Integer
 * code only (part of the device decoder). */
#include <string.h>
#include "model.h"

/* A model of n symbols: uniform (init NULL) or from a trained CDF (n + 1 values); mule_cdf_init. */
static void model_init(mule_model *m, int n, const uint16_t *init)
{
    memset(m, 0, sizeof *m);
    m->n = (uint8_t)n;
    m->cdf[n] = (uint16_t)MULE_PROB_ONE;
    mule_cdf_init(m->cdf + 1, n, init, &m->count);
}

/* A model of n symbols with the uniform CDF (a stream without trained initial table). */
void mule_model_init(mule_model *m, int n)
{
    model_init(m, n, NULL);
}

/* A model of n symbols from a trained CDF (n + 1 values). */
void mule_model_init_cdf(mule_model *m, int n, const uint16_t *cdf)
{
    model_init(m, n, cdf);
}

/* The encoder's side of mule_cdf_find: the coded range [start, start + freq) of symbol sym. */
void mule_model_range(const mule_model *m, int sym, uint32_t *start, uint32_t *freq)
{
    const uint32_t span = MULE_PROB_ONE - (uint32_t)m->n * MULE_MIN_FREQ;
    uint32_t a = ((uint32_t)m->cdf[sym] * span >> MULE_PROB_BITS) + (uint32_t)sym * MULE_MIN_FREQ;
    uint32_t b = sym + 1 == m->n ? MULE_PROB_ONE
               : ((uint32_t)m->cdf[sym + 1] * span >> MULE_PROB_BITS) + (uint32_t)(sym + 1) * MULE_MIN_FREQ;
    *start = a;
    *freq = b - a;
}

/* Adaptation after symbol sym (mule_cdf_update, model.h). */
void mule_model_update(mule_model *m, int sym)
{
    mule_cdf_update(m->cdf + 1, m->n, &m->count, sym);
}
