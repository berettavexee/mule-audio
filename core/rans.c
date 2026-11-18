/* Encoder side of the entropy coding (not part of the device decoder: it allocates, and uses
 * libm): the rANS coder of a packet, the models' allocation, and the cost of a symbol stream. */
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "mule.h"

#define RANS_L (1u << 16)

/* rANS coding of one packet's operations (spec 2, "Décodage rANS"): 32-bit state, 16-bit words,
 * 15-bit probabilities. A forward pass gets each symbol's (start, freq) from the models, adapting
 * them as the decoder will; the symbols are then coded in reverse, so that the decoder reads
 * forward with no division. out: the final state (4 bytes, the decoder's initial one) then the
 * words in reading order. Returns the size, or -1 if it exceeds cap (or out of memory). */
int mule_rans_encode(mule_models *ms, const int32_t *model, const uint32_t *val, int64_t n,
                     uint8_t *out, int cap)
{
    uint16_t *st = malloc(sizeof *st * 2 * (size_t)(n ? n : 1));    /* start, freq per op */
    uint16_t *words = malloc(sizeof *words * (size_t)(cap / 2 + 2));
    if (!st || !words) {
        free(st);
        free(words);
        return -1;
    }
    for (int64_t i = 0; i < n; i++) {
        uint32_t start, freq;
        if (model[i] >= 0) {
            mule_model *m = &ms->m[model[i]];
            mule_model_range(m, (int)val[i], &start, &freq);
            mule_model_update(m, (int)val[i]);
        } else {
            int bits = -model[i];
            freq = 1u << (MULE_PROB_BITS - bits);
            start = val[i] * freq;
        }
        st[2 * i] = (uint16_t)start;
        st[2 * i + 1] = (uint16_t)(freq - 1);     /* freq <= 2^15: fits as freq - 1 */
    }
    uint32_t x = RANS_L;
    int nw = 0, maxw = cap / 2 + 2;
    int ok = 1;
    for (int64_t i = n - 1; i >= 0; i--) {
        uint32_t start = st[2 * i], freq = (uint32_t)st[2 * i + 1] + 1;
        uint32_t xmax = ((RANS_L >> MULE_PROB_BITS) << 16) * freq;
        if (x >= xmax) {
            if (nw >= maxw) {
                ok = 0;
                break;
            }
            words[nw++] = (uint16_t)(x & 0xffff);
            x >>= 16;
        }
        x = ((x / freq) << MULE_PROB_BITS) + (x % freq) + start;
    }
    int size = 4 + 2 * nw;
    if (!ok || size > cap) {
        free(st);
        free(words);
        return -1;
    }
    out[0] = (uint8_t)x;
    out[1] = (uint8_t)(x >> 8);
    out[2] = (uint8_t)(x >> 16);
    out[3] = (uint8_t)(x >> 24);
    for (int k = 0; k < nw; k++) {                  /* emitted last-first: reversed for reading */
        uint16_t w = words[nw - 1 - k];
        out[4 + 2 * k] = (uint8_t)w;
        out[5 + 2 * k] = (uint8_t)(w >> 8);
    }
    free(st);
    free(words);
    return size;
}

/* A set of models on the heap, reset to the initial CDFs. */
mule_models *mule_models_alloc(void)
{
    mule_models *ms = malloc(sizeof *ms);
    if (ms)
        mule_models_reset(ms);
    return ms;
}

/* Frees a set made by mule_models_alloc. */
void mule_models_free(mule_models *ms)
{
    free(ms);
}

/* dst = src (the encoder's snapshot before trying a packet). */
void mule_models_copy(mule_models *dst, const mule_models *src)
{
    memcpy(dst, src, sizeof *dst);
}

/* See mule.h: the bits of the stream, each symbol costing 15 - log2(freq) of its coded range
 * under the adapting model. */
double mule_stream_cost_init(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym,
                             int64_t len, const int64_t *resets, int64_t nresets,
                             const uint16_t *init)
{
    mule_model *ms = malloc(sizeof *ms * (size_t)nctx);
    if (!ms)
        return -1.0;
    double bits = 0.0;
    int64_t r = 0;
    for (int64_t i = 0; i < len; i++) {
        if (i == 0 || (r < nresets && resets[r] == i)) {
            for (int c = 0; c < nctx; c++) {
                if (init)
                    mule_model_init_cdf(&ms[c], nsyms, init + (size_t)c * (size_t)(nsyms + 1));
                else
                    mule_model_init(&ms[c], nsyms);
            }
            while (r < nresets && resets[r] <= i)
                r++;
        }
        uint32_t start, freq;
        mule_model *m = &ms[ctx[i]];
        mule_model_range(m, sym[i], &start, &freq);
        bits += MULE_PROB_BITS - log2((double)freq);
        mule_model_update(m, sym[i]);
    }
    free(ms);
    return bits;
}

/* mule_stream_cost_init with uniform initial models. */
double mule_stream_cost(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym, int64_t len,
                        const int64_t *resets, int64_t nresets)
{
    return mule_stream_cost_init(nsyms, nctx, ctx, sym, len, resets, nresets, NULL);
}
