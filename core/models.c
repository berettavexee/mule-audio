/* Model layout and initial CDFs (decoder and encoder): the streams of core/mule.h (spec 3) and the
 * trained tables of core/init_cdf.h. */
#include "mule.h"
#include "init_cdf.h"
#include "init_cdf_a8.h"

const int mule_init_cdf_id = MULE_INIT_CDF_ID;
const int mule_stream_nsyms[MULE_S_COUNT] = {2, 4, 2, 16, 16, 2, 16, 16, 16, 8};
const int mule_stream_nctx[MULE_S_COUNT] = {1, 1, 3, 9, 6, 1, 16, 96, 1, 1};
const int mule_stream_off[MULE_S_COUNT] = {0, 1, 2, 5, 14, 20, 21, 37, 133, 134};
#define NTABLES ((int)(sizeof mule_init_cdf / sizeof *mule_init_cdf))   /* streams with a table */

/* The initial CDF of stream s (its contexts' n + 1 values each, one after the other), NULL for
 * a uniform start (NFLEV); n: its symbols. a8 (format flag MULE_COEF_A8): the coefficients have 8
 * symbols (escape at 7) and the escape orders their own table (core/init_cdf_a8.h). Built with
 * MULE_DEC_V5_ONLY (core B), the 16-symbol coefficient tables of v2 are not referenced (the
 * linker drops them): every stream is then read as a8. */
const uint16_t *mule_stream_init(int s, int a8, int *n)
{
    *n = mule_stream_nsyms[s];
#ifdef MULE_DEC_V5_ONLY
    a8 = 1;
#endif
    if (a8 && s == MULE_S_COEF) {
        *n = 8;
        return mule_init_coef8;
    }
    if (a8 && s == MULE_S_CESC)
        return mule_init_cesc8;
#ifdef MULE_DEC_V5_ONLY
    static const uint16_t *const other[] = {mule_init_btype, mule_init_alpha, mule_init_stereo,
                                            mule_init_energy, mule_init_alloc, mule_init_amode,
                                            NULL, NULL, mule_init_eaesc};
    return s < (int)(sizeof other / sizeof *other) ? other[s] : NULL;
#else
    return s < NTABLES ? mule_init_cdf[s] : NULL;   /* NFLEV: uniform */
#endif
}

/* Every model to its initial state (a key packet, spec 4): the trained CDF of its stream and
 * context, or the uniform one for a stream without table. */
void mule_models_reset(mule_models *ms)
{
    mule_models_reset_a8(ms, 0);
}

/* mule_models_reset; a8: the 8-symbol coefficient alphabet (mule_stream_init). */
void mule_models_reset_a8(mule_models *ms, int a8)
{
    for (int s = 0; s < MULE_S_COUNT; s++) {
        int n;
        const uint16_t *init = mule_stream_init(s, a8, &n);
        for (int c = 0; c < mule_stream_nctx[s]; c++) {
            mule_model *m = &ms->m[mule_stream_off[s] + c];
            if (init)
                mule_model_init_cdf(m, n, init + (size_t)c * (size_t)(n + 1));
            else
                mule_model_init(m, n);
        }
    }
}
