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

/* The decoder's search: the symbol whose coded range [start, start + freq) holds slot (the rANS
 * state's low 15 bits), with that range; -1 if none (not possible with a valid model). The coded
 * range is the CDF scaled into 2^15 - n MULE_MIN_FREQ, plus MULE_MIN_FREQ per symbol below. */
int mule_model_find(const mule_model *m, uint32_t slot, uint32_t *start, uint32_t *freq)
{
    const uint32_t span = MULE_PROB_ONE - (uint32_t)m->n * MULE_MIN_FREQ;
    uint32_t lo = 0;                            /* start of symbol 0: cdf[0] = 0 */
    for (int s = 0; s < m->n; s++) {
        uint32_t hi = s + 1 == m->n ? MULE_PROB_ONE
                    : ((uint32_t)m->cdf[s + 1] * span >> MULE_PROB_BITS) + (uint32_t)(s + 1) * MULE_MIN_FREQ;
        if (slot < hi) {
            *start = lo;
            *freq = hi - lo;
            return s;
        }
        lo = hi;
    }
    return -1;
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

/* Adaptation after symbol sym: each CDF entry moves towards its target (0 below the symbol, 2^15
 * above) by 2^-rate of the distance. The rate is 4 for the first 16 symbols, then 5, then 6 past
 * 32, plus 1 for alphabets of more than 4 symbols: fast learning after a reset, stable after. */
void mule_model_update(mule_model *m, int sym)
{
    int rate = 4 + (m->count > 15) + (m->count > 31) + (m->n > 4);
    int i = 1;
    for (; i <= sym && i < m->n; i++)           /* two loops, no branch inside */
        m->cdf[i] -= (uint16_t)(m->cdf[i] >> rate);
    for (; i < m->n; i++)
        m->cdf[i] += (uint16_t)((MULE_PROB_ONE - m->cdf[i]) >> rate);
    if (m->count < 32)
        m->count++;
}
