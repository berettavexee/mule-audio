/* MULE format constants, model layout and public API (spec/FORMAT.md is normative). */
#ifndef MULE_H
#define MULE_H

#include <stddef.h>
#include <stdint.h>
#include "model.h"

#define MULE_VERSION      2             /* 2: TCQ shape quantizer (v1: scalar; v0: 480 contexts) */
#define MULE_F            1024          /* frame hop */
#define MULE_N_LONG       2048
#define MULE_N_SHORT      256
#define MULE_N_SUB        8
#define MULE_SHORT_OFF    448
#define MULE_NB           22            /* coded bands */
#define MULE_QMIN         (-100)
#define MULE_QMAX         20
#define MULE_Q_RESET      (-40)
#define MULE_A_RESET      20
#define MULE_A0           9
#define MULE_AMAX         47            /* allocations: 0 (noise) .. MULE_AMAX (spec 5.2) */
#define MULE_KEY_FRAMES   40
#define MULE_PACKET_MAX   8192
#define MULE_PRE_SKIP     1024
#define MULE_HEAD_LEN     20
#define MULE_LCG_SEED     0x2545F491u

/* Shape quantizer (v2): 8-state TCQ (JPEG 2000 part 2 trellis), levels k * D / 2; even states use
 * even k, odd states odd k; the subset k mod 4 picks the next state. */
static const int mule_tcq_next[8][2] = {{0, 1}, {2, 3}, {4, 5}, {6, 7}, {0, 1}, {2, 3}, {4, 5}, {6, 7}};
static const int mule_tcq_subset[8][2] = {{0, 2}, {1, 3}, {2, 0}, {3, 1}, {2, 0}, {3, 1}, {0, 2}, {1, 3}};
/* next state after level k from state s */
static inline int mule_tcq_step(int s, int64_t k)
{
    int j = (int)(((k % 4) + 4) % 4);
    return mule_tcq_subset[s][0] == j ? mule_tcq_next[s][0] : mule_tcq_next[s][1];
}

/* models: streams in this order, each nctx contexts of nsyms symbols (same order in Python) */
enum {
    MULE_S_BTYPE, MULE_S_ALPHA, MULE_S_STEREO, MULE_S_ENERGY, MULE_S_ALLOC, MULE_S_AMODE,
    MULE_S_CESC, MULE_S_COEF, MULE_S_EAESC, MULE_S_COUNT
};
extern const int mule_stream_nsyms[MULE_S_COUNT];
extern const int mule_stream_nctx[MULE_S_COUNT];
extern const int mule_stream_off[MULE_S_COUNT];  /* first model of each stream */
extern const int mule_init_cdf_id;               /* MULEHead byte 19 of the built-in tables */
#define MULE_NMODELS (1 + 1 + 3 + 9 + 6 + 1 + 16 + 96 + 1)

/* models state shared by the encoder and the decoder */
typedef struct {
    mule_model m[MULE_NMODELS];
} mule_models;
void mule_models_reset(mule_models *ms);        /* trained initial CDFs (init_cdf.h) */
mule_models *mule_models_alloc(void);           /* reset */
void mule_models_free(mule_models *ms);
void mule_models_copy(mule_models *dst, const mule_models *src);

/* ---- encoder back end: one packet of coding operations -> rANS payload ----
 * op i: model[i] >= 0: symbol val[i] with that model (adapted); model[i] = -n (1..15): n raw
 * bits val[i]. Returns the payload size, or -1 if it does not fit in cap. */
int mule_rans_encode(mule_models *ms, const int32_t *model, const uint32_t *val, int64_t n,
                     uint8_t *out, int cap);
/* Cost in bits of a symbol stream coded with adaptive models (CDF training, eval/train_cdf.py):
 * model ctx[i] codes sym[i]; nctx models of nsyms symbols, all reset at the positions listed in
 * resets (sorted) to init[c * (nsyms + 1) + i] (init NULL: uniform). -1 if out of memory. */
double mule_stream_cost_init(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym,
                             int64_t len, const int64_t *resets, int64_t nresets,
                             const uint16_t *init);
double mule_stream_cost(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym, int64_t len,
                        const int64_t *resets, int64_t nresets);       /* the same, uniform */

/* ---- decoder (core/dec.c): integers only (no floating point, no libm), int16 output; the
 * format's reference, and core B's decoder ---- */
typedef struct mule_dec_state mule_dec;
/* A decoder in caller-provided memory of mule_dec_size() bytes (no allocation), from the
 * MULEHead packet; NULL if invalid or not readable here (version, unknown CDF table: byte 19). */
mule_dec *mule_dec_init(void *mem, size_t size, const uint8_t *head, int len);
size_t mule_dec_size(void);
/* The same on the heap (not built with MULE_NO_MALLOC). */
mule_dec *mule_dec_new(const uint8_t *head, int len);
void mule_dec_free(mule_dec *d);
int mule_dec_channels(const mule_dec *d);
int mule_dec_pre_skip(const mule_dec *d);
/* Decodes one audio packet into pcm (interleaved int16, up to max_samples per channel).
 * Returns the samples per channel written (1024 per frame), 0 for a packet dropped while
 * waiting for a key packet after mule_dec_seek(), < 0 on error. */
int mule_dec_packet(mule_dec *d, const uint8_t *p, int len, int16_t *pcm, int max_samples);
/* After a jump in the stream: drop packets until a key packet, then its first frame. */
void mule_dec_seek(mule_dec *d);
/* An external FFT for the IMDCT (HIFIACC on the device): re/im hold 2^bits complex values
 * (bits 9 or 6) in bit-reversed order; it writes their forward FFT, unscaled, in natural order
 * and returns 1, or returns 0 to leave it to the software FFT. NULL: software only. */
void mule_dec_set_fft(int (*fft)(int32_t *re, int32_t *im, int bits));

#endif
