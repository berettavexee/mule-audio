/* MULE encoder, the reference encoder: audio (44.1 kHz stereo, double) to a complete Ogg MULE
 * file in memory. Floating point is fine here: only the decoder must be exact (core/dec.c).
 *
 * Per frame of 1024 samples: block type (transient detector), forward MDCT, psychoacoustic masks
 * per band, stereo choice per band, energies, allocations (from the masks, then a
 * rate-distortion choice with exact model costs), TCQ levels (Viterbi), all as "coding
 * operations"; then packets of up to 4 frames are rANS-coded (core/rans.c) and put in Ogg pages.
 *
 * This file: the settings, the coding operations, the measurement trace, the coding of one frame
 * and the API (core/mule_enc.h). The other modules are listed in core/enc_int.h. */
#include "enc_int.h"

static const int ALPHAS[4] = {0, 16, 26, 31};          /* energy prediction weights (spec 5.1) */

/* The production settings (core/mule_enc.h documents each). */
void mule_enc_defaults(mule_enc_params *p)
{
    memset(p, 0, sizeof *p);
    p->q_db = -7.0;             /* about 128 kb/s on a music library (tools/mule_enc.py) */
    p->keyframe = 40;
    p->groups = 0;              /* adaptive */
    p->group_db = 12.0;         /* with group_mode 1 (eval/results/N-LOG.md, 20/11/2026) */
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
    p->tcq_states = 64;         /* format v3 (eval/results/B-LOG.md, C-LOG.md) */
    p->tcq_chain = 1;
    p->coef_a8 = 1;
    p->tcq_rd_states = 8;       /* encoder speed x2, same quality (eval/results/B-LOG.md) */
    p->tg = 0;                  /* zero-bit tonal bands: under study (eval/results/N-LOG.md) */
    p->tg_db = 6.0;
    p->tg_a = 1;
    p->tg_ton = 5.0;
    p->tr_db = 10.0;
    p->group_mode = 1;          /* adaptive grouping per frequency region (N-LOG.md) */
    p->short_db = 0.0;
}

/* ---------------------------------------------------------------- measurement trace */

trace_t *mule_enc_trace;

/* See enc_int.h. */
void trace_add(const int32_t *rec)
{
    trace_t *t = mule_enc_trace;
    if (t->err)
        return;
    if (t->n == t->cap) {
        int64_t cap = t->cap ? 2 * t->cap : 1 << 16;
        int32_t *r = realloc(t->r, sizeof(int32_t) * MULE_TRACE_W * (size_t)cap);
        if (!r) {
            t->err = 1;
            return;
        }
        t->r = r;
        t->cap = cap;
    }
    memcpy(t->r + MULE_TRACE_W * t->n++, rec, sizeof(int32_t) * MULE_TRACE_W);
}

/* ---------------------------------------------------------------- coding operations */

/* See enc_int.h. */
int ops_add(ops_t *o, int32_t m, uint32_t v)
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

/* ---------------------------------------------------------------- frame coding */

/* The encoder's copy of the decoder's state, plus the pre-echo control's last masks. */
typedef struct {
    int qprev[2][NB], aprev[2][NB];
    int ylong[2][F], qlong[2][NB], along[2][NB], lvalid[2];
    double premask[2][NB];      /* encoder-only: last long frame's mask (pre-echo control) */
    int have_pre;
} state_t;

/* One frame's analysis, shared by the steps of encode_frame. */
typedef struct {
    int type, key;              /* block type (0 long, 1 short), first frame of a key packet */
    int ng;                     /* groups of windows (1 in a long frame) */
    group grp[MULE_N_SUB];
    double P[2][MULE_N_SUB][NB];        /* power per coefficient, per channel, group, band */
    double FL[2][MULE_N_SUB][NB];       /* flatness (dB) */
    double MK[2][MULE_N_SUB][NB];       /* masking threshold per coefficient */
    double PM[MULE_N_SUB][NB][2];       /* the same powers in M/S */
    int ms[NB];                         /* stereo per band: 1 M/S, 0 L/R */
    double Y[2][F];                     /* the coded vectors (M/S or L/R) */
    int Q[2][MULE_N_SUB][NB];           /* energies (spec 5.1: 1.5 dB steps) */
    int ai;                             /* energy prediction weight, index in ALPHAS */
    double tq;                          /* the noise target relative to the mask, 10^(q_db/10) */
} frame_t;

/* The mask that band b's noise must stay under in channel c, group g (in M/S, the lower of the
 * two channels'). */
static double band_mask(const frame_t *f, int c, int g, int b)
{
    return f->ms[b] ? (f->MK[0][g][b] < f->MK[1][g][b] ? f->MK[0][g][b] : f->MK[1][g][b])
                    : f->MK[c][g][b];
}

/* The block type, and in a short frame the groups of windows: a new group where the windows'
 * level changes by more than group_db (or always, or never: groups = 8, 1), sent as a 7-bit
 * mask. */
static void frame_groups(const mule_enc_params *pr, double X[2][F], frame_t *f, ops_t *o)
{
    f->ng = 0;
    put(o, MULE_S_BTYPE, 0, f->type);
    if (!f->type) {
        f->grp[f->ng++] = (group){0, 0, 1};
        return;
    }
    /* group_mode 1 (N-LOG.md): also per region of the window's 128 lines (0-1.4, 1.4-4.1,
     * 4.1-8.3 kHz, above), a region within 40 dB of the window's strongest: an attack in the
     * highs under a loud bass hardly moves the whole window's energy */
    static const int RG[5] = {0, 8, 24, 48, 128};
    double db[MULE_N_SUB], rdb[MULE_N_SUB][4];
    for (int k = 0; k < MULE_N_SUB; k++) {
        double e = 0, er[4] = {0, 0, 0, 0};
        for (int c = 0; c < 2; c++)
            for (int r = 0; r < 4; r++)
                for (int i = RG[r]; i < RG[r + 1]; i++) {
                    double v = X[c][k * 128 + i];
                    e += v * v;
                    er[r] += v * v;
                }
        db[k] = 10 * log10(e + 1e-20);
        for (int r = 0; r < 4; r++)
            rdb[k][r] = 10 * log10(er[r] + 1e-20);
    }
    uint32_t mask = 0;
    int k0 = 0;
    for (int k = 1; k < MULE_N_SUB; k++) {
        int split = pr->groups == 8 ? 1 : (pr->groups == 1 ? 0 : fabs(db[k] - db[k - 1]) > pr->group_db);
        if (!split && pr->groups == 0 && pr->group_mode == 1)
            for (int r = 0; r < 4; r++) {
                double hi = rdb[k][r] > rdb[k - 1][r] ? rdb[k][r] : rdb[k - 1][r];
                double top = db[k] > db[k - 1] ? db[k] : db[k - 1];
                if (hi > top - 40 && fabs(rdb[k][r] - rdb[k - 1][r]) > pr->group_db)
                    split = 1;
            }
        if (split) {
            f->grp[f->ng++] = (group){1, k0, k};
            k0 = k;
            mask |= 1u << (k - 1);
        }
    }
    f->grp[f->ng++] = (group){1, k0, MULE_N_SUB};
    raw(o, 7, mask);
}

/* Per (channel, group, band): power, flatness (from the FFT powers PW with fft_tonal), M/S
 * powers, then the masks (fine masks in long frames) and the pre-echo control (a long frame's
 * mask may rise by at most pre_db over the previous long frame's). */
static void frame_analysis(const mule_enc_params *pr, const psy_t *py, double X[2][F],
                           double PW[2][F], frame_t *f, state_t *s)
{
    for (int g = 0; g < f->ng; g++)
        for (int b = 0; b < NB; b++) {
            const group *gr = &f->grp[g];
            int n = band_n(gr, b), nw = f->type ? gr->k1 - gr->k0 : 1, w = n / nw;
            double pm0 = 0, pm1 = 0;
            for (int c = 0; c < 2; c++) {
                double sum = 0;
                double col[176];
                for (int i = 0; i < w; i++)
                    col[i] = 0;
                for (int i = 0; i < n; i++) {
                    int idx = coef_index(gr, b, i);
                    double v = X[c][idx];
                    sum += v * v;
                    col[i % w] += pr->fft_tonal ? PW[c][idx] : v * v;
                }
                f->P[c][g][b] = sum / n;
                double ar = 0, lg = 0;
                for (int i = 0; i < w; i++) {
                    double v = col[i] / nw;
                    ar += v;
                    lg += log(v + 1e-30);
                }
                ar /= w;
                double geo = exp(lg / w);
                f->FL[c][g][b] = 10 * log10((geo + 1e-30) / (ar + 1e-30));
            }
            for (int i = 0; i < n; i++) {
                int idx = coef_index(gr, b, i);
                double l = X[0][idx], r = X[1][idx];
                double mm = (l + r) / sqrt(2.0), ss = (l - r) / sqrt(2.0);
                pm0 += mm * mm;
                pm1 += ss * ss;
            }
            f->PM[g][b][0] = pm0 / n;
            f->PM[g][b][1] = pm1 / n;
        }
    for (int c = 0; c < 2; c++)
        for (int g = 0; g < f->ng; g++) {
            psy_masks(py, pr, f->P[c][g], f->FL[c][g], f->MK[c][g], pr->fft_tonal ? pr->fft_noise_db : 5.5);
            if (pr->fine_p > 0 && f->type == 0)
                psy_fine(py, pr, X[c], f->FL[c][g], f->MK[c][g]);
        }
    if (pr->pre_db > 0) {
        if (f->type == 0) {
            double up = pow(10, pr->pre_db / 10);
            for (int c = 0; c < 2; c++)
                for (int b = 0; b < NB; b++) {
                    if (s->have_pre && f->MK[c][0][b] > s->premask[c][b] * up)
                        f->MK[c][0][b] = s->premask[c][b] * up;
                    s->premask[c][b] = f->MK[c][0][b];
                }
            s->have_pre = 1;
        } else
            s->have_pre = 0;
    }
}

/* Stereo per band (stereo = 0): M/S when its perceptual entropy is lower than L/R's; or always
 * L/R (1), always M/S (2). */
static void stereo_choice(const mule_enc_params *pr, frame_t *f)
{
    for (int b = 0; b < NB; b++) {
        if (pr->stereo == 1) {
            f->ms[b] = 0;
            continue;
        }
        if (pr->stereo == 2) {
            f->ms[b] = 1;
            continue;
        }
        double w = band_n(&f->grp[0], b), lr = 0, mse = 0;
        for (int g = 0; g < f->ng; g++) {
            double mmin = f->MK[0][g][b] < f->MK[1][g][b] ? f->MK[0][g][b] : f->MK[1][g][b];
            lr += 0.5 * log2(1 + f->P[0][g][b] / f->MK[0][g][b]) * w +
                  0.5 * log2(1 + f->P[1][g][b] / f->MK[1][g][b]) * w;
            mse += 0.5 * log2(1 + f->PM[g][b][0] / mmin) * w + 0.5 * log2(1 + f->PM[g][b][1] / mmin) * w;
        }
        f->ms[b] = mse < lr - TIE_EPS;
    }
}

/* The coded vectors Y (M/S or L/R per band) and their energies Q (spec 5.1). */
static void coded_vectors(double X[2][F], frame_t *f)
{
    for (int g = 0; g < f->ng; g++)
        for (int b = 0; b < NB; b++) {
            int n = band_n(&f->grp[g], b);
            for (int i = 0; i < n; i++) {
                int idx = coef_index(&f->grp[g], b, i);
                double l = X[0][idx], r = X[1][idx];
                f->Y[0][idx] = f->ms[b] ? (l + r) / sqrt(2.0) : l;
                f->Y[1][idx] = f->ms[b] ? (l - r) / sqrt(2.0) : r;
            }
        }
    for (int c = 0; c < 2; c++)
        for (int g = 0; g < f->ng; g++)
            for (int b = 0; b < NB; b++) {
                int n = band_n(&f->grp[g], b);
                double e = 0;
                for (int i = 0; i < n; i++) {
                    double v = f->Y[c][coef_index(&f->grp[g], b, i)];
                    e += v * v;
                }
                double q = nearbyint(4 * log2(sqrt(e / n) + 1e-30));
                if (!(q >= MULE_QMIN)) q = MULE_QMIN;           /* NaN included */
                if (q > MULE_QMAX) q = MULE_QMAX;
                f->Q[c][g][b] = (int)q;
            }
}

/* The energy prediction weight of the first group (spec 5.1): the one whose residuals have the
 * smallest sum of log2(1 + |r|); 0 in a key frame. */
static void choose_alpha(const state_t *s, frame_t *f)
{
    f->ai = 0;
    if (f->key)
        return;
    double best = 1e300;
    for (int k = 0; k < 4; k++) {
        double cost = 0;
        for (int c = 0; c < 2; c++) {
            int left = s->qprev[c][0];
            for (int b = 0; b < NB; b++) {
                int pred = floor_div(ALPHAS[k] * s->qprev[c][b] + (32 - ALPHAS[k]) * left, 32);
                cost += log2(1 + abs(f->Q[c][0][b] - pred));
                left = f->Q[c][0][b];
            }
        }
        if (cost < best - TIE_EPS) {
            best = cost;
            f->ai = k;
        }
    }
}

/* The allocations of channel c, group g, from the masks: the step that puts the band's noise at
 * the mask times tq; 0 (noise filling) where the mask is above the band's energy; then the
 * hysteresis (a change of at most alloc_hyst from the previous frame is not made). */
static void alloc_from_masks(const mule_enc_params *pr, const frame_t *f, const state_t *s, int c,
                             int g, const int *q, int *a)
{
    for (int b = 0; b < NB; b++) {
        a[b] = 0;
        double rms = pow(2.0, q[b] / 4.0);
        double target = band_mask(f, c, g, b) * f->tq;
        if (q[b] <= MULE_QMIN || target >= rms * rms)
            continue;                           /* noise-filled (a = 0) */
        double D = sqrt(12 * target) / rms;
        double av = nearbyint(MULE_A0 - 4 * log2(D));
        if (av < 0) av = 0;
        if (av > MULE_AMAX) av = MULE_AMAX;
        a[b] = (int)av;
    }
    const int *ap = s->aprev[c];
    if (pr->alloc_hyst && !f->key)
        for (int b = 0; b < NB; b++)
            if (a[b] > 0 && ap[b] > 0 && abs(a[b] - ap[b]) <= pr->alloc_hyst)
                a[b] = ap[b];
}

/* Zero-bit tonal bands (tg, N-LOG.md): a band the masks leave at allocation 0 (noise filling)
 * that holds a lone line: its strongest coefficient at least tg_ton dB above the strongest a
 * noise of the same n lines would reach (about 2 ln n times the mean power). tg 1: the band gets
 * allocation tg_a if that line reaches the mask target minus tg_db (the line coded instead of spread
 * as flat noise over the band); tg 2: the band is sent silent. (The FFT flatness of the masks
 * misses a line that comes and goes: the crest is taken on the coded coefficients.) */
static void tonal_guard(const mule_enc_params *pr, const frame_t *f, int c, int g, int *q, int *a)
{
    const group *gr = &f->grp[g];
    for (int b = 0; b < NB; b++) {
        if (a[b] != 0 || q[b] <= MULE_QMIN)
            continue;
        int n = band_n(gr, b);
        if (n < 16)
            continue;
        double peak = 0, sum = 0;
        for (int i = 0; i < n; i++) {
            double v = f->Y[c][coef_index(gr, b, i)];
            sum += v * v;
            if (v * v > peak)
                peak = v * v;
        }
        if (peak < (sum / n) * 2 * log(n) * pow(10, pr->tg_ton / 10))
            continue;
        if (pr->tg == 2)
            q[b] = MULE_QMIN;
        else if (peak >= band_mask(f, c, g, b) * f->tq * pow(10, -pr->tg_db / 10))
            a[b] = pr->tg_a < 1 ? 1 : (pr->tg_a > MULE_AMAX ? MULE_AMAX : pr->tg_a);
    }
}

/* The rate-distortion choice of each coded band's allocation among a-1, a, a+1, band after band:
 * noise / (mask tq) + rd_lambda bits, per coefficient, the bits costed with the tracked models
 * (coefficients and the allocation's own symbol). tail1, tail2: the coefficient tails before the
 * group. */
static void alloc_rd(const mule_enc_params *pr, const frame_t *f, const state_t *s, ops_t *o,
                     int c, int g, const int *q, int *a, int inter_ok, int64_t tail1, int64_t tail2)
{
    const int *ap = s->aprev[c];
    int64_t t1 = tail1, t2 = tail2;
    for (int b = 0; b < NB; b++) {
        if (q[b] <= MULE_QMIN || a[b] == 0)
            continue;
        double rms = pow(2.0, q[b] / 4.0);
        double mk = band_mask(f, c, g, b);
        int n = band_n(&f->grp[g], b);
        band_in in = {f->Y[c], &f->grp[g], b, f->type, inter_ok && s->along[c][b] > 0, 0, s->ylong[c],
                      rms, 0.0, pr->tcq_lam, mk * f->tq, pr};
        double best = 1e300;
        int besta = a[b];
        int64_t bt1 = t1, bt2 = t2;
        for (int cand = a[b] - 1; cand <= a[b] + 1; cand++) {
            if (cand < 1 || cand > MULE_AMAX)
                continue;
            in.e = in.inter ? s->qlong[c][b] - q[b] + cand - s->along[c][b] : 0;
            int64_t c1 = t1, c2 = t2;
            double bits, noise;
            band_code(&in, cand, &c1, &c2, o, 0, NULL, &bits, &noise, NULL, NULL);
            int d = cand - ap[b];
            bits += sym_bits(o, MULE_S_ALLOC, band_class(b) + 3, d >= -7 && d <= 7 ? d + 7 : 15);
            double j = noise / (mk * f->tq * n) + pr->rd_lambda * bits / n;
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

/* The energies of channel c, group g (spec 5.1): residuals from the prediction (weight alpha
 * between the previous frame and the band below). */
static void code_energies(const frame_t *f, state_t *s, ops_t *o, int c, int g, const int *q)
{
    int alpha = g == 0 ? ALPHAS[f->ai] : 26;
    int left = s->qprev[c][0], rprev = 0;
    for (int b = 0; b < NB; b++) {
        int pred = floor_div(alpha * s->qprev[c][b] + (32 - alpha) * left, 32);
        int r = q[b] - pred;
        int ctx = band_class(b) * 3 + (abs(rprev) < 2 ? abs(rprev) : 2);
        if (mule_enc_trace) {
            int32_t rec[MULE_TRACE_W] = {1, clip32(o->n), mule_enc_trace->frame, c, f->type, b, q[b], pred, r,
                                         ctx, alpha, g, f->key, s->qprev[c][b], f->ms[b], 0, 0, 0, 0, 0};
            trace_add(rec);
        }
        signed_ops(o, MULE_S_ENERGY, ctx, r);
        left = q[b];
        rprev = r;
    }
    memcpy(s->qprev[c], q, sizeof(int) * NB);
}

/* The allocations of channel c (spec 5.2): the mode (from the band below, or from the previous
 * frame: the cheaper by a log2(1 + |d|) estimate, with alloc_auto), then the differences. */
static void code_allocations(const mule_enc_params *pr, state_t *s, ops_t *o, int c, const int *a)
{
    const int *ap = s->aprev[c];
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
    memcpy(s->aprev[c], a, sizeof(int) * NB);
}

/* The coefficients of channel c, group g (spec 5.3): with tcq_chain, one Viterbi over the
 * group's coded bands, the trellis state running on (point 16), then each band's symbols;
 * else each band's own Viterbi. ycur gets a long frame's indices. */
static void code_coefficients(const mule_enc_params *pr, const frame_t *f, const state_t *s,
                              ops_t *o, int c, int g, const int *q, const int *a, int inter_ok,
                              int64_t *tail1, int64_t *tail2, int *ycur)
{
    band_in bins[NB];
    for (int b = 0; b < NB; b++) {
        if (q[b] <= MULE_QMIN || a[b] == 0)
            continue;
        double rms = pow(2.0, q[b] / 4.0);
        int inter = inter_ok && s->along[c][b] > 0;
        bins[b] = (band_in){f->Y[c], &f->grp[g], b, f->type, inter,
                            inter ? s->qlong[c][b] - q[b] + a[b] - s->along[c][b] : 0, s->ylong[c],
                            rms, 0.0, pr->tcq_lam, band_mask(f, c, g, b) * f->tq, pr};
    }
    int chain = pr->tcq_chain && pr->tcq_rd && o->mr;
    static int64_t ck[MULE_F];
    int cstart[NB];
    if (chain) {
        static double cx[MULE_F], cw[MULE_F];
        static int cac[MULE_F];
        static int64_t cpm[MULE_F];
        int m = 0;
        for (int b = 0; b < NB; b++) {
            cstart[b] = m;
            if (q[b] <= MULE_QMIN || a[b] == 0)
                continue;
            int ac, n = band_n(&f->grp[g], b);
            double u, lam;
            band_prep(&bins[b], a[b], cx + m, cpm + m, &ac, &u, &lam);
            for (int i = 0; i < n; i++) {
                cw[m + i] = u * u / bins[b].mtq;
                cac[m + i] = ac;
            }
            m += n;
        }
        tcq_viterbi_chain(cx, cw, cac, m, pr->tcq_rdl * pr->rd_lambda, o, cpm, *tail1, *tail2,
                          pr->tcq_states, mule_tcq_mask(pr->tcq_states), 0, ck);
    }
    int tst_run = 0;
    for (int b = 0; b < NB; b++) {
        if (q[b] <= MULE_QMIN || a[b] == 0)
            continue;
        band_code(&bins[b], a[b], tail1, tail2, o, 1, ycur, NULL, NULL, chain ? ck + cstart[b] : NULL,
                  pr->tcq_chain ? &tst_run : NULL);
    }
}

/* One frame's coding operations (spec 5) from its MDCT coefficients X (L, R) and FFT powers PW:
 * block type and groups; analysis and masks; stereo per band; energies and their prediction
 * weight; then per coded channel and group the allocations (masks, hysteresis, RD choice),
 * energies, allocations and coefficients. key: the first frame of a key packet (predictions
 * reset). */
static void encode_frame(const mule_enc_params *pr, const psy_t *psy_l, const psy_t *psy_s,
                         int type, int key, double X[2][F], double PW[2][F], state_t *s, ops_t *o)
{
    static frame_t fr;                          /* large: not on the stack */
    frame_t *f = &fr;
    f->type = type;
    f->key = key;
    frame_groups(pr, X, f, o);
    frame_analysis(pr, type ? psy_s : psy_l, X, PW, f, s);
    stereo_choice(pr, f);
    coded_vectors(X, f);
    choose_alpha(s, f);
    put(o, MULE_S_ALPHA, 0, f->ai);
    for (int b = 0; b < NB; b++)
        put(o, MULE_S_STEREO, band_class(b), f->ms[b]);

    f->tq = pow(10, (pr->q_db + (type ? pr->short_db : 0.0)) / 10);
    for (int c = 0; c < 2; c++) {
        int64_t tail1 = 0, tail2 = 0;
        int inter_ok = type == 0 && s->lvalid[c];
        if (mule_enc_trace)
            mule_enc_trace->ch = c;
        int ycur[F];
        memset(ycur, 0, sizeof ycur);
        int a[NB] = {0};
        int *q = NULL;
        for (int g = 0; g < f->ng; g++) {
            q = f->Q[c][g];
            alloc_from_masks(pr, f, s, c, g, q, a);
            if (pr->tg)
                tonal_guard(pr, f, c, g, q, a);
            if (pr->rd_lambda > 0 && o->mr)
                alloc_rd(pr, f, s, o, c, g, q, a, inter_ok, tail1, tail2);
            if (pr->nf_bias > 0)                /* noise-filled bands: energy sent lower */
                for (int b = 0; b < NB; b++)
                    if (a[b] == 0 && q[b] > MULE_QMIN) {
                        int v = q[b] - pr->nf_bias;
                        q[b] = v > MULE_QMIN + 1 ? v : MULE_QMIN + 1;
                    }
            code_energies(f, s, o, c, g, q);
            code_allocations(pr, s, o, c, a);
            if (mule_enc_trace)                 /* band records: the figures (docs/blog) */
                for (int b = 0; b < NB; b++) {
                    double pw = f->ms[b] ? f->PM[g][b][c] : f->P[c][g][b];
                    double fl = f->FL[c][g][b], pk = 0;
                    if (f->ms[b] && f->FL[1 - c][g][b] < fl)
                        fl = f->FL[1 - c][g][b];
                    for (int i = 0; i < band_n(&f->grp[g], b); i++) {
                        double v = f->Y[c][coef_index(&f->grp[g], b, i)];
                        pk = v * v > pk ? v * v : pk;
                    }
                    int32_t rec[MULE_TRACE_W] = {2, clip32(o->n), mule_enc_trace->frame, c, f->type, b, a[b],
                                                 f->ms[b], g, (int32_t)lround(1000 * log10(band_mask(f, c, g, b) + 1e-30)),
                                                 (int32_t)lround(1000 * log10(pw + 1e-30)), q[b],
                                                 f->grp[g].k0, f->grp[g].k1, (int32_t)lround(100 * fl),
                                                 (int32_t)lround(1000 * log10((pk + 1e-30) / (band_mask(f, c, g, b) * f->tq + 1e-30))),
                                                 0, 0, 0, 0};
                    trace_add(rec);
                }
            code_coefficients(pr, f, s, o, c, g, q, a, inter_ok, &tail1, &tail2, ycur);
        }
        if (type == 0) {                        /* the inter-frame context of the next frame */
            memcpy(s->ylong[c], ycur, sizeof ycur);
            memcpy(s->qlong[c], q, sizeof(int) * NB);
            memcpy(s->along[c], a, sizeof a);
            s->lvalid[c] = 1;
        } else
            s->lvalid[c] = 0;
    }
}

/* ---------------------------------------------------------------- API */

/* The settings this encoder accepts: key frames a multiple of 4, trellis sizes 8 to 64. */
static int params_ok(const mule_enc_params *pr)
{
    int ns = pr->tcq_states, nr = pr->tcq_rd_states;
    return pr->keyframe > 0 && pr->keyframe % 4 == 0 &&
           (ns == 8 || ns == 16 || ns == 32 || ns == 64) &&
           (nr == 0 || nr == 8 || nr == 16 || nr == 32 || nr == 64);
}

/* Analysis and frame coding of the whole signal: its operations (out) and each frame's first
 * operation (fstart[0..T]). The frame t covers samples [1024 (t - 1), 1024 (t + 1)). -1 if out
 * of memory (out then empty). */
static int encode_ops(const double *pcm, int64_t L, const mule_enc_params *pr, int T, ops_t *out,
                      int64_t *fstart)
{
    uint8_t *types = malloc((size_t)T);
    mdct_t ml = {0}, msh = {0};
    ops_t o = {0};
    o.esc = pr->coef_a8 ? 7 : 15;
    state_t *s = calloc(1, sizeof *s);
    double (*X)[F] = malloc(sizeof(double) * 2 * F);
    double (*PW)[F] = malloc(sizeof(double) * 2 * F);
    int rc = -1;
    if (!types || !s || !X || !PW || block_types(pcm, L, T, types, pr->tr_db) || mdct_init(&ml, MULE_N_LONG) ||
        mdct_init(&msh, MULE_N_SHORT))
        goto done;
    psy_t pl, ps;
    psy_init(&pl, 1024);
    psy_init(&ps, 128);
    double wl[4][MULE_N_LONG], wsh[MULE_N_SHORT];
    for (int v = 0; v < 4; v++) {                   /* long windows: left short?, right short? */
        int sl = v & 1 ? 128 : 1024, sr = v & 2 ? 128 : 1024;
        for (int i = 0; i < F; i++) {
            wl[v][i] = win_half(i, F, sl);
            wl[v][MULE_N_LONG - 1 - i] = win_half(i, F, sr);
        }
    }
    for (int i = 0; i < MULE_N_SHORT; i++)
        wsh[i] = i < 128 ? win_slope(i, 128) : win_slope(MULE_N_SHORT - 1 - i, 128);

    if (pr->rd_lambda > 0 && !(o.mr = mule_models_alloc()))
        goto done;
    double seg[MULE_N_LONG], tmp[MULE_N_LONG];
    for (int t = 0; t < T; t++) {
        fstart[t] = o.n;
        if (mule_enc_trace)
            mule_enc_trace->frame = t;
        int key = t % pr->keyframe == 0;
        if (key) {
            for (int c = 0; c < 2; c++)
                for (int b = 0; b < NB; b++) {
                    s->qprev[c][b] = MULE_Q_RESET;
                    s->aprev[c][b] = MULE_A_RESET;
                }
            s->lvalid[0] = s->lvalid[1] = 0;
            if (o.mr)
                mule_models_reset_a8(o.mr, o.esc == 7);
        }
        int type = types[t];
        for (int c = 0; c < 2; c++) {
            /* padded segment [F t, F t + 2F) = original [F (t-1), F (t+1)) */
            for (int i = 0; i < MULE_N_LONG; i++) {
                int64_t j = (int64_t)F * (t - 1) + i;
                seg[i] = j >= 0 && j < L ? pcm_sample(pcm[2 * j + c]) : 0.0;
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
    if (!params_ok(pr))
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

/* See mule_enc.h: mule_encode_ops plus the measurement trace. */
int mule_encode_trace(const double *pcm, int64_t L, const mule_enc_params *pr, int32_t **model,
                      uint32_t **val, int64_t *n, int64_t **frame_start, int *frames,
                      int32_t **trace, int64_t *ntrace)
{
    trace_t t = {0};
    mule_enc_trace = &t;
    int r = mule_encode_ops(pcm, L, pr, model, val, n, frame_start, frames);
    mule_enc_trace = NULL;
    if (r || t.err) {
        free(t.r);
        if (!r) {
            free(*model);
            free(*val);
            free(*frame_start);
        }
        return -1;
    }
    *trace = t.r;
    *ntrace = t.n;
    return 0;
}

/* See mule_enc.h: the whole Ogg MULE file (enc_ogg.c). 0, or -1 (out of memory, bad settings),
 * -2 (a frame alone exceeds MULE_PACKET_MAX). */
int mule_encode(const double *pcm, int64_t L, const mule_enc_params *pr,
                const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
                size_t *audio_bytes)
{
    int T = (int)((L + F - 1) / F) + 1;
    if (!params_ok(pr))
        return -1;
    ops_t o = {0};
    int64_t *fstart = malloc(sizeof(int64_t) * (size_t)(T + 1));
    if (!fstart || encode_ops(pcm, L, pr, T, &o, fstart)) {
        free(fstart);
        return -1;
    }
    o.esc = pr->coef_a8 ? 7 : 15;
    int rc = ogg_write(pr, &o, fstart, T, L, tags, ntags, out, out_len, audio_bytes);
    free(o.m);
    free(o.v);
    free(fstart);
    return rc;
}

/* Frees what mule_encode / mule_encode_ops returned. */
void mule_free(void *p)
{
    free(p);
}
