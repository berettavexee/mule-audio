/* MULE encoder: the forward MDCT (orthonormal, through a complex FFT), the FFT power spectrum
 * of the tonality measure, and the window shapes (core/enc_int.h). */
#include "enc_int.h"

/* The tables of an n-point MDCT (n = 2048 or 256) through an n-point complex FFT; -1 if out of
 * memory (mdct_free frees what was allocated). */
int mdct_init(mdct_t *t, int n)
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
void mdct_free(mdct_t *t)
{
    free(t->cr); free(t->ci); free(t->pre_r); free(t->pre_i);
    free(t->post_r); free(t->post_i); free(t->rev);
}

/* Forward MDCT, orthonormal: X[k] = sqrt(2/M) sum_i x[i] cos(2 pi / n (i + 1/2 + n/4)(k + 1/2)),
 * M = n/2 coefficients, x already windowed. */
void mdct_fwd(const mdct_t *t, const double *x, double *X)
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
void fft_power(const mdct_t *t, const double *x, double *pw)
{
    double re[MULE_N_LONG], im[MULE_N_LONG];
    fft_cplx(t, x, re, im);
    for (int k = 0; k < t->n / 2; k++)
        pw[k] = re[k] * re[k] + im[k] * im[k];
}

/* The rising Vorbis window slope of length s at i: sin(pi/2 sin^2(pi (i + 1/2) / 2s)). */
double win_slope(int i, int s)
{
    double t = sin(0.5 * M_PI * (i + 0.5) / s);
    return sin(0.5 * M_PI * t * t);
}

/* A rising half-window of length h with a centred slope of length s: zeros, slope, ones. */
double win_half(int i, int h, int s)
{
    int z = (h - s) / 2;
    return i < z ? 0.0 : (i < z + s ? win_slope(i - z, s) : 1.0);
}
