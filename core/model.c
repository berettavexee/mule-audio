/* Adaptive multi-symbol models (spec 3), shared by the encoder and the decoder: 15-bit CDFs
 * adapted after every symbol, AV1 style, every symbol keeping at least MULE_MIN_FREQ. Integer
 * code only (part of the device decoder). */
#include <string.h>
#include "model.h"

/* A model of n symbols with the uniform CDF, cdf[i] = 2^15 i / n (a stream without trained
 * initial table). */
void mule_model_init(mule_model *m, int n)
{
    memset(m, 0, sizeof *m);
    m->n = (uint8_t)n;
    for (int i = 0; i <= n; i++)
        m->cdf[i] = (uint16_t)((MULE_PROB_ONE * (uint32_t)i) / (uint32_t)n);
}

/* A model of n symbols from a trained CDF (n + 1 values). Its count starts at 16, so that it
 * skips the fastest adaptation rate, meant for models that start knowing nothing. */
void mule_model_init_cdf(mule_model *m, int n, const uint16_t *cdf)
{
    memset(m, 0, sizeof *m);
    m->n = (uint8_t)n;
    memcpy(m->cdf, cdf, sizeof(uint16_t) * (size_t)(n + 1));
    m->count = 16;
}

/* The decoder's search (mule_cdf_find, model.h) on a model. */
int mule_model_find(const mule_model *m, uint32_t slot, uint32_t *start, uint32_t *freq)
{
    return mule_cdf_find(m->cdf + 1, m->n, slot, start, freq);
}

/* The encoder's side of mule_model_find: the coded range [start, start + freq) of symbol sym. */
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
