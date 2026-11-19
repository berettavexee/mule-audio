/* The encoder on hostile inputs, under AddressSanitizer and UndefinedBehaviorSanitizer: NaN,
 * infinities, huge values, denormals, full-scale square waves, DC, a single sample, empty input,
 * at several qualities; each stream must decode (mule_dec_*) to finite 16-bit samples.
 * Built and run by tools/fuzz/enc_edge.sh. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mule.h"
#include "mule_enc.h"

/* The Ogg packets of a file: offsets and lengths (no CRC check: our own output). */
static int packets(const uint8_t *f, size_t n, const uint8_t **pk, int *len, int max)
{
    size_t pos = 0;
    int np = 0, cont = 0;
    static uint8_t acc[1 << 20];
    size_t accn = 0;
    while (pos + 27 <= n && np < max) {
        int ns = f[pos + 26];
        const uint8_t *lace = f + pos + 27;
        size_t body = pos + 27 + (size_t)ns;
        for (int i = 0; i < ns; i++) {
            if (accn + lace[i] > sizeof acc)
                return -1;
            memcpy(acc + accn, f + body, lace[i]);
            accn += lace[i];
            body += lace[i];
            if (lace[i] < 255) {
                uint8_t *p = malloc(accn ? accn : 1);
                memcpy(p, acc, accn);
                pk[np] = p;
                len[np++] = (int)accn;
                accn = 0;
            }
        }
        cont = accn > 0;
        pos = body;
    }
    (void)cont;
    return np;
}

static int check(const char *name, const double *x, int64_t L, double q)
{
    mule_enc_params p;
    mule_enc_defaults(&p);
    p.q_db = q;
    uint8_t *out;
    size_t n, ab;
    int rc = mule_encode(x, L, &p, NULL, 0, &out, &n, &ab);
    if (rc) {
        printf("%-16s q %5.1f: encoder refused (%d)\n", name, q, rc);
        return rc == -2 ? 0 : 1;
    }
    enum { MAXP = 4096 };
    static const uint8_t *pk[MAXP];
    static int len[MAXP];
    int np = packets(out, n, pk, len, MAXP);
    if (np < 2) {
        printf("%-16s q %5.1f: no packets\n", name, q);
        return 1;
    }
    mule_dec *d = mule_dec_new(pk[0], len[0]);
    if (!d) {
        printf("%-16s q %5.1f: header refused\n", name, q);
        return 1;
    }
    static int16_t pcm[4 * MULE_F * 2];
    int bad = 0, total = 0;
    for (int i = 2; i < np; i++) {
        int r = mule_dec_packet(d, pk[i], len[i], pcm, 4 * MULE_F);
        if (r < 0)
            bad++;
        else
            total += r;
    }
    mule_dec_free(d);
    for (int i = 0; i < np; i++)
        free((void *)pk[i]);
    mule_free(out);
    printf("%-16s q %5.1f: %zu bytes, %d packets, %d samples, %d packets refused\n", name, q, n,
           np - 2, total, bad);
    return bad != 0;
}

int main(void)
{
    enum { L = 44100 };
    double *x = malloc(sizeof(double) * 2 * L);
    int fails = 0;
    const double qs[] = {-30.0, -7.0, 10.0};
    for (int kind = 0; kind < 10; kind++) {
        const char *name = "";
        for (int64_t i = 0; i < L; i++)
            for (int c = 0; c < 2; c++) {
                double v = 0.3 * sin(0.05 * (double)i + c);
                switch (kind) {
                case 0: name = "silence"; v = 0; break;
                case 1: name = "nan"; if (i % 1000 == 500) v = NAN; break;
                case 2: name = "inf"; if (i == L / 2) v = c ? -INFINITY : INFINITY; break;
                case 3: name = "huge"; v *= 1e30; break;
                case 4: name = "denormal"; v = 1e-310 * (i % 7); break;
                case 5: name = "square"; v = (i / 50) % 2 ? 1.0 : -1.0; break;
                case 6: name = "dc"; v = 1.0; break;
                case 7: name = "over"; v *= 8; break;
                case 8: name = "clicks"; v = i % 3000 == 0 ? 1.0 : 0.0; break;
                default: name = "all_nan"; v = NAN;
                }
                x[2 * i + c] = v;
            }
        for (int k = 0; k < 3; k++)
            fails += check(name, x, L, qs[k]);
    }
    for (int64_t len = 0; len <= 3; len++)
        fails += check(len ? "short" : "empty", x, len, -7.0);
    free(x);
    printf("%s\n", fails ? "FAILURES" : "all streams decoded");
    return fails != 0;
}
