/* MULE format constants, model layout and public API (spec/FORMAT.md is normative). */
#ifndef MULE_H
#define MULE_H

#include <stddef.h>
#include <stdint.h>
#include "model.h"

#define MULE_VERSION      3             /* 3: chained trellis of 8-64 states, 8-symbol coefficients;
                                         * 2: TCQ (decoded too); 1: scalar; 0: 480 contexts */
#define MULE_F            1024          /* frame hop */
#define MULE_N_LONG       2048
#define MULE_N_SHORT      256
#define MULE_N_SUB        8
#define MULE_SHORT_OFF    448
/* the band edges of format v3 (22 bands), also the parents of the probes' split bands */
#define MULE_EDGES22_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 100, 116, 128}
#ifdef MULE_BANDS24                     /* v4 probes (compile time, a separate build, N-LOG.md): */
#define MULE_SPLIT 3                    /* bands 20 and 21 each cut in two */
#endif
#if defined(MULE_SPLIT) && MULE_SPLIT == 3
#define MULE_NB           24
#define MULE_EDGES_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 89, 100, \
                         108, 116, 128}
#elif defined(MULE_SPLIT) && MULE_SPLIT == 1    /* band 20 only */
#define MULE_NB           23
#define MULE_EDGES_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 89, 100, \
                         116, 128}
#elif defined(MULE_SPLIT) && MULE_SPLIT == 4    /* 24 bands: bands 19 and 20 cut in two */
#define MULE_NB           24
#define MULE_EDGES_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 69, 78, 89, \
                         100, 116, 128}
#elif defined(MULE_SPLIT) && MULE_SPLIT == 5    /* 24 bands: five even bands from 10.3 to 20 kHz */
#define MULE_NB           24
#define MULE_EDGES_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 71, 82, 93, \
                         104, 116, 128}
#elif defined(MULE_SPLIT) && MULE_SPLIT == 2    /* band 21 only */
#define MULE_NB           23
#define MULE_EDGES_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 100, 108, \
                         116, 128}
#else
#define MULE_NB           22            /* coded bands */
/* the band edges in units of 8 long-frame lines (spec 5), the last one past the coded bands */
#define MULE_EDGES_INIT {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 34, 40, 48, 60, 78, 100, 116, 128}
#endif
#define MULE_QMIN         (-100)
#define MULE_QMAX         20
#define MULE_Q_RESET      (-40)
#define MULE_A_RESET      20
#define MULE_A0           9
#define MULE_AMAX         47            /* allocations: 0 (noise) .. MULE_AMAX (spec 5.2) */
#define MULE_KEY_FRAMES   40
#define MULE_PACKET_MAX   8192
#define MULE_PRE_SKIP     1024
#define MULE_HEAD_LEN     22            /* v3; v2: 20 */
#define MULE_HEAD_LEN_V2  20
#define MULE_LCG_SEED     0x2545F491u

/* Shape quantizer: TCQ, levels k * D / 2; even states use even k, odd states odd k (no zero).
 * Trellis of n states (8 in v2; 8, 16, 32 or 64 in v3) and mask: from state s, branch bit br leads to
 * (2 s + br) mod n and uses the subset j = (s & 1) + 2 (br ^ parity(s & mask)) (k mod 4 = j).
 * v2's trellis (JPEG 2000 part 2) is n = 8, mask 0x6. */
#define MULE_TCQ_MAXS     64
/* v3 header: byte 20 log2(states) (3..6), byte 21 flags; the encoder sets both flags */
#define MULE_TCQ_CHAIN    1             /* v3 flag: the trellis state runs on across the bands */
#define MULE_COEF_A8      2             /* v3 flag: coefficient alphabet of 8 symbols (escape 7) */
#define MULE_NF_CODED     4             /* v4 probe flag: noise in the zero coefficients of coded
                                         * bands from MULE_NF_START up, at a level sent per channel
                                         * and frame (3 raw bits before the channel's energies) */
#define MULE_NF_START     12            /* first band with noise in its zero coefficients (2.8 kHz) */
#define MULE_FOLD         8             /* v4 probe flag: a zero-bit band from the header's band
                                         * (byte 22) up is filled from the decoded lines just below
                                         * it, mixed with noise (byte 23, bits 0-3: 0 fold .. 8
                                         * noise; bit 4: decided per channel and frame, 1 raw bit
                                         * after the noise level of MULE_NF_CODED) */
#define MULE_HEAD_LEN_FOLD 24           /* the header with MULE_FOLD */
#define MULE_ROT          32            /* v4 probe flag: coded bands at low allocations rotated
                                         * after decoding (Opus' spreading): byte 24 the angle at
                                         * allocation 1 (degrees; halved every 2 allocations),
                                         * byte 25 the last allocation rotated, byte 26 the first
                                         * band, byte 27 bit 0: a 2-bit spreading level per
                                         * channel and frame (0 none, 1-3: 0.5, 1, 1.5 times the
                                         * angle; else always 1) */
#define MULE_HEAD_LEN_ROT 28            /* the header with MULE_ROT */
#define MULE_TNF          64            /* v4 probe flag: in long frames, the noise of zero-bit
                                         * bands shaped in time by an all-pole filter along the
                                         * frequencies (TNS on the noise only): per channel and
                                         * long frame 1 raw bit, then the order (3 bits, 1-8) and
                                         * 4-bit reflection coefficients sin(i pi / 16), i - 7;
                                         * lines from band byte 28 up */
#define MULE_HEAD_LEN_TNF 30            /* the header with MULE_TNF */
#define MULE_TNF_MAXP     8
#define MULE_SLOPE        16            /* v4 probe flag: in long frames, the noise of a zero-bit
                                         * band from band byte 30 (bits 0-4) up follows the slope
                                         * (in dB) of the neighbouring bands' levels, Vorbis'
                                         * floor-like; the band's energy unchanged; +-12 dB at the
                                         * band's ends at most. Byte 30 bit 5: +-6 dB at most;
                                         * bit 6: only between two heard neighbours (else flat);
                                         * bit 7: the top band falls by 4 dB across at least */
#define MULE_HEAD_LEN_SLOPE 31          /* the header with MULE_SLOPE */
#define MULE_SUBPART      128           /* v4 probe flag: in long frames, a coded band from band
                                         * byte 31 up, of at least 2 subpartitions (4 units, 32
                                         * lines; the last takes the rest), may leave some to noise
                                         * (Vorbis' residue classes; their noise at most a quarter
                                         * of the band's level unit D/2): after the channel's
                                         * allocations, per such band a flag (any left; stream
                                         * MULE_S_SPART, context 0), then one per subpartition
                                         * (1: noise; context 1 + the previous subpartition's). Those lines are skipped by
                                         * the coefficients; their noise has the band's energy less
                                         * the coded lines' */
#define MULE_HEAD_LEN_SUBPART 32        /* the header with MULE_SUBPART */
#define MULE_SP_UNITS     4
/* Subpartition s of a band of w units (of n = w / 4): units [lo, hi) from the band's start. */
static inline int mule_sp_n(int w) { return w / MULE_SP_UNITS; }
static inline int mule_sp_lo(int s) { return MULE_SP_UNITS * s; }
static inline int mule_sp_hi(int w, int s) { return s == mule_sp_n(w) - 1 ? w : MULE_SP_UNITS * (s + 1); }
/* The lines of band (e0, e1) (units) left by the subpartition mask sp: the count, or the place of
 * the i-th (long frames: 8 lines per unit). */
static inline int mule_sp_count(int e0, int e1, uint32_t sp)
{
    int w = e1 - e0, n = 8 * w;
    for (int s = 0; sp && s < mule_sp_n(w); s++)
        if (sp >> s & 1)
            n -= 8 * (mule_sp_hi(w, s) - mule_sp_lo(s));
    return n;
}
static inline int mule_sp_index(int e0, int e1, uint32_t sp, int i)
{
    int w = e1 - e0;
    for (int s = 0; s < mule_sp_n(w); s++) {
        int len = 8 * (mule_sp_hi(w, s) - mule_sp_lo(s));
        if (sp >> s & 1)
            continue;
        if (i < len)
            return 8 * (e0 + mule_sp_lo(s)) + i;
        i -= len;
    }
    return 8 * e0 + i;                          /* (not reached with i < mule_sp_count) */
}
static inline int mule_tcq_mask(int n)
{
    return n == 64 ? 0x33 : (n == 32 ? 0x17 : (n == 16 ? 0xD : 0x6));
}
static inline int mule_tcq_par(int v)
{
    v ^= v >> 8;
    v ^= v >> 4;
    v ^= v >> 2;
    v ^= v >> 1;
    return v & 1;
}
/* subset of branch br from state s */
static inline int mule_tcq_sub(int s, int br, int mask)
{
    return (s & 1) + 2 * (br ^ mule_tcq_par(s & mask));
}
/* next state after level k from state s */
static inline int mule_tcq_step_n(int s, int64_t k, int n, int mask)
{
    int j = (int)(((k % 4) + 4) % 4);
    return (2 * s + ((j >> 1) ^ mule_tcq_par(s & mask))) & (n - 1);
}
static inline int mule_tcq_step(int s, int64_t k)       /* v2's 8-state trellis */
{
    return mule_tcq_step_n(s, k, 8, 0x6);
}

/* models: streams in this order, each nctx contexts of nsyms symbols (same order in Python) */
enum {
    MULE_S_BTYPE, MULE_S_ALPHA, MULE_S_STEREO, MULE_S_ENERGY, MULE_S_ALLOC, MULE_S_AMODE,
    MULE_S_CESC, MULE_S_COEF, MULE_S_EAESC,
    MULE_S_SPART,       /* v4 probe (MULE_SUBPART): its flags; uniform start, no trained table */
    MULE_S_COUNT
};
extern const int mule_stream_nsyms[MULE_S_COUNT];
extern const int mule_stream_nctx[MULE_S_COUNT];
extern const int mule_stream_off[MULE_S_COUNT];  /* first model of each stream */
extern const int mule_init_cdf_id;               /* MULEHead byte 19 of the built-in tables */
#define MULE_NMODELS (1 + 1 + 3 + 9 + 6 + 1 + 16 + 96 + 1 + 3)

/* models state shared by the encoder and the decoder */
typedef struct {
    mule_model m[MULE_NMODELS];
} mule_models;
void mule_models_reset(mule_models *ms);        /* trained initial CDFs (init_cdf.h) */
void mule_models_reset_a8(mule_models *ms, int a8);  /* the same; a8: 8-symbol coefficients */
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
/* mule_stream_cost_init, each symbol's bits also written to each[i] (each NULL: not). */
double mule_stream_cost_each(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym,
                             int64_t len, const int64_t *resets, int64_t nresets,
                             const uint16_t *init, double *each);
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
