/* MULE encoder, the reference encoder: audio (44.1 kHz stereo, double) to a complete Ogg MULE
 * file in memory. Floating point is fine here: only the decoder must be exact (core/dec.c).
 *
 * Per frame of 1024 samples: block type (transient detector), forward MDCT, psychoacoustic masks
 * per band, stereo choice per band, energies, allocations (from the masks, then a
 * rate-distortion choice with exact model costs), TCQ levels (Viterbi), all as "coding
 * operations"; then packets of up to 4 frames are rANS-coded (core/rans.c) and put in Ogg pages.
 * With rd_lambda, tcq_rd, fine_p and pre_db off, its decisions are those of the Python
 * prototype (py/mule/encoder.py), exactly (tests/test_cenc.py). */
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "mule.h"
#include "mule_enc.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define NB MULE_NB
#define F MULE_F
#define TIE_EPS 1e-9     /* same tie rule as the Python encoder (sums in another order) */
static const int EDGES[NB + 2] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28,
                                  34, 40, 48, 60, 78, 100, 116, 128};
static const int ALPHAS[4] = {0, 16, 26, 31};
static const int64_t POW4[4] = {256, 304, 362, 431};   /* 2^(i/4) in Q8: inter-frame rescaling */

/* The production settings (core/mule_enc.h documents each). */
void mule_enc_defaults(mule_enc_params *p)
{
    memset(p, 0, sizeof *p);
    p->q_db = -9.0;
    p->keyframe = 40;
    p->groups = 0;              /* adaptive */
    p->group_db = 6.0;
    p->stereo = 0;              /* auto */
    p->ath_db = 0.0;
    p->tonal_all = 0;
    p->low_db = 10.0;
    p->mid_db = 4.0;
    p->mid_hi = 17;
    p->ton_scale = 20.0;
    p->tcap_db = 25.0;
    p->alloc_auto = 1;
    p->alloc_hyst = 1;
    p->fft_tonal = 1;
    p->fft_noise_db = 4.0;
    p->rd_lambda = 2.0;
    p->tcq_lam = 0.3;
    p->tcq_rd = 1;              /* axes 1 and 3 (eval/results/E-LOG.md) */
    p->tcq_rdl = 0.5;
    p->fine_p = 8.0;
    p->fine_w = 1;
    p->fine_nb = 12;
    p->pre_db = 10.0;           /* axis 2 (eval/results/E2-LOG.md) */
    p->nf_bias = 0;
}

/* ---------------------------------------------------------------- coding operations */

/* The coding operations of the whole signal, in the decoder's reading order: m[i] >= 0 is a
 * symbol v[i] of model m[i]; m[i] = -n a raw value v[i] of n bits. */
typedef struct {
    int32_t *m;
    uint32_t *v;
    int64_t n, cap;
    int err;                    /* an allocation failed: the operations are incomplete */
    mule_models *mr;            /* RD allocation: models tracked as the decoder adapts them */
} ops_t;

/* Appends one operation, growing the arrays; on failure sets err (checked at the end). */
static int ops_add(ops_t *o, int32_t m, uint32_t v)
{
    if (o->n == o->cap) {
        int64_t c = o->cap ? 2 * o->cap : 1 << 16;
        int32_t *nm = realloc(o->m, sizeof *nm * (size_t)c);
        if (!nm) {
            o->err = 1;
            return -1;
        }
        o->m = nm;                              /* kept at once: the old block is gone */
        uint32_t *nv = realloc(o->v, sizeof *nv * (size_t)c);
        if (!nv) {
            o->err = 1;
            return -1;
        }
        o->v = nv;
        o->cap = c;
    }
    o->m[o->n] = m;
    o->v[o->n] = v;
    o->n++;
    return 0;
}

/* A symbol of stream `stream`, context `ctx`; the tracked models (RD choices) adapt to it as
 * the decoder's will. */
static void put(ops_t *o, int stream, int ctx, int sym)
{
    ops_add(o, mule_stream_off[stream] + ctx, (uint32_t)sym);
    if (o->mr)
        mule_model_update(&o->mr->m[mule_stream_off[stream] + ctx], sym);
}

/* The cost in bits of a symbol under the tracked models, now (no update). */
static double sym_bits(const ops_t *o, int stream, int ctx, int sym)
{
    uint32_t st, fr;
    mule_model_range(&o->mr->m[mule_stream_off[stream] + ctx], sym, &st, &fr);
    return MULE_PROB_BITS - log2((double)fr);
}

/* `bits` raw bits of value v. */
static void raw(ops_t *o, int bits, uint32_t v)
{
    ops_add(o, -bits, v);
}

/* floor(log2(v)), v >= 1. */
static int ilog2(uint32_t v)
{
    int k = 0;
    while (v >>= 1)
        k++;
    return k;
}

/* A residual d of the energy or allocation alphabets (spec 5.4): -7 .. 7 as symbols 0 .. 14,
 * else the escape 15, an Exp-Golomb magnitude from 8 and a sign bit. */
static void signed_ops(ops_t *o, int stream, int ctx, int d)
{
    if (d >= -7 && d <= 7) {
        put(o, stream, ctx, d + 7);
        return;
    }
    put(o, stream, ctx, 15);
    uint32_t v = (uint32_t)(abs(d) - 8);
    int k = ilog2(v + 1);
    put(o, MULE_S_EAESC, 0, k);
    if (k)
        raw(o, k, v + 1 - (1u << k));
    raw(o, 1, d < 0);
}

/* A growable byte buffer (the Ogg file, the comment packet). */
typedef struct {
    uint8_t *b;
    size_t n, cap;
} buf_t;

/* Appends n bytes; -1 if out of memory (the buffer is then left as it was). */
static int buf_put(buf_t *b, const void *p, size_t n)
{
    if (b->n + n > b->cap) {
        size_t c = b->cap ? b->cap : 1 << 16;
        while (c < b->n + n)
            c *= 2;
        uint8_t *nb = realloc(b->b, c);
        if (!nb)
            return -1;
        b->b = nb;
        b->cap = c;
    }
    memcpy(b->b + b->n, p, n);
    b->n += n;
    return 0;
}

/* ---------------------------------------------------------------- MDCT (forward) */

typedef struct {
    int n;
    double *cr, *ci;           /* FFT twiddles e^{-2 pi i k / n} */
    double *pre_r, *pre_i;     /* e^{-i pi j / n} */
    double *post_r, *post_i;   /* e^{-2 pi i n0 (k+1/2)/n} sqrt(2/M) */
    int *rev;
} mdct_t;

/* The tables of an n-point MDCT (n = 2048 or 256) through an n-point complex FFT; -1 if out of
 * memory (mdct_free frees what was allocated). */
static int mdct_init(mdct_t *t, int n)
{
    int m = n / 2;
    double n0 = 0.5 + n / 4.0;
    t->n = n;
    t->cr = malloc(sizeof(double) * (size_t)n / 2);
    t->ci = malloc(sizeof(double) * (size_t)n / 2);
    t->pre_r = malloc(sizeof(double) * (size_t)n);
    t->pre_i = malloc(sizeof(double) * (size_t)n);
    t->post_r = malloc(sizeof(double) * (size_t)m);
    t->post_i = malloc(sizeof(double) * (size_t)m);
    t->rev = malloc(sizeof(int) * (size_t)n);
    if (!t->cr || !t->ci || !t->pre_r || !t->pre_i || !t->post_r || !t->post_i || !t->rev)
        return -1;
    for (int k = 0; k < n / 2; k++) {
        t->cr[k] = cos(-2 * M_PI * k / n);
        t->ci[k] = sin(-2 * M_PI * k / n);
    }
    for (int j = 0; j < n; j++) {
        t->pre_r[j] = cos(-M_PI * j / n);
        t->pre_i[j] = sin(-M_PI * j / n);
    }
    double g = sqrt(2.0 / m);
    for (int k = 0; k < m; k++) {
        double a = -2 * M_PI * n0 * (k + 0.5) / n;
        t->post_r[k] = cos(a) * g;
        t->post_i[k] = sin(a) * g;
    }
    int bits = ilog2((uint32_t)n);
    for (int i = 0; i < n; i++) {
        int r = 0;
        for (int b = 0; b < bits; b++)
            r |= (i >> b & 1) << (bits - 1 - b);
        t->rev[i] = r;
    }
    return 0;
}

/* Frees the tables of mdct_init. */
static void mdct_free(mdct_t *t)
{
    free(t->cr); free(t->ci); free(t->pre_r); free(t->pre_i);
    free(t->post_r); free(t->post_i); free(t->rev);
}

/* Forward MDCT, orthonormal: X[k] = sqrt(2/M) sum_i x[i] cos(2 pi / n (i + 1/2 + n/4)(k + 1/2)),
 * M = n/2 coefficients, x already windowed. */
static void mdct_fwd(const mdct_t *t, const double *x, double *X)
{
    int n = t->n;
    double re[MULE_N_LONG], im[MULE_N_LONG];
    for (int j = 0; j < n; j++) {
        int r = t->rev[j];
        re[r] = x[j] * t->pre_r[j];
        im[r] = x[j] * t->pre_i[j];
    }
    for (int len = 2; len <= n; len <<= 1) {
        int step = n / len;
        for (int i = 0; i < n; i += len)
            for (int k = 0; k < len / 2; k++) {
                double wr = t->cr[k * step], wi = t->ci[k * step];
                int a = i + k, b = a + len / 2;
                double vr = re[b] * wr - im[b] * wi, vi = re[b] * wi + im[b] * wr;
                re[b] = re[a] - vr;
                im[b] = im[a] - vi;
                re[a] += vr;
                im[a] += vi;
            }
    }
    for (int k = 0; k < n / 2; k++)
        X[k] = re[k] * t->post_r[k] - im[k] * t->post_i[k];
}

/* The complex FFT of x times a Hann window (n points), into re, im. */
static void fft_cplx(const mdct_t *t, const double *x, double *re, double *im)
{
    int n = t->n;
    for (int j = 0; j < n; j++) {
        double w = 0.5 - 0.5 * cos(2 * M_PI * (j + 0.5) / n);
        re[t->rev[j]] = x[j] * w;
        im[t->rev[j]] = 0;
    }
    for (int len = 2; len <= n; len <<= 1) {
        int step = n / len;
        for (int i = 0; i < n; i += len)
            for (int k = 0; k < len / 2; k++) {
                double wr = t->cr[k * step], wi = t->ci[k * step];
                int a = i + k, b = a + len / 2;
                double vr = re[b] * wr - im[b] * wi, vi = re[b] * wi + im[b] * wr;
                re[b] = re[a] - vr;
                im[b] = im[a] - vi;
                re[a] += vr;
                im[a] += vi;
            }
    }
}

/* The power spectrum |FFT(x w_hann)|^2, bins 0 .. n/2 - 1 (the tonality measure). */
static void fft_power(const mdct_t *t, const double *x, double *pw)
{
    double re[MULE_N_LONG], im[MULE_N_LONG];
    fft_cplx(t, x, re, im);
    for (int k = 0; k < t->n / 2; k++)
        pw[k] = re[k] * re[k] + im[k] * im[k];
}

/* The rising Vorbis window slope of length s at i: sin(pi/2 sin^2(pi (i + 1/2) / 2s)). */
static double slope(int i, int s)
{
    double t = sin(0.5 * M_PI * (i + 0.5) / s);
    return sin(0.5 * M_PI * t * t);
}

/* A rising half-window of length h with a centred slope of length s: zeros, slope, ones. */
static double half(int i, int h, int s)
{
    int z = (h - s) / 2;
    return i < z ? 0.0 : (i < z + s ? slope(i - z, s) : 1.0);
}

/* ---------------------------------------------------------------- transient detector */

/* The block type of each of the T frames (0 long, 1 short): energies of 128-sample blocks of the
 * signal high-passed at 3 kHz; an attack is a block 10 dB above a decaying memory (3 dB per
 * block) or 20 dB above the blocks 7 to 10 earlier, above a -70 dB floor; the frames whose short
 * windows hold it become short. -1 if out of memory. */
static int block_types(const double *x, int64_t L, int T, uint8_t *types)
{
    const double fs = 44100.0, fc = 3000.0, ratio_db = 10.0, decay_db = 3.0, floor_db = -70.0,
                 slow_db = 20.0;
    const int lag0 = 7, lag1 = 10, SUB = 128;
    /* 2nd-order Butterworth high-pass (bilinear, prewarped: scipy's butter) */
    double K = tan(M_PI * fc / fs), Q = 1 / sqrt(2.0);
    double norm = 1 / (1 + K / Q + K * K);
    double b0 = norm, b1 = -2 * norm, b2 = norm;
    double a1 = 2 * (K * K - 1) * norm, a2 = (1 - K / Q + K * K) * norm;
    int64_t nsub = (L + SUB - 1) / SUB;
    double *e = calloc((size_t)(nsub ? nsub : 1) * 2, sizeof(double));
    if (!e)
        return -1;
    for (int c = 0; c < 2; c++) {
        double z1 = 0, z2 = 0;
        for (int64_t i = 0; i < nsub * SUB; i++) {
            double in = i < L ? x[2 * i + c] : 0.0, out = 0.0;
            if (i < L) {
                out = b0 * in + z1;
                z1 = b1 * in - a1 * out + z2;
                z2 = b2 * in - a2 * out;
            }
            e[(i / SUB) * 2 + c] += out * out;
        }
    }
    for (int64_t j = 0; j < nsub * 2; j++)
        e[j] /= SUB;
    double flo = pow(10, floor_db / 10), d = pow(10, -decay_db / 10);
    double mem[2] = {0, 0};
    for (int t = 0; t < T; t++)
        types[t] = 0;
    for (int64_t j = 0; j < nsub; j++) {
        double score = -1e300, emax = 0;
        for (int c = 0; c < 2; c++) {
            double ej = e[j * 2 + c];
            double s1 = 10 * log10((ej + flo) / (mem[c] + flo)) - ratio_db;
            double past = flo;
            for (int k = lag0; k <= lag1; k++)
                if (j - k >= 0 && e[(j - k) * 2 + c] > past)
                    past = e[(j - k) * 2 + c];
            double s2 = 10 * log10((ej + flo) / (past + flo)) - slow_db;
            double s = s1 > s2 ? s1 : s2;
            if (s > score)
                score = s;
            if (ej > emax)
                emax = ej;
            mem[c] = ej > mem[c] * d ? ej : mem[c] * d;
        }
        if (score > 0 && emax > flo) {
            int64_t st = j * SUB;
            int64_t edges[2] = {st, st + SUB - 1};
            for (int k = 0; k < 2; k++) {
                int64_t t = (int64_t)floor((double)(edges[k] + 448) / F);
                if (t < 0) t = 0;
                if (t > T - 1) t = T - 1;
                types[t] = 1;
            }
        }
    }
    free(e);
    return 0;
}

/* ---------------------------------------------------------------- psychoacoustics */

/* The psychoacoustic model's tables for one transform size: band centres (Bark), the spreading
 * between bands, the threshold in quiet per coefficient, the bands' widths. */
typedef struct {
    double zc[NB], spread[NB][NB], ath[NB];
    int width[NB];
} psy_t;

/* Frequency (Hz) to Bark (Zwicker). */
static double bark(double f)
{
    return 13 * atan(0.00076 * f) + 3.5 * atan((f / 7500.0) * (f / 7500.0));
}

/* The tables for m coefficients (1024 or 128): the threshold in quiet (Terhardt's formula, at
 * the band's most sensitive point, 96 dB = full scale), Schroeder's spreading function. */
static void psy_init(psy_t *p, int m)
{
    int scale = m / 128;
    double hz = 44100.0 / 2 / m;
    for (int b = 0; b < NB; b++) {
        double lo = EDGES[b] * scale * hz, hi = EDGES[b + 1] * scale * hz;
        p->zc[b] = bark((lo + hi) / 2);
        p->width[b] = (EDGES[b + 1] - EDGES[b]) * scale;
        double amin = 1e300;
        for (int i = 0; i < 16; i++) {
            double f = (lo + (hi - lo) * i / 15.0) / 1000;
            if (f < 0.02)
                f = 0.02;
            double a = 3.64 * pow(f, -0.8) - 6.5 * exp(-0.6 * (f - 3.3) * (f - 3.3)) + 1e-3 * pow(f, 4);
            if (a < amin)
                amin = a;
        }
        if (amin > 140)
            amin = 140;
        p->ath[b] = (m / 2.0) * pow(10, (amin - 96.0) / 10) / p->width[b];
    }
    for (int i = 0; i < NB; i++)
        for (int j = 0; j < NB; j++) {
            double dz = p->zc[i] - p->zc[j] + 0.474;
            double s = 15.81 + 7.5 * dz - 17.5 * sqrt(1 + dz * dz);
            p->spread[i][j] = pow(10, s / 10);
        }
}

/* Axis 1 (E-LOG.md): a long frame's band masks below fine_nb from sub-band masks of fine_w lines:
 * each sub-band's energy spread over the Bark scale (a density per Bark, per line: times the
 * sub-band's Bark width / w), the offset from the band's tonality; a band's mask is the power
 * mean of exponent -fine_p of its sub-bands' (large: their minimum). */
static void psy_fine(const psy_t *p, const mule_enc_params *pr, const double *X,
                     const double *flat, double *mask)
{
    static double z[F], dz[F], E[F], mk[F];
    static int sb[F], done_w;
    int w = pr->fine_w > 0 ? pr->fine_w : 8, S = F / w;
    double hz = 44100.0 / 2 / F;
    if (done_w != w) {
        for (int s = 0; s < S; s++) {
            z[s] = bark((s * w + w / 2.0) * hz);
            dz[s] = bark((s + 1) * w * hz) - bark(s * w * hz);
            int b = 0;
            while (b < NB - 1 && EDGES[b + 1] * 8 <= s * w)
                b++;
            sb[s] = b;
        }
        done_w = w;
    }
    int nbf = pr->fine_nb > 0 && pr->fine_nb < NB ? pr->fine_nb : NB;
    int smax = EDGES[nbf] * 8 / w;              /* sub-bands needed (maskers: all of them) */
    for (int s = 0; s < S; s++) {
        double e = 0;
        for (int i = 0; i < w; i++)
            e += X[s * w + i] * X[s * w + i];
        E[s] = e;
    }
    double nfl = pr->fft_tonal ? pr->fft_noise_db : 5.5;
    for (int i = 0; i < smax; i++) {
        double C = 0;
        for (int j = 0; j < S; j++) {
            if (E[j] <= 0)
                continue;
            double d = z[i] - z[j] + 0.474;
            if (d < -3 || d > 8)                /* below -60 dB: negligible */
                continue;
            C += pow(10, (15.81 + 7.5 * d - 17.5 * sqrt(1 + d * d)) / 10) * E[j];
        }
        int b = sb[i];
        double t = pr->tonal_all ? 1.0 : (flat[b] + nfl) / -pr->ton_scale;
        t = t < 0 ? 0 : (t > 1 ? 1 : t);
        double tm = 14.5 + z[i];
        if (pr->tcap_db > 0 && tm > pr->tcap_db)
            tm = pr->tcap_db;
        double off = t * tm + (1 - t) * 5.5;
        if (b < 8)
            off += pr->low_db;
        if (b >= 8 && b < pr->mid_hi)
            off += pr->mid_db;
        double v = C * pow(10, -off / 10) * dz[i] / w;
        double at = p->ath[b] * pow(10, pr->ath_db / 10);
        mk[i] = v > at ? v : at;
    }
    for (int b = 0; b < nbf; b++) {
        int s0 = EDGES[b] * 8 / w, s1 = EDGES[b + 1] * 8 / w;
        double acc = 0;
        for (int s = s0; s < s1; s++)
            acc += pow(mk[s], -pr->fine_p);
        mask[b] = pow(acc / (s1 - s0), -1 / pr->fine_p);
    }
}

/* The masking threshold per coefficient of each band (Johnston-style): the bands' energies spread
 * over the Bark scale, lowered by an offset between 5.5 dB (noise) and 14.5 + z dB (tonal,
 * capped at tcap_db) after the band's flatness, plus low_db / mid_db; at least the threshold in
 * quiet. P: power per coefficient; flat: flatness (dB); noise_flat: a noise band's flatness. */
static void psy_masks(const psy_t *p, const mule_enc_params *pr, const double *P,
                      const double *flat, double *mask, double noise_flat)
{
    double E[NB];
    for (int b = 0; b < NB; b++)
        E[b] = P[b] * p->width[b];
    for (int i = 0; i < NB; i++) {
        double C = 0;
        for (int j = 0; j < NB; j++)
            C += p->spread[i][j] * E[j];
        double t = pr->tonal_all ? 1.0 : (flat[i] + noise_flat) / -pr->ton_scale;
        t = t < 0 ? 0 : (t > 1 ? 1 : t);
        double tm = 14.5 + p->zc[i];
        if (pr->tcap_db > 0 && tm > pr->tcap_db)
            tm = pr->tcap_db;
        double off = t * tm + (1 - t) * 5.5;
        if (i < 8)
            off += pr->low_db;
        if (i >= 8 && i < pr->mid_hi)
            off += pr->mid_db;
        double mk = C * pow(10, -off / 10) / p->width[i];
        double at = p->ath[i] * pow(10, pr->ath_db / 10);
        mask[i] = mk > at ? mk : at;
    }
}

/* ---------------------------------------------------------------- frame coding */

/* A group of windows: type 0, the long frame's one window; type 1, short windows [k0, k1). */
typedef struct {
    int type, k0, k1;
} group;

/* The number of coefficients of band b in group g. */
static int band_n(const group *g, int b)
{
    return g->type == 0 ? (EDGES[b + 1] - EDGES[b]) * 8 : (EDGES[b + 1] - EDGES[b]) * (g->k1 - g->k0);
}

/* The place in X of band b's coefficient i in group g (window, then frequency; short frames lay
 * X out as [8][128]). */
static int coef_index(const group *g, int b, int i)
{
    if (g->type == 0)
        return EDGES[b] * 8 + i;
    int w = EDGES[b + 1] - EDGES[b];
    return (g->k0 + i / w) * 128 + EDGES[b] + i % w;
}

/* A band's class for the contexts: 0 below band 8, 1 below band 16, 2 above. */
static int band_class(int b)
{
    return b < 8 ? 0 : (b < 16 ? 1 : 2);
}

/* The neighbourhood measure of a coefficient to one of the 6 magnitude contexts (as dec.c). */
static int nc_map(int64_t m)
{
    static const int t[9] = {0, 1, 2, 3, 3, 4, 4, 4, 4};
    return m < 9 ? t[m] : 5;
}

/* floor(a / b) for b > 0. */
static int floor_div(int a, int b)
{
    return a >= 0 ? a / b : -((-a + b - 1) / b);
}

/* What band_code needs about a band. */
typedef struct {
    const double *Y;            /* coded channel's coefficients */
    const group *g;
    int b, type, inter, e;
    const int *ylong;
    double rms, dz;
    double tcq_lam;
    double mtq;                 /* tcq_rd: the band's noise target (mask * tq) */
    const mule_enc_params *pr;
} band_in;

/* Axis 3 (E-LOG.md): the TCQ Viterbi with the rate of the tracked models. Each survivor carries its tails (the two
 * previous magnitudes) for the coefficient contexts; pm[i] the inter-frame term (-1: none).
 * Distortion (x - k)^2 in (D/2)^2 units, rate weight lam (same units), per bit. */
static void tcq_viterbi_rd(const double *x, int n, double lam, const ops_t *o, int ac,
                           const int64_t *pm, int64_t t1_0, int64_t t2_0, int64_t *kout)
{
    static double lev[176][8];
    static int back[176][8];
    double cost[8], nc[8];
    int64_t t1[8], t2[8], n1[8], n2[8];
    double sc[6][16], esc[16];
    for (int c = 0; c < 6; c++)
        for (int v = 0; v < 16; v++)
            sc[c][v] = sym_bits(o, MULE_S_COEF, ac * 6 + c, v);
    for (int v = 0; v < 16; v++)
        esc[v] = sym_bits(o, MULE_S_CESC, ac, v) + v;
    for (int s = 0; s < 8; s++) {
        cost[s] = s ? 1e300 : 0.0;
        t1[s] = t1_0;
        t2[s] = t2_0;
    }
    for (int i = 0; i < n; i++) {
        for (int t = 0; t < 8; t++)
            nc[t] = 1e300;
        for (int s = 0; s < 8; s++) {
            if (cost[s] >= 1e300)
                continue;
            int even = !(s & 1);
            int64_t mctx = 2 * t1[s] + t2[s];
            if (pm[i] >= 0)
                mctx = (mctx + 3 * pm[i] + 1) >> 1;
            const double *row = sc[nc_map(mctx)];
            for (int br = 0; br < 2; br++) {
                int j = mule_tcq_subset[s][br];
                double k0 = nearbyint((x[i] - j) / 4.0) * 4 + j;
                int t = mule_tcq_next[s][br];
                for (int dk = -4; dk <= 4; dk += 4) {
                    double k = k0 + dk;
                    double ak = fabs(k);
                    int64_t mag = even ? (int64_t)ak / 2 : ((int64_t)ak - 1) / 2;
                    if (mag < 0)
                        continue;
                    double r = row[mag < 15 ? mag : 15];
                    if (mag >= 15)
                        r += esc[ilog2((uint32_t)(mag - 15) + 1)];
                    if (!even || ak > 0)
                        r += 1;
                    double c = cost[s] + (x[i] - k) * (x[i] - k) + lam * r;
                    if (c < nc[t]) {
                        nc[t] = c;
                        back[i][t] = s;
                        lev[i][t] = k;
                        n1[t] = mag;
                        n2[t] = t1[s];
                    }
                }
            }
        }
        memcpy(cost, nc, sizeof cost);
        memcpy(t1, n1, sizeof t1);
        memcpy(t2, n2, sizeof t2);
    }
    int s = 0;
    for (int t = 1; t < 8; t++)
        if (cost[t] < cost[s])
            s = t;
    for (int i = n - 1; i >= 0; i--) {
        kout[i] = (int64_t)lev[i][s];
        s = back[i][s];
    }
}

/* The TCQ Viterbi over the 8-state trellis (spec 5.3) for samples x (units of D/2) from state 0:
 * the levels k minimising sum (x - k)^2 + lam R(k), R a static approximation of the rate. */
static void tcq_viterbi(const double *x, int n, double lam, int64_t *kout)
{
    static double lev[176][8];
    static int back[176][8];
    double cost[8], nc[8];
    for (int s = 0; s < 8; s++)
        cost[s] = s ? 1e300 : 0.0;
    for (int i = 0; i < n; i++) {
        for (int t = 0; t < 8; t++)
            nc[t] = 1e300;
        for (int s = 0; s < 8; s++) {
            if (cost[s] >= 1e300)
                continue;
            for (int br = 0; br < 2; br++) {
                int j = mule_tcq_subset[s][br];
                double k = nearbyint((x[i] - j) / 4.0) * 4 + j;
                double m = floor(fabs(k) / 2);
                double r = 1.0 + 1.6 * log2(1.0 + m) + (k != 0);
                double c = cost[s] + (x[i] - k) * (x[i] - k) + lam * r;
                int t = mule_tcq_next[s][br];
                if (c < nc[t]) {
                    nc[t] = c;
                    back[i][t] = s;
                    lev[i][t] = k;
                }
            }
        }
        memcpy(cost, nc, sizeof cost);
    }
    int s = 0;
    for (int t = 1; t < 8; t++)
        if (cost[t] < cost[s])
            s = t;
    for (int i = n - 1; i >= 0; i--) {
        kout[i] = (int64_t)lev[i][s];
        s = back[i][s];
    }
}

/* One band's coefficients at allocation a: TCQ levels (Viterbi), then their symbols with the
 * decoder's contexts. emit: the operations are appended (ycur gets a long frame's indices);
 * else bits and noise (the band's squared error) are returned, costed with the tracked models,
 * for the RD choice. tail1, tail2 (the two previous indices) are updated either way. */
static void band_code(const band_in *in, int a, int64_t *tail1, int64_t *tail2, ops_t *o, int emit,
                      int *ycur, double *bits, double *noise)
{
    int n = band_n(in->g, in->b);
    double D = pow(2.0, (MULE_A0 - a) / 4.0);
    int ac = a / 3 < 15 ? a / 3 : 15;
    double nb = 0, ns = 0;
    int64_t kt[176];
    int tst = 0;
    double xt[176];
    for (int i = 0; i < n; i++)
        xt[i] = in->Y[coef_index(in->g, in->b, i)] / in->rms / (D / 2);
    if (in->pr && in->pr->tcq_rd && o->mr) {
        int64_t pmv[176];
        for (int i = 0; i < n; i++) {
            pmv[i] = -1;
            if (in->inter) {
                int idx = coef_index(in->g, in->b, i);
                int64_t v = (int64_t)in->ylong[idx] * POW4[in->e & 3];
                int sh = floor_div(in->e, 4);
                int64_t p = sh >= 0 ? (v << (sh < 8 ? sh : 8)) >> 8 : v >> (8 - sh);
                pmv[i] = p > 31 ? 31 : p;
            }
        }
        double u = (D / 2) * in->rms;           /* (D/2)^2 rms^2: the noise of one unit */
        double lam = in->pr->tcq_rdl * in->pr->rd_lambda * in->mtq / (u * u);
        tcq_viterbi_rd(xt, n, lam, o, ac, pmv, *tail1, *tail2, kt);
    } else
        tcq_viterbi(xt, n, in->tcq_lam, kt);
    for (int i = 0; i < n; i++) {
        int idx = coef_index(in->g, in->b, i);
        double xn = in->Y[idx] / in->rms;
        /* TCQ level -> index within the state's union (odd states: no zero, sign always) */
        int64_t k = kt[i], ak = k < 0 ? -k : k;
        int even = !(tst & 1);
        int64_t mag = even ? ak / 2 : (ak - 1) / 2;
        int need_sign = !even || ak > 0, neg = k < 0;
        double rec = (double)ak * D / 2;
        tst = mule_tcq_step(tst, k);
        int64_t mctx = 2 * *tail1 + *tail2;
        if (in->inter) {
            int64_t v = (int64_t)in->ylong[idx] * POW4[in->e & 3];
            int sh = floor_div(in->e, 4);
            int64_t pm = sh >= 0 ? (v << (sh < 8 ? sh : 8)) >> 8 : v >> (8 - sh);
            if (pm > 31)
                pm = 31;
            mctx = (mctx + 3 * pm + 1) >> 1;
        }
        int ctx = ac * 6 + nc_map(mctx), s = mag < 15 ? (int)mag : 15;
        if (emit)
            put(o, MULE_S_COEF, ctx, s);
        else
            nb += sym_bits(o, MULE_S_COEF, ctx, s);
        if (mag >= 15) {
            uint32_t v = (uint32_t)(mag - 15);
            int ek = ilog2(v + 1);              /* escape: Exp-Golomb order */
            if (emit) {
                put(o, MULE_S_CESC, ac, ek);
                if (ek)
                    raw(o, ek, v + 1 - (1u << ek));
            } else
                nb += sym_bits(o, MULE_S_CESC, ac, ek) + ek;
        }
        if (need_sign) {
            if (emit)
                raw(o, 1, (uint32_t)neg);
            else
                nb += 1;
        }
        if (!emit) {
            double d = fabs(xn) - rec;
            ns += d * d;
        }
        if (emit && in->type == 0)
            ycur[idx] = mag < 65535 ? (int)mag : 65535;   /* stored saturated (spec 5.3) */
        *tail2 = *tail1;
        *tail1 = mag;
    }
    if (bits)
        *bits = nb;
    if (noise)
        *noise = ns * in->rms * in->rms;     /* absolute noise energy of the band */
}

/* The encoder's copy of the decoder's state, plus the pre-echo control's last masks. */
typedef struct {
    int qprev[2][NB], aprev[2][NB];
    int ylong[2][F], qlong[2][NB], along[2][NB], lvalid[2];
    double premask[2][NB];      /* encoder-only: last long frame's mask (pre-echo control) */
    int have_pre;
} state_t;

/* One frame's coding operations (spec 5) from its MDCT coefficients X (L, R) and FFT powers PW:
 * groups of short windows; per band powers, flatness, masks (fine masks, pre-echo control);
 * stereo per band by perceptual entropy; energies; energy prediction weight; then per coded
 * channel and group the allocations (masks, hysteresis, RD choice), energies, allocations and
 * coefficients. key: the first frame of a key packet (predictions reset). */
static void encode_frame(const mule_enc_params *pr, const psy_t *psy_l, const psy_t *psy_s,
                         int type, int key, double X[2][F], double PW[2][F], state_t *s, ops_t *o)
{
    const psy_t *py = type ? psy_s : psy_l;
    group grp[MULE_N_SUB];
    int ng = 0;
    put(o, MULE_S_BTYPE, 0, type);
    if (!type) {
        grp[ng++] = (group){0, 0, 1};
    } else {
        double db[MULE_N_SUB];
        for (int k = 0; k < MULE_N_SUB; k++) {
            double e = 0;
            for (int c = 0; c < 2; c++)
                for (int i = 0; i < 128; i++)
                    e += X[c][k * 128 + i] * X[c][k * 128 + i];
            db[k] = 10 * log10(e + 1e-20);
        }
        uint32_t mask = 0;
        int k0 = 0;
        for (int k = 1; k < MULE_N_SUB; k++) {
            int split = pr->groups == 8 ? 1 : (pr->groups == 1 ? 0 : fabs(db[k] - db[k - 1]) > pr->group_db);
            if (split) {
                grp[ng++] = (group){1, k0, k};
                k0 = k;
                mask |= 1u << (k - 1);
            }
        }
        grp[ng++] = (group){1, k0, MULE_N_SUB};
        raw(o, 7, mask);
    }
    /* analysis per (channel, group, band): powers, flatness, masks */
    static double P[2][MULE_N_SUB][NB], FL[2][MULE_N_SUB][NB], MK[2][MULE_N_SUB][NB];
    static double PM[MULE_N_SUB][NB][2];
    for (int g = 0; g < ng; g++)
        for (int b = 0; b < NB; b++) {
            int n = band_n(&grp[g], b), nw = type ? grp[g].k1 - grp[g].k0 : 1, w = n / nw;
            double pm0 = 0, pm1 = 0;
            for (int c = 0; c < 2; c++) {
                double sum = 0;
                double col[176];
                for (int i = 0; i < w; i++)
                    col[i] = 0;
                for (int i = 0; i < n; i++) {
                    int idx = coef_index(&grp[g], b, i);
                    double v = X[c][idx];
                    sum += v * v;
                    col[i % w] += pr->fft_tonal ? PW[c][idx] : v * v;
                }
                P[c][g][b] = sum / n;
                double ar = 0, lg = 0;
                for (int i = 0; i < w; i++) {
                    double v = col[i] / nw;
                    ar += v;
                    lg += log(v + 1e-30);
                }
                ar /= w;
                double geo = exp(lg / w);
                FL[c][g][b] = 10 * log10((geo + 1e-30) / (ar + 1e-30));
            }
            for (int i = 0; i < n; i++) {
                int idx = coef_index(&grp[g], b, i);
                double l = X[0][idx], r = X[1][idx];
                double mm = (l + r) / sqrt(2.0), ss = (l - r) / sqrt(2.0);
                pm0 += mm * mm;
                pm1 += ss * ss;
            }
            PM[g][b][0] = pm0 / n;
            PM[g][b][1] = pm1 / n;
        }
    for (int c = 0; c < 2; c++)
        for (int g = 0; g < ng; g++) {
            psy_masks(py, pr, P[c][g], FL[c][g], MK[c][g], pr->fft_tonal ? pr->fft_noise_db : 5.5);
            if (pr->fine_p > 0 && type == 0)
                psy_fine(py, pr, X[c], FL[c][g], MK[c][g]);
        }
    if (pr->pre_db > 0) {                       /* pre-echo control: the mask's rise bounded */
        if (type == 0) {
            double up = pow(10, pr->pre_db / 10);
            for (int c = 0; c < 2; c++)
                for (int b = 0; b < NB; b++) {
                    if (s->have_pre && MK[c][0][b] > s->premask[c][b] * up)
                        MK[c][0][b] = s->premask[c][b] * up;
                    s->premask[c][b] = MK[c][0][b];
                }
            s->have_pre = 1;
        } else
            s->have_pre = 0;
    }
    /* stereo decision per band */
    int ms[NB];
    for (int b = 0; b < NB; b++) {
        if (pr->stereo == 1) {
            ms[b] = 0;
            continue;
        }
        if (pr->stereo == 2) {
            ms[b] = 1;
            continue;
        }
        double w = band_n(&grp[0], b), lr = 0, mse = 0;
        for (int g = 0; g < ng; g++) {
            double mmin = MK[0][g][b] < MK[1][g][b] ? MK[0][g][b] : MK[1][g][b];
            lr += 0.5 * log2(1 + P[0][g][b] / MK[0][g][b]) * w + 0.5 * log2(1 + P[1][g][b] / MK[1][g][b]) * w;
            mse += 0.5 * log2(1 + PM[g][b][0] / mmin) * w + 0.5 * log2(1 + PM[g][b][1] / mmin) * w;
        }
        ms[b] = mse < lr - TIE_EPS;
    }
    /* coded vectors (M/S or L/R) into Y[c], energies */
    static double Y[2][F];
    for (int g = 0; g < ng; g++)
        for (int b = 0; b < NB; b++) {
            int n = band_n(&grp[g], b);
            for (int i = 0; i < n; i++) {
                int idx = coef_index(&grp[g], b, i);
                double l = X[0][idx], r = X[1][idx];
                Y[0][idx] = ms[b] ? (l + r) / sqrt(2.0) : l;
                Y[1][idx] = ms[b] ? (l - r) / sqrt(2.0) : r;
            }
        }
    int Q[2][MULE_N_SUB][NB];
    for (int c = 0; c < 2; c++)
        for (int g = 0; g < ng; g++)
            for (int b = 0; b < NB; b++) {
                int n = band_n(&grp[g], b);
                double e = 0;
                for (int i = 0; i < n; i++) {
                    double v = Y[c][coef_index(&grp[g], b, i)];
                    e += v * v;
                }
                double q = nearbyint(4 * log2(sqrt(e / n) + 1e-30));
                if (q < MULE_QMIN) q = MULE_QMIN;
                if (q > MULE_QMAX) q = MULE_QMAX;
                Q[c][g][b] = (int)q;
            }
    /* energy prediction weight */
    int ai = 0;
    if (!key) {
        double best = 1e300;
        for (int k = 0; k < 4; k++) {
            double cost = 0;
            for (int c = 0; c < 2; c++) {
                int left = s->qprev[c][0];
                for (int b = 0; b < NB; b++) {
                    int pred = floor_div(ALPHAS[k] * s->qprev[c][b] + (32 - ALPHAS[k]) * left, 32);
                    cost += log2(1 + abs(Q[c][0][b] - pred));
                    left = Q[c][0][b];
                }
            }
            if (cost < best - TIE_EPS) {
                best = cost;
                ai = k;
            }
        }
    }
    put(o, MULE_S_ALPHA, 0, ai);
    for (int b = 0; b < NB; b++)
        put(o, MULE_S_STEREO, band_class(b), ms[b]);

    double tq = pow(10, pr->q_db / 10);
    for (int c = 0; c < 2; c++) {
        int64_t tail1 = 0, tail2 = 0;
        int inter_ok = type == 0 && s->lvalid[c];
        int ycur[F];
        memset(ycur, 0, sizeof ycur);
        int a[NB] = {0};
        int *q = NULL;
        for (int g = 0; g < ng; g++) {
            q = Q[c][g];
            /* allocation */
            for (int b = 0; b < NB; b++) {
                a[b] = 0;
                double rms = pow(2.0, q[b] / 4.0);
                double mk = ms[b] ? (MK[0][g][b] < MK[1][g][b] ? MK[0][g][b] : MK[1][g][b]) : MK[c][g][b];
                double target = mk * tq;
                if (q[b] <= MULE_QMIN || target >= rms * rms)
                    continue;                   /* noise-filled (a = 0) */
                double D = sqrt(12 * target) / rms;
                double av = nearbyint(MULE_A0 - 4 * log2(D));
                if (av < 0) av = 0;
                if (av > MULE_AMAX) av = MULE_AMAX;
                a[b] = (int)av;
            }
            int *ap = s->aprev[c];
            if (pr->alloc_hyst && !key)
                for (int b = 0; b < NB; b++)
                    if (a[b] > 0 && ap[b] > 0 && abs(a[b] - ap[b]) <= pr->alloc_hyst)
                        a[b] = ap[b];
            if (pr->rd_lambda > 0 && o->mr) {     /* RD choice among a-1, a, a+1 */
                int64_t t1 = tail1, t2 = tail2;
                for (int b = 0; b < NB; b++) {
                    if (q[b] <= MULE_QMIN || a[b] == 0)
                        continue;
                    double rms = pow(2.0, q[b] / 4.0);
                    double mk = ms[b] ? (MK[0][g][b] < MK[1][g][b] ? MK[0][g][b] : MK[1][g][b]) : MK[c][g][b];
                    int n = band_n(&grp[g], b);
                    band_in in = {Y[c], &grp[g], b, type, inter_ok && s->along[c][b] > 0, 0, s->ylong[c],
                                  rms, 0.0, pr->tcq_lam, mk * tq, pr};
                    double best = 1e300;
                    int besta = a[b];
                    int64_t bt1 = t1, bt2 = t2;
                    for (int cand = a[b] - 1; cand <= a[b] + 1; cand++) {
                        if (cand < 1 || cand > MULE_AMAX)
                            continue;
                        in.e = in.inter ? s->qlong[c][b] - q[b] + cand - s->along[c][b] : 0;
                        int64_t c1 = t1, c2 = t2;
                        double bits, noise;
                        band_code(&in, cand, &c1, &c2, o, 0, NULL, &bits, &noise);
                        int d = cand - ap[b];
                        bits += sym_bits(o, MULE_S_ALLOC, band_class(b) + 3, d >= -7 && d <= 7 ? d + 7 : 15);
                        double j = noise / (mk * tq * n) + pr->rd_lambda * bits / n;
                        if (j < best - TIE_EPS) {
                            best = j;
                            besta = cand;
                            bt1 = c1;
                            bt2 = c2;
                        }
                    }
                    a[b] = besta;
                    t1 = bt1;
                    t2 = bt2;
                }
            }
            if (pr->nf_bias > 0)                /* noise-filled bands: energy sent lower */
                for (int b = 0; b < NB; b++)
                    if (a[b] == 0 && q[b] > MULE_QMIN) {
                        int v = q[b] - pr->nf_bias;
                        q[b] = v > MULE_QMIN + 1 ? v : MULE_QMIN + 1;
                    }
            int alpha = g == 0 ? ALPHAS[ai] : 26;
            int left = s->qprev[c][0], rprev = 0;
            for (int b = 0; b < NB; b++) {
                int pred = floor_div(alpha * s->qprev[c][b] + (32 - alpha) * left, 32);
                int r = q[b] - pred;
                signed_ops(o, MULE_S_ENERGY, band_class(b) * 3 + (abs(rprev) < 2 ? abs(rprev) : 2), r);
                left = q[b];
                rprev = r;
            }
            memcpy(s->qprev[c], q, sizeof(int) * NB);
            double cf = 0, ct = 0;
            for (int b = 0; b < NB; b++) {
                cf += log2(1 + abs(a[b] - (b ? a[b - 1] : ap[0])));
                ct += log2(1 + abs(a[b] - ap[b]));
            }
            int mode = pr->alloc_auto && ct < cf - TIE_EPS;
            put(o, MULE_S_AMODE, 0, mode);
            for (int b = 0; b < NB; b++) {
                int ref = mode ? ap[b] : (b ? a[b - 1] : ap[0]);
                signed_ops(o, MULE_S_ALLOC, band_class(b) + 3 * mode, a[b] - ref);
            }
            memcpy(s->aprev[c], a, sizeof a);
            /* coefficients */
            for (int b = 0; b < NB; b++) {
                if (q[b] <= MULE_QMIN || a[b] == 0)
                    continue;
                double rms = pow(2.0, q[b] / 4.0);
                int inter = inter_ok && s->along[c][b] > 0;
                double mk = ms[b] ? (MK[0][g][b] < MK[1][g][b] ? MK[0][g][b] : MK[1][g][b]) : MK[c][g][b];
                band_in in = {Y[c], &grp[g], b, type, inter,
                              inter ? s->qlong[c][b] - q[b] + a[b] - s->along[c][b] : 0, s->ylong[c], rms,
                              0.0, pr->tcq_lam, mk * tq, pr};
                band_code(&in, a[b], &tail1, &tail2, o, 1, ycur, NULL, NULL);
            }
        }
        if (type == 0) {
            memcpy(s->ylong[c], ycur, sizeof ycur);
            memcpy(s->qlong[c], q, sizeof(int) * NB);
            memcpy(s->along[c], a, sizeof a);
            s->lvalid[c] = 1;
        } else
            s->lvalid[c] = 0;
    }
}

/* ---------------------------------------------------------------- Ogg */

static uint32_t crc_tab[256];

/* The Ogg CRC-32 table (polynomial 0x04C11DB7, no reflection). */
static void crc_init(void)
{
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t r = i << 24;
        for (int k = 0; k < 8; k++)
            r = r & 0x80000000u ? (r << 1) ^ 0x04C11DB7u : r << 1;
        crc_tab[i] = r;
    }
}

/* One Ogg page holding np complete packets (at most 255 lacing values in all), with its CRC.
 * -1 if out of memory. */
static int page(buf_t *out, int flags, int64_t granule, uint32_t serial, uint32_t seq,
                const uint8_t *const *pk, const int *len, int np)
{
    uint8_t h[27 + 255];
    int nl = 0;
    for (int i = 0; i < np; i++) {
        for (int k = 0; k < len[i] / 255; k++)
            h[27 + nl++] = 255;
        h[27 + nl++] = (uint8_t)(len[i] % 255);
    }
    memcpy(h, "OggS", 4);
    h[4] = 0;
    h[5] = (uint8_t)flags;
    for (int i = 0; i < 8; i++)
        h[6 + i] = (uint8_t)((uint64_t)granule >> (8 * i));
    for (int i = 0; i < 4; i++) {
        h[14 + i] = (uint8_t)(serial >> (8 * i));
        h[18 + i] = (uint8_t)(seq >> (8 * i));
        h[22 + i] = 0;
    }
    h[26] = (uint8_t)nl;
    size_t start = out->n;
    if (buf_put(out, h, (size_t)(27 + nl)))
        return -1;
    for (int i = 0; i < np; i++)
        if (buf_put(out, pk[i], (size_t)len[i]))
            return -1;
    uint32_t crc = 0;
    for (size_t i = start; i < out->n; i++)
        crc = (crc << 8) ^ crc_tab[((crc >> 24) ^ out->b[i]) & 0xff];
    for (int i = 0; i < 4; i++)
        out->b[start + 22 + i] = (uint8_t)(crc >> (8 * i));
    return 0;
}

/* One packet of any size over as many pages as needed (255 segments a page: up to 65,025
 * bytes); the pages after the first are continued (flag 1); only the last, where the packet
 * ends, carries the granule, the others -1 (no packet ends there, RFC 3533) */
static int page_big(buf_t *out, int flags, int64_t granule, uint32_t serial, uint32_t *seq,
                    const uint8_t *data, int len)
{
    int off = 0, first = 1;
    do {
        int rest = len - off, chunk = rest > 255 * 255 ? 255 * 255 : rest;
        int last = chunk == rest && chunk < 255 * 255;      /* ends here (a final lacing value < 255) */
        uint8_t h[27 + 255];
        int nl = 0;
        for (int k = 0; k < chunk / 255; k++)
            h[27 + nl++] = 255;
        if (last)
            h[27 + nl++] = (uint8_t)(chunk % 255);
        memcpy(h, "OggS", 4);
        h[4] = 0;
        h[5] = (uint8_t)((first ? flags : 0) | (first ? 0 : 1));
        int64_t g = last ? granule : -1;
        for (int i = 0; i < 8; i++)
            h[6 + i] = (uint8_t)((uint64_t)g >> (8 * i));
        for (int i = 0; i < 4; i++) {
            h[14 + i] = (uint8_t)(serial >> (8 * i));
            h[18 + i] = (uint8_t)(*seq >> (8 * i));
            h[22 + i] = 0;
        }
        h[26] = (uint8_t)nl;
        size_t start = out->n;
        if (buf_put(out, h, (size_t)(27 + nl)) || buf_put(out, data + off, (size_t)chunk))
            return -1;
        uint32_t crc = 0;
        for (size_t i = start; i < out->n; i++)
            crc = (crc << 8) ^ crc_tab[((crc >> 24) ^ out->b[i]) & 0xff];
        for (int i = 0; i < 4; i++)
            out->b[start + 22 + i] = (uint8_t)(crc >> (8 * i));
        (*seq)++;
        off += chunk;
        first = 0;
        if (last)
            return 0;
    } while (1);
}

/* v as 4 little-endian bytes. */
static void le32(uint8_t *p, uint32_t v)
{
    for (int i = 0; i < 4; i++)
        p[i] = (uint8_t)(v >> (8 * i));
}

/* ---------------------------------------------------------------- API */

/* Analysis and frame coding of the whole signal: its operations (out) and each frame's first
 * operation (fstart[0..T]). The frame t covers samples [1024 (t - 1), 1024 (t + 1)). -1 if out
 * of memory (out then empty). */
static int encode_ops(const double *pcm, int64_t L, const mule_enc_params *pr, int T, ops_t *out,
                      int64_t *fstart)
{
    uint8_t *types = malloc((size_t)T);
    mdct_t ml = {0}, msh = {0};
    ops_t o = {0};
    state_t *s = calloc(1, sizeof *s);
    double (*X)[F] = malloc(sizeof(double) * 2 * F);
    double (*PW)[F] = malloc(sizeof(double) * 2 * F);
    int rc = -1;
    if (!types || !s || !X || !PW || block_types(pcm, L, T, types) || mdct_init(&ml, MULE_N_LONG) ||
        mdct_init(&msh, MULE_N_SHORT))
        goto done;
    psy_t pl, ps;
    psy_init(&pl, 1024);
    psy_init(&ps, 128);
    double wl[4][MULE_N_LONG], wsh[MULE_N_SHORT];
    for (int v = 0; v < 4; v++) {                   /* long windows: left short?, right short? */
        int sl = v & 1 ? 128 : 1024, sr = v & 2 ? 128 : 1024;
        for (int i = 0; i < F; i++) {
            wl[v][i] = half(i, F, sl);
            wl[v][MULE_N_LONG - 1 - i] = half(i, F, sr);
        }
    }
    for (int i = 0; i < MULE_N_SHORT; i++)
        wsh[i] = i < 128 ? slope(i, 128) : slope(MULE_N_SHORT - 1 - i, 128);

    if (pr->rd_lambda > 0 && !(o.mr = mule_models_alloc()))
        goto done;
    double seg[MULE_N_LONG], tmp[MULE_N_LONG];
    for (int t = 0; t < T; t++) {
        fstart[t] = o.n;
        int key = t % pr->keyframe == 0;
        if (key) {
            for (int c = 0; c < 2; c++)
                for (int b = 0; b < NB; b++) {
                    s->qprev[c][b] = MULE_Q_RESET;
                    s->aprev[c][b] = MULE_A_RESET;
                }
            s->lvalid[0] = s->lvalid[1] = 0;
            if (o.mr)
                mule_models_reset(o.mr);
        }
        int type = types[t];
        for (int c = 0; c < 2; c++) {
            /* padded segment [F t, F t + 2F) = original [F (t-1), F (t+1)) */
            for (int i = 0; i < MULE_N_LONG; i++) {
                int64_t j = (int64_t)F * (t - 1) + i;
                seg[i] = j >= 0 && j < L ? pcm[2 * j + c] : 0.0;
            }
            if (pr->fft_tonal) {
                if (!type)
                    fft_power(&ml, seg, PW[c]);
                else
                    for (int k = 0; k < MULE_N_SUB; k++)
                        fft_power(&msh, seg + MULE_SHORT_OFF + 128 * k, PW[c] + 128 * k);
            }
            if (!type) {
                int v = (t > 0 && types[t - 1]) | (t + 1 < T && types[t + 1] ? 2 : 0);
                for (int i = 0; i < MULE_N_LONG; i++)
                    tmp[i] = seg[i] * wl[v][i];
                mdct_fwd(&ml, tmp, X[c]);
            } else {
                for (int k = 0; k < MULE_N_SUB; k++) {
                    for (int i = 0; i < MULE_N_SHORT; i++)
                        tmp[i] = seg[MULE_SHORT_OFF + 128 * k + i] * wsh[i];
                    mdct_fwd(&msh, tmp, X[c] + 128 * k);
                }
            }
        }
        encode_frame(pr, &pl, &ps, type, key, X, PW, s, &o);
    }
    fstart[T] = o.n;
    rc = o.err ? -1 : 0;
done:
    if (o.mr)
        mule_models_free(o.mr);
    o.mr = NULL;
    free(X);
    free(PW);
    free(s);
    mdct_free(&ml);
    mdct_free(&msh);
    free(types);
    if (rc) {                                   /* nothing half made is handed back */
        free(o.m);
        free(o.v);
        o = (ops_t){0};
    }
    *out = o;
    return rc;
}

/* See mule_enc.h: the coding operations only (tests and training). */
int mule_encode_ops(const double *pcm, int64_t L, const mule_enc_params *pr, int32_t **model,
                    uint32_t **val, int64_t *n, int64_t **frame_start, int *frames)
{
    int T = (int)((L + F - 1) / F) + 1;
    if (pr->keyframe <= 0 || pr->keyframe % 4)
        return -1;
    ops_t o = {0};
    int64_t *fstart = malloc(sizeof(int64_t) * (size_t)(T + 1));
    if (!fstart || encode_ops(pcm, L, pr, T, &o, fstart)) {
        free(fstart);
        return -1;
    }
    *model = o.m;
    *val = o.v;
    *n = o.n;
    *frame_start = fstart;
    *frames = T;
    return 0;
}

/* See mule_enc.h: the whole Ogg MULE file. MULEHead, MULETags (the tags, over several pages if
 * needed), then packets of up to 4 frames (fewer before a key frame, or when a packet would
 * exceed MULE_PACKET_MAX), in pages of about 4 KiB, the last page's granule giving the length.
 * 0, or -1 (out of memory, bad keyframe), -2 (a frame alone exceeds MULE_PACKET_MAX). */
int mule_encode(const double *pcm, int64_t L, const mule_enc_params *pr,
                const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
                size_t *audio_bytes)
{
    int T = (int)((L + F - 1) / F) + 1;
    if (pr->keyframe <= 0 || pr->keyframe % 4)
        return -1;
    ops_t o = {0};
    int64_t *fstart = malloc(sizeof(int64_t) * (size_t)(T + 1));
    if (!fstart || encode_ops(pcm, L, pr, T, &o, fstart)) {
        free(fstart);
        return -1;
    }

    /* packets */
    crc_init();
    buf_t file = {0};
    uint8_t head[MULE_HEAD_LEN];
    memcpy(head, "MULEHead", 8);
    head[8] = MULE_VERSION;
    head[9] = 2;
    head[10] = MULE_PRE_SKIP & 255;
    head[11] = MULE_PRE_SKIP >> 8;
    le32(head + 12, 44100);
    head[16] = NB;
    head[17] = (uint8_t)pr->keyframe;
    head[18] = 4;
    head[19] = (uint8_t)mule_init_cdf_id;
    const uint8_t *hp[1] = {head};
    int hl[1] = {MULE_HEAD_LEN};
    uint32_t serial = 0x4D554C45u, seq = 0;
    int rc = page(&file, 2, 0, serial, seq++, hp, hl, 1);
    buf_t tg = {0};
    const char *vendor = "mule-audio C encoder";
    uint8_t w4[4];
    rc |= buf_put(&tg, "MULETags", 8);
    le32(w4, (uint32_t)strlen(vendor));
    rc |= buf_put(&tg, w4, 4);
    rc |= buf_put(&tg, vendor, strlen(vendor));
    le32(w4, (uint32_t)ntags);
    rc |= buf_put(&tg, w4, 4);
    for (int i = 0; i < ntags; i++) {
        le32(w4, (uint32_t)strlen(tags[i]));
        rc |= buf_put(&tg, w4, 4);
        rc |= buf_put(&tg, tags[i], strlen(tags[i]));
    }
    if (!rc)
        rc = page_big(&file, 0, 0, serial, &seq, tg.b, (int)tg.n);   /* cover art: several pages */
    free(tg.b);

    mule_models *models = mule_models_alloc(), *snap = mule_models_alloc();
    enum { MAXP = 64 };
    uint8_t *pkt[MAXP];
    int plen[MAXP], np = 0, cur_size = 0, nlace = 0;
    int64_t frames = 0, total = MULE_PRE_SKIP + L;
    size_t abytes = 0;
    if (!models || !snap)
        rc = -1;
    for (int t = 0; t < T && !rc;) {
        int n = T - t < 4 ? T - t : 4;
        for (int k = 1; k < n; k++)
            if ((t + k) % pr->keyframe == 0) {
                n = k;
                break;
            }
        int key = t % pr->keyframe == 0;
        if (key)
            mule_models_reset(models);
        uint8_t *p = malloc(MULE_PACKET_MAX);
        if (!p) {
            rc = -1;
            break;
        }
        int len;
        for (;;) {
            int hdr = 1;
            p[0] = (uint8_t)((key ? 1 : 0) | (n - 1) << 1);
            if (key) {
                le32(p + 1, (uint32_t)t);
                hdr = 5;
            }
            mule_models_copy(snap, models);
            int sz = mule_rans_encode(models, o.m + fstart[t], o.v + fstart[t], fstart[t + n] - fstart[t],
                                      p + hdr, MULE_PACKET_MAX - hdr);
            if (sz >= 0) {
                len = hdr + sz;
                break;
            }
            if (n == 1) {
                rc = -2;
                len = 0;
                break;
            }
            mule_models_copy(models, snap);
            n = n / 2 > 0 ? n / 2 : 1;
        }
        if (rc) {
            free(p);
            break;
        }
        int lace = len / 255 + 1;
        if (np && (nlace + lace > 255 || np == MAXP)) {
            rc |= page(&file, 0, frames * F, serial, seq++, (const uint8_t *const *)pkt, plen, np);
            for (int i = 0; i < np; i++)
                free(pkt[i]);
            np = cur_size = nlace = 0;
        }
        pkt[np] = p;
        plen[np++] = len;
        cur_size += len;
        nlace += lace;
        abytes += (size_t)len;
        frames += n;
        t += n;
        int last = t >= T;
        if (cur_size >= 4096 || last) {
            int64_t g = last ? total : (frames * F < total ? frames * F : total);
            rc |= page(&file, last ? 4 : 0, g, serial, seq++, (const uint8_t *const *)pkt, plen, np);
            for (int i = 0; i < np; i++)
                free(pkt[i]);
            np = cur_size = nlace = 0;
        }
    }
    for (int i = 0; i < np; i++)
        free(pkt[i]);
    mule_models_free(models);
    mule_models_free(snap);
    free(o.m);
    free(o.v);
    free(fstart);
    if (rc) {
        free(file.b);
        return rc;
    }
    *out = file.b;
    *out_len = file.n;
    if (audio_bytes)
        *audio_bytes = abytes;
    return 0;
}

/* Frees what mule_encode / mule_encode_ops returned. */
void mule_free(void *p)
{
    free(p);
}
