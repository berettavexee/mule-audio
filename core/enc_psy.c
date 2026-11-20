/* MULE encoder: the transient detector (each frame's block type) and the psychoacoustic model
 * (masking threshold per band, core/enc_int.h). */
#include "enc_int.h"

/* ---------------------------------------------------------------- transient detector */

/* The block type of each of the T frames (0 long, 1 short): energies of 128-sample blocks of the
 * signal high-passed at 3 kHz; an attack is a block 10 dB above a decaying memory (3 dB per
 * block) or 20 dB above the blocks 7 to 10 earlier, above a -70 dB floor; the frames whose short
 * windows hold it become short. -1 if out of memory. */
int block_types(const double *x, int64_t L, int T, uint8_t *types, double ratio_db)
{
    const double fs = 44100.0, fc = 3000.0, decay_db = 3.0, floor_db = -70.0,
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

/* Frequency (Hz) to Bark (Zwicker). */
static double bark(double f)
{
    return 13 * atan(0.00076 * f) + 3.5 * atan((f / 7500.0) * (f / 7500.0));
}

/* The tables for m coefficients (1024 or 128): the threshold in quiet (Terhardt's formula, at
 * the band's most sensitive point, 96 dB = full scale), Schroeder's spreading function. */
void psy_init(psy_t *p, int m)
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
void psy_masks(const psy_t *p, const mule_enc_params *pr, const double *P,
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
