/* MULE encoder: the transient detector (each frame's block type) and the psychoacoustic model
 * (masking threshold per band, core/enc_int.h). */
#include "enc_int.h"

/* ---------------------------------------------------------------- transient detector */

/* The block type of each of the T frames (0 long, 1 short): energies of 128-sample blocks of the
 * signal high-passed at fc; an attack is a block ratio_db above a memory decaying by decay_db per
 * block, or 20 dB above the blocks 7 to 10 earlier, above a -70 dB floor; the frames whose short
 * windows hold it become short. add: the frames already short stay short (a second pass). The
 * production's passes and values: mule_enc.h (tr_db, tr_hf_*, tr_decay_db). -1 if out of memory. */
int block_types(const double *x, int64_t L, int T, uint8_t *types, double ratio_db, double fc, int add,
                double decay_db)
{
    const double fs = 44100.0, floor_db = -70.0, slow_db = 20.0;
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
            double in = i < L ? pcm_sample(x[2 * i + c]) : 0.0, out = 0.0;
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
    for (int t = 0; t < T && !add; t++)
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

/* The tonal veto of the highs pass (tr_hf_ton): a frame it made short (short in types, long in
 * first, the 3 kHz pass's decisions) goes back to long if the bands 12-21 (2.8-17 kHz) of its mid
 * channel's long window are flatter than -ton_db dB on average (FFT powers): a short frame on a
 * drone blurs its harmonics (N-LOG.md, Belenos). */
void hf_tonal_veto(const double *pcm, int64_t L, int T, uint8_t *types, const uint8_t *first,
                   double ton_db, const mdct_t *ml)
{
    const int b0 = MULE_NF_START, b1 = 21;
    double seg[MULE_N_LONG], pw[F];
    for (int t = 0; t < T; t++) {
        if (!types[t] || first[t])
            continue;
        for (int i = 0; i < MULE_N_LONG; i++) {         /* the mid of [F (t-1), F (t+1)) */
            int64_t j = (int64_t)F * (t - 1) + i;
            seg[i] = j >= 0 && j < L ? 0.5 * (pcm_sample(pcm[2 * j]) + pcm_sample(pcm[2 * j + 1])) : 0.0;
        }
        fft_power(ml, seg, pw);
        double fl = 0;
        for (int b = b0; b <= b1; b++)
            fl += flatness_db(pw + EDGES[b] * 8, (EDGES[b + 1] - EDGES[b]) * 8) / (b1 + 1 - b0);
        if (fl < -ton_db)
            types[t] = 0;
    }
}

/* ---------------------------------------------------------------- psychoacoustics */

/* Frequency (Hz) to Bark (Zwicker). */
static double bark(double f)
{
    return 13 * atan(0.00076 * f) + 3.5 * atan((f / 7500.0) * (f / 7500.0));
}

/* Schroeder's spreading function (dB) at d = (target - masker in Bark) + 0.474. */
static double schroeder_db(double d)
{
    return 15.81 + 7.5 * d - 17.5 * sqrt(1 + d * d);
}

/* The tables for m coefficients (1024 or 128): the threshold in quiet (Terhardt's formula, at
 * the band's most sensitive point, 96 dB = full scale), Schroeder's spreading function. */
void psy_init(psy_t *p, int m)
{
    int scale = m / 128;
    double hz = 44100.0 / 2 / m;
    p->m = m;
    for (int b = 0; b < NB; b++) {
        double lo = EDGES[b] * scale * hz, hi = EDGES[b + 1] * scale * hz;
        p->zc[b] = bark((lo + hi) / 2);
        p->fc[b] = (lo + hi) / 2;
        p->width[b] = (EDGES[b + 1] - EDGES[b]) * scale;
        double alo = lo, ahi = hi, aw = p->width[b];
        double amin = 1e300;
        for (int i = 0; i < 16; i++) {
            double f = (alo + (ahi - alo) * i / 15.0) / 1000;
            if (f < 0.02)
                f = 0.02;
            double a = 3.64 * pow(f, -0.8) - 6.5 * exp(-0.6 * (f - 3.3) * (f - 3.3)) + 1e-3 * pow(f, 4);
            if (a < amin)
                amin = a;
        }
        if (amin > 140)
            amin = 140;
        p->ath[b] = (m / 2.0) * pow(10, (amin - 96.0) / 10) / aw;
    }
    for (int i = 0; i < NB; i++)
        for (int j = 0; j < NB; j++) {
            p->spread[i][j] = pow(10, schroeder_db(p->zc[i] - p->zc[j] + 0.474) / 10);
        }
}

/* Axis 1 (E-LOG.md): a long frame's band masks below fine_nb from sub-band masks of fine_w lines:
 * each sub-band's energy spread over the Bark scale (a density per Bark, per line: times the
 * sub-band's Bark width / w), the offset from the band's tonality; a band's mask is the power
 * mean of exponent -fine_p of its sub-bands' (large: their minimum). */
void psy_fine(const psy_t *p, const mule_enc_params *pr, const double *X,
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
            C += pow(10, schroeder_db(d) / 10) * E[j];
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
 * quiet. P: power per coefficient; flat: flatness (dB); noise_flat: a noise band's flatness.
 * The spreading (spread_mode, N-LOG.md): 0 Schroeder's; 1 Terhardt's (PEAQ's ear model: the
 * upper slope -24 - 230/f + 0.2 L dB per Bark, steeper for a quiet masker; -27 dB per Bark
 * downwards); 2 the smaller of the two; 3 Schroeder's up to sp_dz Bark above the masker, then
 * Terhardt's slope from there where steeper (MPEG-1 model 1's shape). Band masks only: psy_fine,
 * which replaces the masks of a long frame's bands below fine_nb, keeps Schroeder's. */
void psy_masks(const psy_t *p, const mule_enc_params *pr, const double *P,
                      const double *flat, double *mask, double noise_flat)
{
    double E[NB], su[NB];
    for (int b = 0; b < NB; b++) {
        E[b] = P[b] * p->width[b];
        if (pr->spread_mode) {                  /* Terhardt's upper slope, at most 0 */
            double L = 96.0 + 10 * log10(E[b] * 2.0 / p->m + 1e-30);   /* dB SPL, 96 = full scale */
            su[b] = -24.0 - 230.0 / p->fc[b] + 0.2 * L;
            if (su[b] > 0)
                su[b] = 0;
        }
    }
    double s0 = pr->spread_mode == 3 ? schroeder_db(pr->sp_dz + 0.474) : 0;
    for (int i = 0; i < NB; i++) {
        double C = 0;
        for (int j = 0; j < NB; j++) {
            double w = p->spread[i][j];
            if (pr->spread_mode) {
                double dz = p->zc[i] - p->zc[j];
                if (pr->spread_mode == 3) {
                    if (dz > pr->sp_dz) {
                        double s3 = s0 + su[j] * (dz - pr->sp_dz);
                        double w3 = s3 > -60 ? pow(10, s3 / 10) : 0.0;
                        if (w3 < w)
                            w = w3;
                    }
                } else {
                    double s = dz >= 0 ? su[j] * dz : 27.0 * dz;
                    double wt = s > -60 ? pow(10, s / 10) : 0.0;
                    w = pr->spread_mode == 2 && w < wt ? w : wt;
                }
            }
            C += w * E[j];
        }
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

/* Opus' dynalloc criterion (dyn_a > 0, N-LOG.md; off in production): a band above the lower
 * envelope of the band levels (CELT's follower: +9 dB per band upwards, +12 downwards) gets its
 * mask lowered by dyn_a times the excess, at most 12 dB. P: power per coefficient. */
void psy_dynalloc(const mule_enc_params *pr, const double *P, double *mask)
{
    double e[NB], fo[NB];
    for (int b = 0; b < NB; b++)
        e[b] = 10 * log10(P[b] + 1e-30);
    fo[0] = e[0];
    for (int b = 1; b < NB; b++)
        fo[b] = fo[b - 1] + 9 < e[b] ? fo[b - 1] + 9 : e[b];
    for (int b = NB - 2; b >= 0; b--)
        if (fo[b + 1] + 12 < fo[b])
            fo[b] = fo[b + 1] + 12;
    for (int b = 0; b < NB; b++) {
        double x = e[b] - fo[b];
        if (x > 12)
            x = 12;
        if (x > 0)
            mask[b] *= pow(10, -pr->dyn_a * x / 10);
    }
}

/* The band floor (core/mule_enc.h, bf_rel_db): the masks of the bands within bf_rel_db of the
 * strongest one (power per coefficient) at most bf_snr_db under their own power. */
void psy_floor(const mule_enc_params *pr, const double *P, double *mask)
{
    double pmax = 0;
    for (int b = 0; b < NB; b++)
        if (P[b] > pmax)
            pmax = P[b];
    double gate = pmax * pow(10, -pr->bf_rel_db / 10), k = pow(10, -pr->bf_snr_db / 10);
    for (int b = 0; b < NB; b++)
        if (P[b] >= gate && mask[b] > P[b] * k)
            mask[b] = P[b] * k;
}

/* CELT's band_allocation (libopus celt/modes.c, BSD licence, Copyright Xiph.Org, Skype, CSIRO):
 * 11 rows of 21 bands, 1/32 bit per coefficient. */
static const unsigned char OPUS_ALLOC[11][21] = {
    {  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0},
    { 90, 80, 75, 69, 63, 56, 49, 40, 34, 29, 20, 18, 10,  0,  0,  0,  0,  0,  0,  0,  0},
    {110,100, 90, 84, 78, 71, 65, 58, 51, 45, 39, 32, 26, 20, 12,  0,  0,  0,  0,  0,  0},
    {118,110,103, 93, 86, 80, 75, 70, 65, 59, 53, 47, 40, 31, 23, 15,  4,  0,  0,  0,  0},
    {126,119,112,104, 95, 89, 83, 78, 72, 66, 60, 54, 47, 39, 32, 25, 17, 12,  1,  0,  0},
    {134,127,120,114,103, 97, 91, 85, 78, 72, 66, 60, 54, 47, 41, 35, 29, 23, 16, 10,  1},
    {144,137,130,124,113,107,101, 95, 88, 82, 76, 70, 64, 57, 51, 45, 39, 33, 26, 15,  1},
    {152,145,138,132,123,117,111,105, 98, 92, 86, 80, 74, 67, 61, 55, 49, 43, 36, 20,  1},
    {162,155,148,142,133,127,121,115,108,102, 96, 90, 84, 77, 71, 65, 59, 53, 46, 30,  1},
    {172,165,158,152,143,137,131,125,118,112,106,100, 94, 87, 81, 75, 69, 63, 56, 45, 20},
    {200,200,200,200,200,200,200,200,198,193,188,183,178,173,168,163,158,153,148,129,104},
};

/* The table at row x (0..10, interpolated), bits per coefficient of MULE's bands: CELT's trim
 * offset at alloc_trim 5, LM 3 (-3 (20 - b) / 64 bit per coefficient), at least 0; band 21 as
 * twice band 20 minus band 19. Returns the bits of one channel. */
static double opus_row(double x, double *T)
{
    int lo = (int)x;
    if (lo > 9)
        lo = 9;
    double fr = x - lo, tot = 0;
    for (int b = 0; b < NB; b++) {
        double v;
        if (b < 21)
            v = (1 - fr) * OPUS_ALLOC[lo][b] + fr * OPUS_ALLOC[lo + 1][b];
        else {
            double v20 = (1 - fr) * OPUS_ALLOC[lo][20] + fr * OPUS_ALLOC[lo + 1][20];
            double v19 = (1 - fr) * OPUS_ALLOC[lo][19] + fr * OPUS_ALLOC[lo + 1][19];
            v = 2 * v20 - v19;
        }
        double t = v / 32 - (b < 21 ? 3.0 * (20 - b) / 64 : 0.0);
        T[b] = t > 0 && v > 0 ? t : 0.0;
        tot += T[b] * (EDGES[b + 1] - EDGES[b]) * 8;
    }
    return tot;
}

/* T: the table's bits per coefficient for a rate of kbps (a channel's coefficients get opa_eta
 * of half the rate). */
static void opus_alloc(const mule_enc_params *pr, double kbps, double *T)
{
    double budget = pr->opa_eta * kbps * 1000 * F / 44100.0 / 2, lo = 0, hi = 10;
    if (opus_row(hi, T) <= budget)
        return;
    for (int i = 0; i < 40; i++) {
        double mid = (lo + hi) / 2;
        if (opus_row(mid, T) > budget)
            hi = mid;
        else
            lo = mid;
    }
    opus_row(lo, T);
}

/* Opus' band allocation (core/mule_enc.h, opa_mode). */
void psy_opus(const mule_enc_params *pr, const double *P, double *mask)
{
    static double kb = -1, T[NB], T128[NB], sh[NB];
    if (kb != pr->opa_kbps || pr->opa_mode == 2) {      /* (mode 2: opa_k may change) */
        kb = pr->opa_kbps;
        opus_alloc(pr, kb, T);
        opus_alloc(pr, 128.0, T128);
        double m = 0, n = 0;
        for (int b = 0; b < NB; b++) {
            double w = (EDGES[b + 1] - EDGES[b]) * 8.0;
            m += w * (T[b] - T128[b]);
            n += w;
        }
        for (int b = 0; b < NB; b++)
            sh[b] = T[b] - T128[b] - m / n;
    }
    double q0 = -pr->rc_slope * log2(kb / pr->rc_r0), tq0 = pow(10, q0 / 10);
    for (int b = 0; b < NB; b++) {
        double mo = P[b] * pow(10, -0.602 * T[b]) / tq0 + 1e-30;
        if (pr->opa_mode == 1)
            mask[b] = mo;
        else if (pr->opa_mode == 2)
            mask[b] *= pow(10, -0.602 * pr->opa_k * sh[b]);
        else
            mask[b] = pow(mask[b] + 1e-30, pr->opa_alpha) * pow(mo, 1 - pr->opa_alpha);
    }
}
