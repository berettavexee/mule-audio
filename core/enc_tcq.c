/* MULE encoder: trellis-coded quantization of the band shapes (spec 5.3): the Viterbi searches
 * (with the tracked models' rates, over one band or over a group's chained bands) and the coding
 * of one band's coefficients (core/enc_int.h). */
#include "enc_int.h"

/* Axis 3 (E-LOG.md) and point 16 (V3-IDEAS): the TCQ Viterbi with the rate of the tracked
 * models, over a chain of n coefficients x[i], each in its band's D/2 units: cost
 * w[i] (x - k)^2 + c * bits, bits from the coefficient contexts of each survivor's tails (the two
 * previous magnitudes), pm[i] the inter-frame term (-1: none), ac[i] the allocation class. One
 * band (w = 1, c = its lambda) is axis 3's Viterbi; a group's coded bands chained (w = the
 * band's noise unit over its mask) is point 16's. Trellis of ns states (mask), from state st0;
 * the levels in kout, the end state returned. */
int tcq_viterbi_chain(const double *x, const double *w, const int *ac, int n, double c,
                             const ops_t *o, const int64_t *pm, int64_t t1_0, int64_t t2_0, int ns,
                             int mask, int st0, int64_t *kout)
{
    static double lev[MULE_F][MULE_TCQ_MAXS];
    static int back[MULE_F][MULE_TCQ_MAXS];
    static double sc[16][6][16], esc[16][16];
    double cost[MULE_TCQ_MAXS], nc[MULE_TCQ_MAXS];
    int64_t t1[MULE_TCQ_MAXS], t2[MULE_TCQ_MAXS], n1[MULE_TCQ_MAXS], n2[MULE_TCQ_MAXS];
    int have[16] = {0};
    for (int i = 0; i < n; i++)
        if (!have[ac[i]]) {
            int a = ac[i];
            have[a] = 1;
            for (int cx = 0; cx < 6; cx++)
                for (int v = 0; v <= o->esc; v++)
                    sc[a][cx][v] = sym_bits(o, MULE_S_COEF, a * 6 + cx, v);
            for (int v = 0; v < 16; v++)
                esc[a][v] = sym_bits(o, MULE_S_CESC, a, v) + v;
        }
    for (int s = 0; s < ns; s++) {
        cost[s] = s == st0 ? 0.0 : 1e300;
        t1[s] = t1_0;
        t2[s] = t2_0;
    }
    /* The three candidate levels of each subset j (k mod 4 = j; the states of j's parity) depend
     * on the coefficient only: computed once per coefficient, not per state (same arithmetic,
     * same order of operations: the same result to the bit). */
    double ck[4][3], cd[4][3], ce[4][3];
    int64_t cm[4][3];
    int cs[4][3], cx_[4][3], cv[4][3], cesc_[4][3];
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < 4; j++) {
            int even = !(j & 1);                /* the states using subset j have j's parity */
            double k0 = nearbyint((x[i] - j) / 4.0) * 4 + j;
            for (int d = 0; d < 3; d++) {
                double k = k0 + 4 * (d - 1);
                double ak = fabs(k);
                int64_t mag = even ? (int64_t)ak / 2 : ((int64_t)ak - 1) / 2;
                ck[j][d] = k;
                cv[j][d] = mag >= 0;
                cm[j][d] = mag;
                cx_[j][d] = (int)(mag < o->esc ? mag : o->esc);
                cesc_[j][d] = mag >= o->esc;
                ce[j][d] = mag >= o->esc ? esc[ac[i]][ilog2((uint32_t)(mag - o->esc) + 1)] : 0.0;
                cs[j][d] = !even || ak > 0;
                cd[j][d] = w[i] * (x[i] - k) * (x[i] - k);
            }
        }
        for (int t = 0; t < ns; t++)
            nc[t] = 1e300;
        for (int s = 0; s < ns; s++) {
            if (cost[s] >= 1e300)
                continue;
            int64_t mctx = 2 * t1[s] + t2[s];
            if (pm[i] >= 0)
                mctx = (mctx + 3 * pm[i] + 1) >> 1;
            const double *row = sc[ac[i]][nc_map(mctx)];
            for (int br = 0; br < 2; br++) {
                int j = mule_tcq_sub(s, br, mask);
                int t = (2 * s + br) & (ns - 1);
                for (int d = 0; d < 3; d++) {
                    if (!cv[j][d])
                        continue;
                    double r = row[cx_[j][d]];
                    if (cesc_[j][d])
                        r += ce[j][d];
                    if (cs[j][d])
                        r += 1;
                    double cc = cost[s] + cd[j][d] + c * r;
                    if (cc < nc[t]) {
                        nc[t] = cc;
                        back[i][t] = s;
                        lev[i][t] = ck[j][d];
                        n1[t] = cm[j][d];
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
    for (int t = 1; t < ns; t++)
        if (cost[t] < cost[s])
            s = t;
    int end = s;
    for (int i = n - 1; i >= 0; i--) {
        kout[i] = (int64_t)lev[i][s];
        s = back[i][s];
    }
    return end;
}

/* The TCQ Viterbi (spec 5.3) for samples x (units of D/2) from state st0, trellis of ns states:
 * the levels k minimising sum (x - k)^2 + lam R(k), R a static approximation of the rate. */
static void tcq_viterbi(const double *x, int n, double lam, int ns, int mask, int st0, int64_t *kout)
{
    static double lev[MULE_F][MULE_TCQ_MAXS];
    static int back[MULE_F][MULE_TCQ_MAXS];
    double cost[MULE_TCQ_MAXS], nc[MULE_TCQ_MAXS];
    for (int s = 0; s < ns; s++)
        cost[s] = s == st0 ? 0.0 : 1e300;
    for (int i = 0; i < n; i++) {
        for (int t = 0; t < ns; t++)
            nc[t] = 1e300;
        for (int s = 0; s < ns; s++) {
            if (cost[s] >= 1e300)
                continue;
            for (int br = 0; br < 2; br++) {
                int j = mule_tcq_sub(s, br, mask);
                double k = nearbyint((x[i] - j) / 4.0) * 4 + j;
                double m = floor(fabs(k) / 2);
                double r = 1.0 + 1.6 * log2(1.0 + m) + (k != 0);
                double c = cost[s] + (x[i] - k) * (x[i] - k) + lam * r;
                int t = (2 * s + br) & (ns - 1);
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
    for (int t = 1; t < ns; t++)
        if (cost[t] < cost[s])
            s = t;
    for (int i = n - 1; i >= 0; i--) {
        kout[i] = (int64_t)lev[i][s];
        s = back[i][s];
    }
}

/* The inter-frame term of the band's coefficient idx (spec 5.3): last long frame's index
 * rescaled by 2^(e/4), before the cap at 31 (the trace records it uncapped). */
static int64_t inter_pm(const band_in *in, int idx)
{
    int64_t v = (int64_t)in->ylong[idx] * POW4[in->e & 3];
    int sh = floor_div(in->e, 4);
    return sh >= 0 ? (v << (sh < 8 ? sh : 8)) >> 8 : v >> (8 - sh);
}

/* A coded band's Viterbi inputs at allocation a: samples in D/2 units, the inter-frame terms,
 * its allocation class, its noise unit u (D/2 rms) and lambda. */
/* v4 probe (MULE_ROT): the band's rotation angle at allocation a (radians; 0: none), as the
 * decoder computes it; and the inverse of its rotations (dec.c rot_pass, rot_segment), on the
 * targets: the passes in reverse order, each reversed, with -s. */
static double rot_angle(const band_in *in, int a)
{
    const mule_enc_params *pr = in->pr;
    if (!pr || !pr->rot || in->rot_scale <= 0 || in->b < pr->rot_b0 || a > pr->rot_amax)
        return 0;
    return in->rot_scale * pr->rot_deg * pow(2.0, -(a - 1) / 2.0) * 3.14159265358979323846 / 180;
}

static void rot_pass_inv(double *x, int len, int stride, double c, double s)
{
    for (int i = 0; i <= len - 2 * stride - 1; i++) {
        double x1 = x[i], x2 = x[i + stride];
        x[i + stride] = c * x2 - s * x1;
        x[i] = c * x1 + s * x2;
    }
    for (int i = len - stride - 1; i >= 0; i--) {
        double x1 = x[i], x2 = x[i + stride];
        x[i + stride] = c * x2 - s * x1;
        x[i] = c * x1 + s * x2;
    }
}

static void rot_segment_inv(double *x, int len, double th)
{
    if (len < 2 || th <= 0)
        return;
    double c = cos(th), s = sin(th);
    if (len >= 8) {
        int st = 1;
        while (st * st + st < len)
            st++;
        rot_pass_inv(x, len, st, c, s);
    }
    rot_pass_inv(x, len, 1, c, s);
}

void band_prep(const band_in *in, int a, double *xt, int64_t *pmv, int *ac, double *u,
                      double *lam)
{
    int n = band_n(in->g, in->b);
    double D = pow(2.0, (MULE_A0 - a) / 4.0);
    *ac = a / 3 < 15 ? a / 3 : 15;
    for (int i = 0; i < n; i++) {
        int idx = coef_index(in->g, in->b, i);
        xt[i] = in->Y[idx] / in->rms / (D / 2);
        pmv[i] = -1;
        if (in->inter) {
            int64_t p = inter_pm(in, idx);
            pmv[i] = p > 31 ? 31 : p;
        }
    }
    double th = rot_angle(in, a);
    if (th > 0) {                               /* v4 probe: quantise in the rotated domain */
        int seg = in->type ? EDGES[in->b + 1] - EDGES[in->b] : n;
        for (int k = 0; k + seg <= n; k += seg)
            rot_segment_inv(xt + k, seg, th);
    }
    *u = (D / 2) * in->rms;                     /* (D/2)^2 rms^2: the noise of one unit */
    *lam = in->pr ? in->pr->tcq_rdl * in->pr->rd_lambda * in->mtq / (*u * *u) : 0.0;
}

/* One band's coefficients at allocation a: TCQ levels (Viterbi), then their symbols with the
 * decoder's contexts. emit: the operations are appended (ycur gets a long frame's indices);
 * else bits and noise (the band's squared error) are returned, costed with the tracked models,
 * for the RD choice. tail1, tail2 (the two previous indices) are updated either way. */
void band_code(const band_in *in, int a, int64_t *tail1, int64_t *tail2, ops_t *o, int emit,
                      int *ycur, double *bits, double *noise, const int64_t *klev, int *tst_io)
{
    int n = band_n(in->g, in->b);
    double D = pow(2.0, (MULE_A0 - a) / 4.0);
    int ac;
    double nb = 0, ns = 0, u, lam;
    int64_t kt[176], pmv[176];
    int tst = tst_io ? *tst_io : 0;
    int nst = in->pr ? in->pr->tcq_states : 8;
    if (!emit && in->pr && in->pr->tcq_rd_states)   /* the RD choice's estimate: a smaller trellis */
        nst = in->pr->tcq_rd_states;
    int mask = mule_tcq_mask(nst);
    double xt[176];
    band_prep(in, a, xt, pmv, &ac, &u, &lam);
    double lam_used = in->tcq_lam;              /* the Viterbi's rate weight (trace only) */
    if (klev)                                   /* levels chosen by the group's chained Viterbi */
        memcpy(kt, klev, sizeof(int64_t) * (size_t)n);
    else if (in->pr && in->pr->tcq_rd && o->mr) {
        double w[176];
        int acs[176];
        for (int i = 0; i < n; i++) {
            w[i] = 1.0;
            acs[i] = ac;
        }
        lam_used = lam;
        tcq_viterbi_chain(xt, w, acs, n, lam, o, pmv, *tail1, *tail2, nst, mask, tst, kt);
    } else
        tcq_viterbi(xt, n, in->tcq_lam, nst, mask, tst, kt);
    if (klev)
        lam_used = lam;
    int rot = rot_angle(in, a) > 0;
    for (int i = 0; i < n; i++) {
        int idx = coef_index(in->g, in->b, i);
        double xn = rot ? xt[i] * (D / 2) : in->Y[idx] / in->rms;   /* rotated: its own target */
        /* TCQ level -> index within the state's union (odd states: no zero, sign always) */
        int64_t k = kt[i], ak = k < 0 ? -k : k;
        int even = !(tst & 1);
        int64_t mag = even ? ak / 2 : (ak - 1) / 2;
        int need_sign = !even || ak > 0, neg = k < 0;
        double rec = (double)ak * D / 2;
        tst = mule_tcq_step_n(tst, k, nst, mask);
        int64_t mctx = 2 * *tail1 + *tail2;
        int64_t pm_raw = in->inter ? inter_pm(in, idx) : -1;
        if (in->inter)
            mctx = (mctx + 3 * (pm_raw > 31 ? 31 : pm_raw) + 1) >> 1;
        int ctx = ac * 6 + nc_map(mctx), s = mag < o->esc ? (int)mag : o->esc;
        if (emit && mule_enc_trace) {
            const trace_t *tr = mule_enc_trace;
            int64_t yl = in->inter ? in->ylong[idx] : 0;
            int32_t r[MULE_TRACE_W] = {0, clip32(o->n), tr->frame, tr->ch, in->type, in->b,
                                       idx, ac, clip32(*tail1), clip32(*tail2), in->inter, in->e,
                                       (int32_t)yl, clip32(mag), ctx, clip32(pm_raw),
                                       clip32(k), (int32_t)lrint(xt[i] * 256),
                                       (int32_t)lrint(lam_used * 1e4), (int32_t)tst};
            trace_add(r);
        }
        if (emit)
            put(o, MULE_S_COEF, ctx, s);
        else
            nb += sym_bits(o, MULE_S_COEF, ctx, s);
        if (mag >= o->esc) {
            uint32_t v = (uint32_t)(mag - o->esc);
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
        if (emit && in->nf_acc && k == 0) {     /* v4 probe: what the zeros leave out */
            double r = xn / (D / 2);
            in->nf_acc[0] += r * r;
            in->nf_acc[1] += 1;
        }
        *tail2 = *tail1;
        *tail1 = mag;
    }
    if (bits)
        *bits = nb;
    if (noise)
        *noise = ns * in->rms * in->rms;     /* absolute noise energy of the band */
    if (tst_io)
        *tst_io = tst;
}
