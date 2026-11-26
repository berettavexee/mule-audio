/* MULE decoder, the format's reference (spec/FORMAT.md is normative).
 *
 * Integer arithmetic only, no floating point and no libm, so that it runs as is on the Echo
 * Mini's core B (a Cortex-M3 without FPU) and gives the same samples, bit for bit, on every
 * machine. Every decision comes from the stream; all state derives from decoded integers.
 *
 *   - coefficients in Q24 (1.0 = 2^24), int32;
 *   - IMDCT through an n/4-point complex FFT (the structure of the firmware's HIFIACC path; an
 *     external FFT can be plugged in, mule_dec_set_fft);
 *   - window slopes, rotations and twiddles from core/fx_tables.h (tools/gen_fx_tables.py);
 *   - output: interleaved int16.
 *
 * Built with MULE_NO_MALLOC (the firmware), only the caller-memory API exists (mule_dec_init).
 * Built with MULE_DEC_V5_ONLY (core B), it reads format v5 with 8-symbol coefficients only (what
 * the encoder writes): the paths and tables of v2 to v4 are left out, and so is the room of the
 * 16-symbol coefficient models. */
#include <stdlib.h>
#include <string.h>
#include "mule.h"
#include "fx_tables.h"

typedef int32_t coef_t;                 /* Q24 */

/* Format versions read: v2 to v5, or v5 only (MULE_DEC_V5_ONLY: the version tests are constants,
 * the compiler drops the older paths) */
#ifdef MULE_DEC_V5_ONLY
#define IS_V4(d) 1
#define IS_V5(d) 1
#define COEF_ESC(d) 7
#define DEC_COEF_SYMS 8
#else
#define IS_V4(d) ((d)->v4)
#define IS_V5(d) ((d)->v5)
#define COEF_ESC(d) ((d)->coef_t)
#define DEC_COEF_SYMS 16
#endif

/* The adaptive models' inner CDF entries (n - 1 per context: cdf[0] and cdf[n] are implied, see
 * mule_cdf_find), packed stream after stream: spec 3's table, the coefficients at their widest */
#define DEC_CDF_LEN (1 * 1 + 1 * 3 + 3 * 1 + 9 * 15 + 6 * 15 + 1 * 1 + 16 * 15 \
                     + 96 * (DEC_COEF_SYMS - 1) + 1 * 15 + 1 * 7)

/* the overlap-add accumulator: the current frame's 1024 samples, then what the short blocks of
 * this frame reach beyond (448 + 7 * 128 + 256 = 1600) */
#define ACC_LEN (MULE_SHORT_OFF + 128 * (MULE_N_SUB - 1) + MULE_N_SHORT)

static const int EDGES[MULE_NB + 2] = MULE_EDGES_INIT;
static const int ALPHAS[4] = {0, 16, 26, 31};
static const int64_t POW4[4] = {256, 304, 362, 431};   /* 2^(i/4) in Q8: inter-frame rescaling */

struct mule_dec_state {
    int channels, pre_skip;
    uint32_t rate;
    int tcq_chain;                      /* v3: the trellis state runs on across the bands */
    int coef_t;                         /* the coefficient escape symbol: 15 (v2), 7 (v3 a8) */
    int v4;                             /* v4, v5: noise in coded bands' zeros, sloped noise filling */
    int v5;                             /* v5: folding in short frames, the zeros' noise level modelled */
    uint8_t tcq_next[MULE_TCQ_MAXS][4]; /* next state from (state, k mod 4) (v2: 8 states) */
    uint16_t cdf[DEC_CDF_LEN];          /* the adaptive models (reset at each key packet): inner */
    uint8_t count[MULE_NMODELS];        /* CDF entries, packed, and symbols seen (spec 3) */
    uint16_t sbase[MULE_S_COUNT];       /* each stream's first entry in cdf */
    uint8_t snsym[MULE_S_COUNT];        /* each stream's symbols */
    int qprev[2][MULE_NB], aprev[2][MULE_NB];   /* last energies and allocations (prediction) */
    uint16_t ylong[2][MULE_F];          /* previous long frame's index u, saturated at 65535 */
    int qlong[2][MULE_NB], along[2][MULE_NB], lvalid[2];   /* ... with its energies, allocations */
    uint32_t lcg;                       /* noise generator */
    int prev_type;                      /* type of the previous frame (long at start, after seek) */
    int32_t acc[2][ACC_LEN];            /* overlap-add, from the current frame's start */
    int32_t pend[2][MULE_F];            /* right half of the previous long block (unwindowed) */
    coef_t X[2][MULE_F];                /* the frame's coefficients (short frames: [8][128]) */
    union {                             /* scratch, never both at once (2 KiB saved): */
        uint16_t ycur[MULE_F];          /* a channel's indices of this frame (stream reading) */
        int32_t y[MULE_F];              /* the left half of a block's IMDCT (synthesis) */
    } sc;
#ifndef MULE_FFT_MEM_EXTERNAL
    int32_t fre[512], fim[512];         /* scratch: the FFT (else the caller's, mule_dec_set_fft_mem) */
#endif
    int pend_valid;                     /* pend holds a long block's right half */
    int need_key, drop_frames;          /* after a seek: wait for a key packet, drop its 1st frame */
    const uint8_t *p, *end;             /* rANS: words still to read */
    uint32_t x;                         /* rANS state */
    int err;                            /* the packet is damaged */
};

/* The exact 64-bit product of two int32. Cores without a 32x32 -> 64 multiply (Cortex-M0,
 * -DMULE_NO_LONG_MUL) build it from four 16 x 16 products instead of the C library's general
 * 64 x 64 multiply: the same value, so the same output, bit for bit. */
#if defined(MULE_NO_LONG_MUL) && defined(__thumb__) && !defined(__thumb2__)
/* ARMv6-M (Cortex-M0, M0+, M1): the same four products in 17 Thumb-1 instructions */
static inline int64_t smul64(int32_t a, int32_t b)
{
    uint32_t lo, hi, t0, t1;
    __asm__(".syntax unified\n\t"              /* (GCC hands Thumb-1 asm over divided) */
            "uxth  %[lo], %[a]\n\t"            /* lo = al */
            "uxth  %[t0], %[b]\n\t"            /* t0 = bl */
            "asrs  %[a], %[a], #16\n\t"        /* a = ah */
            "asrs  %[b], %[b], #16\n\t"        /* b = bh */
            "movs  %[hi], %[a]\n\t"
            "muls  %[hi], %[b], %[hi]\n\t"     /* hi = ah bh */
            "muls  %[a], %[t0], %[a]\n\t"      /* a = ah bl */
            "muls  %[t0], %[lo], %[t0]\n\t"    /* t0 = al bl */
            "muls  %[lo], %[b], %[lo]\n\t"     /* lo = al bh */
            "lsls  %[t1], %[a], #16\n\t"       /* (hi:t0) += ah bl << 16 */
            "asrs  %[a], %[a], #16\n\t"
            "adds  %[t0], %[t0], %[t1]\n\t"
            "adcs  %[hi], %[hi], %[a]\n\t"
            "lsls  %[t1], %[lo], #16\n\t"      /* (hi:t0) += al bh << 16 */
            "asrs  %[lo], %[lo], #16\n\t"
            "adds  %[t0], %[t0], %[t1]\n\t"
            "adcs  %[hi], %[hi], %[lo]\n\t"
            ".syntax divided"
            : [lo] "=&l"(lo), [hi] "=&l"(hi), [t0] "=&l"(t0), [t1] "=&l"(t1), [a] "+l"(a), [b] "+l"(b)
            :
            : "cc");
    return (int64_t)((uint64_t)hi << 32 | t0);
}
#elif defined(MULE_NO_LONG_MUL)
static inline int64_t smul64(int32_t a, int32_t b)
{
    uint32_t al = (uint16_t)a, bl = (uint16_t)b;
    int32_t ah = a >> 16, bh = b >> 16;         /* a = ah 2^16 + al, al in [0, 2^16) */
    uint32_t lo = al * bl;
    int32_t hi = ah * bh;
    int32_t m1 = ah * (int32_t)bl, m2 = (int32_t)al * bh;   /* |m| < 2^31 */
    uint32_t t = lo + ((uint32_t)m1 << 16);
    hi += (m1 >> 16) + (t < lo);
    lo = t;
    t = lo + ((uint32_t)m2 << 16);
    hi += (m2 >> 16) + (t < lo);
    return (int64_t)((uint64_t)(uint32_t)hi << 32 | t);
}
#else
static inline int64_t smul64(int32_t a, int32_t b)
{
    return (int64_t)a * b;
}
#endif

/* k * m for a k that usually fits 32 bits (smul64 then), exact either way: past 32 bits, k =
 * kh 2^32 + kl, kl in [0, 2^32): kl m = smul64((int32_t)kl, m) + (m 2^32 if kl >= 2^31), and kh m
 * only matters modulo 2^32 (the product fits 64 bits) */
static inline int64_t mul64k(int64_t k, int32_t m)
{
    if (k == (int32_t)k)
        return smul64((int32_t)k, m);
#ifdef MULE_NO_LONG_MUL
    uint32_t kl = (uint32_t)k, kh = (uint32_t)((uint64_t)k >> 32);
    uint32_t top = kh * (uint32_t)m + (kl >> 31 ? (uint32_t)m : 0);
    return (int64_t)((uint64_t)smul64((int32_t)kl, m) + ((uint64_t)top << 32));
#else
    return k * m;
#endif
}

/* floor(n / d), n >= 0, d > 0: C's 64-bit division, but by shifts and subtractions over the
 * quotient's bits only (the C library's general 64 / 64 division is slow on cores without a
 * divider). The same quotient, so the same output. */
#ifdef MULE_NO_LONG_MUL
/* floor(n / d) for a quotient below 2^(sh + 1): restoring division from d << sh down */
static uint64_t udiv_bits(uint64_t n, uint32_t d, int sh)
{
    uint64_t dd = (uint64_t)d << sh, q = 0;
    for (; sh >= 0; sh--, dd >>= 1) {
        q <<= 1;
        if (n >= dd) {
            n -= dd;
            q |= 1;
        }
    }
    return q;
}
#endif

static uint64_t udiv64_32(uint64_t n, uint32_t d)
{
    if (!(n >> 32))
        return (uint32_t)n / d;
#ifdef MULE_NO_LONG_MUL                         /* d << sh: d's top bit at n's (n >= 2^32 > d) */
    return udiv_bits(n, d, __builtin_clz(d) + 32 - __builtin_clz((uint32_t)(n >> 32)));
#else
    return n / d;
#endif
}

/* n / d truncated towards zero (C's division), d > 0 */
static inline int64_t sdiv64_32(int64_t n, uint32_t d)
{
    return n >= 0 ? (int64_t)udiv64_32((uint64_t)n, d) : -(int64_t)udiv64_32(-(uint64_t)n, d);
}

/* -DMULE_PROF (bench/qemu): the caller's mule_prof_mark(i) is told where the decoder enters
 * section i (0 stream reading, 1 IMDCT pre-rotation, 2 FFT, 3 post-rotation, 4 windows and
 * overlap-add, 5 output, 6 noise-filled and folded bands, 7 inverse M/S) */
#ifdef MULE_PROF
void mule_prof_mark(int section);
#define PROF(i) mule_prof_mark(i)
#else
#define PROF(i) ((void)0)
#endif

/* the state fits MULE_DEC_STATE_MAX (C99: a negative array size fails the build otherwise) */
typedef char mule_dec_state_fits[sizeof(struct mule_dec_state) <= MULE_DEC_STATE_MAX ? 1 : -1];

/* ---------------- stream reading ---------------- */

/* The next 16-bit little-endian word of the packet; sets err past its end. */
static uint16_t rd16(mule_dec *d)
{
    if (d->p + 2 > d->end) {
        d->err = 1;
        return 0;
    }
    uint16_t w = (uint16_t)(d->p[0] | d->p[1] << 8);
    d->p += 2;
    return w;
}

/* rANS decoding step for a symbol at [start, start + freq) of the 2^15 range (slot: the state's
 * low 15 bits), then renormalisation by 16-bit words. */
static void take(mule_dec *d, uint32_t slot, uint32_t start, uint32_t freq)
{
    d->x = freq * (d->x >> MULE_PROB_BITS) + slot - start;
    if (d->x < (1u << 16))
        d->x = (d->x << 16) | rd16(d);
}

#ifdef MULE_STATS                        /* measurement build only (-DMULE_STATS: tools/mule_dec.c prints the counts; eval/results/C-LOG.md) */
uint64_t mule_stat_calls[MULE_S_COUNT], mule_stat_search[MULE_S_COUNT], mule_stat_update[MULE_S_COUNT];
uint64_t mule_stat_raw;
#endif

/* One symbol of stream `stream`, context `ctx`, with its adaptive model (updated). */
static int sym(mule_dec *d, int stream, int ctx)
{
    int n = d->snsym[stream];
    uint16_t *c = d->cdf + d->sbase[stream] + ctx * (n - 1);
    uint32_t slot = d->x & (MULE_PROB_ONE - 1), start = 0, freq = 0;
    int s = mule_cdf_find(c, n, slot, &start, &freq);
#ifdef MULE_STATS
    mule_stat_calls[stream]++;
    mule_stat_search[stream] += (uint64_t)(s + 1);
    mule_stat_update[stream] += (uint64_t)(n - 1);
#endif
    if (s < 0) {                        /* cannot happen with a valid model */
        d->err = 1;
        return 0;
    }
    take(d, slot, start, freq);
    mule_cdf_update(c, n, &d->count[mule_stream_off[stream] + ctx], s);
    return s;
}

/* `bits` raw bits (1 .. 15), coded with a uniform distribution. */
static uint32_t raw(mule_dec *d, int bits)
{
#ifdef MULE_STATS
    mule_stat_raw++;
#endif
    uint32_t slot = d->x & (MULE_PROB_ONE - 1);
    uint32_t v = slot >> (MULE_PROB_BITS - bits);
    take(d, slot, v << (MULE_PROB_BITS - bits), 1u << (MULE_PROB_BITS - bits));
    return v;
}

/* A residual of the energy and allocation alphabets (spec 5.4): symbols 0 .. 14 are -7 .. 7, 15
 * an escape (an Exp-Golomb magnitude from 8 up, then a sign bit). */
static int signed_val(mule_dec *d, int s)
{
    if (s < 15)
        return s - 7;
    int k = sym(d, MULE_S_EAESC, 0);
    uint32_t v = (1u << k) - 1 + (k ? raw(d, k) : 0);
    int mag = (int)v + 8;
    return raw(d, 1) ? -mag : mag;
}

/* |v| (no libc on core B: built with -fno-builtin). */
static int iabs(int v)
{
    return v < 0 ? -v : v;
}

/* A band's class for the contexts: 0 below band 8, 1 below band 16, 2 above. */
static int band_class(int b)
{
    return b < 8 ? 0 : (b < 16 ? 1 : 2);
}

/* The neighbourhood measure m of a coefficient (its two predecessors, the previous frame) mapped
 * to one of the 6 magnitude contexts. */
static int nc_map(int64_t m)
{
    static const int t[9] = {0, 1, 2, 3, 3, 4, 4, 4, 4};
    return m < 9 ? t[m] : 5;
}

/* floor(a / b) for b > 0 (C's division truncates towards zero). */
static int floor_div(int a, int b)
{
    return a >= 0 ? a / b : -((-a + b - 1) / b);
}

/* ---------------- reconstruction: coefficient values, noise, M/S ---------------- */

/* k * 2^(E/4) in Q24, rounded (E in quarter-log2 units), on 64 bits. */
static int64_t fx_scale64(int64_t k, int E)
{
    int sh = 6 - floor_div(E, 4);       /* Q30 mantissa -> Q24, times 2^floor(E/4) */
    int64_t v = k * fx_pow4_q30[E & 3];
    if (sh <= 0)
        return v << -sh;
    if (sh >= 63)
        return 0;
    return (v + ((int64_t)1 << (sh - 1))) >> sh;
}

/* floor(sqrt(v)), bit by bit. */
static uint32_t isqrt64(uint64_t v)
{
    uint64_t r = 0, bit = (uint64_t)1 << 62;
    while (bit > v)
        bit >>= 2;
    while (bit) {
        if (v >= r + bit) {
            v -= r + bit;
            r = (r >> 1) + bit;
        } else
            r >>= 1;
        bit >>= 2;
    }
    return (uint32_t)r;
}

/* A band's reconstruction factor D/2 * 2^(q/4) = 2^((q - a + 5) / 4), as a Q30 mantissa and a
 * shift to Q24, computed once per band (scale_of) and applied per coefficient (coef_value). */
typedef struct {
    int64_t mant;                       /* 2^((E mod 4) / 4), Q30 */
    int sh;                             /* right shift to Q24 (negative: left) */
} band_scale;

/* The factor of a band of energy index q and allocation a. */
static band_scale scale_of(int q, int a)
{
    band_scale bs;
    int E = q - a + 5;
    bs.mant = fx_pow4_q30[E & 3];
    bs.sh = 6 - floor_div(E, 4);
    return bs;
}

/* The coefficient of TCQ level k: k * factor, rounded, saturated to int32. */
static coef_t coef_value(int64_t k, const band_scale *bs)
{
    int64_t v = mul64k(k, (int32_t)bs->mant);   /* (a Q30 mantissa < 2^31) */
    if (bs->sh <= 0)
        v *= (int64_t)1 << -bs->sh;     /* (0 with valid q and a; never a shift of v < 0) */
    else if (bs->sh < 63)
        v = (v + ((int64_t)1 << (bs->sh - 1))) >> bs->sh;
    else
        v = 0;
    return v > INT32_MAX ? INT32_MAX : (v < -INT32_MAX ? -INT32_MAX : (int32_t)v);
}

/* A noise-filled band (allocation 0): n values of the LCG z_i, scaled to the band's energy,
 * X = z * 2^(q/4) * sqrt(n / sum z^2) (spec 5.3); idx: the coefficients' places in X. */
static void noise_band(mule_dec *d, coef_t *X, const int *idx, int n, int q)
{
    int32_t z[MULE_BAND_MAX];
    int64_t e = 0;
    for (int i = 0; i < n; i++) {
        d->lcg = d->lcg * 1664525u + 1013904223u;
        z[i] = (int32_t)(d->lcg >> 16) - 32768;
        e += (uint32_t)(z[i] * z[i]);           /* (<= 2^30) */
    }
    uint32_t R = isqrt64((uint64_t)e);
    if (!R) {
        for (int i = 0; i < n; i++)
            X[idx[i]] = 0;
        return;
    }
    int64_t A = fx_scale64(1 << 8, q);                          /* 2^(q/4), Q32 */
    int64_t gain = sdiv64_32(A * (int64_t)isqrt64((uint64_t)n << 32), R);   /* sqrt(n) (Q16) / R */
    for (int i = 0; i < n; i++)                                 /* Q48 per unit of z -> Q24 */
        X[idx[i]] = (int32_t)(mul64k(gain, z[i]) >> 24);
}

/* v4: 2^x in Q16 for x in Q16 (|x| <= 4), the fraction by a cubic (0.1 %). */
static int64_t exp2_q16(int64_t x)
{
    int32_t i = (int32_t)(x >> 16);             /* x = i + f, f in [0, 1); |i| <= 4 */
    uint32_t f = (uint32_t)x & 0xFFFF;          /* every product below < 2^32 */
    uint32_t p = 65536 + ((f * (45426 + ((f * (15743 + ((f * 4367) >> 16))) >> 16))) >> 16);
    return i >= 0 ? (int64_t)p << i : (int64_t)(p >> -i);
}

/* v4 (spec 5.3): noise_band with a slope, for a long frame's noise-filled band b from
 * MULE_NF_START up: line i weighted by
 * 2^(s (p_i - c_b)), s the log2 slope per line through the levels of the neighbouring bands
 * (both if heard, else the one heard with b itself), c_b the band's centre; then scaled to the
 * band's energy as noise_band does. */
static void noise_band_sloped(mule_dec *d, coef_t *X, const int *idx, int n, const int *q, int b)
{
    int l = b > 0 && q[b - 1] > MULE_QMIN ? b - 1 : b;
    int r = b + 1 < MULE_NB && q[b + 1] > MULE_QMIN ? b + 1 : b;
    int64_t s = 0;                              /* log2 per line, Q16 (q / 4) */
    if (l < r) {
        int cl = 4 * (EDGES[l] + EDGES[l + 1]), cr = 4 * (EDGES[r] + EDGES[r + 1]);
        s = ((q[r] - q[l]) * (1 << 14)) / (cr - cl);    /* (|.| < 2^21: 32 bits) */
    }
    if (!s) {
        noise_band(d, X, idx, n, q[b]);
        return;
    }
    int cb = 4 * (EDGES[b] + EDGES[b + 1]);
    int64_t lim = (1 << 16) / (n / 2 > 0 ? n / 2 : 1);
    s = s > lim ? lim : (s < -lim ? -lim : s);  /* +-1 log2 (6 dB) at the band's ends */
    int32_t z[MULE_BAND_MAX];
    int64_t e = 0;
    for (int i = 0; i < n; i++) {
        d->lcg = d->lcg * 1664525u + 1013904223u;
        int64_t w = exp2_q16(s * (8 * EDGES[b] + i - cb) + (s >> 1));  /* line centre */
        z[i] = (int32_t)(smul64((int32_t)(d->lcg >> 16) - 32768, (int32_t)w) >> 18);   /* |z| < 2^15 */
        e += (uint32_t)(z[i] * z[i]);           /* (< 2^30) */
    }
    uint32_t R = isqrt64((uint64_t)e);
    if (!R) {
        for (int i = 0; i < n; i++)
            X[idx[i]] = 0;
        return;
    }
    int64_t A = fx_scale64(1 << 8, q[b]);
    int64_t gain = sdiv64_32(A * (int64_t)isqrt64((uint64_t)n << 32), R);
    for (int i = 0; i < n; i++)
        X[idx[i]] = (int32_t)(mul64k(gain, z[i]) >> 24);
}

/* v4 (spec 5.3): the noise of a zero coefficient in a coded band, level nf (1..7):
 * z (the LCG, uniform) scaled to an rms of NF_GAIN[nf] times the band's level unit D/2, the
 * gains 0.5 * 2^(-(nf - 1)/2), -6 to -24 dB; NF_Q8: gain * sqrt(3) in Q8 per 2^15 of z. */
static const int32_t NF_Q8[8] = {0, 222, 157, 111, 78, 55, 39, 28};

static coef_t nf_value(mule_dec *d, int nf, const band_scale *bs)
{
    d->lcg = d->lcg * 1664525u + 1013904223u;
    int32_t z = (int32_t)(d->lcg >> 16) - 32768;
    band_scale b8 = {bs->mant, bs->sh + 8};     /* the level in Q8 */
    return coef_value((z * NF_Q8[nf]) >> 15, &b8);     /* (|z| <= 2^15: 32 bits) */
}

/* v5 (spec 5.3): a zero-bit band of a short frame from MULE_NF_START up, filled from the decoded
 * lines w (its width) below each of its lines in the same window, as Opus' folding: that shape and
 * the LCG noise, each normalised, mixed with the weights cos and sin of MULE_FOLD_MIX / 8 * 90
 * degrees (Q8), then scaled to the band's energy as noise_band does; pure noise when the lines
 * below are silent. */
static const int32_t FOLD_COS[9] = {256, 251, 237, 213, 181, 142, 98, 50, 0};

/* (No local arrays: the source lines, below the band in its window, are read again; the noise is
 * replayed from the generator's state; the mix is written into the band, then scaled in place.) */
static void fold_band(mule_dec *d, coef_t *X, const int *idx, int n, int q, int w)
{
    int64_t es = 0, ez = 0;
    uint32_t lcg0 = d->lcg;
    for (int i = 0; i < n; i++) {               /* |sv| < 2^24, |zv| <= 2^15 */
        int32_t sv = X[idx[i] - w] >> 8;
        es += smul64(sv, sv);
        d->lcg = d->lcg * 1664525u + 1013904223u;
        int32_t zv = (int32_t)(d->lcg >> 16) - 32768;
        ez += (uint32_t)(zv * zv);
    }
    uint32_t Rs = isqrt64((uint64_t)es), Rz = isqrt64((uint64_t)ez);
    int32_t cf = Rs ? FOLD_COS[MULE_FOLD_MIX] : 0, cn = Rs ? FOLD_COS[8 - MULE_FOLD_MIX] : 256;
    int32_t sq = (int32_t)isqrt64((uint64_t)n << 32);   /* sqrt(n), Q16: < 2^20 (n <= 176) */
    int64_t e = 0;
    d->lcg = lcg0;                              /* the same noise again */
    for (int i = 0; i < n; i++) {               /* each part at an rms of 2^16; |t| < 2^21 */
        int32_t sv = X[idx[i] - w] >> 8;
        d->lcg = d->lcg * 1664525u + 1013904223u;
        int32_t zv = (int32_t)(d->lcg >> 16) - 32768;
        /* |sv| <= Rs and |zv| <= Rz (each is one of the summed squares): quotients <= sq < 2^20 */
        int32_t a = Rs ? (int32_t)sdiv64_32(smul64(sv, sq), Rs) : 0;
        int32_t b = Rz ? (int32_t)sdiv64_32(smul64(zv, sq), Rz) : 0;
        int32_t t = (cf * a + cn * b) >> 8;     /* (256 2^20 2: < 2^30) */
        X[idx[i]] = t;
        e += smul64(t, t);
    }
    uint32_t R = isqrt64((uint64_t)e);
    if (!R) {
        for (int i = 0; i < n; i++)
            X[idx[i]] = 0;
        return;
    }
    int64_t A = fx_scale64(1 << 8, q);
    int64_t gain = sdiv64_32(A * sq, R);
    for (int i = 0; i < n; i++)
        X[idx[i]] = (int32_t)(mul64k(gain, X[idx[i]]) >> 24);
}

/* M/S to L/R in place: L = (M + S) / sqrt 2, R = (M - S) / sqrt 2 (spec 5.5). */
static void inverse_ms(coef_t *a, coef_t *b)
{
    int64_t m = *a, s = *b;                     /* (m +- s: 33 bits) */
    *a = (int32_t)(mul64k(m + s, FX_INVSQRT2) >> 31);
    *b = (int32_t)(mul64k(m - s, FX_INVSQRT2) >> 31);
}

/* ---------------- transform and synthesis ---------------- */

static int (*fft_hook)(int32_t *re, int32_t *im, int bits);
static int32_t *fft_re, *fft_im;        /* the caller's FFT memory (mule_dec_set_fft_mem), or NULL */

/* An external FFT for the IMDCT (see mule.h); NULL: the software one. */
void mule_dec_set_fft(int (*fft)(int32_t *re, int32_t *im, int bits))
{
    fft_hook = fft;
}

/* The IMDCT's FFT memory, 512 points each (see mule.h): the device's accelerator memory, which
 * the external FFT then works on in place; NULL: the state's own (required with
 * MULE_FFT_MEM_EXTERNAL, whose state has none). */
void mule_dec_set_fft_mem(int32_t *re, int32_t *im)
{
    fft_re = re;
    fft_im = im;
}

/* a + b and a - b on 32 bits, wrapping as the Cortex-M3 does (two's complement, defined in C
 * through unsigned arithmetic): a valid stream never overflows (the transform's headroom), a
 * malformed one gives wrong samples, never undefined behaviour (tools/fuzz). */
static inline int32_t wadd(int32_t a, int32_t b)
{
    return (int32_t)((uint32_t)a + (uint32_t)b);
}

static inline int32_t wsub(int32_t a, int32_t b)
{
    return (int32_t)((uint32_t)a - (uint32_t)b);
}

#if defined(MULE_NO_LONG_MUL) && defined(__thumb__) && !defined(__thumb2__)
/* fx_fft for ARMv6-M (Cortex-M0, M0+), the same values bit for bit: each 64-bit product from four
 * 16 x 16 ones, summed exactly on 64 bits; the twiddle's halves split once per k (the butterflies
 * of a stage, k outer, i inner: disjoint pairs, the same results in any order).
 * mule_fft_v6m(re, im, n, fx_fft_tw). Stack: 0 wl, 4 wh, 8 xl, 12 xh (the twiddle's halves),
 * 16 vr, 20 re, 24 len (bytes), 28 twiddle stride (bytes), 32 twiddle pointer, 36 k (bytes),
 * 40 n (bytes), 44 twiddles; r8 a's pointer, r9 im - re, r10 len / 2, r11 len, r12 re's end;
 * r0 rh, r1 ih, r2 rl, r3 il (the halves of re[b], im[b]), r4:r5 the 64-bit sum. */
void mule_fft_v6m(int32_t *re, int32_t *im, int n, const int32_t *tw);
__asm__(
    "    .syntax unified\n"
    "    .text\n"
    "    .align 2\n"
    "    .global mule_fft_v6m\n"
    "    .type mule_fft_v6m, %function\n"
    "    .thumb_func\n"
    "mule_fft_v6m:\n"
    "push  {r4-r7, lr}\n"
    "mov   r4, r8\n"
    "mov   r5, r9\n"
    "mov   r6, r10\n"
    "mov   r7, r11\n"
    "push  {r4-r7}\n"
    "sub   sp, #48\n"
    "str   r0, [sp, #20]\n"
    "subs  r1, r1, r0\n"
    "mov   r9, r1\n"
    "lsls  r2, r2, #2\n"
    "str   r2, [sp, #40]\n"
    "adds  r4, r0, r2\n"
    "mov   r12, r4\n"
    "str   r3, [sp, #44]\n"
    "movs  r4, #8\n"
    "str   r4, [sp, #24]\n"
    "movs  r4, #1\n"
    "lsls  r4, r4, #11\n"
    "str   r4, [sp, #28]\n"
    ".Lfft_stage:\n"
    "ldr   r4, [sp, #24]\n"
    "mov   r11, r4\n"
    "lsrs  r4, r4, #1\n"
    "mov   r10, r4\n"
    "ldr   r4, [sp, #44]\n"
    "str   r4, [sp, #32]\n"
    "movs  r4, #0\n"
    "str   r4, [sp, #36]\n"
    ".Lfft_k:\n"
    "ldr   r4, [sp, #32]\n"
    "ldr   r5, [r4]\n"
    "ldr   r6, [r4, #4]\n"
    "uxth  r7, r5\n"
    "str   r7, [sp, #0]\n"
    "asrs  r5, r5, #16\n"
    "str   r5, [sp, #4]\n"
    "uxth  r7, r6\n"
    "str   r7, [sp, #8]\n"
    "asrs  r6, r6, #16\n"
    "str   r6, [sp, #12]\n"
    "ldr   r5, [sp, #28]\n"
    "adds  r4, r4, r5\n"
    "str   r4, [sp, #32]\n"
    "ldr   r4, [sp, #20]\n"
    "ldr   r5, [sp, #36]\n"
    "adds  r4, r4, r5\n"
    "mov   r8, r4\n"
    ".Lfft_bf:\n"
    "mov   r6, r8\n"
    "add   r6, r10\n"
    "mov   r7, r9\n"
    "ldr   r0, [r6]\n"
    "ldr   r1, [r6, r7]\n"
    "uxth  r2, r0\n"
    "asrs  r0, r0, #16\n"
    "uxth  r3, r1\n"
    "asrs  r1, r1, #16\n"
    "ldr   r4, [sp, #4]\n"
    "muls  r4, r0, r4\n"
    "ldr   r6, [sp, #12]\n"
    "muls  r6, r1, r6\n"
    "subs  r4, r4, r6\n"
    "ldr   r5, [sp, #0]\n"
    "muls  r5, r2, r5\n"
    "ldr   r6, [sp, #8]\n"
    "muls  r6, r3, r6\n"
    "subs  r5, r5, r6\n"
    "movs  r6, #0\n"
    "sbcs  r4, r4, r6\n"
    "ldr   r6, [sp, #0]\n"
    "muls  r6, r0, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "adds  r5, r5, r7\n"
    "adcs  r4, r4, r6\n"
    "ldr   r6, [sp, #4]\n"
    "muls  r6, r2, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "adds  r5, r5, r7\n"
    "adcs  r4, r4, r6\n"
    "ldr   r6, [sp, #8]\n"
    "muls  r6, r1, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "subs  r5, r5, r7\n"
    "sbcs  r4, r4, r6\n"
    "ldr   r6, [sp, #12]\n"
    "muls  r6, r3, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "subs  r5, r5, r7\n"
    "sbcs  r4, r4, r6\n"
    "lsls  r4, r4, #1\n"
    "lsrs  r5, r5, #31\n"
    "orrs  r4, r4, r5\n"
    "str   r4, [sp, #16]\n"
    "ldr   r4, [sp, #12]\n"
    "muls  r4, r0, r4\n"
    "ldr   r6, [sp, #4]\n"
    "muls  r6, r1, r6\n"
    "adds  r4, r4, r6\n"
    "ldr   r5, [sp, #8]\n"
    "muls  r5, r2, r5\n"
    "ldr   r6, [sp, #0]\n"
    "muls  r6, r3, r6\n"
    "adds  r5, r5, r6\n"
    "movs  r6, #0\n"
    "adcs  r4, r4, r6\n"
    "ldr   r6, [sp, #8]\n"
    "muls  r6, r0, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "adds  r5, r5, r7\n"
    "adcs  r4, r4, r6\n"
    "ldr   r6, [sp, #12]\n"
    "muls  r6, r2, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "adds  r5, r5, r7\n"
    "adcs  r4, r4, r6\n"
    "ldr   r6, [sp, #0]\n"
    "muls  r6, r1, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "adds  r5, r5, r7\n"
    "adcs  r4, r4, r6\n"
    "ldr   r6, [sp, #4]\n"
    "muls  r6, r3, r6\n"
    "lsls  r7, r6, #16\n"
    "asrs  r6, r6, #16\n"
    "adds  r5, r5, r7\n"
    "adcs  r4, r4, r6\n"
    "lsls  r4, r4, #1\n"
    "lsrs  r5, r5, #31\n"
    "orrs  r4, r4, r5\n"
    "mov   r6, r8\n"
    "mov   r7, r9\n"
    "ldr   r0, [r6]\n"
    "ldr   r1, [r6, r7]\n"
    "ldr   r5, [sp, #16]\n"
    "adds  r2, r0, r5\n"
    "subs  r0, r0, r5\n"
    "adds  r3, r1, r4\n"
    "subs  r1, r1, r4\n"
    "str   r2, [r6]\n"
    "str   r3, [r6, r7]\n"
    "add   r6, r10\n"
    "str   r0, [r6]\n"
    "str   r1, [r6, r7]\n"
    "add   r8, r11\n"
    "cmp   r8, r12\n"
    "bhs   .Lfft_knext\n"
    "b     .Lfft_bf\n"
    ".Lfft_knext:\n"
    "ldr   r4, [sp, #36]\n"
    "adds  r4, r4, #4\n"
    "str   r4, [sp, #36]\n"
    "cmp   r4, r10\n"
    "bhs   .Lfft_snext\n"
    "b     .Lfft_k\n"
    ".Lfft_snext:\n"
    "ldr   r4, [sp, #28]\n"
    "lsrs  r4, r4, #1\n"
    "str   r4, [sp, #28]\n"
    "ldr   r4, [sp, #24]\n"
    "lsls  r4, r4, #1\n"
    "str   r4, [sp, #24]\n"
    "ldr   r5, [sp, #40]\n"
    "cmp   r4, r5\n"
    "bhi   .Lfft_done\n"
    "b     .Lfft_stage\n"
    ".Lfft_done:\n"
    "add   sp, #48\n"
    "pop   {r4-r7}\n"
    "mov   r8, r4\n"
    "mov   r9, r5\n"
    "mov   r10, r6\n"
    "mov   r11, r7\n"
    "pop   {r4-r7, pc}\n"
    "    .size mule_fft_v6m, . - mule_fft_v6m\n");
#define MULE_FFT_V6M 1
#endif

/* In-place complex FFT (forward, unscaled) of n = 64 or 512 points. The input is in bit-reversed
 * order already, as HIFIACC wants it; twiddles exp(-2 i pi k / 512) in Q31. */
static void fx_fft(int32_t *re, int32_t *im, int n)
{
#ifdef MULE_FFT_V6M
    mule_fft_v6m(re, im, n, fx_fft_tw);
    return;
#endif
    for (int len = 2; len <= n; len <<= 1) {
        int step = 512 / len;
        for (int i = 0; i < n; i += len)
            for (int k = 0; k < len / 2; k++) {
                int32_t wr = fx_fft_tw[2 * k * step], wi = fx_fft_tw[2 * k * step + 1];
                int a = i + k, b = a + len / 2;
                int32_t vr = (int32_t)((smul64(re[b], wr) - smul64(im[b], wi)) >> 31);
                int32_t vi = (int32_t)((smul64(re[b], wi) + smul64(im[b], wr)) >> 31);
                re[b] = wsub(re[a], vr);
                im[b] = wsub(im[a], vi);
                re[a] = wadd(re[a], vr);
                im[a] = wadd(im[a], vi);
            }
    }
}

/* (u g) >> 31 on 32 bits, for the IMDCT's gains: g = 2^28 (n = 256) is a shift */
static inline int32_t post_gain(int64_t u, int32_t g)
{
    if (g == FX_G128 && FX_G128 == 1 << 28)
        return (int32_t)(u >> 3);
    return (int32_t)(mul64k(u, g) >> 31);
}

/* y[0..n) = g * IMDCT(X[0..m)) in Q24, n = 2m (2048 or 256), through the n/4-point FFT:
 *   d = w FFT(w (X[2j] + i X[m-1-2j])), w[j] = exp(-2 i pi (j + 1/8) / n)
 *   out[4q] = -Im d[q], out[4q+1] = -Re d[q], out[4q+2] = Re d[n/4-1-q], out[4q+3] = Im d[n/4-1-q]
 *   y[i] = out[m-2-2i], -out[2t], out[m-1-2t], out[2t+1] in the four quarters (t = i mod n/4)
 * The pre-rotation halves (headroom for the unscaled FFT), the post-rotation doubles back.
 * y[i] for i < m goes to ylo, the rest to yhi[i - m] (a long block's right half: pend). */
static void imdct(mule_dec *d, const int32_t *X, int32_t *ylo, int32_t *yhi, int m)
{
    PROF(1);
    int n = 2 * m, n4 = n / 4, bits = n == 2048 ? 9 : 6;
    const int32_t *w = n == 2048 ? fx_w2048 : fx_w256;
    int32_t g = n == 2048 ? FX_G1024 : FX_G128;
#ifdef MULE_FFT_MEM_EXTERNAL
    int32_t *re = fft_re, *im = fft_im;
    (void)d;
#else
    int32_t *re = fft_re ? fft_re : d->fre, *im = fft_re ? fft_im : d->fim;
#endif
    uint32_t r = 0;                             /* bitrev(j, bits), counted in reverse */
    for (int j = 0; j < n4; j++) {
        int32_t a = X[2 * j], b = X[m - 1 - 2 * j], c = w[2 * j], s = w[2 * j + 1];
        re[r] = (int32_t)((smul64(a, c) + smul64(b, s)) >> 32);
        im[r] = (int32_t)((smul64(b, c) - smul64(a, s)) >> 32);
        uint32_t bit = (uint32_t)n4 >> 1;       /* r + 1 in reversed bit order */
        while (r & bit) {
            r ^= bit;
            bit >>= 1;
        }
        r |= bit;
    }
    (void)bits;
    PROF(2);
    if (!fft_hook || !fft_hook(re, im, bits))
        fx_fft(re, im, n4);
    PROF(3);
    /* post-rotation and unfolding together; out[j] (j = 4q .. 4q+3) goes to two outputs:
     *   j even (2t): y[n4 + t] = -g out, y[n4 - 1 - t] = g out
     *   j odd (2t + 1): y[3 n4 + t] = g out, y[3 n4 - 1 - t] = g out */
    int32_t *h = yhi - m;
    for (int q = 0; q < n4 / 2; q++) {
        int k = n4 - 1 - q;
        int32_t fr = re[q], fi = im[q], c = w[2 * q], s = w[2 * q + 1];
        int32_t gr = re[k], gi = im[k], c2 = w[2 * k], s2 = w[2 * k + 1];
        int32_t o0 = post_gain(-((smul64(fi, c) - smul64(fr, s)) >> 30), g);
        int32_t o1 = post_gain(-((smul64(fr, c) + smul64(fi, s)) >> 30), g);
        int32_t o2 = post_gain((smul64(gr, c2) + smul64(gi, s2)) >> 30, g);
        int32_t o3 = post_gain((smul64(gi, c2) - smul64(gr, s2)) >> 30, g);
        ylo[n4 + 2 * q] = -o0;
        ylo[n4 - 1 - 2 * q] = o0;
        h[3 * n4 + 2 * q] = o1;
        h[3 * n4 - 1 - 2 * q] = o1;
        ylo[n4 + 2 * q + 1] = -o2;
        ylo[n4 - 2 - 2 * q] = o2;
        h[3 * n4 + 2 * q + 1] = o3;
        h[3 * n4 - 2 - 2 * q] = o3;
    }
    PROF(4);
}

/* The frame's overlap-add (spec 6), per channel: the previous long block's falling half (its
 * slope set by this frame's type), then this frame's block(s): a long block's rising half (its
 * slope set by the previous frame's type), its right half kept in pend; or the 8 short blocks,
 * each windowed by the 128-sample slopes, at 448 + 128 k. */
static void synth(mule_dec *d, int type)
{
    int prev_short = d->prev_type == 1, cur_short = type == 1;
    for (int c = 0; c < 2; c++) {
        int32_t *y = d->sc.y, *acc = d->acc[c];
        if (d->pend_valid) {
            int s = cur_short ? 128 : 1024, z = (MULE_F - s) / 2;
            const int32_t *sl = s == 1024 ? fx_slope1024 : fx_slope128;
            const int32_t *p = d->pend[c];
            for (int i = 0; i < z; i++)         /* window 1, then the slope read backwards */
                acc[i] += p[i];
            for (int i = z; i < z + s; i++)
                acc[i] += (int32_t)(smul64(p[i], sl[z + s - 1 - i]) >> 31);
        }                                       /* (window 0 beyond: nothing) */
        if (!cur_short) {
            imdct(d, d->X[c], y, d->pend[c], MULE_F);
            int s = prev_short ? 128 : 1024, z = (MULE_F - s) / 2;
            const int32_t *sl = s == 1024 ? fx_slope1024 : fx_slope128;
            for (int i = z; i < z + s; i++)
                acc[i] += (int32_t)(smul64(y[i], sl[i - z]) >> 31);
            for (int i = z + s; i < MULE_F; i++)
                acc[i] += y[i];
        } else {
            for (int k = 0; k < MULE_N_SUB; k++) {
                imdct(d, d->X[c] + 128 * k, y, y + 128, 128);
                int o = MULE_SHORT_OFF + 128 * k;
                for (int i = 0; i < MULE_N_SHORT; i++) {
                    int32_t wv = i < 128 ? fx_slope128[i] : fx_slope128[MULE_N_SHORT - 1 - i];
                    acc[o + i] += (int32_t)(smul64(y[i], wv) >> 31);
                }
            }
        }
    }
}

/* A Q24 accumulator value as a 16-bit sample: rounded, saturated. */
static int16_t to_sample(int32_t v)
{
    int32_t s = (v + (1 << 8)) >> 9;
    return (int16_t)(s > 32767 ? 32767 : (s < -32768 ? -32768 : s));
}

/* ---------------- frame decoding ---------------- */

/* The models' layout in cdf (sbase, snsym) for the stream's alphabet; 0 if it does not fit. */
static int models_layout(mule_dec *d)
{
    int off = 0;
    for (int s = 0; s < MULE_S_COUNT; s++) {
        int n;
        mule_stream_init(s, COEF_ESC(d) == 7, &n);
        d->sbase[s] = (uint16_t)off;
        d->snsym[s] = (uint8_t)n;
        off += mule_stream_nctx[s] * (n - 1);
    }
    return off <= DEC_CDF_LEN;
}

/* Every model to its initial state (spec 3, 4): the trained CDF of its stream and context with a
 * count of 16, or the uniform one with a count of 0 (as mule_model_init_cdf and mule_model_init). */
static void models_reset(mule_dec *d)
{
    for (int s = 0; s < MULE_S_COUNT; s++) {
        int n;
        const uint16_t *init = mule_stream_init(s, COEF_ESC(d) == 7, &n);
        for (int c = 0; c < mule_stream_nctx[s]; c++) {
            uint16_t *e = d->cdf + d->sbase[s] + c * (n - 1);
            for (int i = 1; i < n; i++)
                e[i - 1] = init ? init[c * (n + 1) + i] : (uint16_t)((MULE_PROB_ONE * (uint32_t)i) / (uint32_t)n);
            d->count[mule_stream_off[s] + c] = init ? 16 : 0;
        }
    }
}

/* The state a key packet starts from (spec 4): initial models, predictions reset, no previous
 * long frame, the noise generator's seed. */
static void reset_key(mule_dec *d)
{
    models_reset(d);
    for (int c = 0; c < 2; c++)
        for (int b = 0; b < MULE_NB; b++) {
            d->qprev[c][b] = MULE_Q_RESET;
            d->aprev[c][b] = MULE_A_RESET;
        }
    d->lvalid[0] = d->lvalid[1] = 0;
    d->lcg = MULE_LCG_SEED;
}

/* A group of windows: type 0, the long frame's one window; type 1, short windows [k0, k1). */
typedef struct {
    int type, k0, k1;
} group;

/* The number of coefficients of band b in group g. */
static int band_count(const group *g, int b)
{
    int w = EDGES[b + 1] - EDGES[b];
    return g->type == 0 ? w * 8 : w * (g->k1 - g->k0);
}

/* The place in X of band b's coefficient i in group g (scan order: window, then frequency;
 * short frames lay X out as [8][128]). */
static int coef_index(const group *g, int b, int i)
{
    if (g->type == 0)
        return EDGES[b] * 8 + i;
    int w = EDGES[b + 1] - EDGES[b];
    return (g->k0 + i / w) * 128 + EDGES[b] + i % w;
}

/* The groups of windows of a frame of block type `type` (spec 5): the long frame's one window,
 * or the short windows cut where the 7-bit mask says. The number of groups. */
static int read_groups(mule_dec *d, int type, group *grp)
{
    int ng = 0;
    if (type == 0) {
        grp[ng++] = (group){0, 0, 1};
    } else {
        uint32_t mask = raw(d, 7);              /* bit k-1: a group starts at window k */
        int k0 = 0;
        for (int k = 1; k < MULE_N_SUB; k++)
            if (mask >> (k - 1) & 1) {
                grp[ng++] = (group){1, k0, k};
                k0 = k;
            }
        grp[ng++] = (group){1, k0, MULE_N_SUB};
    }
    return ng;
}

/* The energies q of channel c, group g (spec 5.1): predicted from the previous frame and the
 * band below (weight alpha), plus the coded residuals. -1 if out of bounds (not a valid
 * stream). */
static int read_energies(mule_dec *d, int c, int alpha, int *q)
{
    int left = d->qprev[c][0], rprev = 0;
    for (int b = 0; b < MULE_NB; b++) {
        int s = sym(d, MULE_S_ENERGY, band_class(b) * 3 + (iabs(rprev) < 2 ? iabs(rprev) : 2));
        int r = signed_val(d, s);
        int pred = floor_div(alpha * d->qprev[c][b] + (32 - alpha) * left, 32);
        q[b] = pred + r;
        if (q[b] < MULE_QMIN || q[b] > MULE_QMAX)
            return -1;
        left = q[b];
        rprev = r;
    }
    memcpy(d->qprev[c], q, sizeof(int) * MULE_NB);
    return 0;
}

/* The allocations a of channel c (spec 5.2): from the band below or from the previous frame
 * (mode), plus the coded differences. -1 if out of bounds (not a valid stream). */
static int read_allocations(mule_dec *d, int c, int *a)
{
    int mode = sym(d, MULE_S_AMODE, 0);
    for (int b = 0; b < MULE_NB; b++) {
        int s = sym(d, MULE_S_ALLOC, band_class(b) + 3 * mode);
        int dv = signed_val(d, s);
        int ref = mode ? d->aprev[c][b] : (b ? a[b - 1] : d->aprev[c][0]);
        a[b] = ref + dv;
        if (a[b] < 0 || a[b] > MULE_AMAX)
            return -1;
    }
    memcpy(d->aprev[c], a, sizeof(int) * MULE_NB);
    return 0;
}

/* The coefficients of one coded band b (a > 0) of channel c in group g (spec 5.3), into X; a
 * long frame's indices into ycur. inter: the inter-frame prediction applies (e its exponent);
 * tail1, tail2: the two previous indices; tst: the trellis state at the band's start. The
 * trellis state at its end. */
static int read_band(mule_dec *d, coef_t *X, uint16_t *ycur, const group *gr, int c, int b, int q,
                     int a, int inter, int e, int64_t *tail1, int64_t *tail2, int tst, int nf)
{
    int n = band_count(gr, b), type = gr->type;
    int ac = a / 3 < 15 ? a / 3 : 15;
    int64_t ipw = POW4[e & 3];                  /* inter-frame rescaling, per band */
    int ish = floor_div(e, 4);
    band_scale bs = scale_of(q, a);
    int w = EDGES[b + 1] - EDGES[b], col = 0;   /* short groups: window by window */
    int idx = coef_index(gr, b, 0);
    int64_t t1 = *tail1, t2 = *tail2;
    for (int i = 0; i < n; i++) {
        int64_t mctx = 2 * t1 + t2;
        if (inter) {                            /* the same coefficient, last frame */
            int64_t v = (int64_t)d->ylong[c][idx] * ipw;
            int64_t pm = ish >= 0 ? (v << (ish < 8 ? ish : 8)) >> 8 : v >> (8 - ish);
            if (pm > 31)
                pm = 31;
            mctx = (mctx + 3 * pm + 1) >> 1;
        }
        int ctx = ac * 6 + nc_map(mctx);
        int s = sym(d, MULE_S_COEF, ctx);
        int64_t mag = s;
        if (s == COEF_ESC(d)) {                 /* escape: Exp-Golomb */
            int k = sym(d, MULE_S_CESC, ac);
            mag = COEF_ESC(d) + (int64_t)(1u << k) - 1 + (k ? raw(d, k) : 0);
        }
        /* TCQ: the state gives the level's parity (odd states have no zero) */
        int even = !(tst & 1);
        int64_t k = even ? 2 * mag : 2 * mag + 1;
        if ((!even || mag) && raw(d, 1))
            k = -k;
        tst = d->tcq_next[tst][k & 3];
        X[idx] = k == 0 && nf ? nf_value(d, nf, &bs) : coef_value(k, &bs);
        if (type == 0)
            ycur[idx] = (uint16_t)(mag < 65535 ? mag : 65535);
        t2 = t1;
        t1 = mag;
        idx++;
        if (type && ++col == w) {               /* next short window */
            col = 0;
            idx += 128 - w;
        }
    }
    *tail1 = t1;
    *tail2 = t2;
    return tst;
}

/* One frame (spec 5): block type and groups, energy prediction weight, stereo flags; for each
 * coded channel and group the energies (5.1), allocations (5.2) and coefficients (5.3: noise or
 * TCQ levels with their contexts); inverse M/S; synthesis; 1024 samples per channel to out.
 * Returns early with err set on a damaged stream (energies or allocations out of range). */
static void decode_frame(mule_dec *d, int16_t *out)
{
    PROF(0);
    int type = sym(d, MULE_S_BTYPE, 0);
    group grp[MULE_N_SUB];
    int ng = read_groups(d, type, grp);
    int ai = sym(d, MULE_S_ALPHA, 0);
    int ms[MULE_NB];
    for (int b = 0; b < MULE_NB; b++)
        ms[b] = sym(d, MULE_S_STEREO, band_class(b));

    memset(d->X, 0, sizeof d->X);
    for (int c = 0; c < 2; c++) {
        coef_t *X = d->X[c];
        int64_t tail1 = 0, tail2 = 0;           /* index u of the two previous coefficients */
        int inter_ok = type == 0 && d->lvalid[c];
        uint16_t *ycur = d->sc.ycur;
        memset(ycur, 0, sizeof d->sc.ycur);
        int q[MULE_NB] = {0}, a[MULE_NB] = {0};
        int nf = IS_V5(d) ? sym(d, MULE_S_NFLEV, 0) /* the level of the zero coefficients' noise: */
               : IS_V4(d) ? (int)raw(d, 3) : 0; /* modelled (v5), 3 raw bits (v4) */
        for (int g = 0; g < ng; g++) {
            if (read_energies(d, c, g == 0 ? ALPHAS[ai] : 26, q) || read_allocations(d, c, a)) {
                d->err = 1;                     /* not a valid stream (5.1, 5.2) */
                return;
            }
            int tst_run = 0;                    /* v3 chain: the state across the group's bands */
            for (int b = 0; b < MULE_NB; b++) {
                if (q[b] <= MULE_QMIN)          /* silent band */
                    continue;
                if (a[b] == 0) {                /* noise at the band's energy */
                    PROF(6);
                    int n = band_count(&grp[g], b), idx[MULE_BAND_MAX];
                    for (int i = 0; i < n; i++)
                        idx[i] = coef_index(&grp[g], b, i);
                    if (IS_V5(d) && type && b >= MULE_NF_START)   /* v5: folded */
                        fold_band(d, X, idx, n, q[b], EDGES[b + 1] - EDGES[b]);
                    else if (IS_V4(d) && type == 0 && b >= MULE_NF_START)   /* v4: sloped */
                        noise_band_sloped(d, X, idx, n, q, b);
                    else
                        noise_band(d, X, idx, n, q[b]);
                    PROF(0);
                    continue;
                }
                int inter = inter_ok && d->along[c][b] > 0;
                int e = inter ? d->qlong[c][b] - q[b] + a[b] - d->along[c][b] : 0;
                tst_run = read_band(d, X, ycur, &grp[g], c, b, q[b], a[b], inter, e, &tail1, &tail2,
                                    d->tcq_chain ? tst_run : 0,    /* v2: state 0 at each band */
                                    b >= MULE_NF_START ? nf : 0);
            }
        }
        if (type == 0) {                        /* the inter-frame context of the next frame */
            memcpy(d->ylong[c], ycur, sizeof d->sc.ycur);
            memcpy(d->qlong[c], q, sizeof q);
            memcpy(d->along[c], a, sizeof a);
            d->lvalid[c] = 1;
        } else
            d->lvalid[c] = 0;
    }
    PROF(7);
    for (int g = 0; g < ng; g++)                /* inverse M/S, per band */
        for (int b = 0; b < MULE_NB; b++) {
            if (!ms[b])
                continue;
            int n = band_count(&grp[g], b);
            for (int i = 0; i < n; i++) {
                int idx = coef_index(&grp[g], b, i);
                inverse_ms(&d->X[0][idx], &d->X[1][idx]);
            }
        }
#ifndef MULE_BENCH_NOSYNTH                      /* (bench/qemu: the stream reading alone) */
    PROF(4);
    synth(d, type);
#endif
    PROF(5);
    d->pend_valid = type == 0;
    d->prev_type = type;
    for (int i = 0; i < MULE_F; i++)
        for (int c = 0; c < d->channels; c++)
            out[i * d->channels + c] = to_sample(d->acc[c][i]);
    for (int c = 0; c < 2; c++) {               /* the accumulator moves on by a frame */
        memmove(d->acc[c], d->acc[c] + MULE_F, sizeof(int32_t) * (ACC_LEN - MULE_F));
        memset(d->acc[c] + (ACC_LEN - MULE_F), 0, sizeof(int32_t) * MULE_F);
    }
}

/* ---------------- API (mule.h) ---------------- */

/* A decoder in caller-provided memory of at least mule_dec_size() bytes, from the MULEHead
 * packet h; NULL if the header is not one this decoder reads (version, channels, bands, initial
 * CDF table). */
mule_dec *mule_dec_init(void *mem, size_t size, const uint8_t *h, int len)
{
    if (size < sizeof(mule_dec) || len < MULE_HEAD_LEN_V2 || memcmp(h, "MULEHead", 8))
        return NULL;
#ifdef MULE_FFT_MEM_EXTERNAL
    if (!fft_re || !fft_im)                     /* the FFT memory must be given first */
        return NULL;
#endif
    int n = 8, flags = 0;               /* v2: 8 states, restarted in each band, 16 symbols */
#ifdef MULE_DEC_V5_ONLY
    if (h[8] != 5 || len < MULE_HEAD_LEN || !(h[21] & MULE_COEF_A8))   /* v5, 8-symbol coefficients */
        return NULL;
#endif
    if (h[8] >= 3 && h[8] <= MULE_VERSION) {    /* v3 to v5: the trellis's size, chaining, alphabet */
        if (len < MULE_HEAD_LEN || h[20] < 3 || h[20] > 6 || (h[21] & ~(MULE_TCQ_CHAIN | MULE_COEF_A8)))
            return NULL;
        n = 1 << h[20];
        flags = h[21];
    } else if (h[8] != 2 || len < MULE_HEAD_LEN_V2)
        return NULL;
    if (h[9] != 2 || h[16] != MULE_NB || h[19] != mule_init_cdf_id)
        return NULL;
    mule_dec *d = mem;
    memset(d, 0, sizeof *d);
    d->channels = h[9];
    d->pre_skip = h[10] | h[11] << 8;
    d->rate = (uint32_t)h[12] | (uint32_t)h[13] << 8 | (uint32_t)h[14] << 16 | (uint32_t)h[15] << 24;
    for (int st = 0; st < n; st++)
        for (int j = 0; j < 4; j++)
            d->tcq_next[st][j] = (uint8_t)mule_tcq_step_n(st, j, n, mule_tcq_mask(n));
    d->tcq_chain = flags & MULE_TCQ_CHAIN;
    d->coef_t = flags & MULE_COEF_A8 ? 7 : 15;
    d->v4 = h[8] >= 4;
    d->v5 = h[8] >= 5;
    if (!models_layout(d))
        return NULL;
    reset_key(d);
    return d;
}

/* The memory a decoder needs (its whole state). */
size_t mule_dec_size(void)
{
    return sizeof(mule_dec);
}

#ifndef MULE_NO_MALLOC
/* A decoder on the heap (mule_dec_init on malloc'd memory); free with mule_dec_free. */
mule_dec *mule_dec_new(const uint8_t *h, int len)
{
    void *mem = malloc(sizeof(mule_dec));
    mule_dec *d = mem ? mule_dec_init(mem, sizeof(mule_dec), h, len) : NULL;
    if (!d)
        free(mem);
    return d;
}

/* Frees a decoder made by mule_dec_new. */
void mule_dec_free(mule_dec *d)
{
    free(d);
}
#endif

/* Channels of the stream (2). */
int mule_dec_channels(const mule_dec *d)
{
    return d->channels;
}

/* Samples per channel to drop at the start of the stream (MULEHead). */
int mule_dec_pre_skip(const mule_dec *d)
{
    return d->pre_skip;
}

/* After a jump in the stream: packets are dropped until a key packet, then its first frame
 * (its overlap with the frame before is missing). */
void mule_dec_seek(mule_dec *d)
{
    d->need_key = 1;
    d->pend_valid = 0;
    d->prev_type = 0;
    memset(d->acc, 0, sizeof d->acc);
}

/* One audio packet (spec 2): its header (key flag, frame count, a key packet's frame index), the
 * rANS initial state, then its frames decoded straight into pcm (interleaved, max_samples per
 * channel of room). Returns the samples per channel written, 0 for a packet dropped while
 * waiting for a key packet, -1 for a damaged packet, -2 if the rANS stream does not end where
 * the encoder's did (all words read, the initial state back). */
int mule_dec_packet(mule_dec *d, const uint8_t *p, int len, int16_t *pcm, int max_samples)
{
    if (len < 5)
        return -1;
    int key = p[0] & 1, nframes = (p[0] >> 1 & 7) + 1;
    const uint8_t *q = p + 1;
    if (key) {
        if (len < 9)
            return -1;
        q += 4;                                 /* frame index: for players, not needed here */
    }
    if (d->need_key) {
        if (!key)
            return 0;
        d->need_key = 0;
        d->drop_frames = 1;
    }
    if (key)
        reset_key(d);
    if (q + 4 > p + len)
        return -1;
    d->x = (uint32_t)q[0] | (uint32_t)q[1] << 8 | (uint32_t)q[2] << 16 | (uint32_t)q[3] << 24;
    d->p = q + 4;
    d->end = p + len;
    d->err = 0;
    int written = 0;
    for (int f = 0; f < nframes; f++) {
        if (written + MULE_F > max_samples)
            return -1;
        decode_frame(d, pcm + (size_t)written * d->channels);
        if (d->err)
            return -1;
        if (d->drop_frames) {
            d->drop_frames--;
            continue;                           /* overwritten by the next frame */
        }
        written += MULE_F;
    }
    if (d->x != (1u << 16) || d->p != d->end)
        return -2;
    return written;
}
