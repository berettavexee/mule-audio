/* MULE encoder, internal interface between its modules (not installed, not part of the API):
 *
 *   enc.c      settings, coding operations, measurement trace, frame coding, the API
 *   enc_dsp.c  forward MDCT, FFT power spectrum, window shapes
 *   enc_psy.c  transient detector (block types), psychoacoustic masks
 *   enc_tcq.c  TCQ: the Viterbi searches, one band's coefficients
 *   enc_ogg.c  the Ogg MULE file: headers, packets (rANS), pages
 *
 * Floating point is fine in the encoder: only the decoder must be exact (core/dec.c). */
#ifndef MULE_ENC_INT_H
#define MULE_ENC_INT_H

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "mule.h"
#include "mule_enc.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define NB MULE_NB
#define F MULE_F
#define TIE_EPS 1e-9     /* tie rule of the decisions (sums in another order would differ) */

/* Band edges in units of 8 long-frame lines (spec 5); a short window's band b spans
 * EDGES[b] .. EDGES[b + 1] of its 128 lines. */
static const int EDGES[NB + 2] = MULE_EDGES_INIT;
static const int64_t POW4[4] = {256, 304, 362, 431};   /* 2^(i/4) in Q8: inter-frame rescaling */

/* ---------------------------------------------------------------- small helpers */

/* An input sample as the encoder reads it: NaN and infinities (a damaged source) as silence,
 * every finite value as it is. */
static inline double pcm_sample(double v)
{
    return isfinite(v) ? v : 0.0;
}

/* floor(log2(v)), v >= 1. */
static inline int ilog2(uint32_t v)
{
    int k = 0;
    while (v >>= 1)
        k++;
    return k;
}

/* floor(a / b) for b > 0. */
static inline int floor_div(int a, int b)
{
    return a >= 0 ? a / b : -((-a + b - 1) / b);
}

/* Spectral flatness of v[0..n) in dB: geometric over arithmetic mean (0: flat, < 0: tonal). */
static inline double flatness_db(const double *v, int n)
{
    double ar = 0, lg = 0;
    for (int i = 0; i < n; i++) {
        ar += v[i];
        lg += log(v[i] + 1e-30);
    }
    ar /= n;
    double geo = exp(lg / n);
    return 10 * log10((geo + 1e-30) / (ar + 1e-30));
}

/* A band's class for the contexts: 0 below band 8, 1 below band 16, 2 above. */
static inline int band_class(int b)
{
    return b < 8 ? 0 : (b < 16 ? 1 : 2);
}

/* The neighbourhood measure of a coefficient to one of the 6 magnitude contexts (as dec.c). */
static inline int nc_map(int64_t m)
{
    static const int t[9] = {0, 1, 2, 3, 3, 4, 4, 4, 4};
    return m < 9 ? t[m] : 5;
}

/* A group of windows: type 0, the long frame's one window; type 1, short windows [k0, k1). */
typedef struct {
    int type, k0, k1;
} group;

/* The number of coefficients of band b in group g. */
static inline int band_n(const group *g, int b)
{
    return g->type == 0 ? (EDGES[b + 1] - EDGES[b]) * 8 : (EDGES[b + 1] - EDGES[b]) * (g->k1 - g->k0);
}

/* The place in X of band b's coefficient i in group g (window, then frequency; short frames lay
 * X out as [8][128]). */
static inline int coef_index(const group *g, int b, int i)
{
    if (g->type == 0)
        return EDGES[b] * 8 + i;
    int w = EDGES[b + 1] - EDGES[b];
    return (g->k0 + i / w) * 128 + EDGES[b] + i % w;
}

/* ---------------------------------------------------------------- coding operations (enc.c) */

/* The coding operations of the whole signal, in the decoder's reading order: m[i] >= 0 is a
 * symbol v[i] of model m[i]; m[i] = -n a raw value v[i] of n bits. */
typedef struct {
    int32_t *m;
    uint32_t *v;
    int64_t n, cap;
    int err;                    /* an allocation failed: the operations are incomplete */
    int esc;                    /* the coefficients' escape symbol: 7 (coef_a8), 15 (16 symbols) */
    mule_models *mr;            /* RD allocation: models tracked as the decoder adapts them */
} ops_t;

/* Appends one operation, growing the arrays; on failure sets err (checked at the end). */
int ops_add(ops_t *o, int32_t m, uint32_t v);

/* A symbol of stream `stream`, context `ctx`; the tracked models (RD choices) adapt to it as
 * the decoder's will. */
static inline void put(ops_t *o, int stream, int ctx, int sym)
{
    ops_add(o, mule_stream_off[stream] + ctx, (uint32_t)sym);
    if (o->mr)
        mule_model_update(&o->mr->m[mule_stream_off[stream] + ctx], sym);
}

/* The cost in bits of a symbol under the tracked models, now (no update). */
static inline double sym_bits(const ops_t *o, int stream, int ctx, int sym)
{
    uint32_t st, fr;
    mule_model_range(&o->mr->m[mule_stream_off[stream] + ctx], sym, &st, &fr);
    return MULE_PROB_BITS - log2((double)fr);
}

/* `bits` raw bits of value v. */
static inline void raw(ops_t *o, int bits, uint32_t v)
{
    ops_add(o, -bits, v);
}

/* ---------------------------------------------------------------- measurement trace (enc.c) */

/* Encoder-only trace of the coefficient and energy symbols, for the context measurements
 * (eval/ctx_lab.py); NULL (the default) records nothing and changes nothing in the stream.
 * One record of MULE_TRACE_W int32 per symbol, see mule_encode_trace (mule_enc.h). Not
 * thread-safe: one traced encode at a time per process. */
typedef struct {
    int32_t *r;
    int64_t n, cap;
    int err, frame, ch;
} trace_t;
extern trace_t *mule_enc_trace;

/* Appends one record to mule_enc_trace (missing fields 0). */
void trace_add(const int32_t *rec);

/* v saturated to int32 (trace fields). */
static inline int32_t clip32(int64_t v)
{
    return v > INT32_MAX ? INT32_MAX : (int32_t)v;
}

/* ---------------------------------------------------------------- enc_dsp.c */

/* The tables of an n-point MDCT through an n-point complex FFT (also the FFT power spectrum). */
typedef struct {
    int n;
    double *cr, *ci;           /* FFT twiddles e^{-2 pi i k / n} */
    double *pre_r, *pre_i;     /* e^{-i pi j / n} */
    double *post_r, *post_i;   /* e^{-2 pi i n0 (k+1/2)/n} sqrt(2/M) */
    int *rev;
} mdct_t;

int mdct_init(mdct_t *t, int n);
void mdct_free(mdct_t *t);
void mdct_fwd(const mdct_t *t, const double *x, double *X);
void fft_power(const mdct_t *t, const double *x, double *pw);
double win_slope(int i, int s);
double win_half(int i, int h, int s);

/* ---------------------------------------------------------------- enc_psy.c */

/* The psychoacoustic model's tables for one transform size: band centres (Bark), the spreading
 * between bands, the threshold in quiet per coefficient, the bands' widths. */
typedef struct {
    double zc[NB], spread[NB][NB], ath[NB];
    double fc[NB];              /* band centres (Hz): spread_mode 1 */
    int width[NB], m;
} psy_t;

#define TR_FC 3000.0    /* the transient detector's first pass: high-passed at 3 kHz */
int block_types(const double *x, int64_t L, int T, uint8_t *types, double ratio_db, double fc, int add,
                double decay_db);
void hf_tonal_veto(const double *pcm, int64_t L, int T, uint8_t *types, const uint8_t *first,
                   double ton_db, const mdct_t *ml);
void psy_init(psy_t *p, int m);
void psy_fine(const psy_t *p, const mule_enc_params *pr, const double *X, const double *flat,
              double *mask);
void psy_masks(const psy_t *p, const mule_enc_params *pr, const double *P, const double *flat,
               double *mask, double noise_flat);
void psy_dynalloc(const mule_enc_params *pr, const double *P, double *mask);

/* ---------------------------------------------------------------- enc_tcq.c */

/* What band_code needs about a band. */
typedef struct {
    const double *Y;            /* coded channel's coefficients */
    const group *g;
    int b, type, inter, e;      /* band, block type, inter-frame prediction and its exponent */
    const int *ylong;           /* last long frame's indices (inter-frame prediction) */
    double rms, dz;
    double tcq_lam;
    double mtq;                 /* tcq_rd: the band's noise target (mask * tq) */
    const mule_enc_params *pr;
    double *nf_acc;             /* v4: sum of the zero coefficients' (x / (D/2))^2, count */
} band_in;

int tcq_viterbi_chain(const double *x, const double *w, const int *ac, int n, double c,
                      const ops_t *o, const int64_t *pm, int64_t t1_0, int64_t t2_0, int ns,
                      int mask, int st0, int64_t *kout);
void band_prep(const band_in *in, int a, double *xt, int64_t *pmv, int *ac, double *u, double *lam);
void band_code(const band_in *in, int a, int64_t *tail1, int64_t *tail2, ops_t *o, int emit,
               int *ycur, double *bits, double *noise, const int64_t *klev, int *tst_io);

/* ---------------------------------------------------------------- enc_ogg.c */

int ogg_write(const mule_enc_params *pr, const ops_t *o, const int64_t *fstart, int T, int64_t L,
              const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
              size_t *audio_bytes);

#endif
